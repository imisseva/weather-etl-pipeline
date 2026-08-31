import sys
from datetime import datetime

from src.extract import extract_all_locations
from src.transform import transform_weather_data
from src.load import get_connection, seed_dim_location, load_weather_data
from src.quality_check import run_quality_checks
from src.logger import get_logger

logger = get_logger("main")


def run_pipeline() -> bool:
    """
    Dieu phoi toan bo ETL pipeline theo mo hinh Star Schema:
    1. Extract        : Goi API Open-Meteo lay du lieu thoi tiet 63 tinh thanh.
    2. Connect        : Ket noi toi Supabase PostgreSQL.
    3. Transform      : Gan timezone UTC+7, ep kieu, validate, aggregate thanh daily records,
                        map dimension (location_id, date_id, condition_id).
    4. Load           : Seed dim_location va load daily records vao weather_fact.
    5. Quality Check  : Kiem tra chat luong du lieu trong DB (Completeness, Nulls, Uniqueness, Ranges).

    Returns:
        True neu pipeline chay thanh cong, False neu co loi.
    """
    start_time = datetime.now()
    logger.info("==================================================")
    logger.info("BAT DAU CHAY WEATHER ETL PIPELINE")
    logger.info(f"Thoi gian bat dau: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("==================================================")

    conn = None
    try:
        # --------------------------------------------------
        # Buoc 1: EXTRACT
        # --------------------------------------------------
        logger.info("[BUOC 1/4] LAY DU LIEU (EXTRACT)")
        raw_df = extract_all_locations()

        if raw_df is None or raw_df.empty:
            logger.error("Pipeline THAT BAI: Buoc Extract khong lay duoc du lieu.")
            return False

        logger.info(f"Extract thanh cong: Lay duoc {len(raw_df)} ban ghi theo gio.")

        # --------------------------------------------------
        # Ket noi Database
        # --------------------------------------------------
        logger.info("Ket noi toi Database...")
        conn = get_connection()

        # --------------------------------------------------
        # Buoc 2: TRANSFORM
        # --------------------------------------------------
        logger.info("[BUOC 2/4] XU LY DU LIEU (TRANSFORM)")
        transformed_df = transform_weather_data(raw_df, conn)

        if transformed_df is None or transformed_df.empty:
            logger.error("Pipeline THAT BAI: Buoc Transform that bai.")
            return False

        logger.info(f"Transform thanh cong: Da gom thanh {len(transformed_df)} ban ghi theo ngay.")

        # --------------------------------------------------
        # Buoc 3: LOAD
        # --------------------------------------------------
        logger.info("[BUOC 3/4] LUU DU LIEU VAO DATABASE (LOAD)")

        # 3.1 Seed dim_location (neu chua co)
        if not seed_dim_location(conn):
            logger.error("Pipeline THAT BAI: Seed dim_location that bai.")
            return False

        # 3.2 Insert vao weather_fact
        inserted = load_weather_data(conn, transformed_df)
        if inserted is None:
            logger.error("Pipeline THAT BAI: Load weather_fact that bai.")
            return False

        logger.info(f"Load thanh cong: Da ghi {inserted} ban ghi vao weather_fact.")

        # --------------------------------------------------
        # Buoc 4: DATA QUALITY CHECK
        # --------------------------------------------------
        logger.info("[BUOC 4/4] KIEM TRA CHAT LUONG DU LIEU (QUALITY CHECK)")
        target_date_id = int(transformed_df["date_id"].iloc[0])
        qc_passed = run_quality_checks(conn, target_date_id=target_date_id)

        if not qc_passed:
            logger.error("Pipeline THAT BAI: Data Quality Check khong dat yeu cau!")
            return False

        # --------------------------------------------------
        # HOAN THANH PIPELINE
        # --------------------------------------------------
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("==================================================")
        logger.info("PIPELINE CHAY THANH CONG HOAN TOAN")
        logger.info(f"Thoi gian ket thuc: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Tong thoi gian    : {duration:.2f} giay")
        logger.info("==================================================")

        return True

    except Exception as e:
        logger.error(f"Pipeline THAT BAI do loi khong mong muon: {e}")
        return False

    finally:
        if conn is not None:
            conn.close()
            logger.info("Da dong ket noi Database.")


if __name__ == "__main__":
    is_success = run_pipeline()
    if not is_success:
        sys.exit(1)
