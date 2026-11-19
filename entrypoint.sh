#!/bin/bash
set -e

# Ensure runtime directories exist
mkdir -p /app/data/captures /app/data/recordings /app/data/test_recordings /app/config

# Configurable port (default 9025)
PORT="${PORT:-9025}"

echo "[ENTRYPOINT] Starting ABLBL Afterhours Sentinel Surveillance System on port ${PORT}..."
exec python3 -m uvicorn src.api.app:app --host 0.0.0.0 --port "${PORT}" "$@"
