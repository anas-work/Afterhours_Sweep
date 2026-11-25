import os
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.database.repository import AfterhoursRepository
from src.scheduler.sweep_scheduler import SweepScheduler
from src.ml.telemetry import get_system_telemetry
from scripts.setup_test_streams import copy_test_videos

router = APIRouter(prefix="/api")

# Injected by app.py
db_repo: Optional[AfterhoursRepository] = None
scheduler: Optional[SweepScheduler] = None
active_websockets: List[WebSocket] = []

class CameraCreateRequest(BaseModel):
    id: str
    name: str
    rtsp_url: str
    location: Optional[str] = "Main Facility"
    is_active: Optional[bool] = True

class SettingsUpdateRequest(BaseModel):
    scheduled_time: Optional[str] = None
    sweep_duration_seconds: Optional[int] = None
    mode: Optional[str] = None

class ModeRequest(BaseModel):
    mode: str  # "AUTO" or "MANUAL"

@router.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "ABLBL Afterhours Sentinel",
        "device": "NVIDIA RTX A4000 (GPU 0)",
        "version": "1.0.0"
    }

@router.get("/status")
def get_status():
    if not scheduler:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")
    return scheduler.get_status()

@router.get("/telemetry")
def get_telemetry():
    return get_system_telemetry(device_id=0)

@router.post("/mode")
def set_mode(payload: ModeRequest):
    if not scheduler:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")
    if payload.mode not in ["AUTO", "MANUAL"]:
        raise HTTPException(status_code=400, detail="Mode must be 'AUTO' or 'MANUAL'")
    scheduler.set_mode(payload.mode)
    return {"status": "success", "mode": scheduler.mode}

# Manual Mode Controls
@router.post("/sweep/start_manual")
def start_manual_sweep():
    if not scheduler:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")
    try:
        msg = scheduler.start_manual_recording()
        return {"status": "success", "message": msg}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/sweep/stop_manual")
def stop_manual_sweep():
    if not scheduler:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")
    try:
        msg = scheduler.stop_manual_recording()
        return {"status": "success", "message": msg}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Auto Mode Trigger
@router.post("/sweep/trigger")
def trigger_sweep():
    if not scheduler:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")
    try:
        msg = scheduler.trigger_sweep_now()
        return {"status": "success", "message": msg}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/sweep/silence_alarm")
def silence_alarm():
    if not scheduler:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")
    scheduler.silence_alarm()
    return {"status": "success", "message": "Alarm silenced"}

@router.post("/flush")
def flush_history():
    """Flushes all database sweeps, detections, recording clips, and capture images."""
    if not scheduler:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")
    res = scheduler.flush_all_data()
    return res

@router.get("/sweeps")
def list_sweeps(limit: int = 25):
    sweeps = db_repo.get_sweeps(limit=limit)
    return [s.to_dict() for s in sweeps]

@router.get("/sweeps/{sweep_id}")
def get_sweep(sweep_id: str):
    sweep = db_repo.get_sweep_by_id(sweep_id)
    if not sweep:
        raise HTTPException(status_code=404, detail="Sweep not found")
    detections = db_repo.get_detections(sweep_id=sweep_id, limit=200)
    data = sweep.to_dict()
    data["detections"] = [d.to_dict() for d in detections]
    return data

@router.get("/detections")
def list_detections(sweep_id: Optional[str] = None, camera_id: Optional[str] = None, limit: int = 150):
    dets = db_repo.get_detections(sweep_id=sweep_id, camera_id=camera_id, limit=limit)
    return [d.to_dict() for d in dets]

@router.get("/detections/by_dock")
def list_detections_by_dock(sweep_id: Optional[str] = None):
    """Returns detections consolidated and organized per dock / camera location."""
    if not db_repo:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return db_repo.get_detections_by_dock(sweep_id=sweep_id)

@router.get("/cameras")
def list_cameras():
    cams = db_repo.get_cameras(active_only=False)
    return [c.to_dict() for c in cams]

@router.post("/cameras")
def add_camera(payload: CameraCreateRequest):
    cam = db_repo.add_or_update_camera(
        camera_id=payload.id,
        name=payload.name,
        rtsp_url=payload.rtsp_url,
        location=payload.location or "Premises",
        is_active=payload.is_active if payload.is_active is not None else True
    )
    return {"status": "success", "camera": cam.to_dict()}

@router.delete("/cameras/{camera_id}")
def delete_camera(camera_id: str):
    success = db_repo.delete_camera(camera_id)
    if not success:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"status": "success", "message": f"Camera {camera_id} deleted"}

@router.post("/cameras/seed_cctv")
def seed_cctv_streams():
    """Copies sample CCTV test footages from ABLBL_AttendanceV1 and configures them as camera streams."""
    vids = copy_test_videos()
    created = []
    
    cctv_configs = [
        ("cctv_dock_01", "Warehouse Dock Gate 1", "rtsp://127.0.0.1:8554/afterhours/dock1", "Dock 1"),
        ("cctv_dock_02", "Warehouse Dock Gate 2", "rtsp://127.0.0.1:8554/afterhours/dock2", "Dock 2"),
        ("cctv_dock_03", "Warehouse Dock Gate 3", "rtsp://127.0.0.1:8554/afterhours/dock3", "Dock 3"),
        ("cctv_dock_04", "Warehouse Dock Gate 4", "rtsp://127.0.0.1:8554/afterhours/dock4", "Dock 4"),
        ("cctv_dock_05", "Warehouse Dock Gate 5", "rtsp://127.0.0.1:8554/afterhours/dock5", "Dock 5"),
        ("cctv_dock_06", "Warehouse Dock Gate 6", "rtsp://127.0.0.1:8554/afterhours/dock6", "Dock 6"),
        ("cctv_dock_07", "Warehouse Dock Gate 7", "rtsp://127.0.0.1:8554/afterhours/dock7", "Dock 7"),
        ("cctv_dock_08", "Warehouse Dock Gate 8", "rtsp://127.0.0.1:8554/afterhours/dock8", "Dock 8"),
        ("cctv_dock_09", "Warehouse Dock Gate 9", "rtsp://127.0.0.1:8554/afterhours/dock9", "Dock 9"),
        ("cctv_dock_10", "Warehouse Dock Gate 10", "rtsp://127.0.0.1:8554/afterhours/dock10", "Dock 10"),
        ("cctv_dock_11", "Warehouse Dock Gate 11", "rtsp://127.0.0.1:8554/afterhours/dock11", "Dock 11"),
    ]

    for cid, name, path, loc in cctv_configs:
        cam = db_repo.add_or_update_camera(cid, name, path, loc, True)
        created.append(cam.to_dict())

    return {"status": "success", "count": len(created), "cameras": created}

@router.get("/settings")
def get_settings():
    return {
        "mode": scheduler.mode if scheduler else "AUTO",
        "scheduled_time": scheduler.scheduled_time_str if scheduler else "22:00:00",
        "sweep_duration_seconds": scheduler.sweep_duration if scheduler else 180
    }

@router.post("/settings")
def update_settings(payload: SettingsUpdateRequest):
    if payload.mode:
        scheduler.set_mode(payload.mode)
    if payload.scheduled_time:
        scheduler.set_scheduled_time(payload.scheduled_time)
    if payload.sweep_duration_seconds:
        scheduler.set_sweep_duration(payload.sweep_duration_seconds)
    return {
        "status": "success",
        "settings": {
            "mode": scheduler.mode,
            "scheduled_time": scheduler.scheduled_time_str,
            "sweep_duration_seconds": scheduler.sweep_duration
        }
    }
