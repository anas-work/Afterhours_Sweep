# Production Dockerfile for ABLBL Afterhours Sentinel Surveillance System
# NVIDIA CUDA accelerated YOLO26n Vision Engine & FastAPI Backend

FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV TZ=Asia/Kolkata

WORKDIR /app

# Install system dependencies & OpenCV runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt && \
    pip3 install --no-cache-dir "uvicorn[standard]>=0.22.0" "websockets>=12.0"

# Copy application source code
COPY . .

# Expose Sentinel Port 9002
EXPOSE 9002

CMD ["python3", "-m", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "9002"]
