# ABLBL Afterhours Sentinel
### Automated Scheduled Multi-Camera Surveillance & Person Detection Engine
Powered by **YOLO26n ONNX** on **NVIDIA RTX A4000 (GPU 0)**

---

## 📌 Overview

**ABLBL Afterhours Sentinel** is a high-performance afterhours facility surveillance and intrusion verification system designed to monitor premises across multiple RTSP camera feeds. 

Unlike conventional continuous motion systems that trigger frequent false alarms from shadows or dust, Sentinel operates on an automated, scheduled surveillance cycle:
1. **Scheduled Start**: Automatically triggers at a programmed hour (e.g. 23:30:00 IST) or on manual demand.
2. **Concurrent Multi-Camera Recording**: Simultaneously records a 3-minute video window across all active RTSP camera streams (11 docks out of the box, scalable to 200 cameras).
3. **Parallel 1-FPS GPU Ingestion**: Once video capture completes, footages are decoded at ~1 FPS using batched **YOLO26n ONNX** accelerated on NVIDIA GPU 0.
4. **Intrusion Alarm & Evidence Capture**: If a person is detected, an audible and visual alarm is immediately tripped on the dashboard, saving annotated evidence snapshots with bounding boxes, person counts, timestamps, and camera locations.
5. **Smart De-duplication**: Consecutive alert snapshots per camera are throttled by at least 5.0 seconds, eliminating alert spam while tracking movement.

---

## ⚡ High-Throughput Architecture & Hardware

- **Target GPU**: NVIDIA RTX A4000 (GPU 0, 16 GB VRAM)
- **Model**: YOLO26n ONNX with `CUDAExecutionProvider`
- **Inference Speed**: ~40–60 FPS per batch (tested at 41.0 FPS across 2,433 frames in 59.33s)
- **Confidence Threshold**: 0.45 (45% confidence cutoff)
- **200-Camera Scalability**: All 36,000 frames from 200 cameras analyzed in under 60 seconds with 8 parallel extraction workers and dynamic batch queues.

---

## 🚀 Quickstart

### 1. Requirements
- Python 3.10+
- NVIDIA GPU with CUDA & cuDNN
- ONNX Runtime GPU (`onnxruntime-gpu`)
- MediaMTX (Docker or standalone binary)
- OpenCV, FastAPI, Uvicorn, SQLAlchemy

### 2. Start Streaming & Sentinel Server
```bash
cd /h3/anas/ABLBL_Afterhours

# Step 1: Ensure MediaMTX RTSP Server is running
docker start mtx_rtsp_test

# Step 2: Start 11-camera RTSP background loop publisher
nohup python3 scripts/publish_demo_rtsp_streams.py > /dev/null 2>&1 &

# Step 3: Launch the Sentinel Backend
python3 -m uvicorn src.api.app:app --host 0.0.0.0 --port 9002
```

### 3. Open the Dashboard
Navigate to:
```
http://49.206.228.75:9002
http://localhost:9002
```

### 4. Run Automated Tests
```bash
python3 -m pytest tests/test_api.py tests/test_afterhours.py -v
```

---

## 📚 Documentation & Integration Guides

- **[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)**: Comprehensive guide for frontend engineers including REST APIs, WebSocket events, React hooks, Web Audio synthesizer siren, and JSON schemas.
- **[startup_commands.txt](startup_commands.txt)**: Complete cheat sheet for operators, background daemons, port mappings, and curl commands.

---

## 📡 REST API & WebSocket Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Health check & GPU 0 verification |
| `GET` | `/api/status` | Real-time scheduler state, timers, FPS, and telemetry |
| `POST` | `/api/mode` | Switch mode (`"AUTO"` or `"MANUAL"`) |
| `POST` | `/api/sweep/trigger` | Trigger immediate surveillance sweep |
| `POST` | `/api/sweep/start_manual` | Start continuous manual recording |
| `POST` | `/api/sweep/stop_manual` | Stop manual recording and run GPU analysis |
| `POST` | `/api/sweep/silence_alarm` | Silence active sirens and alarm banners |
| `POST` | `/api/flush` | Flush all sweeps, captures, and database history |
| `GET` | `/api/detections` | List person detections with bounding boxes |
| `GET` | `/api/detections/by_dock` | Consolidated detections grouped by warehouse dock |
| `GET` | `/api/cameras` | List registered RTSP camera streams |
| `POST` | `/api/cameras` | Add or update a camera feed |
| `POST` | `/api/cameras/seed_cctv` | Seed default 11 warehouse dock streams |
| `GET` | `/api/sweeps` | List historical surveillance sweeps |
| `WS` | `/ws/events` | Real-time WebSocket event broadcaster |
| `STATIC` | `/captures/{file}` | Annotated evidence snapshots (`.jpg`) |

---

## 🏗 Repository Structure

```
ABLBL_Afterhours/
├── config/
│   └── config.yaml             # Core system, GPU, database & surveillance settings
├── data/                       # Local SQLite DB (WAL mode), captures & clips
│   ├── afterhours.db
│   ├── captures/               # Annotated intrusion JPEG snapshots
│   └── recordings/             # 3-minute multi-camera MP4 video recordings
├── frontend/                   # Modern React + Tailwind minimalist dashboard
│   ├── dist/bundle.js          # Compiled client bundle
│   ├── src/                    # Modular components (CommandCenter, DetectionsGallery, etc.)
│   └── index.html
├── models/
│   └── yolo26n.onnx            # YOLO26n ONNX weights for GPU 0
├── scripts/
│   ├── publish_demo_rtsp_streams.py  # MediaMTX 11-camera RTSP streaming loop
│   └── setup_test_streams.py
├── src/
│   ├── api/                    # FastAPI app & REST/WebSocket routes
│   ├── database/               # SQLAlchemy models & repository
│   ├── ml/                     # YOLO26n detector & hardware telemetry
│   ├── processing/             # 1-FPS frame extractor & GPU batch processor
│   ├── recording/              # Multi-camera RTSP recorder
│   └── scheduler/              # Automated IST sweep scheduler & alarm state machine
├── test_videos/                # 11 sample CCTV dock test videos
├── tests/                      # Automated pytest unit & integration test suite
├── INTEGRATION_GUIDE.md        # Dedicated frontend developer integration guide
├── startup_commands.txt        # Operations reference & CLI commands
└── Dockerfile & docker-compose.yml
```
