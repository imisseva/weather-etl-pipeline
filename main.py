import sys
from datetime import datetime

from src.extract import extract_all_locations
from src.transform import transform_weather_data
from src.load import load_to_database
from src.logger import get_logger

logger = get_logger("main")


def run_pipeline() -> bool:
    """
    Điều phối toàn bộ ETL pipeline:
    1. Extract   : Gọi API Open-Meteo lấy dữ liệu 63 tỉnh thành.
    2. Transform : Gán timezone UTC+7, validate, loại bỏ trùng, map location_id.
    3. Load      : Seed dim_locations và load data vào weather_fact trên Supabase.

    Returns:
        True nếu pipeline hoàn thành công, False nếu có lỗi.
    """
    start_time = datetime.now()
    logger.info("==================================================")
    logger.info("BAT DAU CHAY WEATHER ETL PIPELINE")
    logger.info(f"Thoi gian bat dau: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("==================================================")

    # --------------------------------------------------
    # Bước 1: EXTRACT
    # --------------------------------------------------
    logger.info("[BUOC 1/3] LAY DU LIEU (EXTRACT)")
    raw_df = extract_all_locations()

    if raw_df is None or raw_df.empty:
        logger.error("Pipeline THAT BAI: Buoc Extract khong lay duoc du lieu.")
        return False

    logger.info(f"Extract thanh cong: Lay duoc {len(raw_df)} ban ghi.")

    # --------------------------------------------------
    # Bước 2: TRANSFORM
    # --------------------------------------------------
    logger.info("[BUOC 2/3] XU LY DU LIEU (TRANSFORM)")
    transformed_df = transform_weather_data(raw_df)

    if transformed_df is None or transformed_df.empty:
        logger.error("Pipeline THAT BAI: Buoc Transform that bai.")
        return False

    logger.info(f"Transform thanh cong: Da lam sach {len(transformed_df)} ban ghi.")

    # --------------------------------------------------
    # Bước 3: LOAD
    # --------------------------------------------------
    logger.info("[BUOC 3/3] LUU DU LIEU VAO DATABASE (LOAD)")
    success = load_to_database(transformed_df)

    if not success:
        logger.error("Pipeline THAT BAI: Buoc Load database that bai.")
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


if __name__ == "__main__":
    is_success = run_pipeline()
    if not is_success:
        sys.exit(1)
