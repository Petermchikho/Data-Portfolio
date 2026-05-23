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
dir_data    = "/opt/airflow/data/files"
dir_archive = "/opt/airflow/data/archive"
geolocations_file_name="olist_geolocation_dataset.csv"
customers_file_name="olist_customers_dataset.csv"
sellers_file_name="olist_sellers_dataset.csv"
product_category_name_translation_file_name="product_category_name_translation.csv"
products_file_name="olist_products_dataset.csv"
orders_file_name="olist_orders_dataset.csv"
order_items_file_name="olist_order_items_dataset.csv"
order_payments_file_name="olist_order_payments_dataset.csv"
order_reviews_file_name="olist_order_reviews_dataset.csv"

geolocations_file = f"{dir_data}/{geolocations_file_name}"
customers_file    = f"{dir_data}/{customers_file_name}"
sellers_file      = f"{dir_data}/{sellers_file_name}"
product_category_name_translation_file = f"{dir_data}/{product_category_name_translation_file_name}"
products_file=f"{dir_data}/{products_file_name}"
orders_file=f"{dir_data}/{orders_file_name}"
order_items_file=f"{dir_data}/{order_items_file_name}"
order_payments_file=f"{dir_data}/{order_payments_file_name}"
order_reviews_file=f"{dir_data}/{order_reviews_file_name}"

geolocations_columns=["geolocation_zip_code_prefix","geolocation_lat","geolocation_lng","geolocation_city","geolocation_state"]
customers_columns=["customer_id","customer_unique_id","customer_zip_code_prefix","customer_city","customer_state"]
sellers_columns=["seller_id","seller_zip_code_prefix","seller_city","seller_state"]
product_category_name_translation_columns=["product_category_name","product_category_name_english"]
products_columns=["product_id","product_category_name","product_name_length","product_description_length","product_photos_qty","product_weight_g","product_length_cm","product_height_cm","product_width_cm"]
orders_columns=["order_id","customer_id","order_status","order_purchase_timestamp","order_approved_at","order_delivered_carrier_date","order_delivered_customer_date","order_estimated_delivery_date"]
order_items_columns=["order_id","order_item_id","product_id","seller_id","shipping_limit_date","price","freight_value"]
order_payments_columns=["order_id","payment_sequential","payment_type","payment_installments","payment_value"]
order_reviews_columns=["review_id","order_id","review_score","review_comment_title","review_comment_message","review_creation_date","review_answer_timestamp"]

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
    
def loading_geolocations():
    """Load geolocations data into olist_db"""
    try:
        """Load geolocations CSV ==> Postgres, skipping duplicates, archive on success."""

        # 1. Read file 
        if not os.path.exists(geolocations_file):
            raise AirflowSkipException(f"CSV not found: {geolocations_file}")

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
            _archive_file(geolocations_file_name)  # still archive the file to avoid reprocessing
            return

        # 5. Bulk insert 
        _copy_to_postgres(hook, df, "olist_geolocation", geolocations_columns)
        
        logger.info(f"Inserted {len(df)} rows into olist_geolocation table")

        # 6. Archive the file
        _archive_file(geolocations_file_name)
    except Exception as e:
        logger.error(f" Failed to load olist_geolocation data: {e}")
        raise

def loading_customers():
    try:

        # 1. Read file
        if not os.path.exists(customers_file):
            raise AirflowSkipException(f"CSV not found: {customers_file}")
        df = pd.read_csv(customers_file)
        df["customer_zip_code_prefix"] = ( df["customer_zip_code_prefix"]
            .astype(str)
            .str.zfill(5)   
        ) 

        df = df.drop_duplicates(subset=["customer_id", "customer_unique_id", "customer_zip_code_prefix"])

        # 2. Validate columns
        missing = set(customers_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns in CSV: {missing}")
        df = df[customers_columns]  # keep only needed columns, in correct order

        # 3. Fetch existing customer IDs from DB to avoid duplicates
        hook = PostgresHook(postgres_conn_id='olist_ecommerce')
        existing = hook.get_records("SELECT DISTINCT customer_id FROM olist_customers")
        existing_zips = {row[0] for row in existing}          # fast set lookup
        logger.info(f"Found {len(existing_zips)} existing zip prefixes in DB")

        # 4. Filter out duplicates
        before = len(df)
        df = df[~df["customer_id"].isin(existing_zips)]
        skipped = before - len(df)
        logger.info(f"Skipping {skipped} duplicate rows, inserting {len(df)} new rows")

        if df.empty:
            logger.info("Nothing new to insert — all rows already exist in DB.")
            _archive_file(customers_file_name)  # still archive the file to avoid reprocessing
            return
        
        # 5. Bulk insert 
        _copy_to_postgres(hook, df, "olist_customers", customers_columns, temp_constraints="INCLUDING ALL")
        
        logger.info(f"Inserted {len(df)} rows into olist_customers table")

        # 6. Archive the file
        _archive_file(customers_file_name)

    
    except Exception as e:
        logger.error(f" Failed to load olist_customers data: {e}")
        raise

def loading_sellers():
    try:
        # 1. Read file
        if not os.path.exists(sellers_file):
            raise AirflowSkipException(f"CSV not found: {sellers_file}")
        df = pd.read_csv(sellers_file)
        df["seller_zip_code_prefix"] = ( df["seller_zip_code_prefix"]
            .astype(str)
            .str.zfill(5)   
        )
        df = df.drop_duplicates(subset=["seller_id", "seller_zip_code_prefix"])

        # 2. Validate columns
        missing = set(sellers_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns in CSV: {missing}")
        df = df[sellers_columns]  # keep only needed columns, in correct order

        # 3. Fetch existing seller IDs from DB to avoid duplicates
        hook = PostgresHook(postgres_conn_id='olist_ecommerce')
        existing = hook.get_records("SELECT DISTINCT seller_id FROM olist_sellers")
        existing_zips = {row[0] for row in existing}          # fast set lookup
        logger.info(f"Found {len(existing_zips)} existing zip prefixes in DB")

        # 4. Filter out duplicates
        before = len(df)
        df = df[~df["seller_id"].isin(existing_zips)]
        skipped = before - len(df)
        logger.info(f"Skipping {skipped} duplicate rows, inserting {len(df)} new rows")

        if df.empty:
            logger.info("Nothing new to insert — all rows already exist in DB.")
            _archive_file(sellers_file_name)  # still archive the file to avoid reprocessing
            return
        
        # 5. Bulk insert 
        _copy_to_postgres(hook, df, "olist_sellers", sellers_columns, temp_constraints="INCLUDING ALL")
        logger.info(f"Inserted {len(df)} rows into olist_sellers table")
        # 6. Archive the file
        _archive_file(sellers_file_name)
    
    except Exception as e:
        logger.error(f" Failed to load olist_sellers data: {e}")
        raise

def loading_product_category_name():
    try:
        # 1. Read file
        if not os.path.exists(product_category_name_translation_file):
            raise AirflowSkipException(f"CSV not found: {product_category_name_translation_file}")
        df = pd.read_csv(product_category_name_translation_file)
        df = df.drop_duplicates(subset=["product_category_name", "product_category_name_english"])
        # 2. Validate columns
        missing = set(product_category_name_translation_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns in CSV: {missing}")
        df = df[product_category_name_translation_columns]  # keep only needed columns, in correct order
        # 3. Fetch existing product category names from DB to avoid duplicates
        hook = PostgresHook(postgres_conn_id='olist_ecommerce')
        existing = hook.get_records("SELECT DISTINCT product_category_name FROM olist_product_category_name_translation")
        existing_names = {row[0] for row in existing}          # fast set lookup
        logger.info(f"Found {len(existing_names)} existing product category names in DB")
        # 4. Filter out duplicates
        before = len(df)
        df = df[~df["product_category_name"].isin(existing_names)]
        skipped = before - len(df)
        logger.info(f"Skipping {skipped} duplicate rows, inserting {len(df)} new rows")
        if df.empty:
            logger.info("Nothing new to insert — all rows already exist in DB.")
            _archive_file(product_category_name_translation_file_name)  # still archive the file to avoid reprocessing
            return
        # 5. Bulk insert
        _copy_to_postgres(hook, df, "olist_product_category_name_translation", product_category_name_translation_columns, temp_constraints="INCLUDING ALL")
        logger.info(f"Inserted {len(df)} rows into olist_product_category_name_translation table")
        # 6. Archive the file
        _archive_file(product_category_name_translation_file_name)

    except Exception as e:
        logger.error(f" Failed to load olist_product_category_name_translation data: {e}")
        raise

def loading_products():
    try:
        # 1. Read file
        if not os.path.exists(products_file):
            raise AirflowSkipException(f"CSV not found: {products_file}")
            # raise FileNotFoundError(f"CSV not found: {products_file}")
        df = pd.read_csv(products_file)
        df = df.drop_duplicates(subset=["product_id"])
        # 2. Validate columns
        missing = set(products_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns in CSV: {missing}")
        df = df[products_columns]  # keep only needed columns, in correct order
        # 3. Fetch existing product IDs from DB to avoid duplicates
        hook = PostgresHook(postgres_conn_id='olist_ecommerce')
        existing = hook.get_records("SELECT DISTINCT product_id FROM olist_products")
        existing_ids = {row[0] for row in existing}          # fast set lookup
        logger.info(f"Found {len(existing_ids)} existing product IDs in DB")
        # 4. Filter out duplicates
        before = len(df)
        df = df[~df["product_id"].isin(existing_ids)]
        skipped = before - len(df)
        logger.info(f"Skipping {skipped} duplicate rows, inserting {len(df)} new rows")
        if df.empty:
            logger.info("Nothing new to insert — all rows already exist in DB.")
            _archive_file(products_file_name)  # still archive the file to avoid reprocessing
            return
        # 5. Bulk insert
        _copy_to_postgres(hook, df, "olist_products", products_columns, temp_constraints="INCLUDING ALL")
        logger.info(f"Inserted {len(df)} rows into olist_products table")
        # 6. Archive the file
        _archive_file(products_file_name)

    except Exception as e:
        logger.error(f" Failed to load olist_products data: {e}")
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

    load_customers_task =PythonOperator(
        task_id='load_customers',
        python_callable=loading_customers,
    )

    loading_sellers_task = PythonOperator(
        task_id='load_sellers',
        python_callable=loading_sellers,
    )

    loading_product_category_name_task = PythonOperator(
        task_id='load_product_category_name_translation',
        python_callable=loading_product_category_name,
    )

    loading_products_task = PythonOperator(
        task_id='load_products',
        python_callable=loading_products,
    )

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

    