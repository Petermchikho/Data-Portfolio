from datetime import datetime
from airflow.utils.email import send_email
import os
import shutil
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.smtp.notifications.smtp import SmtpNotifier 
import pandas as pd
import logging
import io

logger = logging.getLogger(__name__)
dir_data    = "/opt/airflow/data/files"
dir_archive = "/opt/airflow/data/archive"
geolocations_file = f"{dir_data}/olist_geolocation_dataset.csv"
geolocations_columns=["geolocation_zip_code_prefix","geolocation_lat","geolocation_lng","geolocation_city","geolocation_state"]

def notify_failure(context):
    """Called automatically by Airflow on any task failure."""
    dag_id   = context["dag"].dag_id
    task_id  = context["task_instance"].task_id
    log_url  = context["task_instance"].log_url
    exc      = context.get("exception", "Unknown error")

    send_email(
        to=["petercharlesmchikho1@gmail.com"], 
        subject=f"Airflow failure: {dag_id} / {task_id}",
        html_content=f"""
            <h3>Task failed</h3>
            <b>DAG:</b>  {dag_id}<br>
            <b>Task:</b> {task_id}<br>
            <b>Error:</b> {exc}<br>
            <b>Logs:</b> <a href="{log_url}">{log_url}</a>
        """,
    )

def test_olist_connection():
    """Test connection to olist_db"""
    try:
        hook = PostgresHook(postgres_conn_id='olist_ecommerce')
        result = hook.get_first("SELECT 'Connection Successful!' as message, version(), NOW() as current_time")
        logger.info("=" * 50)
        logger.info(f" {result[0]}")
        logger.info(f" PostgreSQL Version: {result[1]}")
        logger.info(f" Server Time: {result[2]}")
        logger.info("=" * 50)
        return True
    except Exception as e:
        logger.error(f" Connection Failed: {e}")
        raise

def list_olist_tables():
    """Check if Olist tables already exist"""
    hook = PostgresHook(postgres_conn_id='olist_ecommerce')
    
    tables = hook.get_pandas_df("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE';
    """)
    
    if len(tables) > 0:
        logger.info(" Existing Olist Tables Found:")
        for idx, row in tables.iterrows():
            logger.info(f"  {row['table_name']}")
    else:
        logger.info("ℹ No Olist tables found. Ready to create them.")
    
    return tables
def _copy_to_postgres(hook, df, table, columns):
    """Fast bulk insert, silently skipping any PK conflicts."""
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)

    conn   = hook.get_conn()
    cursor = conn.cursor()

    # load into temp table first
    cursor.execute(f"CREATE TEMP TABLE tmp_{table} (LIKE {table} INCLUDING DEFAULTS)")
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

def _archive_file():
    """Move processed CSV to archive folder with a timestamp."""
    os.makedirs(dir_archive, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = f"{dir_archive}/geolocations_{timestamp}.csv"
    shutil.move(geolocations_file, dest)
    logger.info(f"Archived file ==> {dest}")

def loading_geolocations():
    """Load geolocations data into olist_db"""
    try:
        """Load geolocations CSV ==> Postgres, skipping duplicates, archive on success."""

        # 1. Read file 
        if not os.path.exists(geolocations_file):
            raise FileNotFoundError(f"CSV not found: {geolocations_file}")

        df = pd.read_csv(geolocations_file)
        df["geolocation_zip_code_prefix"] = (
            df["geolocation_zip_code_prefix"]
            .astype(str)
            .str.zfill(5)   # pads 1037 ==> "01037"
        )

        df = df.drop_duplicates(subset=["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"])

        logger.info(f"Read {len(df)} rows from CSV")

        # 2. Validate columns 
        missing = set(geolocations_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns in CSV: {missing}")

        df = df[geolocations_columns]  # keep only needed columns, in correct order

        # 3. Fetch existing zip codes from DB to avoid duplicates
        hook = PostgresHook(postgres_conn_id='olist_ecommerce')

        existing = hook.get_records("SELECT DISTINCT geolocation_zip_code_prefix FROM olist_geolocation")
        existing_zips = {row[0] for row in existing}          # fast set lookup
        logger.info(f"Found {len(existing_zips)} existing zip prefixes in DB")

        # 4. Filter out duplicates
        before = len(df)
        df = df[~df["geolocation_zip_code_prefix"].isin(existing_zips)]
        skipped = before - len(df)
        logger.info(f"Skipping {skipped} duplicate rows, inserting {len(df)} new rows")

        if df.empty:
            logger.info("Nothing new to insert — all rows already exist in DB.")
            _archive_file()
            return

        # 5. Bulk insert 
        _copy_to_postgres(hook, df, "olist_geolocation", geolocations_columns)
        
        logger.info(f"Inserted {len(df)} rows into olist_geolocation table")

        # 6. Archive the file
        _archive_file()
    except Exception as e:
        logger.error(f" Failed to load olist_geolocation data: {e}")
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
    
    test_conn = PythonOperator(
        task_id='test_connection',
        python_callable=test_olist_connection,
    )
    
    list_tables = PythonOperator(
        task_id='list_existing_tables',
        python_callable=list_olist_tables,
    )

    load_geolocations_task = PythonOperator(
        task_id='load_geolocations',
        python_callable=loading_geolocations,
    )

    test_conn >> [list_tables, load_geolocations_task]

    
    