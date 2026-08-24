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
LOCATIONS = [
    # Miền Bắc
    {"name": "Ha Noi",           "latitude": 21.0285, "longitude": 105.8542},
    {"name": "Hai Phong",        "latitude": 20.8449, "longitude": 106.6881},
    {"name": "Quang Ninh",       "latitude": 21.0064, "longitude": 107.2925},
    {"name": "Bac Giang",        "latitude": 21.2731, "longitude": 106.1946},
    {"name": "Bac Kan",          "latitude": 22.1473, "longitude": 105.8346},
    {"name": "Bac Ninh",         "latitude": 21.1861, "longitude": 106.0763},
    {"name": "Cao Bang",         "latitude": 22.6666, "longitude": 106.2638},
    {"name": "Dien Bien",        "latitude": 21.3856, "longitude": 103.0230},
    {"name": "Ha Giang",         "latitude": 22.8233, "longitude": 104.9836},
    {"name": "Ha Nam",           "latitude": 20.5468, "longitude": 105.9230},
    {"name": "Hai Duong",        "latitude": 20.9373, "longitude": 106.3145},
    {"name": "Hoa Binh",         "latitude": 20.8172, "longitude": 105.3380},
    {"name": "Hung Yen",         "latitude": 20.6464, "longitude": 106.0511},
    {"name": "Lai Chau",         "latitude": 22.3964, "longitude": 103.4580},
    {"name": "Lang Son",         "latitude": 21.8537, "longitude": 106.7617},
    {"name": "Lao Cai",          "latitude": 22.4809, "longitude": 103.9753},
    {"name": "Nam Dinh",         "latitude": 20.4241, "longitude": 106.1696},
    {"name": "Ninh Binh",        "latitude": 20.2581, "longitude": 105.9745},
    {"name": "Phu Tho",          "latitude": 21.3227, "longitude": 105.2213},
    {"name": "Son La",           "latitude": 21.3275, "longitude": 103.9144},
    {"name": "Thai Binh",        "latitude": 20.4463, "longitude": 106.3366},
    {"name": "Thai Nguyen",      "latitude": 21.5943, "longitude": 105.8484},
    {"name": "Tuyen Quang",      "latitude": 21.8233, "longitude": 105.2140},
    {"name": "Vinh Phuc",        "latitude": 21.3089, "longitude": 105.5989},
    {"name": "Yen Bai",          "latitude": 21.7051, "longitude": 104.9108},
    # Miền Trung
    {"name": "Da Nang",          "latitude": 16.0544, "longitude": 108.2022},
    {"name": "Ha Tinh",          "latitude": 18.3558, "longitude": 105.8877},
    {"name": "Khanh Hoa",        "latitude": 12.2388, "longitude": 109.1967},
    {"name": "Nghe An",          "latitude": 18.6733, "longitude": 105.6922},
    {"name": "Ninh Thuan",       "latitude": 11.5645, "longitude": 108.9880},
    {"name": "Phu Yen",          "latitude": 13.0882, "longitude": 109.0929},
    {"name": "Quang Binh",       "latitude": 17.4689, "longitude": 106.5915},
    {"name": "Quang Nam",        "latitude": 15.5394, "longitude": 108.0191},
    {"name": "Quang Ngai",       "latitude": 15.1214, "longitude": 108.8048},
    {"name": "Quang Tri",        "latitude": 16.7399, "longitude": 107.1854},
    {"name": "Thanh Hoa",        "latitude": 19.8066, "longitude": 105.7851},
    {"name": "Thua Thien Hue",   "latitude": 16.4674, "longitude": 107.5905},
    {"name": "Binh Dinh",        "latitude": 13.7827, "longitude": 109.2196},
    {"name": "Binh Thuan",       "latitude": 11.0904, "longitude": 108.0721},
    # Tây Nguyên
    {"name": "Dak Lak",          "latitude": 12.6630, "longitude": 108.0378},
    {"name": "Dak Nong",         "latitude": 11.9904, "longitude": 107.6909},
    {"name": "Gia Lai",          "latitude": 13.9929, "longitude": 108.0022},
    {"name": "Kon Tum",          "latitude": 14.3497, "longitude": 108.0004},
    {"name": "Lam Dong",         "latitude": 11.9404, "longitude": 108.4583},
    # Miền Nam
    {"name": "Ho Chi Minh City", "latitude": 10.8231, "longitude": 106.6297},
    {"name": "An Giang",         "latitude": 10.3861, "longitude": 105.4350},
    {"name": "Ba Ria Vung Tau",  "latitude": 10.5417, "longitude": 107.2429},
    {"name": "Bac Lieu",         "latitude":  9.2941, "longitude": 105.7278},
    {"name": "Ben Tre",          "latitude": 10.2417, "longitude": 106.3759},
    {"name": "Binh Duong",       "latitude": 11.1625, "longitude": 106.6524},
    {"name": "Binh Phuoc",       "latitude": 11.7512, "longitude": 106.7235},
    {"name": "Ca Mau",           "latitude":  9.1769, "longitude": 105.1524},
    {"name": "Can Tho",          "latitude": 10.0452, "longitude": 105.7469},
    {"name": "Dong Nai",         "latitude": 10.9450, "longitude": 106.8251},
    {"name": "Dong Thap",        "latitude": 10.4938, "longitude": 105.6882},
    {"name": "Hau Giang",        "latitude":  9.7574, "longitude": 105.6412},
    {"name": "Kien Giang",       "latitude": 10.0128, "longitude": 105.0800},
    {"name": "Long An",          "latitude": 10.6958, "longitude": 106.2431},
    {"name": "Soc Trang",        "latitude":  9.6027, "longitude": 105.9739},
    {"name": "Tay Ninh",         "latitude": 11.3101, "longitude": 106.0980},
    {"name": "Tien Giang",       "latitude": 10.4493, "longitude": 106.3421},
    {"name": "Tra Vinh",         "latitude":  9.9477, "longitude": 106.3420},
    {"name": "Vinh Long",        "latitude": 10.2538, "longitude": 105.9722},
]

# Các trường hourly muốn lấy từ Open-Meteo
HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
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
