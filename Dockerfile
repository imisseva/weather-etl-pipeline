# ============================================================================
# STAGE 1: BUILDER — Cài đặt dependencies vào virtual environment
# ============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Tách riêng requirements để tận dụng Docker layer cache
COPY requirements.txt .

# Tạo venv sạch, cài production deps (bỏ pytest/pytest-cov)
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \
    grep -Ev "pytest" requirements.txt | /opt/venv/bin/pip install --no-cache-dir -r /dev/stdin

# ============================================================================
# STAGE 2: RUNTIME — Image tối giản, chỉ chứa những gì cần thiết
# ============================================================================
FROM python:3.11-slim

LABEL maintainer="imisseva" \
      description="Vietnam Weather ETL Pipeline" \
      version="1.0.0"

WORKDIR /app

# Copy virtual environment từ builder (không cần pip, wheel, setuptools)
COPY --from=builder /opt/venv /opt/venv

# Biến môi trường
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app"

# Copy project files (theo thứ tự từ ít thay đổi đến hay thay đổi — tối ưu cache)
COPY config/ ./config/
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY main.py .

# Tạo thư mục logs (mount từ host vào đây)
RUN mkdir -p /app/logs

# Health check: kiểm tra kết nối DB trước khi coi container là healthy
HEALTHCHECK --interval=60s --timeout=15s --start-period=10s --retries=3 \
    CMD python scripts/test_connection.py || exit 1

# Entry point: chạy ETL pipeline
CMD ["python", "main.py"]
