import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from datetime import date, timezone, timedelta

from src.transform import (
    transform_weather_data,
    _query_date_id_map,
    _query_condition_id_map,
    VN_TIMEZONE,
)


class TestTransform(unittest.TestCase):
    """
    Unit tests cho module src/transform.py
    Kiểm tra 8 bước xử lý dữ liệu từ raw hourly sang daily aggregated record cho Star Schema.
    """

    def setUp(self):
        """Thiết lập dữ liệu mẫu và mock connection."""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__.return_value = self.mock_cursor

        # Cấu trúc DataFrame raw 24 giờ của 1 tỉnh (Ví dụ: Hà Nội)
        self.raw_df = pd.DataFrame({
            "location_name": ["Ha Noi"] * 24,
            "temperature": [25.0 + (h * 0.2) for h in range(24)],
            "humidity": [80.0] * 24,
            "wind_speed": [10.0] * 24,
            "weather_code": [3] * 24,
            "recorded_at": pd.date_range("2026-08-30 00:00:00", periods=24, freq="h"),
        })

    def _setup_transform_db_mocks(self, condition_fetch=None):
        """Helper để mock kết quả fetchall cho transform_weather_data (dim_time + dim_weather_condition)."""
        if condition_fetch is None:
            condition_fetch = [(3, 4)]
        self.mock_cursor.fetchall.side_effect = [
            [(date(2026, 8, 30), 2434)],  # dim_time mapping
            condition_fetch,              # dim_weather_condition mapping
        ]

    # ──────────────────────────────────────────
    # Test 1: Các hàm query helper
    # ──────────────────────────────────────────

    def test_query_date_id_map(self):
        """Test hàm query tạo dictionary date -> date_id từ dim_time."""
        self.mock_cursor.fetchall.side_effect = None
        self.mock_cursor.fetchall.return_value = [
            (date(2026, 8, 30), 2434),
            (date(2026, 8, 31), 2435),
        ]

        result = _query_date_id_map(self.mock_conn)

        self.assertEqual(result, {date(2026, 8, 30): 2434, date(2026, 8, 31): 2435})
        self.mock_cursor.execute.assert_called_once_with("SELECT date, date_id FROM dim_time")

    def test_query_condition_id_map(self):
        """Test hàm query tạo dictionary weather_code -> condition_id từ dim_weather_condition."""
        self.mock_cursor.fetchall.side_effect = None
        self.mock_cursor.fetchall.return_value = [(0, 1), (3, 4), (95, 21)]

        result = _query_condition_id_map(self.mock_conn)

        self.assertEqual(result, {0: 1, 3: 4, 95: 21})
        self.mock_cursor.execute.assert_called_once_with("SELECT weather_code, condition_id FROM dim_weather_condition")

    # ──────────────────────────────────────────
    # Test 2: transform_weather_data() với các kịch bản
    # ──────────────────────────────────────────

    def test_transform_empty_or_none_df(self):
        """Test khi truyền vào DataFrame rỗng hoặc None -> trả về None."""
        self.assertIsNone(transform_weather_data(None, self.mock_conn))
        self.assertIsNone(transform_weather_data(pd.DataFrame(), self.mock_conn))

    def test_transform_success_pipeline(self):
        """Test toàn bộ 8 bước Transform thành công từ 24 giờ -> 1 dòng daily."""
        self._setup_transform_db_mocks([(3, 4)])
        transformed = transform_weather_data(self.raw_df, self.mock_conn)

        self.assertIsNotNone(transformed)
        self.assertIsInstance(transformed, pd.DataFrame)

        # Gom 24 giờ -> đúng 1 dòng đại diện cho ngày đó
        self.assertEqual(len(transformed), 1)

        # Kiểm tra đúng các cột đầu ra của Star Schema
        expected_columns = [
            "location_id",
            "date_id",
            "condition_id",
            "temperature",
            "humidity",
            "wind_speed",
            "recorded_at",
        ]
        self.assertEqual(list(transformed.columns), expected_columns)

        row = transformed.iloc[0]

        # Hà Nội trong settings có location_id = 1
        self.assertEqual(row["location_id"], 1)

        # Date 2026-08-30 được map sang date_id = 2434
        self.assertEqual(row["date_id"], 2434)

        # Weather code 3 được map sang condition_id = 4
        self.assertEqual(row["condition_id"], 4)

        # Kiểm tra tính toán trung bình nhiệt độ: (25.0 + 29.6) / 2 = 27.3
        self.assertAlmostEqual(row["temperature"], 27.3, places=1)
        self.assertEqual(row["humidity"], 80)
        self.assertEqual(row["wind_speed"], 10.0)

        # Kiểm tra múi giờ recorded_at đã được gán UTC+7
        self.assertEqual(row["recorded_at"].tzinfo, VN_TIMEZONE)

    def test_transform_out_of_range_validation(self):
        """Test lọc bỏ dữ liệu bất thường ngoài khoảng cho phép (ví dụ nhiệt độ 150°C)."""
        self._setup_transform_db_mocks([(3, 4)])
        bad_df = self.raw_df.copy()
        # Gán 1 dòng có nhiệt độ bất thường = 150°C
        bad_df.loc[0, "temperature"] = 150.0

        transformed = transform_weather_data(bad_df, self.mock_conn)

        # Dòng bị lỗi 150°C sẽ bị loại trước khi tính trung bình (còn 23 dòng hợp lệ)
        self.assertIsNotNone(transformed)
        self.assertEqual(len(transformed), 1)

    def test_transform_duplicate_hourly_deduplication(self):
        """Test tự động loại bỏ bản ghi bị trùng giờ trước khi aggregate."""
        self._setup_transform_db_mocks([(3, 4)])
        duplicated_df = pd.concat([self.raw_df, self.raw_df.iloc[[0]]], ignore_index=True)
        self.assertEqual(len(duplicated_df), 25)  # 24 dòng + 1 dòng trùng

        transformed = transform_weather_data(duplicated_df, self.mock_conn)

        # Kết quả vẫn gom sạch về 1 dòng daily duy nhất
        self.assertEqual(len(transformed), 1)

    def test_transform_unknown_weather_code(self):
        """Test khi gặp weather_code lạ chưa có trong dim_weather_condition -> condition_id là None (NaN)."""
        self._setup_transform_db_mocks([])  # dim_weather_condition không có mã 3

        transformed = transform_weather_data(self.raw_df, self.mock_conn)

        self.assertIsNotNone(transformed)
        row = transformed.iloc[0]
        # condition_id phải là NaN/None do không map được
        self.assertTrue(pd.isna(row["condition_id"]))


if __name__ == "__main__":
    unittest.main()
