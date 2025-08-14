# Sử dụng Python 3.12 slim để image nhẹ hơn
FROM python:3.12-slim

# Cài thư viện hệ thống cần thiết để build dlib, OpenCV, face_recognition
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libboost-all-dev \
    libopenblas-dev \
    liblapack-dev \
    python3-dev \
    libjpeg-dev \
    libpng-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy file requirements trước để tận dụng cache
COPY requirements.txt .

# Cài dependencies Python (bao gồm face_recognition, opencv-python)
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source code vào container
COPY . .

# Expose cổng Railway sẽ dùng
EXPOSE 8080

# Chạy Flask qua Gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--timeout", "120"]
