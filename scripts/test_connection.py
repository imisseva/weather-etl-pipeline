import psycopg2
from config.settings import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

def test_connection():
    print("==================================================")
    print(f"Connecting to {DB_HOST}:{DB_PORT}/{DB_NAME}...")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME,
            sslmode="require",
        )
        print("Connection successful!")
        
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM dim_location")
            loc_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM dim_time")
            time_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM dim_weather_condition")
            cond_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM weather_fact")
            fact_count = cur.fetchone()[0]

        print("--------------------------------------------------")
        print(f"  dim_location          : {loc_count} records")
        print(f"  dim_time              : {time_count} records")
        print(f"  dim_weather_condition : {cond_count} records")
        print(f"  weather_fact          : {fact_count} records")
        print("==================================================")
        
        conn.close()
        return True

    except Exception as e:
        print(f"Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()
