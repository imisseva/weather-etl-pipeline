import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import requests

from src.extract import fetch_weather_for_location, extract_all_locations


class TestExtract(unittest.TestCase):
    """
    Unit tests cho module src/extract.py
    Dung unittest.mock.patch de gia lap (mock) cac phan phu thuoc bên ngoai (API network calls).
    """

    def setUp(self):
        """Thiet lap du lieu mau cho moi test case."""
        self.sample_location = {
            "name": "Ha Noi",
            "latitude": 21.0285,
            "longitude": 105.8542,
            "region": "North",
        }

        # Structure du lieu JSON gia lap giong hệt API Open-Meteo tra ve (24 gio)
        self.mock_api_response = {
            "hourly": {
                "time": [f"2026-08-30T{h:02d}:00" for h in range(24)],
                "temperature_2m": [25.0 + h * 0.1 for h in range(24)],
                "relative_humidity_2m": [80 + (h % 5) for h in range(24)],
                "wind_speed_10m": [10.0 + h * 0.2 for h in range(24)],
                "weather_code": [3 for _ in range(24)],
            }
        }

    @patch("src.extract.requests.get")
    def test_fetch_weather_for_location_success(self, mock_get):
        """Test truong hop goi API thanh cong 100%."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_api_response
        mock_get.return_value = mock_response

        df = fetch_weather_for_location(self.sample_location)

        self.assertIsNotNone(df)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 24)
        self.assertIn("location_name", df.columns)
        self.assertIn("temperature", df.columns)
        self.assertIn("humidity", df.columns)
        self.assertIn("wind_speed", df.columns)
        self.assertIn("weather_code", df.columns)
        self.assertIn("recorded_at", df.columns)
        self.assertEqual(df["location_name"].iloc[0], "Ha Noi")

    @patch("src.extract.time.sleep")
    @patch("src.extract.requests.get")
    def test_fetch_weather_retry_on_timeout(self, mock_get, mock_sleep):
        """Test co che Retry: lan 1 bi Timeout, lan 2 thanh cong."""
        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = self.mock_api_response

        mock_get.side_effect = [
            requests.exceptions.Timeout("Connection timed out"),
            mock_success_response,
        ]

        df = fetch_weather_for_location(self.sample_location)

        self.assertEqual(mock_get.call_count, 2)
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 24)

    @patch("src.extract.requests.get")
    def test_fetch_weather_client_error_no_retry(self, mock_get):
        """Test loi 4xx (vi du 404 Client Error): khong retry va tra ve None ngay."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        http_error = requests.exceptions.HTTPError("404 Client Error")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response

        df = fetch_weather_for_location(self.sample_location)

        self.assertEqual(mock_get.call_count, 1)
        self.assertIsNone(df)

    @patch("src.extract.requests.get")
    def test_fetch_weather_missing_key_error(self, mock_get):
        """Test khi API tra ve JSON thieu field cau truc (KeyError)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid_structure": {}}
        mock_get.return_value = mock_response

        df = fetch_weather_for_location(self.sample_location)

        self.assertIsNone(df)

    @patch("src.extract.fetch_weather_for_location")
    def test_extract_all_locations_success(self, mock_fetch):
        """Test gop du lieu tu nhieu location thanh 1 DataFrame chung."""
        df_hanoi = pd.DataFrame({
            "location_name": ["Ha Noi"] * 24,
            "temperature": [28.0] * 24,
            "humidity": [80] * 24,
            "wind_speed": [10.0] * 24,
            "weather_code": [3] * 24,
            "recorded_at": pd.date_range("2026-08-30", periods=24, freq="h"),
        })

        df_hphong = pd.DataFrame({
            "location_name": ["Hai Phong"] * 24,
            "temperature": [29.0] * 24,
            "humidity": [82] * 24,
            "wind_speed": [12.0] * 24,
            "weather_code": [2] * 24,
            "recorded_at": pd.date_range("2026-08-30", periods=24, freq="h"),
        })

        mock_fetch.side_effect = lambda loc: df_hanoi if loc["name"] == "Ha Noi" else df_hphong

        result_df = extract_all_locations()

        self.assertIsNotNone(result_df)
        self.assertEqual(len(result_df), 63 * 24)
        self.assertIn("Ha Noi", result_df["location_name"].values)
        self.assertIn("Hai Phong", result_df["location_name"].values)

    @patch("src.extract.fetch_weather_for_location")
    def test_extract_all_locations_all_failed(self, mock_fetch):
        """Test khi tat ca cac location deu lay du lieu that bai."""
        mock_fetch.return_value = None

        result_df = extract_all_locations()

        self.assertIsNone(result_df)


if __name__ == "__main__":
    unittest.main()
