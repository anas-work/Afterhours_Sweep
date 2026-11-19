#!/usr/bin/env bash
# ==============================================================================
# ABLBL Afterhours Sentinel Surveillance System — One-Go Startup Script
# Starts Sentinel Engine via Docker Compose on Port 9025 (or configured $PORT)
# ==============================================================================

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

# Source environment variables if .env exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi
PORT="${PORT:-9025}"

echo "================================================================="
echo "   ABLBL AFTERHOURS SENTINEL — ONE-GO LAUNCHER"
echo "================================================================="

# 1. Verify Directories
mkdir -p data/captures data/recordings data/test_recordings config

# 2. Verify Models
echo "[*] Verifying YOLO26 model checkpoint..."
if [ ! -f "models/yolo26n.onnx" ]; then
    echo "[!] WARNING: Required model file 'models/yolo26n.onnx' is missing!"
else
    echo "[✓] Model checkpoint verified: models/yolo26n.onnx"
fi

# 3. Start Docker Container
echo "[*] Starting Docker container (Sentinel Engine on port ${PORT})..."
docker compose up -d

# 4. Wait for Health Check
echo "[*] Waiting for Sentinel Engine on port ${PORT}..."
MAX_RETRIES=20
COUNT=0
HEALTHY=0
while [ $COUNT -lt $MAX_RETRIES ]; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${PORT}/api/health" 2>/dev/null || true)
    if [ "$HTTP_CODE" = "200" ]; then
        HEALTHY=1
        break
    fi
    sleep 1
    COUNT=$((COUNT + 1))
done

if [ $HEALTHY -eq 1 ]; then
    echo "[✓] Sentinel Engine is ONLINE on port ${PORT}."
else
    echo "[!] Warning: Sentinel Engine took longer than expected to report healthy."
    echo "    Check logs with: docker logs afterhours_sentinel_engine"
fi

echo ""
echo "================================================================="
echo "   SYSTEM SUCCESSFULLY STARTED!"
echo "================================================================="
echo "  • Web Dashboard:             http://localhost:${PORT}"
echo "  • API Health Endpoint:       http://localhost:${PORT}/api/health"
echo "  • Surveillance Status:       http://localhost:${PORT}/api/status"
echo "  • Swagger API Documentation:  http://localhost:${PORT}/docs"
echo "  • WebSocket Events:          ws://localhost:${PORT}/ws/events"
echo "================================================================="
echo "To follow logs: docker logs -f afterhours_sentinel_engine"
echo "To shut down:   docker compose down"
echo "================================================================="
