import os
import yaml
import json
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

import src.api.routes as routes
from src.database.repository import AfterhoursRepository
from src.ml.yolo26_detector import YOLO26Detector
from src.recording.rtsp_recorder import RTSPRecorder
from src.processing.sweep_processor import SweepProcessor
from src.scheduler.sweep_scheduler import SweepScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ABLBL_Afterhours.App")

def create_app(config_path: str = "config/config.yaml") -> FastAPI:
    # Setup Event Loop / Broadcaster for WebSockets
    active_websockets = []
    main_loop = None

    # Load configuration
    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    db_cfg = config.get("database", {})
    db_url = os.environ.get("DATABASE_URL") or db_cfg.get("url", "sqlite:///data/afterhours.db")
    db_repo = AfterhoursRepository(db_url=db_url)

    # Hardware & ML configuration
    hw_cfg = config.get("hardware", {})
    ml_cfg = config.get("ml", {})
    device_id = hw_cfg.get("device_id", 0)
    batch_size = hw_cfg.get("batch_size", 16)
    num_extraction_workers = hw_cfg.get("num_extraction_workers", 8)
    model_path = ml_cfg.get("model_path", "models/yolo26n.onnx")
    conf_threshold = ml_cfg.get("confidence_threshold", 0.45)
    iou_threshold = ml_cfg.get("iou_threshold", 0.45)

    logger.info(f"Initializing YOLO26n Detector on GPU {device_id}...")
    detector = YOLO26Detector(
        model_path=model_path,
        device_id=device_id,
        conf_threshold=conf_threshold,
        iou_threshold=iou_threshold
    )

    # Storage paths
    storage_cfg = config.get("storage", {})
    recordings_dir = storage_cfg.get("recordings_dir", "data/recordings")
    captures_dir = storage_cfg.get("captures_dir", "data/captures")
    os.makedirs(recordings_dir, exist_ok=True)
    os.makedirs(captures_dir, exist_ok=True)

    recorder = RTSPRecorder(recordings_base_dir=recordings_dir)
    processor = SweepProcessor(
        detector=detector,
        db_repo=db_repo,
        captures_base_dir=captures_dir,
        batch_size=batch_size,
        num_extraction_workers=num_extraction_workers
    )

    def broadcast_sync(event_type: str, data: Dict[str, Any]):
        payload = json.dumps({"event": event_type, "data": data})
        to_remove = []
        for ws in list(active_websockets):
            try:
                if main_loop and main_loop.is_running():
                    asyncio.run_coroutine_threadsafe(ws.send_text(payload), main_loop)
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            if ws in active_websockets:
                active_websockets.remove(ws)

    surv_cfg = config.get("surveillance", {})
    sched_time = surv_cfg.get("default_scheduled_time", "22:00:00")
    sweep_dur = surv_cfg.get("sweep_duration_seconds", 180)
    max_stored = storage_cfg.get("max_stored_sweeps", 50)

    scheduler = SweepScheduler(
        recorder=recorder,
        processor=processor,
        db_repo=db_repo,
        default_scheduled_time=sched_time,
        default_sweep_duration=sweep_dur,
        max_stored_sweeps=max_stored,
        recordings_dir=recordings_dir,
        captures_dir=captures_dir,
        event_broadcaster=broadcast_sync
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal main_loop
        try:
            main_loop = asyncio.get_running_loop()
        except RuntimeError:
            main_loop = None
        scheduler.start()
        # Seed default warehouse dock cameras if empty
        if not db_repo.get_cameras():
            db_repo.add_or_update_camera("cctv_dock_01", "Warehouse Dock Gate 1", "rtsp://127.0.0.1:8554/afterhours/dock1", "Dock 1")
            db_repo.add_or_update_camera("cctv_dock_02", "Warehouse Dock Gate 2", "rtsp://127.0.0.1:8554/afterhours/dock2", "Dock 2")
            db_repo.add_or_update_camera("cctv_dock_03", "Warehouse Dock Gate 3", "rtsp://127.0.0.1:8554/afterhours/dock3", "Dock 3")
            db_repo.add_or_update_camera("cctv_dock_04", "Warehouse Dock Gate 4", "rtsp://127.0.0.1:8554/afterhours/dock4", "Dock 4")
            db_repo.add_or_update_camera("cctv_dock_05", "Warehouse Dock Gate 5", "rtsp://127.0.0.1:8554/afterhours/dock5", "Dock 5")
            db_repo.add_or_update_camera("cctv_dock_06", "Warehouse Dock Gate 6", "rtsp://127.0.0.1:8554/afterhours/dock6", "Dock 6")
            db_repo.add_or_update_camera("cctv_dock_07", "Warehouse Dock Gate 7", "rtsp://127.0.0.1:8554/afterhours/dock7", "Dock 7")
            db_repo.add_or_update_camera("cctv_dock_08", "Warehouse Dock Gate 8", "rtsp://127.0.0.1:8554/afterhours/dock8", "Dock 8")
            db_repo.add_or_update_camera("cctv_dock_09", "Warehouse Dock Gate 9", "rtsp://127.0.0.1:8554/afterhours/dock9", "Dock 9")
            db_repo.add_or_update_camera("cctv_dock_10", "Warehouse Dock Gate 10", "rtsp://127.0.0.1:8554/afterhours/dock10", "Dock 10")
            db_repo.add_or_update_camera("cctv_dock_11", "Warehouse Dock Gate 11", "rtsp://127.0.0.1:8554/afterhours/dock11", "Dock 11")
        yield
        scheduler.stop()

    app = FastAPI(
        title="ABLBL Afterhours Sentinel",
        description="High-Throughput Afterhours Surveillance & Intrusion Detection System powered by YOLO26n ONNX on NVIDIA GPU 0",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Inject singletons into routes
    routes.db_repo = db_repo
    routes.scheduler = scheduler
    routes.active_websockets = active_websockets

    app.include_router(routes.router)

    # WebSocket for real-time events
    @app.websocket("/ws/events")
    async def websocket_events(websocket: WebSocket):
        await websocket.accept()
        nonlocal main_loop
        main_loop = asyncio.get_running_loop()
        active_websockets.append(websocket)
        logger.info(f"WebSocket client connected. Active subscribers: {len(active_websockets)}")
        
        # Send initial status
        await websocket.send_text(json.dumps({"event": "STATUS_UPDATE", "data": scheduler.get_status()}))
        
        try:
            while True:
                # Keepalive / ping
                msg = await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in active_websockets:
                active_websockets.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining: {len(active_websockets)}")

    # Mount static assets
    app.mount("/captures", StaticFiles(directory=captures_dir), name="captures")
    app.mount("/recordings", StaticFiles(directory=recordings_dir), name="recordings")
    if os.path.exists("frontend/dist"):
        app.mount("/dist", StaticFiles(directory="frontend/dist"), name="frontend_dist")
    if os.path.exists("frontend/src"):
        app.mount("/src", StaticFiles(directory="frontend/src"), name="frontend_src")

    # Serve Frontend Dashboard
    @app.get("/", response_class=HTMLResponse)
    async def read_index():
        frontend_index = "frontend/index.html"
        if os.path.exists(frontend_index):
            with open(frontend_index, "r", encoding="utf-8") as f:
                return f.read()
        return "<h1>ABLBL Afterhours Sentinel Backend Active. Frontend loading...</h1>"

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 9025))
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=port, reload=False)
