import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env từ root của project (2 cấp trên config/)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# ──────────────────────────────────────────
# Database Configuration (Supabase/PostgreSQL)
# ──────────────────────────────────────────
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# Build connection string tiện dùng với psycopg2
DB_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


# ──────────────────────────────────────────
# API Configuration
# ──────────────────────────────────────────
OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")

# Tất cả 63 tỉnh thành Việt Nam
# region: "North" | "Central" | "South"
LOCATIONS = [
    # ── MIỀN BẮC (25 tỉnh thành) ──────────────────────────────────────
    {"name": "Ha Noi",           "latitude": 21.0285, "longitude": 105.8542, "region": "North"},
    {"name": "Hai Phong",        "latitude": 20.8449, "longitude": 106.6881, "region": "North"},
    {"name": "Quang Ninh",       "latitude": 21.0064, "longitude": 107.2925, "region": "North"},
    {"name": "Bac Giang",        "latitude": 21.2731, "longitude": 106.1946, "region": "North"},
    {"name": "Bac Kan",          "latitude": 22.1473, "longitude": 105.8346, "region": "North"},
    {"name": "Bac Ninh",         "latitude": 21.1861, "longitude": 106.0763, "region": "North"},
    {"name": "Cao Bang",         "latitude": 22.6666, "longitude": 106.2638, "region": "North"},
    {"name": "Dien Bien",        "latitude": 21.3856, "longitude": 103.0230, "region": "North"},
    {"name": "Ha Giang",         "latitude": 22.8233, "longitude": 104.9836, "region": "North"},
    {"name": "Ha Nam",           "latitude": 20.5468, "longitude": 105.9230, "region": "North"},
    {"name": "Hai Duong",        "latitude": 20.9373, "longitude": 106.3145, "region": "North"},
    {"name": "Hoa Binh",         "latitude": 20.8172, "longitude": 105.3380, "region": "North"},
    {"name": "Hung Yen",         "latitude": 20.6464, "longitude": 106.0511, "region": "North"},
    {"name": "Lai Chau",         "latitude": 22.3964, "longitude": 103.4580, "region": "North"},
    {"name": "Lang Son",         "latitude": 21.8537, "longitude": 106.7617, "region": "North"},
    {"name": "Lao Cai",          "latitude": 22.4809, "longitude": 103.9753, "region": "North"},
    {"name": "Nam Dinh",         "latitude": 20.4241, "longitude": 106.1696, "region": "North"},
    {"name": "Ninh Binh",        "latitude": 20.2581, "longitude": 105.9745, "region": "North"},
    {"name": "Phu Tho",          "latitude": 21.3227, "longitude": 105.2213, "region": "North"},
    {"name": "Son La",           "latitude": 21.3275, "longitude": 103.9144, "region": "North"},
    {"name": "Thai Binh",        "latitude": 20.4463, "longitude": 106.3366, "region": "North"},
    {"name": "Thai Nguyen",      "latitude": 21.5943, "longitude": 105.8484, "region": "North"},
    {"name": "Tuyen Quang",      "latitude": 21.8233, "longitude": 105.2140, "region": "North"},
    {"name": "Vinh Phuc",        "latitude": 21.3089, "longitude": 105.5989, "region": "North"},
    {"name": "Yen Bai",          "latitude": 21.7051, "longitude": 104.9108, "region": "North"},

    # ── MIỀN TRUNG (19 tỉnh thành, bao gồm Tây Nguyên) ───────────────
    {"name": "Thanh Hoa",        "latitude": 19.8066, "longitude": 105.7851, "region": "Central"},
    {"name": "Nghe An",          "latitude": 18.6733, "longitude": 105.6922, "region": "Central"},
    {"name": "Ha Tinh",          "latitude": 18.3558, "longitude": 105.8877, "region": "Central"},
    {"name": "Quang Binh",       "latitude": 17.4689, "longitude": 106.5915, "region": "Central"},
    {"name": "Quang Tri",        "latitude": 16.7399, "longitude": 107.1854, "region": "Central"},
    {"name": "Thua Thien Hue",   "latitude": 16.4674, "longitude": 107.5905, "region": "Central"},
    {"name": "Da Nang",          "latitude": 16.0544, "longitude": 108.2022, "region": "Central"},
    {"name": "Quang Nam",        "latitude": 15.5394, "longitude": 108.0191, "region": "Central"},
    {"name": "Quang Ngai",       "latitude": 15.1214, "longitude": 108.8048, "region": "Central"},
    {"name": "Binh Dinh",        "latitude": 13.7827, "longitude": 109.2196, "region": "Central"},
    {"name": "Phu Yen",          "latitude": 13.0882, "longitude": 109.0929, "region": "Central"},
    {"name": "Khanh Hoa",        "latitude": 12.2388, "longitude": 109.1967, "region": "Central"},
    {"name": "Ninh Thuan",       "latitude": 11.5645, "longitude": 108.9880, "region": "Central"},
    {"name": "Binh Thuan",       "latitude": 11.0904, "longitude": 108.0721, "region": "Central"},
    # Tây Nguyên (thuộc Miền Trung về địa lý)
    {"name": "Dak Lak",          "latitude": 12.6630, "longitude": 108.0378, "region": "Central"},
    {"name": "Dak Nong",         "latitude": 11.9904, "longitude": 107.6909, "region": "Central"},
    {"name": "Gia Lai",          "latitude": 13.9929, "longitude": 108.0022, "region": "Central"},
    {"name": "Kon Tum",          "latitude": 14.3497, "longitude": 108.0004, "region": "Central"},
    {"name": "Lam Dong",         "latitude": 11.9404, "longitude": 108.4583, "region": "Central"},

    # ── MIỀN NAM (19 tỉnh thành) ──────────────────────────────────────
    {"name": "Ho Chi Minh City", "latitude": 10.8231, "longitude": 106.6297, "region": "South"},
    {"name": "An Giang",         "latitude": 10.3861, "longitude": 105.4350, "region": "South"},
    {"name": "Ba Ria Vung Tau",  "latitude": 10.5417, "longitude": 107.2429, "region": "South"},
    {"name": "Bac Lieu",         "latitude":  9.2941, "longitude": 105.7278, "region": "South"},
    {"name": "Ben Tre",          "latitude": 10.2417, "longitude": 106.3759, "region": "South"},
    {"name": "Binh Duong",       "latitude": 11.1625, "longitude": 106.6524, "region": "South"},
    {"name": "Binh Phuoc",       "latitude": 11.7512, "longitude": 106.7235, "region": "South"},
    {"name": "Ca Mau",           "latitude":  9.1769, "longitude": 105.1524, "region": "South"},
    {"name": "Can Tho",          "latitude": 10.0452, "longitude": 105.7469, "region": "South"},
    {"name": "Dong Nai",         "latitude": 10.9450, "longitude": 106.8251, "region": "South"},
    {"name": "Dong Thap",        "latitude": 10.4938, "longitude": 105.6882, "region": "South"},
    {"name": "Hau Giang",        "latitude":  9.7574, "longitude": 105.6412, "region": "South"},
    {"name": "Kien Giang",       "latitude": 10.0128, "longitude": 105.0800, "region": "South"},
    {"name": "Long An",          "latitude": 10.6958, "longitude": 106.2431, "region": "South"},
    {"name": "Soc Trang",        "latitude":  9.6027, "longitude": 105.9739, "region": "South"},
    {"name": "Tay Ninh",         "latitude": 11.3101, "longitude": 106.0980, "region": "South"},
    {"name": "Tien Giang",       "latitude": 10.4493, "longitude": 106.3421, "region": "South"},
    {"name": "Tra Vinh",         "latitude":  9.9477, "longitude": 106.3420, "region": "South"},
    {"name": "Vinh Long",        "latitude": 10.2538, "longitude": 105.9722, "region": "South"},
]

# Các trường hourly muốn lấy từ Open-Meteo
HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "weather_code",         # Mã thời tiết WMO → map vào dim_weather_condition
]

# ──────────────────────────────────────────
# Logging Configuration
# ──────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)  # tự tạo thư mục logs nếu chưa có


# ──────────────────────────────────────────
# Validation: kiểm tra các biến bắt buộc
# ──────────────────────────────────────────
REQUIRED_VARS = {
    "DB_HOST": DB_HOST,
    "DB_PORT": DB_PORT,
    "DB_USER": DB_USER,
    "DB_PASSWORD": DB_PASSWORD,
    "DB_NAME": DB_NAME,
}

missing = [key for key, val in REQUIRED_VARS.items() if not val]
if missing:
    raise EnvironmentError(
        f"Thiếu các biến môi trường bắt buộc: {', '.join(missing)}\n"
        f"Hãy kiểm tra lại file .env"
    )
