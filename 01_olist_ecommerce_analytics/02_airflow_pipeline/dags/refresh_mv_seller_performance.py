from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

POSTGRES_CONN_ID = "olist_ecommerce"  
MV_NAME = "mv_seller_performance"
default_args = {
    'owner': 'Peter Mchikho',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def refresh_concurrently():
    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    conn = hook.get_conn()
    conn.autocommit = True
    cursor = conn.cursor()
    try:
        cursor.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME};")
    finally:
        cursor.close()
        conn.close()

with DAG(
    'refresh_mv_seller_performance',
    default_args=default_args,
    description='refresh_mv_seller_performance',
    schedule='@daily',
    catchup=False,
    tags=["olist", "postgres", "materialized-view"],
) as dag:
    
    task1 = PythonOperator(
        task_id='refresh_concurrently_mv_seller_performance',
        python_callable=refresh_concurrently,
    )
    task1 