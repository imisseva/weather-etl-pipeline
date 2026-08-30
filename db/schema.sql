-- ============================================================================
-- WEATHER DATA WAREHOUSE - STAR SCHEMA (Core)
-- ============================================================================
-- Tables:
--   1. dim_location (63 Vietnamese provinces)
--   2. dim_time (2020-2030)
--   3. dim_weather_condition (Open-Meteo weather codes)
--   4. weather_fact (daily weather measurements)
-- ============================================================================


-- ============================================================================
-- 1. DIMENSION: Locations
-- ============================================================================

DROP TABLE IF EXISTS dim_locations CASCADE;

CREATE TABLE dim_location (
    location_id SERIAL PRIMARY KEY,
    location_name VARCHAR(100) UNIQUE NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    region VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dim_location_name
ON dim_location(location_name);

COMMENT ON TABLE dim_location
IS 'Dimension table for 63 Vietnamese provinces/cities';

COMMENT ON COLUMN dim_location.location_name
IS 'Unique location name';

COMMENT ON COLUMN dim_location.region
IS 'Geographic region (North/Central/South)';


-- ============================================================================
-- 2. DIMENSION: Time
-- ============================================================================

DROP TABLE IF EXISTS dim_time CASCADE;

CREATE TABLE dim_time (
    date_id SERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day INT NOT NULL,
    quarter INT NOT NULL,
    day_of_week VARCHAR(10),
    week_of_year INT,
    is_weekend BOOLEAN DEFAULT FALSE,
    is_holiday BOOLEAN DEFAULT FALSE,
    holiday_name VARCHAR(100)
);

CREATE INDEX idx_dim_time_date
ON dim_time(date);

CREATE INDEX idx_dim_time_yearmonth
ON dim_time(year, month);

COMMENT ON TABLE dim_time
IS 'Dimension table for time (2020-2030)';

COMMENT ON COLUMN dim_time.is_weekend
IS 'TRUE if Saturday or Sunday';

COMMENT ON COLUMN dim_time.is_holiday
IS 'TRUE if Vietnamese holiday';

COMMENT ON COLUMN dim_time.holiday_name
IS 'Name of holiday (e.g., Tet, National Day)';


-- ============================================================================
-- 3. DIMENSION: Weather Conditions
-- ============================================================================

DROP TABLE IF EXISTS dim_weather_condition CASCADE;

CREATE TABLE dim_weather_condition (
    condition_id SERIAL PRIMARY KEY,
    weather_code INT UNIQUE NOT NULL,
    condition_name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    severity VARCHAR(20)
);

CREATE INDEX idx_dim_weather_code
ON dim_weather_condition(weather_code);

COMMENT ON TABLE dim_weather_condition
IS 'Dimension table for Open-Meteo weather codes';

COMMENT ON COLUMN dim_weather_condition.weather_code
IS 'Open-Meteo weather code (0-99)';

COMMENT ON COLUMN dim_weather_condition.severity
IS 'Weather severity level';


-- ============================================================================
-- 4. FACT: Weather Measurements
-- ============================================================================

DROP TABLE IF EXISTS weather_fact CASCADE;

CREATE TABLE weather_fact (
    id SERIAL PRIMARY KEY,

    location_id INT NOT NULL
        REFERENCES dim_location(location_id)
        ON DELETE CASCADE,

    date_id INT NOT NULL
        REFERENCES dim_time(date_id)
        ON DELETE CASCADE,

    condition_id INT
        REFERENCES dim_weather_condition(condition_id),

    -- Measurements
    temperature FLOAT NOT NULL,
    humidity INT NOT NULL
        CHECK (humidity >= 0 AND humidity <= 100),

    wind_speed FLOAT NOT NULL,

    pressure FLOAT,

    precipitation FLOAT,

    -- Timestamp
    recorded_at TIMESTAMP NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- One record per location per day
    UNIQUE(location_id, date_id)
);

CREATE INDEX idx_weather_fact_location_date
ON weather_fact(location_id, date_id);

CREATE INDEX idx_weather_fact_date
ON weather_fact(date_id);

CREATE INDEX idx_weather_fact_condition
ON weather_fact(condition_id);

COMMENT ON TABLE weather_fact
IS 'Fact table for daily weather measurements (63 locations)';

COMMENT ON COLUMN weather_fact.temperature
IS 'Temperature in Celsius';

COMMENT ON COLUMN weather_fact.humidity
IS 'Relative humidity (0-100%)';

COMMENT ON COLUMN weather_fact.wind_speed
IS 'Wind speed in m/s';

COMMENT ON COLUMN weather_fact.pressure
IS 'Atmospheric pressure in hPa';

COMMENT ON COLUMN weather_fact.precipitation
IS 'Precipitation in mm';


-- ============================================================================
-- 5. POPULATE: dim_weather_condition
-- ============================================================================
-- Open-Meteo Weather Codes
-- ============================================================================

INSERT INTO dim_weather_condition (
    weather_code,
    condition_name,
    description,
    severity
)
VALUES
    (0,  'Clear sky',
        'Clear sky',
        'Light'),

    (1,  'Mainly clear',
        'Mainly clear, partly cloudy',
        'Light'),

    (2,  'Partly cloudy',
        'Partly cloudy',
        'Light'),

    (3,  'Overcast',
        'Overcast',
        'Light'),

    (45, 'Foggy',
        'Foggy',
        'Moderate'),

    (48, 'Depositing rime fog',
        'Rime fog',
        'Moderate'),

    (51, 'Light drizzle',
        'Light drizzle',
        'Moderate'),

    (53, 'Moderate drizzle',
        'Moderate drizzle',
        'Moderate'),

    (55, 'Dense drizzle',
        'Dense drizzle',
        'Severe'),

    (61, 'Slight rain',
        'Slight rain',
        'Moderate'),

    (63, 'Moderate rain',
        'Moderate rain',
        'Moderate'),

    (65, 'Heavy rain',
        'Heavy rain',
        'Severe'),

    (71, 'Slight snow',
        'Slight snow',
        'Moderate'),

    (73, 'Moderate snow',
        'Moderate snow',
        'Moderate'),

    (75, 'Heavy snow',
        'Heavy snow',
        'Severe'),

    (80, 'Slight rain showers',
        'Rain showers',
        'Moderate'),

    (81, 'Moderate rain showers',
        'Rain showers',
        'Moderate'),

    (82, 'Violent rain showers',
        'Violent rain showers',
        'Severe'),

    (85, 'Slight snow showers',
        'Snow showers',
        'Moderate'),

    (86, 'Heavy snow showers',
        'Heavy snow showers',
        'Severe'),

    (95, 'Thunderstorm',
        'Thunderstorm with slight hail',
        'Severe'),

    (96, 'Thunderstorm with hail',
        'Thunderstorm with hail',
        'Severe'),

    (99, 'Thunderstorm with heavy hail',
        'Thunderstorm with heavy hail',
        'Severe')

ON CONFLICT (weather_code) DO NOTHING;


-- ============================================================================
-- 6. GENERATE: dim_time
-- ============================================================================
-- Generate dates from 2020-01-01 to 2030-12-31
-- PostgreSQL generate_series() is used instead of recursive CTE.
-- ============================================================================

INSERT INTO dim_time (
    date,
    year,
    month,
    day,
    quarter,
    day_of_week,
    week_of_year,
    is_weekend
)
SELECT
    dt::DATE AS date,

    EXTRACT(YEAR FROM dt)::INT AS year,

    EXTRACT(MONTH FROM dt)::INT AS month,

    EXTRACT(DAY FROM dt)::INT AS day,

    EXTRACT(QUARTER FROM dt)::INT AS quarter,

    TRIM(TO_CHAR(dt, 'Day')) AS day_of_week,

    EXTRACT(WEEK FROM dt)::INT AS week_of_year,

    EXTRACT(DOW FROM dt) IN (0, 6) AS is_weekend

FROM generate_series(
    '2020-01-01'::DATE,
    '2030-12-31'::DATE,
    INTERVAL '1 day'
) AS series(dt)

ON CONFLICT (date) DO NOTHING;


-- ============================================================================
-- 7. VERIFICATION
-- ============================================================================

SELECT '=== STAR SCHEMA VERIFICATION ===' AS status;


-- Check row counts
SELECT
    'dim_location' AS table_name,
    COUNT(*) AS row_count
FROM dim_location

UNION ALL

SELECT
    'dim_time',
    COUNT(*)
FROM dim_time

UNION ALL

SELECT
    'dim_weather_condition',
    COUNT(*)
FROM dim_weather_condition

UNION ALL

SELECT
    'weather_fact',
    COUNT(*)
FROM weather_fact;


-- ============================================================================
-- 8. VERIFY dim_time
-- ============================================================================

SELECT
    MIN(date) AS start_date,
    MAX(date) AS end_date,
    COUNT(*) AS total_days
FROM dim_time;


-- ============================================================================
-- 9. VERIFY weather conditions
-- ============================================================================

SELECT
    condition_id,
    weather_code,
    condition_name,
    severity
FROM dim_weather_condition
ORDER BY weather_code;


-- ============================================================================
-- 10. FINAL STATUS
-- ============================================================================

SELECT
    'Star Schema creation completed!' AS status;

SELECT
    'Ready to populate weather_fact with ETL pipeline' AS next_step;

