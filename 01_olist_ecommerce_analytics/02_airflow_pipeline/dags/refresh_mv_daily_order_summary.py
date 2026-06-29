from datetime import datetime, timedelta

from airflow.sdk import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook

POSTGRES_CONN_ID = "olist_ecommerce"  
MV_NAME = "mv_daily_order_summary"

default_args = {
    "owner": "peter",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}


@dag(
    dag_id="refresh_mv_daily_order_summary",
    schedule="0 3 * * *",  # daily at 3am
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["olist", "postgres", "materialized-view"],
)
def refresh_mv_daily_order_summary():

    @task
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

    refresh_concurrently()


refresh_mv_daily_order_summary()