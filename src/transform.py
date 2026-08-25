import pandas as pd
from datetime import timezone, timedelta
from typing import Optional

from config.settings import LOCATIONS
from src.logger import get_logger

logger = get_logger(__name__)

# Timezone Việt Nam: UTC+7
VN_TIMEZONE = timezone(timedelta(hours=7))

# Giới hạn hợp lệ cho từng field
VALID_RANGES = {
    "temperature": (-10, 60),     # °C — VN không dưới -10 hoặc trên 60
    "humidity":    (0, 100),      # % — theo định nghĩa
    "wind_speed":  (0, 200),     # km/h — trên 200 là bão cực mạnh, rất hiếm
}

# Map location_name → location_id (thứ tự trong LOCATIONS = thứ tự ID trong DB)
LOCATION_NAME_TO_ID = {loc["name"]: idx + 1 for idx, loc in enumerate(LOCATIONS)}


def transform_weather_data(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Transform raw weather data từ Extract.

    Bước 1: Gán timezone UTC+7 cho recorded_at
    Bước 2: Ép kiểu humidity → int
    Bước 3: Validate range (loại bỏ record bất thường)
    Bước 4: Loại bỏ duplicate (location + recorded_at)
    Bước 5: Map location_name → location_id

    Args:
        df: DataFrame raw từ extract_all_locations()

    Returns:
        DataFrame sẵn sàng load vào weather_fact, hoặc None nếu rỗng.
    """
    if df is None or df.empty:
        logger.error("Transform: input DataFrame rong hoac None")
        return None

    logger.info(f"=== START TRANSFORM | {len(df)} records ===")
    df = df.copy()

    # ──────────────────────────────────────────
    # Bước 1: Gán timezone UTC+7 cho recorded_at
    # ──────────────────────────────────────────
    df["recorded_at"] = df["recorded_at"].dt.tz_localize(VN_TIMEZONE)
    logger.info(f"  [1] Timezone: naive -> UTC+7")

    # ──────────────────────────────────────────
    # Bước 2: Ép kiểu humidity → int
    # Schema DB: humidity INT NOT NULL
    # ──────────────────────────────────────────
    df["humidity"] = df["humidity"].astype(int)
    logger.info(f"  [2] Humidity: ep kieu -> int")

    # ──────────────────────────────────────────
    # Bước 3: Validate range — loại bỏ record bất thường
    # ──────────────────────────────────────────
    before = len(df)

    for col, (min_val, max_val) in VALID_RANGES.items():
        invalid = (df[col] < min_val) | (df[col] > max_val)
        count = invalid.sum()
        if count > 0:
            logger.warning(
                f"  [3] {col}: {count} records ngoai range "
                f"[{min_val}, {max_val}] — da loai bo"
            )
            df = df[~invalid]

    dropped = before - len(df)
    if dropped > 0:
        logger.warning(f"  [3] Validate: loai {dropped}/{before} records bat thuong")
    else:
        logger.info(f"  [3] Validate: tat ca {before} records hop le")

    # ──────────────────────────────────────────
    # Bước 4: Loại bỏ duplicate (location_name + recorded_at)
    # Phòng trường hợp pipeline chạy 2 lần cùng ngày
    # ──────────────────────────────────────────
    before = len(df)
    df = df.drop_duplicates(subset=["location_name", "recorded_at"], keep="first")
    dup_removed = before - len(df)

    if dup_removed > 0:
        logger.warning(f"  [4] Duplicate: loai {dup_removed} records trung")
    else:
        logger.info(f"  [4] Duplicate: 0 records trung")

    # ──────────────────────────────────────────
    # Bước 5: Map location_name → location_id
    # Dựa vào thứ tự LOCATIONS trong settings.py
    # ──────────────────────────────────────────
    df["location_id"] = df["location_name"].map(LOCATION_NAME_TO_ID)

    # Kiểm tra có location nào không map được không
    unmapped = df["location_id"].isnull().sum()
    if unmapped > 0:
        unmapped_names = df[df["location_id"].isnull()]["location_name"].unique()
        logger.error(f"  [5] {unmapped} records khong map duoc location_id: {unmapped_names}")
        df = df.dropna(subset=["location_id"])

    df["location_id"] = df["location_id"].astype(int)

    # Bỏ cột location_name, giữ location_id (khớp schema weather_fact)
    df = df.drop(columns=["location_name"])

    # Sắp xếp lại cột đúng thứ tự schema weather_fact
    df = df[["location_id", "temperature", "humidity", "wind_speed", "recorded_at"]]

    logger.info(f"=== TRANSFORM DONE | {len(df)} records | "
                f"{df['location_id'].nunique()} tinh ===")
    return df


if __name__ == "__main__":
    from src.extract import extract_all_locations

    print("Extracting...")
    raw_df = extract_all_locations()

    if raw_df is not None:
        print(f"\n--- BEFORE TRANSFORM ---")
        print(f"Columns : {raw_df.columns.tolist()}")
        print(f"Shape   : {raw_df.shape}")
        print(f"Timezone: {raw_df['recorded_at'].dt.tz}")
        print(raw_df.head(3))

        transformed = transform_weather_data(raw_df)

        print(f"\n--- AFTER TRANSFORM ---")
        print(f"Columns : {transformed.columns.tolist()}")
        print(f"Shape   : {transformed.shape}")
        print(f"Timezone: {transformed['recorded_at'].dt.tz}")
        print(transformed.head(3))
        print(f"\nlocation_id range: {transformed['location_id'].min()} -> {transformed['location_id'].max()}")
