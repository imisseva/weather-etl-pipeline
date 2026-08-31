import unittest
import pandas as pd

from src.extract import extract_all_locations
from src.transform import transform_weather_data
from src.load import get_connection, seed_dim_location, load_weather_data


class TestPipelineIntegration(unittest.TestCase):
    """
    Integration Tests (End-to-End Test) cho toan bo Weather ETL Pipeline.
    Ket noi thuc te toi Open-Meteo API va Supabase Database.
    """

    @classmethod
    def setUpClass(cls):
        """Mo ket noi DB thuc te cho ca test suite."""
        cls.conn = get_connection()

    @classmethod
    def tearDownClass(cls):
        """Dong ket noi DB sau khi test xong."""
        if cls.conn:
            cls.conn.close()

    def test_full_etl_pipeline_integration(self):
        """
        Test End-to-End luong ETL thuc te:
        1. Extract   : Goi API Open-Meteo thuc te.
        2. Transform : Chuyen 1,512 hourly records -> 63 daily records, map dimension.
        3. Load      : Seed dim_location va insert vao weather_fact trong Supabase DB.
        4. Verify    : Query nguoc lai DB xem du lieu da co dung va du chua.
        """
        # --- BƯỚC 1: EXTRACT ---
        raw_df = extract_all_locations()
        self.assertIsNotNone(raw_df, "Extract phai tra ve DataFrame du lieu")
        self.assertFalse(raw_df.empty, "Extract DataFrame khong duoc rong")
        self.assertGreaterEqual(len(raw_df), 63 * 24, "Phai lay du 24h cho 63 tinh thanh")

        # --- BƯỚC 2: TRANSFORM ---
        transformed_df = transform_weather_data(raw_df, self.conn)
        self.assertIsNotNone(transformed_df, "Transform phai tra ve DataFrame")
        self.assertEqual(len(transformed_df), 63, "Sau khi aggregate phai co dung 63 records dai dien cho 63 tinh")

        # Kiem tra cac cot cua Star Schema
        expected_columns = [
            "location_id",
            "date_id",
            "condition_id",
            "temperature",
            "humidity",
            "wind_speed",
            "recorded_at",
        ]
        self.assertEqual(list(transformed_df.columns), expected_columns)

        # --- BƯỚC 3: LOAD ---
        # Seed dim_location
        seed_success = seed_dim_location(self.conn)
        self.assertTrue(seed_success, "Seed dim_location phai thanh cong")

        # Load vao weather_fact
        inserted_count = load_weather_data(self.conn, transformed_df)
        self.assertIsNotNone(inserted_count, "Load weather_fact phai tra ve so luong inserted/skipped")

        # --- BƯỚC 4: VERIFY VIA DATABASE QUERY ---
        # Lấy date_id vừa load
        test_date_id = int(transformed_df["date_id"].iloc[0])

        with self.conn.cursor() as cur:
            # Query dem so luong ban ghi trong weather_fact cho date_id nay
            cur.execute(
                "SELECT COUNT(*) FROM weather_fact WHERE date_id = %s",
                (test_date_id,),
            )
            fact_count = cur.fetchone()[0]

        # Phai co du 63 tinh cho date_id nay trong DB
        self.assertEqual(fact_count, 63, f"Trong DB phai co dung 63 ban ghi cho date_id = {test_date_id}")

    def test_pipeline_idempotency(self):
        """
        Test tinh Idempotent:
        Khi chay lai luong Load voi cung du lieu ngay do lan thu 2,
        he thong phai tu dong skip (0 inserted) nho ON CONFLICT DO NOTHING.
        """
        # 1. Extract & Transform
        raw_df = extract_all_locations()
        self.assertIsNotNone(raw_df)

        transformed_df = transform_weather_data(raw_df, self.conn)
        self.assertIsNotNone(transformed_df)

        # 2. Load lan 1 (co the insert hoac skip neu da co trong DB)
        load_weather_data(self.conn, transformed_df)

        # 3. Load lan 2 ngay lap tuc voi cung transformed_df
        second_insert_count = load_weather_data(self.conn, transformed_df)

        # Lan 2 phai insert thanh cong 0 ban ghi (tat ca 63 ban ghi deu bi skip)
        self.assertEqual(
            second_insert_count,
            0,
            "Chay lai lan 2 phai skip 100% (0 inserted) de dam bao tinh idempotent",
        )


if __name__ == "__main__":
    unittest.main()
