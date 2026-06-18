

from datetime import datetime

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def _test_email():
    from airflow.providers.smtp.hooks.smtp import SmtpHook

    with SmtpHook(smtp_conn_id="smtp_default") as smtp:
        smtp.send_email_smtp(
            to="petercharlesmchikho1@gmail.com",
            subject="✅ Airflow SMTP test",
            html_content="""
                <h3 style="color:#27ae60">SMTP is wired correctly</h3>
                <table>
                  <tr><td><b>Connection</b></td><td>smtp_default</td></tr>
                  <tr><td><b>Host</b></td><td>smtp.gmail.com:587</td></tr>
                  <tr><td><b>Time</b></td><td>{}</td></tr>
                </table>
                <p>You can now delete the <code>test_smtp</code> DAG.</p>
            """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            from_email="petercharlesmchikho1@gmail.com",
        )


with DAG(
    dag_id="test_smtp",
    start_date=datetime(2024, 1, 1),
    schedule=None,          # manual trigger only — never runs on a schedule
    catchup=False,
    tags=["test", "smtp"],
    description="One-shot SMTP verification — delete after confirmed",
) as dag:

    PythonOperator(
        task_id="send_test_email",
        python_callable=_test_email,
    )