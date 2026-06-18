from datetime import datetime
from airflow.utils.email import send_email
import os
import shutil
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.smtp.notifications.smtp import SmtpNotifier 
import pandas as pd
from airflow.sdk.exceptions import AirflowSkipException

import logging
import io


logger = logging.getLogger(__name__)
dir_data    = "/opt/airflow/data/daily_data"
dir_archive = "/opt/airflow/data/archive/daily_data"

orders_file_name="olist_orders_dataset.csv"
order_items_file_name="olist_order_items_dataset.csv"
order_payments_file_name="olist_order_payments_dataset.csv"
order_reviews_file_name="olist_order_reviews_dataset.csv"

orders_file=f"{dir_data}/{orders_file_name}"
order_items_file=f"{dir_data}/{order_items_file_name}"
order_payments_file=f"{dir_data}/{order_payments_file_name}"
order_reviews_file=f"{dir_data}/{order_reviews_file_name}"

orders_columns=["order_id","customer_id","order_status","order_purchase_timestamp","order_approved_at","order_delivered_carrier_date","order_delivered_customer_date","order_estimated_delivery_date"]
order_items_columns=["order_id","order_item_id","product_id","seller_id","shipping_limit_date","price","freight_value"]
order_payments_columns=["order_id","payment_sequential","payment_type","payment_installments","payment_value"]
order_reviews_columns=["review_id","order_id","review_score","review_comment_title","review_comment_message","review_creation_date","review_answer_timestamp"]


def _copy_to_postgres(hook, df, table, columns,temp_constraints="INCLUDING DEFAULTS"):
    """Fast bulk insert, silently skipping any PK conflicts."""
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)

    conn   = hook.get_conn()
    cursor = conn.cursor()

    # load into temp table first
    cursor.execute(f"CREATE TEMP TABLE tmp_{table} (LIKE {table} {temp_constraints})")
    cursor.copy_expert(
        f"COPY tmp_{table} ({', '.join(columns)}) FROM STDIN WITH CSV",
        buffer,
    )

    # insert skipping any precision-caused conflicts
    cursor.execute(f"""
        INSERT INTO {table} ({', '.join(columns)})
        SELECT {', '.join(columns)} FROM tmp_{table}
        ON CONFLICT DO NOTHING
    """)
    inserted = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    return inserted

def _archive_file(filename):
    """Move processed CSV to archive folder with a timestamp."""
    try:
        os.makedirs(dir_archive, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  
        name, ext = os.path.splitext(filename)                                     
        dest = f"{dir_archive}/{name}_{timestamp}.{ext}"
        shutil.move(f"{dir_data}/{filename}", dest)
        logger.info(f"Archived file ==> {dest}")
    except Exception as e:
        logger.error(f"Failed to archive file {filename}: {e}")
        raise

def loading_orders():
    try:
        # 1. Read file
        if not os.path.exists(orders_file):
            # raise AirflowSkipException(f"CSV not found: {orders_file}")
            raise FileNotFoundError(f"CSV not found: {orders_file}")
        df = pd.read_csv(orders_file)
        df = df.drop_duplicates(subset=["order_id"])
        # 2. Validate columns
        missing = set(orders_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns in CSV: {missing}")
        df = df[orders_columns]  # keep only needed columns, in correct order
        # 3. Fetch existing product IDs from DB to avoid duplicates
        hook = PostgresHook(postgres_conn_id='olist_ecommerce')
        existing = hook.get_records("SELECT DISTINCT order_id FROM olist_orders")
        existing_ids = {row[0] for row in existing}          # fast set lookup
        logger.info(f"Found {len(existing_ids)} existing order IDs in DB")
        # 4. Filter out duplicates
        before = len(df)
        df = df[~df["order_id"].isin(existing_ids)]
        skipped = before - len(df)
        logger.info(f"Skipping {skipped} duplicate rows, inserting {len(df)} new rows")
        if df.empty:
            logger.info("Nothing new to insert — all rows already exist in DB.")
            _archive_file(orders_file_name)  # still archive the file to avoid reprocessing
            return
        # 5. Bulk insert
        _copy_to_postgres(hook, df, "olist_orders", orders_columns, temp_constraints="INCLUDING ALL")
        logger.info(f"Inserted {len(df)} rows into olist_orders table")
        # 6. Archive the file
        _archive_file(orders_file_name)
    
    except Exception as e:
        logger.error(f" Failed to load olist_orders data: {e}")
        raise

def loading_order_items():
    try:
        # 1. Read file
        if not os.path.exists(order_items_file):
            # raise AirflowSkipException(f"CSV not found: {orders_file}")
            raise FileNotFoundError(f"CSV not found: {order_items_file}")
        df = pd.read_csv(order_items_file)
        df = df.drop_duplicates(subset=["order_id","order_item_id"])
        # 2. Validate columns
        missing = set(order_items_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns in CSV: {missing}")
        df = df[order_items_columns]  # keep only needed columns, in correct order
        # 3. Fetch existing product IDs from DB to avoid duplicates
        hook = PostgresHook(postgres_conn_id='olist_ecommerce')
        existing = hook.get_records("SELECT DISTINCT order_item_id FROM olist_order_items")
        existing_ids = {row[0] for row in existing}          # fast set lookup
        logger.info(f"Found {len(existing_ids)} existing order_items IDs in DB")
        # 4. Filter out duplicates
        before = len(df)
        df = df[~df["order_item_id"].isin(existing_ids)]
        skipped = before - len(df)
        logger.info(f"Skipping {skipped} duplicate rows, inserting {len(df)} new rows")
        if df.empty:
            logger.info("Nothing new to insert — all rows already exist in DB.")
            _archive_file(order_items_file_name)  # still archive the file to avoid reprocessing
            return
        # 5. Bulk insert
        _copy_to_postgres(hook, df, "olist_order_items", order_items_columns, temp_constraints="INCLUDING ALL")
        logger.info(f"Inserted {len(df)} rows into olist_order_items table")
        # 6. Archive the file
        _archive_file(order_items_file_name)
    
    except Exception as e:
        logger.error(f" Failed to load olist_order_items data: {e}")
        raise

def loading_order_payments():
    try:
        # 1. Read file
        if not os.path.exists(order_payments_file):
            # raise AirflowSkipException(f"CSV not found: {orders_file}")
            raise FileNotFoundError(f"CSV not found: {order_payments_file}")
        df = pd.read_csv(order_payments_file)
        df = df.drop_duplicates(subset=["order_id","payment_sequential"])
        # 2. Validate columns
        missing = set(order_payments_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns in CSV: {missing}")
        df = df[order_payments_columns]  # keep only needed columns, in correct order
        # 3. Fetch existing composite keys from DB
        hook = PostgresHook(postgres_conn_id='olist_ecommerce')
        existing = hook.get_records(
            "SELECT DISTINCT order_id, payment_sequential FROM olist_order_payments"
        )
        existing_ids = {(row[0], row[1]) for row in existing}  
        logger.info(f"Found {len(existing_ids)} existing order_payment records in DB")

        # 4. Filter out duplicates using composite key
        before = len(df)
        df = df[~df.apply(
            lambda r: (r["order_id"], r["payment_sequential"]) in existing_ids,
            axis=1
        )]
        skipped = before - len(df)
        logger.info(f"Skipping {skipped} duplicate rows, inserting {len(df)} new rows")
        if df.empty:
            logger.info("Nothing new to insert — all rows already exist in DB.")
            _archive_file(order_payments_file_name)  # still archive the file to avoid reprocessing
            return
        # 5. Bulk insert
        _copy_to_postgres(hook, df, "olist_order_payments", order_payments_columns, temp_constraints="INCLUDING ALL")
        logger.info(f"Inserted {len(df)} rows into olist_order_payments table")
        # 6. Archive the file
        _archive_file(order_payments_file_name)
    
    except Exception as e:
        logger.error(f" Failed to load olist_order_payments data: {e}")
        raise

def loading_order_reviews():
    try:
        # 1. Read file
        if not os.path.exists(order_reviews_file):
            # raise AirflowSkipException(f"CSV not found: {orders_file}")
            raise FileNotFoundError(f"CSV not found: {order_reviews_file}")
        df = pd.read_csv(order_reviews_file)
        df = df.drop_duplicates(subset=["review_id"])
        # 2. Validate columns
        missing = set(order_reviews_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns in CSV: {missing}")
        df = df[order_reviews_columns]  # keep only needed columns, in correct order
        # 3. Fetch existing composite keys from DB
        hook = PostgresHook(postgres_conn_id='olist_ecommerce')
        existing = hook.get_records(
            "SELECT DISTINCT review_id FROM olist_order_reviews"
        )
        existing_ids = {row[0] for row in existing}   
        logger.info(f"Found {len(existing_ids)} existing order_reviewst records in DB")

        # 4. Filter out duplicates using composite key

        before = len(df)
        df = df[~df["review_id"].isin(existing_ids)]
        skipped = before - len(df)
        logger.info(f"Skipping {skipped} duplicate rows, inserting {len(df)} new rows")
        if df.empty:
            logger.info("Nothing new to insert — all rows already exist in DB.")
            _archive_file(order_reviews_file_name)  # still archive the file to avoid reprocessing
            return
        
        # 5. Bulk insert
        _copy_to_postgres(hook, df, "olist_order_reviews", order_reviews_columns, temp_constraints="INCLUDING ALL")
        logger.info(f"Inserted {len(df)} rows into olist_order_reviews table")
        # 6. Archive the file
        _archive_file(order_reviews_file_name)
    
    except Exception as e:
        logger.error(f" Failed to load olist_order_reviews data: {e}")
        raise



smtp_notifier = SmtpNotifier(
    smtp_conn_id="smtp_default",
    to=["petercharlesmchikho1@gmail.com"],
    subject="Airflow failure: {{ dag.dag_id }} / {{ task_instance.task_id }}",
    html_content="""
        <h3>Task failed</h3>
        <b>DAG:</b>   {{ dag.dag_id }}<br>
        <b>Task:</b>  {{ task_instance.task_id }}<br>
        <b>Logs:</b>  <a href="{{ task_instance.log_url }}">View logs</a>
    """,
)

with DAG(
    'initial_dataload_olist_db',
    start_date=datetime(2024, 1, 1),
    on_failure_callback=smtp_notifier,
    schedule='@daily', 
    catchup=False,
    description='Test connection to olist_db (manual trigger)',
    tags=['test', 'olist'],
) as dag:
    
    loading_orders_task=PythonOperator(
        task_id='load_orders',
        python_callable=loading_orders
    )

    loading_order_items_task=PythonOperator(
        task_id='load_orders_items',
        python_callable=loading_order_items
    )
    
    loading_order_payments_task=PythonOperator(
        task_id='load_order_payments',
        python_callable=loading_order_payments
    )

    loading_order_reviews_task=PythonOperator(
        task_id='load_order_reviews',
        python_callable=loading_order_reviews
    )



    test_conn >> [list_tables, load_geolocations_task, load_customers_task, loading_sellers_task, loading_product_category_name_task] >> loading_products_task >> loading_orders_task >> [loading_order_reviews_task,loading_order_payments_task,loading_order_items_task]

    