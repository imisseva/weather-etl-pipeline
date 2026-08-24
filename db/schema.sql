-- ============================================================
-- Weather ETL Pipeline - Database Schema
-- Database: PostgreSQL (Supabase)
-- ============================================================

-- Dimension table: lưu thông tin các địa điểm
CREATE TABLE IF NOT EXISTS dim_locations (
    location_id   SERIAL PRIMARY KEY,
    location_name VARCHAR(100) UNIQUE NOT NULL,
    latitude      FLOAT NOT NULL,
    longitude     FLOAT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fact table: lưu dữ liệu thời tiết theo giờ
CREATE TABLE IF NOT EXISTS weather_fact (
    id          SERIAL PRIMARY KEY,
    location_id INT NOT NULL REFERENCES dim_locations(location_id) ON DELETE CASCADE,
    temperature FLOAT NOT NULL,
    humidity    INT NOT NULL CHECK (humidity >= 0 AND humidity <= 100),
    wind_speed  FLOAT NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (location_id, recorded_at)
);

-- Index: tối ưu query theo location + thời gian
CREATE INDEX IF NOT EXISTS idx_location_recorded_at
    ON weather_fact (location_id, recorded_at);

-- Index: tối ưu query theo thời gian
CREATE INDEX IF NOT EXISTS idx_weather_recorded_at
    ON weather_fact (recorded_at);

-- Verify schema
SELECT 'Schema created successfully' AS status;
SELECT COUNT(*) AS total_locations FROM dim_locations;
