import unittest
from unittest.mock import MagicMock, patch

from src.quality_check import (
    check_completeness,
    check_nulls,
    check_uniqueness,
    check_value_ranges,
    run_quality_checks,
)


class TestQualityCheck(unittest.TestCase):
    """
    Unit tests cho module src/quality_check.py
    Gia lap connection va cursor PostgreSQL de test 4 bai kiem tra chat luong du lieu.
    """

    def setUp(self):
        """Thiet lap mock DB connection va cursor."""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__.return_value = self.mock_cursor

    def test_check_completeness_pass(self):
        """Test Check 1: Completeness - Du 63 tinh thanh -> PASS."""
        self.mock_cursor.fetchone.return_value = [63]

        result = check_completeness(self.mock_conn, target_date_id=2434)

        self.assertTrue(result)
        self.mock_cursor.execute.assert_called_once()

    def test_check_completeness_fail(self):
        """Test Check 1: Completeness - Chi co 50 tinh thanh -> FAIL."""
        self.mock_cursor.fetchone.return_value = [50]

        result = check_completeness(self.mock_conn, target_date_id=2434)

        self.assertFalse(result)

    def test_check_nulls_pass(self):
        """Test Check 2: Null Check - 0 ban ghi bi NULL -> PASS."""
        self.mock_cursor.fetchone.return_value = [0]

        result = check_nulls(self.mock_conn, target_date_id=2434)

        self.assertTrue(result)

    def test_check_nulls_fail(self):
        """Test Check 2: Null Check - Co 3 ban ghi bi NULL -> FAIL."""
        self.mock_cursor.fetchone.return_value = [3]

        result = check_nulls(self.mock_conn, target_date_id=2434)

        self.assertFalse(result)

    def test_check_uniqueness_pass(self):
        """Test Check 3: Uniqueness - 0 ban ghi bi trung lap -> PASS."""
        self.mock_cursor.fetchall.return_value = []

        result = check_uniqueness(self.mock_conn, target_date_id=2434)

        self.assertTrue(result)

    def test_check_uniqueness_fail(self):
        """Test Check 3: Uniqueness - Co 1 location bi trung -> FAIL."""
        self.mock_cursor.fetchall.return_value = [(1, 2)]

        result = check_uniqueness(self.mock_conn, target_date_id=2434)

        self.assertFalse(result)

    def test_check_value_ranges_pass(self):
        """Test Check 4: Value Range - Tat ca gia tri deu hop le -> PASS."""
        self.mock_cursor.fetchone.return_value = [0]

        result = check_value_ranges(self.mock_conn, target_date_id=2434)

        self.assertTrue(result)

    def test_check_value_ranges_fail(self):
        """Test Check 4: Value Range - Co 2 ban ghi nhiet do/do am bat thuong -> FAIL."""
        self.mock_cursor.fetchone.return_value = [2]

        result = check_value_ranges(self.mock_conn, target_date_id=2434)

        self.assertFalse(result)

    @patch("src.quality_check.check_value_ranges")
    @patch("src.quality_check.check_uniqueness")
    @patch("src.quality_check.check_nulls")
    @patch("src.quality_check.check_completeness")
    def test_run_quality_checks_all_pass(self, mock_c1, mock_c2, mock_c3, mock_c4):
        """Test hàm run_quality_checks khi ca 4 bai test deu PASS."""
        mock_c1.return_value = True
        mock_c2.return_value = True
        mock_c3.return_value = True
        mock_c4.return_value = True

        result = run_quality_checks(self.mock_conn, target_date_id=2434)

        self.assertTrue(result)

    @patch("src.quality_check.check_value_ranges")
    @patch("src.quality_check.check_uniqueness")
    @patch("src.quality_check.check_nulls")
    @patch("src.quality_check.check_completeness")
    def test_run_quality_checks_one_fail(self, mock_c1, mock_c2, mock_c3, mock_c4):
        """Test hàm run_quality_checks khi co 1 bai test FAIL."""
        mock_c1.return_value = True
        mock_c2.return_value = False  # Test 2 bi Fail
        mock_c3.return_value = True
        mock_c4.return_value = True

        result = run_quality_checks(self.mock_conn, target_date_id=2434)

        self.assertFalse(result)

    def test_run_quality_checks_none_connection(self):
        """Test run_quality_checks khi connection bang None -> return False."""
        result = run_quality_checks(None)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
