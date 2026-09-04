"""
Weather ETL DAG — chay hang ngay luc 1:00 AM (UTC+7)

Pipeline 4 buoc:
    Task 1: extract       — Goi API Open-Meteo lay 1512 hourly records (63 tinh x 24h)
    Task 2: transform     — Aggregate thanh 63 daily records, map dimension IDs
    Task 3: load          — Seed dim_location, insert vao weather_fact (idempotent)
    Task 4: data_quality  — Kiem tra Completeness, Nulls, Uniqueness, Value Ranges
"""

import sys
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# Airflow container dung /opt/airflow lam WORKDIR
sys.path.insert(0, "/opt/airflow")

# Import cac ham ETL truc tiep tu src/
from src.extract import extract_all_locations
from src.transform import transform_weather_data
from src.load import get_connection, seed_dim_location, load_weather_data
from src.data_quality import run_data_quality_checks

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

# ============================================================================
# Cac ham callable cho tung Task
# XCom duoc dung de truyen du lieu giua cac task trong cung mot DAG run
# ============================================================================

def task_extract(**context) -> None:
    """
    Task 1: EXTRACT
    Goi API Open-Meteo va push raw DataFrame len XCom de task sau dung.
    """
    raw_df = extract_all_locations()

    if raw_df is None or raw_df.empty:
        raise ValueError("EXTRACT THAT BAI: Khong lay duoc du lieu tu Open-Meteo API.")

    # Chuyen DataFrame -> JSON string de luu vao XCom (XCom chi luu duoc serializable data)
    context["ti"].xcom_push(key="raw_df_json", value=raw_df.to_json(orient="records", date_format="iso"))
    print(f"EXTRACT OK: {len(raw_df)} hourly records tu 63 tinh")


def task_transform(**context) -> None:
    """
    Task 2: TRANSFORM
    Doc raw_df tu XCom, aggregate thanh daily records, push transformed_df len XCom.
    """
    import pandas as pd

    raw_json = context["ti"].xcom_pull(key="raw_df_json", task_ids="extract")
    raw_df = pd.read_json(raw_json, orient="records")

    # Can conn de query dim_time va dim_weather_condition
    conn = get_connection()
    try:
        transformed_df = transform_weather_data(raw_df, conn)
        if transformed_df is None or transformed_df.empty:
            raise ValueError("TRANSFORM THAT BAI: Khong the xu ly du lieu.")

        context["ti"].xcom_push(
            key="transformed_df_json",
            value=transformed_df.to_json(orient="records", date_format="iso"),
        )
        print(f"TRANSFORM OK: {len(transformed_df)} daily records")
    finally:
        conn.close()


def task_load(**context) -> None:
    """
    Task 3: LOAD
    Doc transformed_df tu XCom, seed dim_location, insert vao weather_fact.
    Push date_id cua ngay hom nay len XCom de task data_quality dung.
    """
    import pandas as pd

    transformed_json = context["ti"].xcom_pull(key="transformed_df_json", task_ids="transform")
    transformed_df = pd.read_json(transformed_json, orient="records")

    conn = get_connection()
    try:
        if not seed_dim_location(conn):
            raise RuntimeError("LOAD THAT BAI: Seed dim_location that bai.")

        inserted = load_weather_data(conn, transformed_df)
        if inserted is None:
            raise RuntimeError("LOAD THAT BAI: Insert weather_fact that bai.")

        # Push date_id de task data_quality su dung
        target_date_id = int(transformed_df["date_id"].iloc[0])
        context["ti"].xcom_push(key="target_date_id", value=target_date_id)

        print(f"LOAD OK: {inserted} records inserted (so con lai da ton tai trong DB)")
    finally:
        conn.close()


def task_data_quality(**context) -> None:
    """
    Task 4: DATA QUALITY CHECK
    Doc date_id tu XCom, kiem tra Completeness / Nulls / Uniqueness / Ranges.
    """
    target_date_id = context["ti"].xcom_pull(key="target_date_id", task_ids="load")

    conn = get_connection()
    try:
        passed = run_data_quality_checks(conn, target_date_id=target_date_id)
        if not passed:
            raise ValueError("DATA QUALITY THAT BAI: Co check khong dat yeu cau!")
        print("DATA QUALITY OK: PASS 100%")
    finally:
        conn.close()


# ============================================================================
# Dinh nghia DAG
# ============================================================================
with DAG(
    dag_id="weather_etl_pipeline",
    description="Daily Vietnam weather ETL: Open-Meteo API -> Supabase PostgreSQL (Star Schema)",
    default_args=DEFAULT_ARGS,
    # Chay luc 1:00 AM gio Viet Nam (UTC+7 = 18:00 UTC ngay hom truoc)
    schedule="0 18 * * *",
    start_date=datetime(2026, 9, 1),
    catchup=False,
    tags=["etl", "weather", "vietnam"],
) as dag:

    extract = PythonOperator(
        task_id="extract",
        python_callable=task_extract,
    )

    transform = PythonOperator(
        task_id="transform",
        python_callable=task_transform,
    )

    load = PythonOperator(
        task_id="load",
        python_callable=task_load,
    )

    data_quality = PythonOperator(
        task_id="data_quality",
        python_callable=task_data_quality,
    )

    # Luong thuc thi: extract -> transform -> load -> data_quality
    extract >> transform >> load >> data_quality
