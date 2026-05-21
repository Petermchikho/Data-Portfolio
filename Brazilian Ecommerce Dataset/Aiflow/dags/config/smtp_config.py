import os
from dotenv import load_dotenv

def configure_smtp():
    load_dotenv("/airflow/config/.env")
    os.environ.update({
        "AIRFLOW__SMTP__SMTP_HOST":      "smtp.gmail.com",
        "AIRFLOW__SMTP__SMTP_PORT":      "587",
        "AIRFLOW__SMTP__SMTP_USER":      os.getenv("SMTP_USER", ""),
        "AIRFLOW__SMTP__SMTP_PASSWORD":  os.getenv("SMTP_PASSWORD", ""),
        "AIRFLOW__SMTP__SMTP_MAIL_FROM": os.getenv("SMTP_USER", ""),
        "AIRFLOW__SMTP__SMTP_SSL":       "False",
        "AIRFLOW__SMTP__SMTP_STARTTLS":  "True",
        
    })