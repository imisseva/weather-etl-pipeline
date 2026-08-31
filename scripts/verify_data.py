import psycopg2
from config.settings import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

def verify_data():
    print("==================================================")
    print("VERIFYING DATA IN SUPABASE POSTGRESQL DATABASE")
    print("==================================================")

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME,
        sslmode="require",
    )

    with conn.cursor() as cur:
        # Total records
        cur.execute("SELECT COUNT(*) FROM weather_fact")
        total_records = cur.fetchone()[0]
        print(f"Total records in weather_fact: {total_records}")

        # Latest date count
        cur.execute("SELECT MAX(date_id) FROM weather_fact")
        latest_date_id = cur.fetchone()[0]

        if latest_date_id:
            cur.execute("SELECT COUNT(*) FROM weather_fact WHERE date_id = %s", (latest_date_id,))
            latest_count = cur.fetchone()[0]
            print(f"Latest date_id ({latest_date_id}) records: {latest_count} locations")

        # Sample data
        print("\n--- SAMPLE DATA (Top 5) ---")
        cur.execute("""
            SELECT l.location_name, f.temperature, f.humidity, f.wind_speed, c.condition_name
            FROM weather_fact f
            JOIN dim_location l ON f.location_id = l.location_id
            LEFT JOIN dim_weather_condition c ON f.condition_id = c.condition_id
            LIMIT 5
        """)
        rows = cur.fetchall()
        for row in rows:
            print(f"  [{row[0]}] Temp: {row[1]}°C, Humidity: {row[2]}%, Wind: {row[3]} km/h, Condition: {row[4]}")

        # Null check
        cur.execute("""
            SELECT COUNT(*) FROM weather_fact
            WHERE temperature IS NULL OR humidity IS NULL OR wind_speed IS NULL OR location_id IS NULL
        """)
        nulls = cur.fetchone()[0]
        print(f"\nNull check    : {nulls} records with NULLs")

        # Range check
        cur.execute("""
            SELECT COUNT(*) FROM weather_fact
            WHERE temperature < -10 OR temperature > 60 OR humidity < 0 OR humidity > 100
        """)
        out_of_range = cur.fetchone()[0]
        print(f"Range check   : {out_of_range} records out of range")

        # Duplicate check
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT location_id, date_id, COUNT(*)
                FROM weather_fact
                GROUP BY location_id, date_id
                HAVING COUNT(*) > 1
            ) sub
        """)
        dups = cur.fetchone()[0]
        print(f"Duplicate check: {dups} duplicates")

    print("==================================================")
    conn.close()

if __name__ == "__main__":
    verify_data()
