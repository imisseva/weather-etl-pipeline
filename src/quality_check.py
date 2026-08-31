from datetime import date
from typing import Optional, Dict, Any
import psycopg2

from config.settings import LOCATIONS
from src.logger import get_logger

logger = get_logger(__name__)


def check_completeness(conn, target_date_id: int) -> bool:
    """
    Kiem tra 1: Do day du (Completeness Check)
    Kiem tra xem ngay target_date_id co du 63 tinh thanh trong weather_fact khong.
    """
    query = """
        SELECT COUNT(DISTINCT location_id)
        FROM weather_fact
        WHERE date_id = %s
    """
    with conn.cursor() as cur:
        cur.execute(query, (target_date_id,))
        count = cur.fetchone()[0]

    expected = len(LOCATIONS)  # 63 tinh
    if count == expected:
        logger.info(f"  [CHECK 1/4] Completeness OK: Du {count}/{expected} tinh thanh")
        return True
    else:
        logger.error(f"  [CHECK 1/4] Completeness FAIL: Chi co {count}/{expected} tinh thanh!")
        return False


def check_nulls(conn, target_date_id: int) -> bool:
    """
    Kiem tra 2: Kiem tra du lieu rong (Null Check)
    Kiem tra xem cac cot quan trong co bi dinh NULL bat thuong khong.
    """
    query = """
        SELECT COUNT(*)
        FROM weather_fact
        WHERE date_id = %s
          AND (temperature IS NULL OR humidity IS NULL OR wind_speed IS NULL OR location_id IS NULL)
    """
    with conn.cursor() as cur:
        cur.execute(query, (target_date_id,))
        null_count = cur.fetchone()[0]

    if null_count == 0:
        logger.info(f"  [CHECK 2/4] Null Check OK: 0 ban ghi bi dinh NULL bat thuong")
        return True
    else:
        logger.error(f"  [CHECK 2/4] Null Check FAIL: Co {null_count} ban ghi bi dinh NULL!")
        return False


def check_uniqueness(conn, target_date_id: int) -> bool:
    """
    Kiem tra 3: Kiem tra trung lap (Uniqueness Check)
    Kiem tra xem co cap (location_id, date_id) nao bi trung lap khong.
    """
    query = """
        SELECT location_id, COUNT(*)
        FROM weather_fact
        WHERE date_id = %s
        GROUP BY location_id
        HAVING COUNT(*) > 1
    """
    with conn.cursor() as cur:
        cur.execute(query, (target_date_id,))
        duplicates = cur.fetchall()

    if not duplicates:
        logger.info(f"  [CHECK 3/4] Uniqueness OK: 0 cap location_id + date_id bi trung lap")
        return True
    else:
        logger.error(f"  [CHECK 3/4] Uniqueness FAIL: Co {len(duplicates)} location bi trung lap record!")
        return False


def check_value_ranges(conn, target_date_id: int) -> bool:
    """
    Kiem tra 4: Kiem tra mien gia tri (Range Check)
    Kiem tra xem co gia tri nhiet do, do am, gio nao bat thuong trong DB khong.
    """
    query = """
        SELECT COUNT(*)
        FROM weather_fact
        WHERE date_id = %s
          AND (
            temperature < -10 OR temperature > 60 OR
            humidity < 0 OR humidity > 100 OR
            wind_speed < 0 OR wind_speed > 200
          )
    """
    with conn.cursor() as cur:
        cur.execute(query, (target_date_id,))
        invalid_count = cur.fetchone()[0]

    if invalid_count == 0:
        logger.info(f"  [CHECK 4/4] Value Range OK: Tat ca gia tri deu hop le")
        return True
    else:
        logger.error(f"  [CHECK 4/4] Value Range FAIL: Co {invalid_count} ban ghi ngoai khoang hop le!")
        return False


def run_quality_checks(conn, target_date_id: Optional[int] = None) -> bool:
    """
    Hieu chinh va chay toan bo 4 bai test Post-Load Data Quality Check.

    Args:
        conn: psycopg2 connection toi Database
        target_date_id: ID cua ngay can test trong dim_time.
                        Neu None, tu dong lay date_id moi nhat trong weather_fact.

    Returns:
        True neu tat ca 4 bai test deu PASS, False neu co bat ky bai test nao FAIL.
    """
    logger.info("==================================================")
    logger.info("BAT DAU CHAY POST-LOAD DATA QUALITY CHECKS")

    if conn is None:
        logger.error("Quality Check THAT BAI: DB Connection bang None")
        return False

    # Neu target_date_id bang None, lay date_id moi nhat trong weather_fact
    if target_date_id is None:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(date_id) FROM weather_fact")
            row = cur.fetchone()
            target_date_id = row[0] if row else None

    if target_date_id is None:
        logger.error("Quality Check THAT BAI: Khong tim thay date_id nao trong weather_fact")
        return False

    logger.info(f"Kiem tra chat luong du lieu cho date_id = {target_date_id}")
    logger.info("==================================================")

    c1 = check_completeness(conn, target_date_id)
    c2 = check_nulls(conn, target_date_id)
    c3 = check_uniqueness(conn, target_date_id)
    c4 = check_value_ranges(conn, target_date_id)

    all_passed = c1 and c2 and c3 and c4

    logger.info("==================================================")
    if all_passed:
        logger.info("POST-LOAD QUALITY CHECKS: PASS 100%")
    else:
        logger.error("POST-LOAD QUALITY CHECKS: FAIL - Vui long kiem tra lai du lieu!")
    logger.info("==================================================")

    return all_passed


if __name__ == "__main__":
    from src.load import get_connection

    conn = get_connection()
    try:
        success = run_quality_checks(conn)
        print("Ket qua Data Quality Check:", "PASS" if success else "FAIL")
    finally:
        conn.close()
