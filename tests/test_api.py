import os
import sys
import time
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.api.app import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_api_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "GPU 0" in data["device"]

def test_api_status(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "mode" in data
    assert "current_state" in data
    assert "scheduled_time" in data
    assert "sweep_duration_seconds" in data
    assert "telemetry" in data

def test_api_telemetry(client):
    response = client.get("/api/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert "gpu_available" in data
    assert "cpu_utilization_pct" in data
    assert "ram_used_mb" in data

def test_api_mode_toggle(client):
    resp = client.post("/api/mode", json={"mode": "MANUAL"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "MANUAL"

    resp = client.post("/api/mode", json={"mode": "AUTO"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "AUTO"

def test_api_cameras_and_cctv_seed(client):
    response = client.post("/api/cameras/seed_cctv")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    response = client.get("/api/cameras")
    assert response.status_code == 200
    cams = response.json()
    assert len(cams) >= 5
    assert any("cctv" in c["id"] for c in cams)

def test_api_settings_update(client):
    response = client.post("/api/settings", json={"scheduled_time": "23:30:00", "sweep_duration_seconds": 15})
    assert response.status_code == 200
    data = response.json()
    assert data["settings"]["scheduled_time"] == "23:30:00"
    assert data["settings"]["sweep_duration_seconds"] == 15

def test_api_silence_alarm(client):
    resp = client.post("/api/sweep/silence_alarm")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

def test_api_dashboard_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "ABLBL AFTERHOURS SENTINEL" in response.text
    assert "/dist/bundle.js" in response.text

    # Verify compiled production bundle delivery
    bundle_res = client.get("/dist/bundle.js")
    assert bundle_res.status_code == 200
    assert len(bundle_res.content) > 10000

    # Verify modular component source delivery
    cmd_res = client.get("/src/components/CommandCenter.jsx")
    assert cmd_res.status_code == 200
    assert "Start Surveillance" in cmd_res.text

def test_api_flush_and_by_dock(client):
    dock_res = client.get("/api/detections/by_dock")
    assert dock_res.status_code == 200
    assert isinstance(dock_res.json(), list)

    flush_res = client.post("/api/flush")
    assert flush_res.status_code == 200
    assert flush_res.json()["status"] == "success"
