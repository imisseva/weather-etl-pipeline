import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestIsJupyter(unittest.TestCase):
    """Unit tests cho ham _is_jupyter() trong src.logger."""

    def test_is_jupyter_returns_false_when_ipython_not_installed(self):
        """Gia lap IPython chua duoc cai -> _is_jupyter() tra ve False."""
        with patch.dict("sys.modules", {"IPython": None}):
            # Reload de dam bao import lai sach
            import importlib
            import src.logger as logger_module
            importlib.reload(logger_module)
            result = logger_module._is_jupyter()
        self.assertFalse(result)

    def test_is_jupyter_returns_false_when_no_active_kernel(self):
        """get_ipython() tra ve None (chay script thuong) -> _is_jupyter() = False."""
        mock_ipython = MagicMock()
        mock_ipython.get_ipython.return_value = None

        with patch.dict("sys.modules", {"IPython": mock_ipython}):
            import importlib
            import src.logger as logger_module
            importlib.reload(logger_module)
            result = logger_module._is_jupyter()

        self.assertFalse(result)

    def test_is_jupyter_returns_true_when_kernel_active(self):
        """get_ipython() tra ve object (dang trong Jupyter) -> _is_jupyter() = True."""
        mock_ipython = MagicMock()
        mock_ipython.get_ipython.return_value = MagicMock()  # Kernel dang chay

        with patch.dict("sys.modules", {"IPython": mock_ipython}):
            import importlib
            import src.logger as logger_module
            importlib.reload(logger_module)
            result = logger_module._is_jupyter()

        self.assertTrue(result)


class TestGetLogger(unittest.TestCase):
    """Unit tests cho ham get_logger() trong src.logger."""

    def setUp(self):
        """Xoa cache logger truoc moi test de tranh handlers bi lap."""
        # Xoa tat ca logger co ten bat dau bang "test_" de tranh ket tu test khac
        for name in list(logging.Logger.manager.loggerDict.keys()):
            if name.startswith("test_logger_"):
                logger = logging.getLogger(name)
                logger.handlers.clear()

    def _get_fresh_logger(self, name: str) -> logging.Logger:
        """Helper: tao logger moi sach (khong co handler cu)."""
        logger = logging.getLogger(name)
        logger.handlers.clear()
        return logger

    def test_get_logger_returns_logger_instance(self):
        """get_logger() phai tra ve logging.Logger."""
        from src.logger import get_logger
        logger = get_logger("test_logger_instance")
        self.assertIsInstance(logger, logging.Logger)

    def test_get_logger_adds_handlers(self):
        """get_logger() phai them it nhat 1 handler (console + file)."""
        self._get_fresh_logger("test_logger_handlers")
        from src.logger import get_logger
        logger = get_logger("test_logger_handlers")
        self.assertGreaterEqual(len(logger.handlers), 1)

    def test_get_logger_no_duplicate_handlers(self):
        """Goi get_logger() nhieu lan voi cung ten -> khong bi them handler trung."""
        from src.logger import get_logger
        name = "test_logger_no_dup"
        logger1 = get_logger(name)
        handler_count_after_first = len(logger1.handlers)

        logger2 = get_logger(name)
        handler_count_after_second = len(logger2.handlers)

        self.assertEqual(handler_count_after_first, handler_count_after_second)
        self.assertIs(logger1, logger2)

    def test_get_logger_uses_correct_format(self):
        """Logger phai dung format: timestamp | level | module | message."""
        self._get_fresh_logger("test_logger_format")
        from src.logger import get_logger
        logger = get_logger("test_logger_format")

        # Lay handler dau tien (console handler)
        handler = logger.handlers[0]
        fmt = handler.formatter._fmt
        self.assertIn("%(asctime)s", fmt)
        self.assertIn("%(levelname)", fmt)
        self.assertIn("%(name)s", fmt)
        self.assertIn("%(message)s", fmt)

    def test_get_logger_file_handler_exists(self):
        """Logger phai co it nhat 1 FileHandler (ghi log ra file)."""
        self._get_fresh_logger("test_logger_file_handler")
        from src.logger import get_logger
        logger = get_logger("test_logger_file_handler")

        file_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.FileHandler)
        ]
        self.assertGreaterEqual(len(file_handlers), 1)

    def test_get_logger_console_handler_exists(self):
        """Logger phai co it nhat 1 StreamHandler (in ra console)."""
        self._get_fresh_logger("test_logger_console_handler")
        from src.logger import get_logger
        logger = get_logger("test_logger_console_handler")

        stream_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
        ]
        self.assertGreaterEqual(len(stream_handlers), 1)

    @patch("src.logger._is_jupyter", return_value=True)
    def test_get_logger_jupyter_uses_sys_stdout(self, mock_is_jupyter):
        """Khi chay trong Jupyter, console handler dung sys.stdout truc tiep."""
        name = "test_logger_jupyter_stdout"
        self._get_fresh_logger(name)

        from src.logger import get_logger
        logger = get_logger(name)

        # Tim console StreamHandler
        stream_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        self.assertGreaterEqual(len(stream_handlers), 1)
        # Handler phai dung sys.stdout
        self.assertEqual(stream_handlers[0].stream, sys.stdout)

    def test_get_logger_level_set_correctly(self):
        """Logger level phai duoc set theo LOG_LEVEL trong config."""
        from config.settings import LOG_LEVEL
        self._get_fresh_logger("test_logger_level")
        from src.logger import get_logger
        logger = get_logger("test_logger_level")

        expected_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
        self.assertEqual(logger.level, expected_level)

    @patch("src.logger._is_jupyter", return_value=False)
    def test_get_logger_fallback_to_sys_stdout_on_fileno_error(self, mock_is_jupyter):
        """Khi open(fileno()) that bai, fallback ve sys.stdout."""
        name = "test_logger_fallback_stdout"
        self._get_fresh_logger(name)

        with patch("builtins.open", side_effect=Exception("Cannot open fileno")):
            from src.logger import get_logger
            logger = get_logger(name)

        stream_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        self.assertGreaterEqual(len(stream_handlers), 1)


if __name__ == "__main__":
    unittest.main()
