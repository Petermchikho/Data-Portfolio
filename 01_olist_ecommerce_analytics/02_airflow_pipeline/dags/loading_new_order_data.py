from __future__ import annotations

import io
import logging
import os
import shutil
from contextlib import contextmanager
from datetime import datetime

import pandas as pd
from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.smtp.notifications.smtp import SmtpNotifier
from airflow.providers.standard.operators.python import PythonOperator

logger = logging.getLogger(__name__)


DIR_DATA    = "/opt/airflow/data/daily_data"
DIR_ARCHIVE = "/opt/airflow/data/archive/daily_data"
POSTGRES_CONN_ID = "olist_ecommerce"

TABLE_CONFIG: dict[str, dict] = {
    "olist_orders": {
        "file_name": "olist_orders_dataset.csv",
        "columns": [
            "order_id", "customer_id", "order_status",
            "order_purchase_timestamp", "order_approved_at",
            "order_delivered_carrier_date", "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
        "pk_columns":    ["order_id"],
        "dedup_subset":  ["order_id"],
    },
    "olist_order_items": {
        "file_name": "olist_order_items_dataset.csv",
        "columns": [
            "order_id", "order_item_id", "product_id", "seller_id",
            "shipping_limit_date", "price", "freight_value",
        ],
        "pk_columns":   ["order_id", "order_item_id"],
        "dedup_subset": ["order_id", "order_item_id"],
    },
    "olist_order_payments": {
        "file_name": "olist_order_payments_dataset.csv",
        "columns": [
            "order_id", "payment_sequential", "payment_type",
            "payment_installments", "payment_value",
        ],
        "pk_columns":   ["order_id", "payment_sequential"],
        "dedup_subset": ["order_id", "payment_sequential"],
    },
    "olist_order_reviews": {
        "file_name": "olist_order_reviews_dataset.csv",
        "columns": [
            "review_id", "order_id", "review_score",
            "review_comment_title", "review_comment_message",
            "review_creation_date", "review_answer_timestamp",
        ],
        "pk_columns":   ["review_id"],
        "dedup_subset": ["review_id"],
    },
}



# DB helpers

@contextmanager
def _pg_cursor(hook: PostgresHook):
    """
    Yield a cursor inside a single transaction.
    Commits on clean exit; rolls back and re-raises on any exception.
    Always closes cursor + connection — even if the caller raises.
    """
    conn   = hook.get_conn()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def _bulk_insert(
    hook: PostgresHook,
    df: pd.DataFrame,
    table: str,
    columns: list[str],
    pk_columns: list[str],
) -> int:
 
    col_list = ", ".join(columns)
    pk_list  = ", ".join(pk_columns)

    # Use Postgres-native NULL marker so empty CSV cells become proper NULLs
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False, na_rep="\\N")
    buffer.seek(0)

    with _pg_cursor(hook) as cursor:
       
        cursor.execute(
            f"CREATE TEMP TABLE tmp_daily_{table} (LIKE {table} INCLUDING ALL) ON COMMIT DROP"
        )

        cursor.copy_expert(
            f"COPY tmp_daily_{table} ({col_list}) FROM STDIN WITH (FORMAT CSV, NULL '\\N')",
            buffer,
        )

        cursor.execute(f"""
            INSERT INTO {table} ({col_list})
            SELECT {col_list} FROM tmp_daily_{table}
            ON CONFLICT ({pk_list}) DO NOTHING
        """)

        inserted = cursor.rowcount

    logger.info("[%s] Inserted %d new rows", table, inserted)
    return inserted

# Archive helper

def _archive_file(filename: str) -> None:
    
    os.makedirs(DIR_ARCHIVE, exist_ok=True)
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    name, ext   = os.path.splitext(filename)
    dest        = os.path.join(DIR_ARCHIVE, f"{name}_{timestamp}{ext}")
    shutil.move(os.path.join(DIR_DATA, filename), dest)
    logger.info("[archive] %s → %s", filename, dest)


def load_table(table: str) -> None:
    cfg         = TABLE_CONFIG[table]
    file_name   = cfg["file_name"]
    file_path   = os.path.join(DIR_DATA, file_name)
    columns     = cfg["columns"]
    pk_columns  = cfg["pk_columns"]
    dedup_subset = cfg["dedup_subset"]

    # 1. File check
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"[{table}] CSV not found: {file_path}")

    # 2. Read + in-file dedup
    df = pd.read_csv(file_path, dtype=str)   
    before = len(df)
    df = df.drop_duplicates(subset=dedup_subset)
    logger.info(
        "[%s] Read %d rows, dropped %d in-file duplicates → %d to process",
        table, before, before - len(df), len(df),
    )

    # 3. Column validation
    missing = set(columns) - set(df.columns)
    if missing:
        raise ValueError(f"[{table}] Missing columns in CSV: {missing}")
    df = df[columns]

    # 4. Early exit 
    if df.empty:
        logger.info("[%s] No rows to insert after dedup — archiving and skipping.", table)
        _archive_file(file_name)
        return

    # 5. Bulk insert 
    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    _bulk_insert(hook, df, table, columns, pk_columns)

    # 6. Archive — only reached if insert succeeded
    _archive_file(file_name)


# ─────────────────────────────────────────────────────────────
# SMTP failure notifier
# ─────────────────────────────────────────────────────────────
smtp_notifier = SmtpNotifier(
    smtp_conn_id="smtp_default",
    to=["petercharlesmchikho1@gmail.com"],
    subject="[Airflow] FAILED: {{ dag.dag_id }} / {{ task_instance.task_id }}",
    html_content="""
        <h3 style="color:#c0392b">Task Failed</h3>
        <table>
          <tr><td><b>DAG</b></td><td>{{ dag.dag_id }}</td></tr>
          <tr><td><b>Task</b></td><td>{{ task_instance.task_id }}</td></tr>
          <tr><td><b>Run</b></td><td>{{ run_id }}</td></tr>
          <tr><td><b>Time</b></td><td>{{ ts }}</td></tr>
          <tr><td><b>Logs</b></td><td><a href="{{ task_instance.log_url }}">View logs</a></td></tr>
        </table>
    """,
)


# DAG definition

with DAG(
    dag_id="olist_daily_load",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    on_failure_callback=smtp_notifier,
    description="Daily load of Olist CSVs into PostgreSQL",
    tags=["olist", "ingestion"],
    # Prevent concurrent runs from racing on the same CSV files
    max_active_runs=1,
) as dag:
    t_orders = PythonOperator(
        task_id="load_orders",
        python_callable=load_table,
        op_kwargs={"table": "olist_orders"},
        on_failure_callback=smtp_notifier,  
    )

    t_items = PythonOperator(
        task_id="load_order_items",
        python_callable=load_table,
        op_kwargs={"table": "olist_order_items"},
        on_failure_callback=smtp_notifier,
    )

    t_payments = PythonOperator(
        task_id="load_order_payments",
        python_callable=load_table,
        op_kwargs={"table": "olist_order_payments"},
        on_failure_callback=smtp_notifier,
    )

    t_reviews = PythonOperator(
        task_id="load_order_reviews",
        python_callable=load_table,
        op_kwargs={"table": "olist_order_reviews"},
        on_failure_callback=smtp_notifier,
    )

    # orders must land first (FK parent); items/payments/reviews load in parallel after
    t_orders >> [t_items, t_payments, t_reviews]