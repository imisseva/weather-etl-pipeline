import time
import requests
import pandas as pd
from typing import Optional

from config.settings import OPEN_METEO_URL, LOCATIONS, HOURLY_VARIABLES
from src.logger import get_logger

logger = get_logger(__name__)


def fetch_weather_for_location(location: dict) -> Optional[pd.DataFrame]:
    """
    Gọi Open-Meteo API lấy dữ liệu thời tiết theo giờ cho 1 địa điểm.

    Mỗi lần chạy lấy 24 bản ghi (24 giờ qua).
    Cronjob chạy hàng ngày → DB tích lũy 24 bản ghi/tỉnh/ngày.

    Args:
        location: dict với 'name', 'latitude', 'longitude'

    Returns:
        DataFrame gồm: location_name, temperature, humidity,
        wind_speed, weather_code, recorded_at. Hoặc None nếu lỗi.
    """
    name = location["name"]
    logger.info(f"Fetching: {name}")

    params = {
        "latitude":      location["latitude"],
        "longitude":     location["longitude"],
        "hourly":        ",".join(HOURLY_VARIABLES),
        "timezone":      "Asia/Bangkok",   # UTC+7
        "past_days":     1,                # 24h qua
        "forecast_days": 0,                # không lấy dự báo tương lai
    }

    # ──────────────────────────────────────────
    # Retry với exponential backoff: 3 lần, delay 1s → 2s → 4s
    # ──────────────────────────────────────────
    MAX_RETRIES = 3
    data = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(OPEN_METEO_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            break  # thành công → thoát vòng lặp

        except requests.exceptions.Timeout:
            logger.warning(f"[{name}] Timeout (attempt {attempt}/{MAX_RETRIES})")

        except requests.exceptions.ConnectionError:
            logger.warning(f"[{name}] Connection error (attempt {attempt}/{MAX_RETRIES})")

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            if isinstance(status, int) and status < 500:
                # Lỗi 4xx: client error, retry không giúp được gì
                logger.error(f"[{name}] HTTP {status} - không retry: {e}")
                return None
            logger.warning(f"[{name}] HTTP {status} error (attempt {attempt}/{MAX_RETRIES})")

        # Nếu chưa phải lần cuối → đợi rồi thử lại
        if attempt < MAX_RETRIES:
            delay = 2 ** (attempt - 1)  # 1s, 2s, 4s
            logger.info(f"[{name}] Retry sau {delay}s...")
            time.sleep(delay)
        else:
            logger.error(f"[{name}] Tất cả {MAX_RETRIES} lần thử đều thất bại - bỏ qua")
            return None

    if data is None:
        return None

    # ──────────────────────────────────────────
    # Parse hourly response → DataFrame
    # ──────────────────────────────────────────
    try:
        hourly = data["hourly"]

        df = pd.DataFrame({
            "location_name": name,
            "temperature":   hourly["temperature_2m"],
            "humidity":      hourly["relative_humidity_2m"],
            "wind_speed":    hourly["wind_speed_10m"],
            "weather_code":  hourly["weather_code"],     # mã WMO → map sang dim_weather_condition
            "recorded_at":   pd.to_datetime(hourly["time"]),
        })

        # Bỏ các hàng thiếu dữ liệu quan trọng
        before = len(df)
        df.dropna(
            subset=["temperature", "humidity", "wind_speed", "weather_code", "recorded_at"],
            inplace=True,
        )
        dropped = before - len(df)
        if dropped > 0:
            logger.warning(f"[{name}] Dropped {dropped} rows do thieu data")

        logger.info(f"[{name}] OK - {len(df)} records")
        return df

    except KeyError as e:
        logger.error(f"[{name}] Missing field: {e}")
        logger.error(f"[{name}] API tra ve keys : {list(data.get('hourly', {}).keys())}")
        logger.error(f"[{name}] Code dang doc   : ['temperature_2m', 'relative_humidity_2m', 'wind_speed_10m', 'weather_code', 'time']")
        logger.error(f"[{name}] → So sanh 2 dong tren de tim field bi doi ten")
        return None



def extract_all_locations() -> Optional[pd.DataFrame]:
    """
    Lấy dữ liệu thời tiết cho TẤT CẢ locations trong settings.
    24 records/tinh x 63 tinh = 1,512 records/lan chay.

    Returns:
        DataFrame gộp tất cả locations, hoặc None nếu không có data.
    """
    logger.info(
        f"=== START EXTRACT | {len(LOCATIONS)} tinh thanh | "
        f"past_days=1, forecast_days=0 → 24 records/tinh ==="
    )

    all_frames = []
    failed = []

    for location in LOCATIONS:
        df = fetch_weather_for_location(location)
        if df is not None and not df.empty:
            all_frames.append(df)
        else:
            failed.append(location["name"])

    if failed:
        logger.warning(f"Failed locations ({len(failed)}): {failed}")

    if not all_frames:
        logger.error("Khong lay duoc data tu bat ky dia diem nao!")
        return None

    result = pd.concat(all_frames, ignore_index=True)

    logger.info(
        f"=== EXTRACT DONE | Tong: {len(result)} records "
        f"tu {result['location_name'].nunique()}/{len(LOCATIONS)} tinh ==="
    )
    return result


if __name__ == "__main__":
    df = extract_all_locations()
    if df is not None:
        print(f"\nTong: {len(df)} records")
        print(f"Thoi gian: {df['recorded_at'].min()} -> {df['recorded_at'].max()}")
        print("\nSo records theo tinh:")
        print(df.groupby("location_name").size().to_string())
