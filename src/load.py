import time
import psycopg2
from psycopg2.extras import execute_values
import pandas as pd
from typing import Optional

from config.settings import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, LOCATIONS
from src.logger import get_logger

logger = get_logger(__name__)

# Retry config cho DB operations
MAX_RETRIES = 3


def get_connection():
    """
    Tạo connection tới Supabase PostgreSQL.
    Retry 3 lần với exponential backoff nếu connection thất bại.

    Returns:
        psycopg2 connection object

    Raises:
        psycopg2.OperationalError: Nếu kết nối thất bại sau 3 lần thử
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                dbname=DB_NAME,
                sslmode="require",
            )
            logger.info(f"Connected to {DB_HOST}")
            return conn

        except psycopg2.OperationalError as e:
            if attempt < MAX_RETRIES:
                delay = 2 ** (attempt - 1)
                logger.warning(f"Connection failed (attempt {attempt}/{MAX_RETRIES}): {e}")
                logger.info(f"Retry sau {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Failed to connect after {MAX_RETRIES} attempts: {e}")
                raise


def seed_dim_location(conn) -> bool:
    """
    Insert 63 tỉnh thành vào dim_location nếu chưa có.
    Schema mới: dim_location (không có 's') với cột region.
    Dùng ON CONFLICT DO NOTHING → idempotent, chạy bao nhiêu lần cũng an toàn.

    Args:
        conn: psycopg2 connection

    Returns:
        True nếu thành công, False nếu có lỗi
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Seeding dim_location...")

            # Bao gồm cột region (mới so với schema cũ)
            data = [
                (loc["name"], loc["latitude"], loc["longitude"], loc["region"])
                for loc in LOCATIONS
            ]

            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    INSERT INTO dim_location (location_name, latitude, longitude, region)
                    VALUES %s
                    ON CONFLICT (location_name) DO NOTHING
                    """,
                    data,
                )
            conn.commit()

            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM dim_location")
                count = cur.fetchone()[0]

            logger.info(f"  dim_location: {count} tinh trong DB")
            return True

        except psycopg2.OperationalError as e:
            conn.rollback()
            if attempt < MAX_RETRIES:
                delay = 2 ** (attempt - 1)
                logger.warning(f"DB error seeding dim_location (attempt {attempt}/{MAX_RETRIES}): {e}")
                logger.info(f"Retry sau {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Failed to seed dim_location after {MAX_RETRIES} attempts: {e}")
                return False

        except psycopg2.IntegrityError as e:
            logger.error(f"Integrity error seeding dim_location — khong retry: {e}")
            conn.rollback()
            return False

        except Exception as e:
            logger.error(f"Unexpected error seeding dim_location — khong retry: {e}")
            conn.rollback()
            return False


def load_weather_data(conn, df: pd.DataFrame) -> Optional[int]:
    """
    Load daily weather data đã transform vào weather_fact (Star Schema).

    Columns cần: location_id, date_id, condition_id,
                 temperature, humidity, wind_speed, recorded_at

    ON CONFLICT (location_id, date_id) DO NOTHING:
    → Pipeline chạy 2 lần cùng ngày sẽ tự bỏ qua record đã tồn tại.

    Args:
        conn: psycopg2 connection
        df:   DataFrame đã transform từ transform_weather_data()

    Returns:
        Số records được insert thực tế. Trả về None nếu có lỗi.
    """
    if df is None or df.empty:
        logger.error("Load: DataFrame rong hoac None")
        return None

    # Chọn đúng cột theo thứ tự INSERT INTO bên dưới
    # condition_id có thể là NaN (nullable) → giữ nguyên để psycopg2 chuyển thành NULL
    records = [
        (
            int(row.location_id),
            int(row.date_id),
            int(row.condition_id) if pd.notna(row.condition_id) else None,
            float(row.temperature),
            int(row.humidity),
            float(row.wind_speed),
            row.recorded_at,
        )
        for row in df.itertuples(index=False)
    ]

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"=== START LOAD | {len(df)} daily records ===")

            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    INSERT INTO weather_fact
                        (location_id, date_id, condition_id,
                         temperature, humidity, wind_speed, recorded_at)
                    VALUES %s
                    ON CONFLICT (location_id, date_id) DO NOTHING
                    """,
                    records,
                )
                inserted = cur.rowcount

            conn.commit()

            skipped = len(df) - inserted
            logger.info(f"  Inserted : {inserted} records")
            if skipped > 0:
                logger.info(f"  Skipped  : {skipped} records (da ton tai trong DB)")
            logger.info(f"=== LOAD DONE | {inserted}/{len(df)} records ===")

            return inserted

        except psycopg2.OperationalError as e:
            conn.rollback()
            if attempt < MAX_RETRIES:
                delay = 2 ** (attempt - 1)
                logger.warning(f"DB error loading weather_fact (attempt {attempt}/{MAX_RETRIES}): {e}")
                logger.info(f"Retry sau {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Failed to load weather_fact after {MAX_RETRIES} attempts: {e}")
                return None

        except psycopg2.IntegrityError as e:
            logger.error(f"Integrity error loading weather_fact — khong retry: {e}")
            conn.rollback()
            return None

        except Exception as e:
            logger.error(f"Unexpected error loading weather_fact — khong retry: {e}")
            conn.rollback()
            return None


def load_to_database(df: pd.DataFrame) -> tuple[bool, psycopg2.extensions.connection]:
    """
    Main load function:
        1. Tạo DB connection
        2. Seed dim_location (63 tỉnh + region)
        3. Load weather_fact (daily records)

    Transform cần conn để query dim_time và dim_weather_condition,
    nên hàm này trả về conn để main.py tái sử dụng.

    Args:
        df: DataFrame đã transform từ transform_weather_data()

    Returns:
        (success: bool, conn: connection | None)
        Caller có trách nhiệm đóng conn sau khi dùng xong.
    """
    conn = None
    try:
        conn = get_connection()

        # Seed dim_location (bao gồm region)
        if not seed_dim_location(conn):
            return False, conn

        # Load weather_fact
        inserted = load_weather_data(conn, df)
        if inserted is None:
            return False, conn

        logger.info(f"Load phase completed: {inserted} records inserted")
        return True, conn

    except Exception as e:
        logger.error(f"Unexpected error in load_to_database: {e}")
        return False, conn


if __name__ == "__main__":
    from src.extract import extract_all_locations
    from src.transform import transform_weather_data

    print("=" * 60)
    print("TEST: Extract → Transform → Load")
    print("=" * 60)

    # Extract
    print("\n[1] Extracting...")
    raw_df = extract_all_locations()
    if raw_df is None:
        print("Extract that bai!")
        exit(1)
    print(f"Extracted: {len(raw_df)} hourly records")

    # Cần conn trước khi Transform (để query dim_time, dim_weather_condition)
    print("\n[2] Connecting to DB...")
    conn = get_connection()

    try:
        # Transform
        print("\n[3] Transforming...")
        transformed_df = transform_weather_data(raw_df, conn)
        if transformed_df is None:
            print("Transform that bai!")
            exit(1)
        print(f"Transformed: {len(transformed_df)} daily records")
        print(transformed_df.to_string())

        # Load
        print("\n[4] Loading to Supabase...")
        if not seed_dim_location(conn):
            print("Seed dim_location that bai!")
            exit(1)

        inserted = load_weather_data(conn, transformed_df)
        if inserted is None:
            print("Load that bai!")
            exit(1)

        # Verify
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM weather_fact")
            total = cur.fetchone()[0]
        print(f"\nTong records trong weather_fact: {total}")
        print("Pipeline completed successfully!")

    finally:
        conn.close()
        print("DB connection closed.")
