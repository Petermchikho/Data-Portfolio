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

geolocations_file_name="olist_geolocation_dataset.csv"
customers_file_name="olist_customers_dataset.csv"
sellers_file_name="olist_sellers_dataset.csv"
product_category_name_translation_file_name="product_category_name_translation.csv"
products_file_name="olist_products_dataset.csv"