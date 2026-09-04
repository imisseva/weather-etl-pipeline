"""
Weather ETL DAG — chay hang ngay luc 1:00 AM (UTC+7 = 18:00 UTC)

Thiet ke: 1 PythonOperator duy nhat goi run_pipeline() tu main.py
Ly do: Raw DataFrame (1512 records) qua lon cho XCom Airflow (~48KB limit).
Giu nguyen logic 4 buoc ben trong run_pipeline():
    1. Extract       — Goi API Open-Meteo
    2. Transform     — Aggregate thanh 63 daily records
    3. Load          — Seed dim_location, insert weather_fact (idempotent)
    4. Data Quality  — Completeness, Nulls, Uniqueness, Value Ranges
"""

import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.insert(0, "/opt/airflow")


def run_etl_pipeline() -> None:
    """
    Goi run_pipeline() tu main.py.
    Nem RuntimeError neu pipeline that bai de Airflow danh dau task la failed.
    """
    from main import run_pipeline

    success = run_pipeline()
    if not success:
        raise RuntimeError("Weather ETL Pipeline that bai — xem log phia tren de biet nguyen nhan.")


# ============================================================================
# Cau hinh DAG
# ============================================================================
DEFAULT_ARGS = {
    "owner": "imisseva",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="weather_etl_pipeline",
    description="Daily Vietnam weather ETL: Open-Meteo API -> Supabase PostgreSQL (Star Schema)",
    default_args=DEFAULT_ARGS,
    # Chay luc 1:00 AM gio Viet Nam (UTC+7) = 18:00 UTC
    schedule="0 18 * * *",
    start_date=datetime(2026, 9, 1),
    catchup=False,
    tags=["etl", "weather", "vietnam"],
) as dag:

    etl_pipeline = PythonOperator(
        task_id="run_pipeline",
        python_callable=run_etl_pipeline,
    )
