#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "[*] Stopping ABLBL Afterhours Sentinel Surveillance System..."
docker compose down

echo "[✓] Afterhours containers stopped."
