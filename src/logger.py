import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# Fix Unicode encoding trên Windows terminal (cp1252 → utf-8)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def get_logger(name: str) -> logging.Logger:
    """
    Tạo và trả về một logger có cấu hình sẵn.

    Args:
        name: Tên logger, thường dùng __name__ của module gọi vào.

    Returns:
        logging.Logger đã được cấu hình với console + file handler.

    Example:
        from src.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Bắt đầu pipeline")
    """
    from config.settings import LOG_LEVEL, LOG_DIR  # import muộn để tránh circular import

    logger = logging.getLogger(name)

    # Tránh thêm handler trùng nếu logger đã được tạo trước đó
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # ──────────────────────────────────────────
    # Format log: timestamp | level | module | message
    # ──────────────────────────────────────────
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ──────────────────────────────────────────
    # Handler 1: In ra console (stdout)
    # ──────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1, closefd=False)
    logger.addHandler(console_handler)

    # ──────────────────────────────────────────
    # Handler 2: Ghi vào file, tự rotate mỗi ngày
    # Giữ lại 7 ngày log gần nhất
    # ──────────────────────────────────────────
    log_file = Path(LOG_DIR) / "pipeline.log"
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",      # rotate lúc 00:00
        interval=1,           # mỗi 1 ngày
        backupCount=7,        # giữ 7 file cũ
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
