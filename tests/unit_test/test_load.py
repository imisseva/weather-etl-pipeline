import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import psycopg2

from src.load import (
    get_connection,
    seed_dim_location,
    load_weather_data,
    load_to_database,
)


class TestLoad(unittest.TestCase):
    """
    Unit tests cho module src/load.py
    Dung MagicMock va patch de gia lap connection va cursor PostgreSQL.
    """

    def setUp(self):
        """Thiet lap mock connection va cursor DB."""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__.return_value = self.mock_cursor

        # DataFrame mau da qua Transform
        self.sample_transformed_df = pd.DataFrame({
            "location_id": [1, 2],
            "date_id": [2434, 2434],
            "condition_id": [4, None],  # Co 1 record None (nullable)
            "temperature": [28.5, 29.0],
            "humidity": [80, 85],
            "wind_speed": [10.5, 12.0],
            "recorded_at": [pd.Timestamp("2026-08-30 00:00:00+0700")] * 2,
        })

    # ──────────────────────────────────────────
    # Test 1: get_connection()
    # ──────────────────────────────────────────

    @patch("src.load.psycopg2.connect")
    def test_get_connection_success(self, mock_connect):
        """Test ket noi DB thành cong ngay lan dau."""
        mock_connect.return_value = self.mock_conn

        conn = get_connection()

        self.assertEqual(conn, self.mock_conn)
        self.assertEqual(mock_connect.call_count, 1)

    @patch("src.load.time.sleep")
    @patch("src.load.psycopg2.connect")
    def test_get_connection_retry_and_fail(self, mock_connect, mock_sleep):
        """Test ket noi DB that bai 3 lan lien tiep va nem exception."""
        mock_connect.side_effect = psycopg2.OperationalError("Connection refused")

        with self.assertRaises(psycopg2.OperationalError):
            get_connection()

        # Phai retry 3 lan
        self.assertEqual(mock_connect.call_count, 3)

    # ──────────────────────────────────────────
    # Test 2: seed_dim_location()
    # ──────────────────────────────────────────

    @patch("src.load.execute_values")
    def test_seed_dim_location_success(self, mock_execute_values):
        """Test seed 63 tinh thanh vao dim_location thanh cong."""
        self.mock_cursor.fetchone.return_value = [63]

        success = seed_dim_location(self.mock_conn)

        self.assertTrue(success)
        self.assertEqual(mock_execute_values.call_count, 1)
        self.mock_conn.commit.assert_called_once()

    @patch("src.load.execute_values")
    def test_seed_dim_location_integrity_error(self, mock_execute_values):
        """Test seed dim_location gap loi IntegrityError (khong retry, rollback)."""
        mock_execute_values.side_effect = psycopg2.IntegrityError("Duplicate key")

        success = seed_dim_location(self.mock_conn)

        self.assertFalse(success)
        self.mock_conn.rollback.assert_called_once()

    # ──────────────────────────────────────────
    # Test 3: load_weather_data()
    # ──────────────────────────────────────────

    def test_load_weather_data_empty_df(self):
        """Test load DataFrame rong -> tra ve None."""
        empty_df = pd.DataFrame()

        result = load_weather_data(self.mock_conn, empty_df)

        self.assertIsNone(result)

    @patch("src.load.execute_values")
    def test_load_weather_data_success(self, mock_execute_values):
        """Test load du lieu thanh cong vao weather_fact."""
        self.mock_cursor.rowcount = 2

        inserted = load_weather_data(self.mock_conn, self.sample_transformed_df)

        self.assertEqual(inserted, 2)
        self.assertEqual(mock_execute_values.call_count, 1)
        self.mock_conn.commit.assert_called_once()

        # Kiem tra gia tri condition_id = None duoc truyen chinh xac sang SQL
        executed_records = mock_execute_values.call_args[0][2]
        self.assertIsNone(executed_records[1][2])  # condition_id cua record thu 2 la None

    @patch("src.load.execute_values")
    def test_load_weather_data_integrity_error(self, mock_execute_values):
        """Test khi insert va weather_fact bi loi IntegrityError -> rollback va tra ve None."""
        mock_execute_values.side_effect = psycopg2.IntegrityError("FK violation")

        result = load_weather_data(self.mock_conn, self.sample_transformed_df)

        self.assertIsNone(result)
        self.mock_conn.rollback.assert_called_once()

    # ──────────────────────────────────────────
    # Test 4: load_to_database()
    # ──────────────────────────────────────────

    @patch("src.load.load_weather_data")
    @patch("src.load.seed_dim_location")
    @patch("src.load.get_connection")
    def test_load_to_database_success(self, mock_get_conn, mock_seed, mock_load):
        """Test luong main load_to_database thanh cong."""
        mock_get_conn.return_value = self.mock_conn
        mock_seed.return_value = True
        mock_load.return_value = 2

        success, conn = load_to_database(self.sample_transformed_df)

        self.assertTrue(success)
        self.assertEqual(conn, self.mock_conn)

    @patch("src.load.seed_dim_location")
    @patch("src.load.get_connection")
    def test_load_to_database_seed_failed(self, mock_get_conn, mock_seed):
        """Test luong main load_to_database that bai khi seed_dim_location bi loi."""
        mock_get_conn.return_value = self.mock_conn
        mock_seed.return_value = False

        success, conn = load_to_database(self.sample_transformed_df)

        self.assertFalse(success)
        self.assertEqual(conn, self.mock_conn)


if __name__ == "__main__":
    unittest.main()
