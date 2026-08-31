import pandas as pd
from datetime import timezone, timedelta
from typing import Optional

import psycopg2

from config.settings import LOCATIONS
from src.logger import get_logger

logger = get_logger(__name__)

# Timezone Việt Nam: UTC+7
VN_TIMEZONE = timezone(timedelta(hours=7))

# Giới hạn hợp lệ cho từng field
VALID_RANGES = {
    "temperature": (-10, 60),
    "humidity":    (0, 100),
    "wind_speed":  (0, 200),
}

# Map location_name → location_id (dựa vào thứ tự LOCATIONS trong settings.py)
LOCATION_NAME_TO_ID = {loc["name"]: idx + 1 for idx, loc in enumerate(LOCATIONS)}


def _query_date_id_map(conn) -> dict:
    """
    Query toàn bộ dim_time, trả về dict: date (python date) → date_id.
    Chỉ 1 query duy nhất, rất nhanh.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT date, date_id FROM dim_time")
        rows = cur.fetchall()
    return {row[0]: row[1] for row in rows}   # {datetime.date(2026,8,30): 2435, ...}


def _query_condition_id_map(conn) -> dict:
    """
    Query toàn bộ dim_weather_condition, trả về dict: weather_code → condition_id.
    Chỉ 1 query duy nhất.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT weather_code, condition_id FROM dim_weather_condition")
        rows = cur.fetchall()
    return {row[0]: row[1] for row in rows}   # {0: 1, 1: 2, 2: 3, ...}


def transform_weather_data(df: pd.DataFrame, conn: psycopg2.extensions.connection) -> Optional[pd.DataFrame]:
    """
    Transform raw hourly weather data → daily aggregated records
    sẵn sàng insert vào weather_fact (Star Schema).

    Pipeline Transform:
        Bước 1: Gán timezone UTC+7 cho recorded_at
        Bước 2: Ép kiểu humidity → int
        Bước 3: Validate range (loại record bất thường)
        Bước 4: Loại bỏ duplicate (location + recorded_at)
        Bước 5: Aggregate hourly → daily (mean temp/humidity/wind, mode weather_code)
        Bước 6: Map location_name → location_id
        Bước 7: Map date → date_id (query dim_time)
        Bước 8: Map weather_code → condition_id (query dim_weather_condition)

    Args:
        df:   DataFrame raw từ extract_all_locations()
              Columns: location_name, temperature, humidity, wind_speed, weather_code, recorded_at
        conn: psycopg2 connection (dùng để query dim_time và dim_weather_condition)

    Returns:
        DataFrame sẵn sàng load vào weather_fact, hoặc None nếu lỗi.
        Columns: location_id, date_id, condition_id, temperature, humidity, wind_speed, recorded_at
    """
    if df is None or df.empty:
        logger.error("Transform: input DataFrame rong hoac None")
        return None

    logger.info(f"=== START TRANSFORM | {len(df)} hourly records ===")
    df = df.copy()

    # ──────────────────────────────────────────
    # Bước 1: Gán timezone UTC+7 cho recorded_at
    # EDA xác nhận Open-Meteo trả giờ theo Asia/Bangkok = UTC+7
    # → tz_localize: KHÔNG đổi giá trị giờ, chỉ đánh dấu múi giờ
    # ──────────────────────────────────────────
    df["recorded_at"] = df["recorded_at"].dt.tz_localize(VN_TIMEZONE)
    logger.info(f"  [1] Timezone: naive -> UTC+7")

    # ──────────────────────────────────────────
    # Bước 2: Ép kiểu humidity → int
    # API trả về float (ví dụ 86.0), schema DB yêu cầu INT
    # ──────────────────────────────────────────
    df["humidity"] = df["humidity"].astype(int)
    logger.info(f"  [2] Humidity: float -> int")

    # ──────────────────────────────────────────
    # Bước 3: Validate range
    # Loại bỏ record có giá trị bất thường trước khi aggregate
    # ──────────────────────────────────────────
    before = len(df)
    for col, (min_val, max_val) in VALID_RANGES.items():
        invalid = (df[col] < min_val) | (df[col] > max_val)
        if invalid.sum() > 0:
            logger.warning(f"  [3] {col}: loai {invalid.sum()} records ngoai range [{min_val}, {max_val}]")
            df = df[~invalid]

    dropped = before - len(df)
    if dropped > 0:
        logger.warning(f"  [3] Validate: da loai {dropped} records bat thuong")
    else:
        logger.info(f"  [3] Validate: tat ca {before} hourly records hop le")

    # ──────────────────────────────────────────
    # Bước 4: Loại bỏ duplicate theo giờ
    # Phòng pipeline chạy 2 lần / ngày
    # ──────────────────────────────────────────
    before = len(df)
    df = df.drop_duplicates(subset=["location_name", "recorded_at"], keep="first")
    dup_removed = before - len(df)
    if dup_removed > 0:
        logger.warning(f"  [4] Duplicate: loai {dup_removed} hourly records trung")
    else:
        logger.info(f"  [4] Duplicate: 0 records trung")

    # ──────────────────────────────────────────
    # Bước 5: Aggregate hourly → daily
    # Schema mới: UNIQUE(location_id, date_id) → 1 record/tỉnh/ngày
    # - temperature: trung bình cả ngày
    # - humidity   : trung bình cả ngày
    # - wind_speed : trung bình cả ngày
    # - weather_code: mode (mã thời tiết xuất hiện nhiều nhất trong ngày)
    # - recorded_at : giờ đầu tiên của ngày (00:00)
    # ──────────────────────────────────────────
    df["date"] = df["recorded_at"].dt.date  # tách cột date để group

    daily_df = df.groupby(["location_name", "date"]).agg(
        temperature  = ("temperature",  "mean"),
        humidity     = ("humidity",     "mean"),
        wind_speed   = ("wind_speed",   "mean"),
        weather_code = ("weather_code", lambda x: x.mode()[0]),  # mode: phổ biến nhất
        recorded_at  = ("recorded_at",  "min"),                   # 00:00 của ngày đó
    ).reset_index()

    # Round sau khi aggregate
    daily_df["temperature"] = daily_df["temperature"].round(1)
    daily_df["humidity"]    = daily_df["humidity"].round(0).astype(int)
    daily_df["wind_speed"]  = daily_df["wind_speed"].round(1)
    daily_df["weather_code"]= daily_df["weather_code"].astype(int)

    logger.info(f"  [5] Aggregate: {len(df)} hourly -> {len(daily_df)} daily records")

    # ──────────────────────────────────────────
    # Bước 6: Map location_name → location_id
    # Dựa vào thứ tự LOCATIONS trong settings.py (63 tỉnh cố định)
    # ──────────────────────────────────────────
    daily_df["location_id"] = daily_df["location_name"].map(LOCATION_NAME_TO_ID)
    unmapped = daily_df["location_id"].isnull().sum()
    if unmapped > 0:
        bad_names = daily_df[daily_df["location_id"].isnull()]["location_name"].unique()
        logger.error(f"  [6] {unmapped} records khong map duoc location_id: {bad_names}")
        daily_df = daily_df.dropna(subset=["location_id"])
    daily_df["location_id"] = daily_df["location_id"].astype(int)
    logger.info(f"  [6] location_name -> location_id: {daily_df['location_id'].nunique()} tinh")

    # ──────────────────────────────────────────
    # Bước 7: Map date → date_id
    # Query dim_time 1 lần, build dict, rồi map cả DataFrame
    # ──────────────────────────────────────────
    date_id_map = _query_date_id_map(conn)
    daily_df["date_id"] = daily_df["date"].map(date_id_map)

    unmapped = daily_df["date_id"].isnull().sum()
    if unmapped > 0:
        bad_dates = daily_df[daily_df["date_id"].isnull()]["date"].unique()
        logger.error(f"  [7] {unmapped} records khong tim thay date_id: {bad_dates}")
        daily_df = daily_df.dropna(subset=["date_id"])
    daily_df["date_id"] = daily_df["date_id"].astype(int)
    logger.info(f"  [7] date -> date_id: OK ({len(date_id_map)} dates trong dim_time)")

    # ──────────────────────────────────────────
    # Bước 8: Map weather_code → condition_id
    # Query dim_weather_condition 1 lần, build dict, rồi map cả DataFrame
    # Nếu weather_code không có trong dim (mã hiếm) → condition_id = None (nullable trong schema)
    # ──────────────────────────────────────────
    condition_id_map = _query_condition_id_map(conn)
    daily_df["condition_id"] = daily_df["weather_code"].map(condition_id_map)

    unmapped = daily_df["condition_id"].isnull().sum()
    if unmapped > 0:
        unknown_codes = daily_df[daily_df["condition_id"].isnull()]["weather_code"].unique()
        logger.warning(f"  [8] {unmapped} records co weather_code chua co trong dim: {unknown_codes}")
        # Không drop — condition_id là nullable trong schema (FK không bắt buộc)

    mapped_count = daily_df["condition_id"].notna().sum()
    logger.info(f"  [8] weather_code -> condition_id: {mapped_count}/{len(daily_df)} records map duoc")

    # Sắp xếp lại cột đúng thứ tự schema weather_fact
    daily_df = daily_df[[
        "location_id",
        "date_id",
        "condition_id",
        "temperature",
        "humidity",
        "wind_speed",
        "recorded_at",
    ]]

    logger.info(
        f"=== TRANSFORM DONE | {len(daily_df)} daily records | "
        f"{daily_df['location_id'].nunique()} tinh ==="
    )
    return daily_df


if __name__ == "__main__":
    from src.extract import extract_all_locations
    from src.load import get_connection

    print("Extracting...")
    raw_df = extract_all_locations()

    if raw_df is not None:
        print(f"\n--- BEFORE TRANSFORM ---")
        print(f"Shape  : {raw_df.shape}  (hourly)")
        print(f"Columns: {raw_df.columns.tolist()}")
        print(raw_df.head(3).to_string())

        print("\nConnecting to DB...")
        conn = get_connection()
        try:
            transformed = transform_weather_data(raw_df, conn)
            if transformed is not None:
                print(f"\n--- AFTER TRANSFORM ---")
                print(f"Shape  : {transformed.shape}  (daily aggregate)")
                print(f"Columns: {transformed.columns.tolist()}")
                print(transformed.head(3).to_string())
                print(f"\nlocation_id : {transformed['location_id'].min()} -> {transformed['location_id'].max()}")
                print(f"date_id     : {transformed['date_id'].unique()}")
                print(f"condition_id unique: {sorted(transformed['condition_id'].dropna().astype(int).unique().tolist())}")
        finally:
            conn.close()
