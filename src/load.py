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


def seed_dim_locations(conn) -> bool:
    """
    Insert 63 tỉnh thành vào dim_locations nếu chưa có.
    Dùng ON CONFLICT DO NOTHING để không bị lỗi duplicate.
    Retry khi gặp OperationalError (connection drop).

    Args:
        conn: psycopg2 connection

    Returns:
        True nếu thành công, False nếu có lỗi
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Seeding dim_locations...")

            data = [
                (loc["name"], loc["latitude"], loc["longitude"])
                for loc in LOCATIONS
            ]

            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    INSERT INTO dim_locations (location_name, latitude, longitude)
                    VALUES %s
                    ON CONFLICT (location_name) DO NOTHING
                    """,
                    data,
                )
            conn.commit()

            # Kiểm tra số lượng trong DB
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM dim_locations")
                count = cur.fetchone()[0]

            logger.info(f"  dim_locations: {count} locations in DB")
            return True

        except psycopg2.OperationalError as e:
            conn.rollback()
            if attempt < MAX_RETRIES:
                delay = 2 ** (attempt - 1)
                logger.warning(f"DB error seeding locations (attempt {attempt}/{MAX_RETRIES}): {e}")
                logger.info(f"Retry sau {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Failed to seed locations after {MAX_RETRIES} attempts: {e}")
                return False

        except psycopg2.IntegrityError as e:
            # Data sai → retry không giúp được
            logger.error(f"Integrity error seeding locations — khong retry: {e}")
            conn.rollback()
            return False

        except Exception as e:
            # Bug code → retry không giúp được
            logger.error(f"Unexpected error seeding locations — khong retry: {e}")
            conn.rollback()
            return False


def load_weather_data(conn, df: pd.DataFrame) -> Optional[int]:
    """
    Load weather data đã transform vào weather_fact.
    Retry khi gặp OperationalError (connection drop).

    Dùng ON CONFLICT (location_id, recorded_at) DO NOTHING
    để tránh duplicate khi pipeline chạy 2 lần cùng ngày.

    Args:
        conn: psycopg2 connection
        df:   DataFrame đã transform (location_id, temperature,
              humidity, wind_speed, recorded_at)

    Returns:
        Số records được insert thực tế. Trả về None nếu có lỗi.
    """
    if df is None or df.empty:
        logger.error("Load: DataFrame rong hoac None")
        return None

    records = list(df.itertuples(index=False, name=None))

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"=== START LOAD | {len(df)} records ===")

            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    INSERT INTO weather_fact
                        (location_id, temperature, humidity, wind_speed, recorded_at)
                    VALUES %s
                    ON CONFLICT (location_id, recorded_at) DO NOTHING
                    """,
                    records,
                )
                inserted = cur.rowcount

            conn.commit()

            skipped = len(df) - inserted
            logger.info(f"  Inserted : {inserted} records")
            if skipped > 0:
                logger.info(f"  Skipped  : {skipped} records (already exist in DB)")
            logger.info(f"=== LOAD DONE | {inserted}/{len(df)} records ===")

            return inserted

        except psycopg2.OperationalError as e:
            conn.rollback()
            if attempt < MAX_RETRIES:
                delay = 2 ** (attempt - 1)
                logger.warning(f"DB error loading data (attempt {attempt}/{MAX_RETRIES}): {e}")
                logger.info(f"Retry sau {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Failed to load data after {MAX_RETRIES} attempts: {e}")
                return None

        except psycopg2.IntegrityError as e:
            logger.error(f"Integrity error loading data — khong retry: {e}")
            conn.rollback()
            return None

        except Exception as e:
            logger.error(f"Unexpected error loading data — khong retry: {e}")
            conn.rollback()
            return None


def load_to_database(df: pd.DataFrame) -> bool:
    """
    Main function: Seed dim_locations + Load weather_fact.
    Handles connection + error handling + cleanup.

    Args:
        df: DataFrame đã transform từ transform_weather_data()

    Returns:
        True nếu load thành công, False nếu có lỗi.
    """
    conn = None
    try:
        conn = get_connection()

        if not seed_dim_locations(conn):
            return False

        inserted = load_weather_data(conn, df)
        if inserted is None:
            return False

        logger.info(f"Load phase completed: {inserted} records inserted")
        return True

    except Exception as e:
        logger.error(f"Unexpected error in load_to_database: {e}")
        return False

    finally:
        if conn is not None:
            conn.close()
            logger.info("DB connection closed.")


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
        print("Extract failed!")
        exit(1)
    print(f"Extracted: {len(raw_df)} records")

    # Transform
    print("\n[2] Transforming...")
    transformed_df = transform_weather_data(raw_df)
    if transformed_df is None:
        print("Transform failed!")
        exit(1)
    print(f"Transformed: {len(transformed_df)} records")

    # Load
    print("\n[3] Loading to Supabase...")
    success = load_to_database(transformed_df)

    if success:
        print("\nPipeline completed successfully!")
    else:
        print("\nPipeline failed!")
        exit(1)
