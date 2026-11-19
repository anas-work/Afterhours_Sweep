# ABLBL Afterhours Sentinel — Frontend Integration Guide

This guide provides everything a frontend developer needs to integrate, build upon, or embed the **ABLBL Afterhours Sentinel** surveillance and intrusion detection system into external portals, mobile apps, or unified enterprise dashboards.

---

## 1. System Overview & Architecture

ABLBL Afterhours Sentinel operates as an automated, scheduled multi-camera surveillance and intrusion verification engine:
- **Phase 1: Recording**: Simultaneously captures video streams across all registered RTSP cameras for a configurable duration (default: 180s / 3 minutes).
- **Phase 2: GPU Batch Inference**: Extracts 1-FPS frames and feeds them in batches into **YOLO26n ONNX** on **NVIDIA RTX A4000 (GPU 0)**.
- **Phase 3: Real-Time Alarm & Evidence Dispatch**: If any person is detected, the engine instantly fires WebSocket alerts, saves annotated snapshot images with bounding boxes, and activates visual/audible alarms.

### Network Endpoints & Ports

| Service | Protocol | Host / URL | Default Port | Description |
| :--- | :--- | :--- | :--- | :--- |
| **REST API** | HTTP/1.1 | `http://<HOST>:9002/api` | `9002` | Management, triggering, telemetry & history |
| **Real-Time Stream** | WebSocket | `ws://<HOST>:9002/ws/events` | `9002` | Live state transitions, progress, and alerts |
| **Captured Evidence** | HTTP Static | `http://<HOST>:9002/captures/` | `9002` | Annotated intrusion snapshots (`.jpg`) |
| **Video Recordings** | HTTP Static | `http://<HOST>:9002/recordings/` | `9002` | Raw multi-camera MP4 video recordings |

> **CORS Policy**: CORS is enabled for all origins (`*`), allowing direct requests from any local or remote frontend port (`localhost:3000`, `localhost:5173`, etc.).

---

## 2. REST API Reference

All REST endpoints are prefixed with `/api`. Standard JSON is returned.

### 2.1 System Health & Live Status

#### `GET /api/health`
Returns system operational status, hardware binding, and software version.
```json
{
  "status": "healthy",
  "service": "ABLBL Afterhours Sentinel",
  "device": "NVIDIA RTX A4000 (GPU 0)",
  "version": "1.0.0"
}
```

#### `GET /api/status`
Returns the complete real-time status of the surveillance scheduler, countdowns, recording timers, and GPU telemetry.
```json
{
  "mode": "AUTO",                     // "AUTO" or "MANUAL"
  "current_state": "IDLE",            // "IDLE" | "RECORDING" | "PROCESSING" | "ALARM_ACTIVE" | "COMPLETED"
  "current_sweep_id": null,           // e.g. "sweep_20261001_144355" when active
  "scheduled_time": "23:30:00",       // IST 24-hr schedule
  "sweep_duration_seconds": 180,      // Configured window (seconds)
  "seconds_until_next_sweep": 31200,  // Integer seconds until next automated sweep
  "next_sweep_iso": "2026-10-01T23:30:00+05:30",
  "recording_elapsed_seconds": 0,
  "recording_remaining_seconds": 0,
  "is_alarm_active": false,
  "alarm_camera_info": "",
  "current_time_ist": "2026-10-01 15:02:39",
  "processing_time_sec": 5.57,
  "processing_fps": 26.8,
  "total_frames": 149,
  "processed_frames": 149,
  "telemetry": {
    "gpu_available": true,
    "gpu_name": "NVIDIA RTX A4000",
    "gpu_utilization_pct": 21,
    "gpu_memory_used_mb": 4813,
    "gpu_memory_total_mb": 16376,
    "gpu_memory_pct": 29.4,
    "cpu_utilization_pct": 81.2,
    "ram_used_mb": 66030.7,
    "ram_total_mb": 128487.9,
    "ram_utilization_pct": 52.8
  }
}
```

---

### 2.2 Surveillance Controls

#### `POST /api/mode`
Switch between automated schedule mode and manual on-demand mode.
- **Request Body**:
```json
{
  "mode": "MANUAL" // or "AUTO"
}
```
- **Response**:
```json
{
  "status": "success",
  "mode": "MANUAL"
}
```

#### `POST /api/sweep/start_manual`
*(Manual Mode Only)* Starts continuous recording across all active camera streams.
```json
{
  "status": "success",
  "message": "Manual surveillance sweep started [sweep_20261001_152000]"
}
```

#### `POST /api/sweep/stop_manual`
*(Manual Mode Only)* Stops manual recording and immediately triggers GPU batch inference.
```json
{
  "status": "success",
  "message": "Manual surveillance recording stopped. Analyzing footages on GPU..."
}
```

#### `POST /api/sweep/trigger`
*(Auto Mode / Testing)* Immediately triggers a full scheduled sweep (180s recording followed by batch analysis).
```json
{
  "status": "success",
  "message": "Surveillance sweep triggered."
}
```

#### `POST /api/sweep/silence_alarm`
Silences an active audible/visual alarm.
```json
{
  "status": "success",
  "message": "Alarm silenced"
}
```

#### `POST /api/flush`
Clears all historical sweeps, person detection records, raw video files, and snapshot images. Resets the scheduler to a pristine IDLE state.
```json
{
  "status": "success",
  "cleared": {
    "detections_cleared": 149,
    "sweeps_cleared": 2
  }
}
```

---

### 2.3 Settings & Configuration

#### `GET /api/settings`
Returns surveillance configuration parameters.
```json
{
  "mode": "AUTO",
  "scheduled_time": "23:30:00",
  "sweep_duration_seconds": 180
}
```

#### `POST /api/settings`
Updates schedule, mode, or sweep duration.
- **Request Body**:
```json
{
  "mode": "AUTO",
  "scheduled_time": "23:00:00",
  "sweep_duration_seconds": 180
}
```
- **Response**:
```json
{
  "status": "success",
  "settings": {
    "mode": "AUTO",
    "scheduled_time": "23:00:00",
    "sweep_duration_seconds": 180
  }
}
```

---

### 2.4 Detections & Evidence

#### `GET /api/detections`
Lists detected person captures with bounding boxes, confidence, and timestamps.
- **Query Parameters**:
  - `sweep_id` (optional): Filter by specific sweep ID.
  - `camera_id` (optional): Filter by specific camera ID.
  - `limit` (optional, default: 150): Maximum items to return.
- **Response**:
```json
[
  {
    "id": 107,
    "sweep_id": "sweep_20261001_144355",
    "camera_id": "cctv_dock_04",
    "camera_name": "Warehouse Dock Gate 4",
    "timestamp": "2026-10-01T14:47:27.391976",
    "video_offset_sec": 53.0,
    "person_count": 1,
    "max_confidence": 0.6328,
    "bounding_boxes": [
      [238, 1520, 1279, 2426] // [y_min, x_min, y_max, x_max]
    ],
    "capture_path": "data/captures/sweep_20261001_144355/cctv_dock_04_sec053_p1.jpg",
    "capture_url": "/captures/sweep_20261001_144355/cctv_dock_04_sec053_p1.jpg",
    "created_at": "2026-10-01T14:47:27.395511"
  }
]
```

#### `GET /api/detections/by_dock`
Aggregates and organizes person detections by camera / dock location to prevent UI clutter and display peak intrusion snapshots per dock.
- **Response**:
```json
[
  {
    "dock_id": "cctv_dock_01",
    "dock_name": "Warehouse Dock Gate 1",
    "location": "Dock 1",
    "total_frames": 39,
    "peak_confidence": 0.958,
    "peak_snapshot_url": "/captures/sweep_20261001_144355/cctv_dock_01_sec105_p1.jpg",
    "first_offset_sec": 0.0,
    "last_offset_sec": 190.0,
    "duration_sec": 190.0,
    "peak_detection": { /* Full detection object */ },
    "frames": [ /* Array of all alert snapshots in this dock */ ]
  }
]
```

---

### 2.5 Camera Management

#### `GET /api/cameras`
Lists all configured surveillance cameras.
```json
[
  {
    "id": "cctv_dock_01",
    "name": "Warehouse Dock Gate 1",
    "rtsp_url": "rtsp://127.0.0.1:8554/dock1",
    "location": "Dock 1",
    "is_active": true,
    "created_at": "2026-09-30T14:32:43.000722"
  }
]
```

#### `POST /api/cameras`
Adds a new camera or updates an existing camera stream.
- **Request Body**:
```json
{
  "id": "cctv_dock_12",
  "name": "North Gate Bay",
  "rtsp_url": "rtsp://192.168.1.105:554/stream1",
  "location": "North Bay",
  "is_active": true
}
```

#### `DELETE /api/cameras/{camera_id}`
Removes a camera from surveillance monitoring.

#### `POST /api/cameras/seed_cctv`
Seeds the standard 11 demo warehouse dock streams (`dock1` to `dock11`).

---

### 2.6 Past Sweeps

#### `GET /api/sweeps?limit=25`
Lists past surveillance sweep sessions with intruder counts and status.

#### `GET /api/sweeps/{sweep_id}`
Returns details of a specific sweep, including all associated detections.

---

## 3. Real-Time WebSocket Protocol

Connect to:
```
ws://<HOST>:9002/ws/events
```

All WebSocket messages are JSON payloads containing an `event` name and `data` dictionary:
```json
{
  "event": "<EVENT_NAME>",
  "data": { ... }
}
```

### Event Types & Payloads

| Event Name | Trigger | Payload Contents | Recommended UI Reaction |
| :--- | :--- | :--- | :--- |
| `STATUS_UPDATE` | On connect / state change | Full status dict (same as `GET /api/status`) | Sync top-level app state |
| `SWEEP_STARTED` | Sweep begins | `{ "sweep_id": str, "status": "RECORDING", "mode": str, "duration_seconds": int, "cameras_count": int }` | Switch UI badge to "Recording", start countdown |
| `RECORDING_TICK` | Every second during recording | `{ "elapsed_seconds": int, "remaining_seconds": int }` | Update recording timer display |
| `PROCESSING_STARTED` | Video captured, GPU starting | `{ "sweep_id": str, "status": "PROCESSING", "total_frames": int }` | Switch badge to "Analyzing Footages" |
| `PROCESSING_PROGRESS` | Inference batch processed | `{ "processed_frames": int, "total_frames": int, "progress_percent": float, "fps": float, "telemetry": { ... } }` | Update progress bar and live FPS indicator |
| `ALARM_TRIGGERED` | Intruder detected | `{ "sweep_id": str, "camera_id": str, "camera_name": str, "timestamp": str, "confidence": float, "capture_url": str }` | Trigger siren audio, show red flashing alarm banner, refresh detections |
| `ALARM_SILENCED` | User silenced alarm | `{ "status": "silenced" }` | Stop audio siren, hide flashing banner |
| `SWEEP_COMPLETED` | Sweep finished | `{ "sweep_id": str, "status": "COMPLETED", "processed_frames": int, "processing_fps": float, "processing_time_sec": float, "detections_count": int, "alarm_triggered": bool }` | Set progress to 100%, show summary toast, refresh history |
| `SYSTEM_FLUSHED` | System reset | `{ "status": "success" }` | Clear gallery items and reset badge to "Ready" |

---

## 4. Frontend Integration Examples

### 4.1 React Hook for Real-Time Sentinel Connection
```jsx
import { useEffect, useState, useRef } from 'react';

export function useSentinelWebSocket(host = window.location.host) {
  const [status, setStatus] = useState(null);
  const [alarm, setAlarm] = useState({ active: false, camera: '' });
  const [progress, setProgress] = useState(0);
  const wsRef = useRef(null);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${host}/ws/events`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const { event: evType, data } = JSON.parse(event.data);
        switch (evType) {
          case 'STATUS_UPDATE':
            setStatus(data);
            if (data.is_alarm_active) {
              setAlarm({ active: true, camera: data.alarm_camera_info });
            }
            break;
          case 'PROCESSING_PROGRESS':
            setProgress(data.progress_percent || 0);
            break;
          case 'ALARM_TRIGGERED':
            setAlarm({ active: true, camera: data.camera_name });
            break;
          case 'ALARM_SILENCED':
            setAlarm({ active: false, camera: '' });
            break;
          case 'SWEEP_COMPLETED':
            setProgress(100);
            break;
          default:
            break;
        }
      } catch (err) {
        console.error('WebSocket parse error:', err);
      }
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) ws.close();
    };
  }, [host]);

  return { status, alarm, progress };
}
```

### 4.2 Web Audio Multi-Tone Siren (Zero Audio Assets Required)
```javascript
let audioCtx = null;
let sirenInterval = null;

export function playSynthesizedSiren() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === 'suspended') audioCtx.resume();

  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type = 'sawtooth';
  gain.gain.value = 0.15;
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.start();

  let high = false;
  sirenInterval = setInterval(() => {
    osc.frequency.setValueAtTime(high ? 960 : 640, audioCtx.currentTime);
    high = !high;
  }, 280);

  return () => {
    clearInterval(sirenInterval);
    try { osc.stop(); osc.disconnect(); } catch (e) {}
  };
}
```

---

## 5. Security & Deployment Notes
- **Static Assets**: Images (`/captures/...`) and video clips (`/recordings/...`) are served directly by the FastAPI static mount. Use absolute paths or relative URLs as provided in the API response `capture_url`.
- **5-Second Pause Guarantee**: Consecutive frame alerts per camera are throttled by at least 5.0 seconds. The frontend does not need to deduplicate frames from the same second.
- **Port Reservation**: Default backend port is `9002` to avoid conflicts with ABLBL Attendance (`9001`) and PostgreSQL (`5433`).

---

## 6. aimdev Environment Deployment

> **Environment:** `aimdev`  
> **Server Host:** `106.51.83.253` (Public IP) / `192.168.0.32` (Internal LAN) / `127.0.0.1` (Localhost)  
> **Assigned Sentinel Engine Port:** `9025` (HTTP)  

### Network Endpoints & Ports

| Service Component | Protocol | Host / URL | Port | Description |
| :--- | :--- | :--- | :--- | :--- |
| **REST API Base** | HTTP/1.1 | `http://106.51.83.253:9025/api` | `9025` | Management, surveillance triggers, telemetry & history |
| **System Health Check** | HTTP/1.1 | `http://106.51.83.253:9025/api/health` | `9025` | GPU binding and engine health |
| **Real-Time Event Stream** | WebSocket | `ws://106.51.83.253:9025/ws/events` | `9025` | Live intrusion alerts, sweeps, and state changes |
| **Surveillance Status** | HTTP/1.1 | `http://106.51.83.253:9025/api/status` | `9025` | Telemetry, scheduler countdowns, and active sweep state |
| **Captured Evidence Snapshots** | HTTP Static | `http://106.51.83.253:9025/captures/` | `9025` | Annotated intrusion snapshots (`.jpg`) with bounding boxes |
| **Video Recordings** | HTTP Static | `http://106.51.83.253:9025/recordings/` | `9025` | Full multi-camera MP4 surveillance sweep recordings |

### Quick Verification Commands
```bash
# Verify Health Endpoint
curl -s http://106.51.83.253:9025/api/health

# Verify Scheduler Status
curl -s http://106.51.83.253:9025/api/status | head -n 20
```

### `/bv3` Migration & Deployment Notes
- **Repository Location:** `/bv3/anas/ABLBL_Afterhours`
- **Virtual Environment:** `/bv3/anas/ABLBL_Afterhours/.venv` (all shebangs and activate scripts updated for native `/bv3` execution).
- **Database & Storage:** Local SQLite at `data/afterhours.db` and recordings at `data/recordings`.
- **Native Startup Command:**
  ```bash
  cd /bv3/anas/ABLBL_Afterhours
  .venv/bin/uvicorn src.api.app:app --host 0.0.0.0 --port 9025
  ```
- **Verified Status:** Operational (HTTP 200 on Web UI, `/api/status`, and Swagger documentation).

