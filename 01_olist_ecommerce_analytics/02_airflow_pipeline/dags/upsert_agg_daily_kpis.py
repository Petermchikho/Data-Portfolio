from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

POSTGRES_CONN_ID = "olist_ecommerce"

default_args = {
    'owner': 'Peter Mchikho',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

UPSERT_SQL = """
INSERT INTO agg_daily_kpis (kpi_date, total_orders, gmv, new_customers, updated_at)
SELECT
    %(kpi_date)s AS kpi_date,
    COUNT(DISTINCT o.order_id) AS total_orders,
    COALESCE(SUM(p.payment_value), 0) AS gmv,
    (
        SELECT COUNT(DISTINCT c.customer_id)
        FROM olist_customers c
        WHERE c.first_order_date = %(kpi_date)s
    ) AS new_customers,
    now() AS updated_at
FROM olist_orders o
JOIN olist_order_payments p ON p.order_id = o.order_id
WHERE o.order_purchase_date = %(kpi_date)s
ON CONFLICT (kpi_date)
DO UPDATE SET
    total_orders  = EXCLUDED.total_orders,
    gmv           = EXCLUDED.gmv,
    new_customers = EXCLUDED.new_customers,
    updated_at    = EXCLUDED.updated_at;
"""


def upsert_daily_kpis(**context):
    kpi_date = context["logical_date"].date()

    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    conn = hook.get_conn()
    cursor = conn.cursor()
    try:
        print(f"Upserting KPIs for date: {kpi_date}")
        cursor.execute(UPSERT_SQL, {"kpi_date": kpi_date})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


with DAG(
    'upsert_agg_daily_kpis',
    default_args=default_args,
    description='Upsert yesterday aggregated KPIs into agg_daily_kpis',
    schedule='@daily',
    catchup=False,
    tags=["olist", "postgres", "kpi", "upsert"],
) as dag:

    upsert_task = PythonOperator(
        task_id='upsert_daily_kpis',
        python_callable=upsert_daily_kpis,
    )