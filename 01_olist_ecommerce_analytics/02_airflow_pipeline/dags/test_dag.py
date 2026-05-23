from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator  # Fixed import
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def test_function():
    print("Airflow is working!")

with DAG(
    'test_airflow_dag',
    default_args=default_args,
    description='A simple test DAG',
    schedule='@daily',
    catchup=False,
    tags=['test'],
) as dag:

    task1 = BashOperator(
        task_id='print_date',
        bash_command='date',
    )
    
    task2 = PythonOperator(
        task_id='test_python',
        python_callable=test_function,
    )
    
    task3 = BashOperator(
        task_id='echo_hello',
        bash_command='echo "Hello from Airflow!"',
    )
    
    task1 >> task2 >> task3