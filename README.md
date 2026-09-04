# Vietnam Weather ETL Pipeline

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)
![Apache Airflow](https://img.shields.io/badge/Apache_Airflow-2.9.3-017CEE?style=flat&logo=apacheairflow&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat&logo=docker&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=flat&logo=postgresql&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-2.x-150458?style=flat&logo=pandas&logoColor=white)
![Coverage](https://img.shields.io/badge/Test_Coverage-94%25-brightgreen?style=flat)

A production-grade daily weather ETL pipeline that collects hourly data from **63 Vietnamese provinces**, transforms it into a Star Schema, and loads it into a cloud PostgreSQL database — fully containerized with Docker and orchestrated with Apache Airflow.

---

## Architecture Diagram

```text
                 ┌─────────────────────┐
                 │   Open-Meteo API    │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │       EXTRACT       │
                 │     Python / API    │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │      TRANSFORM      │
                 │ pandas / UTC+7      │
                 │ hourly → daily      │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │    DATA QUALITY     │
                 │ completeness / null │
                 │ uniqueness / ranges │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │        LOAD         │
                 │      psycopg2       │
                 │    idempotent       │
                 └──────────┬──────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │   PostgreSQL Data Warehouse │
              │                             │
              │       weather_fact          │
              │       /    |    \           │
              │ dim_location dim_time       │
              │       dim_weather_condition │
              └─────────────────────────────┘

       ┌─────────────────┐       ┌───────────────┐
       │   Apache Airflow│──────▶│ ETL Pipeline  │
       │ Daily @ 01:00   │       └───────────────┘
       └─────────────────┘

                 Docker Container
```

### Data Flow

```
Open-Meteo API
  63 provinces × 24 h/day = 1,512 hourly records
        │
        ▼
  [1] EXTRACT      — HTTP requests, sequential fetch, exponential backoff retry
        │
        ▼
  [2] TRANSFORM    — Timezone (UTC → UTC+7), aggregate hourly → 63 daily records,
        │             map dimension IDs (location_id, date_id, condition_id)
        ▼
  [3] DATA QUALITY — 4 post-load checks (Completeness, Nulls, Uniqueness, Ranges)
        │
        ▼
  [4] LOAD         — Seed dim_location, INSERT ON CONFLICT DO NOTHING (idempotent)
        │
        ▼
  PostgreSQL Data Warehouse — Star Schema (4 tables)
```

---

## Business Value

**Problem:** Vietnam's agricultural, logistics, and tourism sectors need reliable, structured weather data across all 63 provinces. Raw API responses are hourly, unstructured, and lack dimension modeling — making them difficult to query for business analytics.

**What this pipeline delivers:**
- **Daily aggregated weather metrics** (avg temperature, avg humidity, avg wind speed) per province — ready for BI dashboards
- **Star Schema design** enables fast, intuitive SQL queries: *"Which region had the highest average temperature last week?"*, *"How many rainy days did the Central region have this month?"*
- **Fully automated**: runs at 1:00 AM daily without manual intervention
- **Idempotent**: safe to re-run — duplicate records are detected and skipped automatically

---

## Challenges & Solutions

### 1. Timezone Ambiguity in Raw Data

**Problem:** Open-Meteo returns timestamps without timezone info (naive datetime). Aggregating hourly data into a "daily" record without proper timezone handling produces incorrect results — midnight UTC is 7:00 AM Vietnam time, causing data to belong to the wrong calendar day.

**Solution:** Added an explicit UTC+7 localization step as the first transform operation:
```python
df["recorded_at"] = pd.to_datetime(df["recorded_at"]).dt.tz_localize("UTC").dt.tz_convert("Asia/Ho_Chi_Minh")
```
This ensures aggregation groups by the correct Vietnamese calendar date.

---

### 2. Dirty Data — Float Humidity Values

**Problem:** The API returned humidity as `float64` (e.g., `78.0`), but the database schema defines `humidity` as `INTEGER`. Pandas' default aggregation (`mean()`) preserves float precision, causing `psycopg2` type mismatch errors on insert.

**Solution:** Added explicit type coercion after aggregation:
```python
df["humidity"] = df["humidity"].round().astype(int)
```

---

### 3. Airflow XCom Size Limit

**Problem:** The initial DAG design passed DataFrames between 4 separate tasks via Airflow XCom. The 1,512-record raw DataFrame serialized to ~300KB JSON — far exceeding Airflow's default XCom limit of ~48KB stored in PostgreSQL metadata DB.

**Solution:** Restructured the DAG to a single `PythonOperator` task that calls the existing `run_pipeline()` function directly. This avoids XCom entirely while preserving the 4-step logic inside one observable, testable unit. XCom is designed for small metadata (IDs, file paths, status flags) — not large datasets.

---

### 4. Windows File Lock on Log Rotation (WinError 32)

**Problem:** `TimedRotatingFileHandler` rotates log files at midnight by renaming the current log file. On Windows, attempting to rename a file that another process has open raises `WinError 32: The process cannot access the file`.

**Solution:** Switched to `RotatingFileHandler` with `delay=True` (file handle opened lazily, not at logger initialization):
```python
handler = RotatingFileHandler(log_path, maxBytes=10*1024*1024, backupCount=5, delay=True)
```

---

### 5. Pipeline Idempotency

**Problem:** If the pipeline runs twice on the same day (e.g., due to a retry), it would insert duplicate records into `weather_fact`, violating the `UNIQUE(location_id, date_id)` constraint.

**Solution:** Used PostgreSQL's `INSERT ... ON CONFLICT DO NOTHING` pattern. Duplicate records are silently skipped, and the pipeline reports how many were inserted vs. skipped:
```sql
INSERT INTO weather_fact (...) VALUES (...)
ON CONFLICT (location_id, date_id) DO NOTHING
```

---

## Tech Stack Rationale

| Tool | Choice | Why not the alternative? |
|---|---|---|
| **Python 3.11** | Core language | Mature ecosystem for data engineering; `pandas`, `psycopg2` are industry standards |
| **Open-Meteo API** | Data source | Free, no API key required, reliable hourly historical data for any coordinate |
| **pandas** | Transform | Vectorized operations for aggregation; cleaner than raw SQL for multi-step transforms |
| **psycopg2-binary** | DB driver | Direct PostgreSQL driver; SQLAlchemy adds unnecessary abstraction for simple inserts |
| **PostgreSQL** | Storage | Relational database supporting Star Schema DDL, transactions & ACID compliance |
| **Star Schema** | Data model | Optimized for analytical queries (GROUP BY region, date range filters) vs. flat tables |
| **Apache Airflow** | Orchestration | Industry-standard scheduler with UI, retry logic, and run history vs. cron (no visibility) |
| **LocalExecutor** | Airflow executor | Sufficient for a single sequential DAG; CeleryExecutor adds Redis complexity for no gain |
| **Docker** | Containerization | Reproducible environment; eliminates "works on my machine" issues |
| **pytest** | Testing | 94% coverage across unit + integration tests; `unittest.mock` for DB isolation |

---

## Project Structure

```
weather-etl-pipeline/
├── config/
│   └── settings.py            # DB config, 63 province coordinates, API settings
├── dags/
│   └── weather_etl_dag.py     # Airflow DAG (daily at 1:00 AM UTC+7)
├── db/
│   └── schema.sql             # Star Schema DDL (4 tables)
├── scripts/
│   ├── test_connection.py     # Quick DB connectivity check
│   └── verify_data.py         # Post-run data inspection
├── src/
│   ├── extract.py             # Open-Meteo API calls
│   ├── transform.py           # Pandas transformations & dimension mapping
│   ├── load.py                # psycopg2 DB writes, retry logic
│   ├── data_quality.py        # 4 post-load quality checks
│   └── logger.py              # Rotating file + console logging
├── tests/
│   ├── unit_test/             # Isolated unit tests (mocked DB/API)
│   └── integration_test/      # End-to-end pipeline test (real DB)
├── Dockerfile.airflow          # Custom Airflow image with ETL dependencies
├── docker-compose.yml          # Airflow stack: postgres + webserver + scheduler
├── main.py                     # Pipeline entry point: run_pipeline()
└── requirements.txt
```

---

## Setup Instructions

### Prerequisites

- Python 3.10+
- Docker Desktop (running)
- A PostgreSQL database (local or cloud)
- `.env` file with your database credentials

### 1. Clone the Repository

```bash
git clone https://github.com/imisseva/weather-etl-pipeline.git
cd weather-etl-pipeline
```

### 2. Configure Environment Variables

```bash
# Copy the example file and fill in your credentials
cp .env.example .env
```

```dotenv
DB_HOST=localhost        # or your cloud DB host
DB_PORT=5432
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_db_name
```

> **Any PostgreSQL database works** — local Docker, managed cloud (Supabase, Neon, Railway, AWS RDS), or self-hosted.

### 3. Initialize the Database

The Star Schema DDL is included in the repo. Run it once against your PostgreSQL database:

```bash
# Via psql
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f db/schema.sql
```

This creates 4 tables: `dim_location`, `dim_time`, `dim_weather_condition`, `weather_fact`.
`dim_time` (2020–2030) and `dim_weather_condition` (WMO codes) are pre-seeded automatically.

### 4. Option A — Run Once (without Airflow)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the pipeline directly
python main.py
```

### 5. Option B — Schedule with Airflow (Docker)

```bash
# Step 1: Build the Airflow image
docker compose build

# Step 2: Initialize Airflow DB and create admin user (run once)
docker compose up airflow-init

# Step 3: Start Airflow
docker compose up -d airflow-webserver airflow-scheduler

# Step 4: Open Airflow UI
# http://localhost:8080  →  Username: admin  |  Password: admin
```

The DAG `weather_etl_pipeline` will appear in the UI and run automatically at **1:00 AM Vietnam time** daily.

**Trigger manually (no need to wait):**
```bash
docker compose exec airflow-scheduler airflow dags trigger weather_etl_pipeline
```

**Stop all services:**
```bash
docker compose down -v
```

### 6. Run Tests

```bash
# All tests with coverage report
pytest tests/ -v --cov=src --cov-report=term-missing

# Unit tests only
pytest tests/unit_test/ -v

# Integration test (requires real DB connection)
pytest tests/integration_test/ -v
```

---

## Data Quality Checks

After every load, 4 automated checks run against the database:

| Check | Description | Pass Condition |
|---|---|---|
| **Completeness** | All 63 provinces present | `COUNT(DISTINCT location_id) = 63` |
| **Null Check** | No critical fields are NULL | `temperature, humidity, wind_speed, location_id` all non-null |
| **Uniqueness** | No duplicate (location, date) pairs | `COUNT(*) = 1` per `(location_id, date_id)` |
| **Value Ranges** | Metrics within physical limits | `-10°C ≤ temp ≤ 60°C`, `0% ≤ humidity ≤ 100%`, `0 ≤ wind ≤ 200 km/h` |
