import requests
import pandas as pd
from datetime import datetime
from typing import Optional

from config.settings import OPEN_METEO_URL, LOCATIONS, HOURLY_VARIABLES
from src.logger import get_logger

logger = get_logger(__name__)


def fetch_weather_for_location(location: dict) -> Optional[pd.DataFrame]:
    """
    Gọi Open-Meteo API để lấy dữ liệu thời tiết theo giờ cho 1 địa điểm.

    Args:
        location: dict chứa 'name', 'latitude', 'longitude'

    Returns:
        DataFrame với các cột: location_name, temperature, humidity,
        wind_speed, recorded_at. Trả về None nếu có lỗi.
    """
    name = location["name"]
    logger.info(f"Đang fetch data cho: {name}")

    params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": "Asia/Bangkok",
        "past_days": 1,
        "forecast_days": 1,
    }

    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

    except requests.exceptions.Timeout:
        logger.error(f"[{name}] Request timeout sau 10 giây")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"[{name}] Không thể kết nối tới Open-Meteo API")
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(f"[{name}] HTTP error: {e}")
        return None

    # ──────────────────────────────────────────
    # Parse response → DataFrame
    # ──────────────────────────────────────────
    try:
        hourly = data["hourly"]

        df = pd.DataFrame({
            "location_name": name,
            "temperature":   hourly["temperature_2m"],
            "humidity":      hourly["relative_humidity_2m"],
            "wind_speed":    hourly["wind_speed_10m"],
            "recorded_at":   pd.to_datetime(hourly["time"]),
        })

        # Bỏ các hàng có giá trị null ở các cột quan trọng
        before = len(df)
        df.dropna(subset=["temperature", "humidity", "wind_speed", "recorded_at"], inplace=True)
        dropped = before - len(df)

        if dropped > 0:
            logger.warning(f"[{name}] Bỏ {dropped} hàng do thiếu dữ liệu")

        logger.info(f"[{name}] Lấy thành công {len(df)} bản ghi")
        return df

    except KeyError as e:
        logger.error(f"[{name}] Thiếu field trong response API: {e}")
        return None


def extract_all_locations() -> Optional[pd.DataFrame]:
    """
    Lấy dữ liệu thời tiết cho TẤT CẢ locations trong settings.

    Returns:
        DataFrame gộp của tất cả locations, hoặc None nếu không có data.
    """
    logger.info(f"Bắt đầu extract | {len(LOCATIONS)} địa điểm: "
                f"{[loc['name'] for loc in LOCATIONS]}")

    all_frames = []

    for location in LOCATIONS:
        df = fetch_weather_for_location(location)
        if df is not None and not df.empty:
            all_frames.append(df)

    if not all_frames:
        logger.error("Không lấy được data từ bất kỳ địa điểm nào!")
        return None

    result = pd.concat(all_frames, ignore_index=True)

    logger.info(
        f"Extract hoàn tất | Tổng: {len(result)} bản ghi "
        f"từ {result['location_name'].nunique()} địa điểm"
    )
    return result


if __name__ == "__main__":
    # Chạy thử trực tiếp: python -m src.extract.weather_api
    df = extract_all_locations()
    if df is not None:
        print("\n--- Sample data (5 dòng đầu) ---")
        print(df.head())
        print(f"\nShape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        print(f"\nKhoảng thời gian: {df['recorded_at'].min()} → {df['recorded_at'].max()}")
