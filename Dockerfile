# Production Dockerfile for ABLBL Afterhours Sentinel Surveillance System
# Based on validated CUDA 12.2 environment with full ONNX Runtime GPU support

FROM ablbl_attendancev1-recognition_engine:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV TZ=Asia/Kolkata
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cublas/lib:/usr/local/cuda/lib64:${LD_LIBRARY_PATH}

WORKDIR /app

# Copy application source code
COPY . .
RUN chmod +x /app/entrypoint.sh

# Expose Sentinel Port 9025
EXPOSE 9025

ENTRYPOINT ["/app/entrypoint.sh"]
CMD []
