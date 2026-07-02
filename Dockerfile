FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p storage/uploads storage/outputs storage/logs storage/jobs storage/temp models

EXPOSE 8000

# Dùng shell form (không phải JSON array) để $PORT được Railway inject và expand đúng lúc chạy.
# Nếu chạy local không có PORT, mặc định dùng 8000.
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
