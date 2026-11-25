import os
import shutil
import time
import logging
import datetime
import threading
from typing import Dict, Any, List, Optional, Callable

from src.recording.rtsp_recorder import RTSPRecorder
from src.processing.sweep_processor import SweepProcessor
from src.database.repository import AfterhoursRepository
from src.database.models import get_ist_now, IST
from src.ml.telemetry import get_system_telemetry

logger = logging.getLogger("ABLBL_Afterhours.SweepScheduler")

class SweepScheduler:
    """
    Coordinates afterhours surveillance sweeps.
    Supports both AUTO mode (scheduled clock trigger) and MANUAL mode (Start/Stop recording buttons),
    broadcasting live timer, hardware metrics, and alarm triggers.
    """
    def __init__(
        self,
        recorder: RTSPRecorder,
        processor: SweepProcessor,
        db_repo: AfterhoursRepository,
        default_scheduled_time: str = "22:00:00",
        default_sweep_duration: int = 180,
        max_stored_sweeps: int = 5,
        recordings_dir: str = "data/recordings",
        captures_dir: str = "data/captures",
        event_broadcaster: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ):
        self.recorder = recorder
        self.processor = processor
        self.db_repo = db_repo
        self.scheduled_time_str = default_scheduled_time
        self.sweep_duration = default_sweep_duration
        self.max_stored_sweeps = max(1, int(max_stored_sweeps))
        self.recordings_dir = recordings_dir
        self.captures_dir = captures_dir
        self.event_broadcaster = event_broadcaster

        self.mode = "AUTO"  # "AUTO" or "MANUAL"
        self.current_state = "IDLE"  # IDLE, RECORDING, PROCESSING, ALARM_ACTIVE, COMPLETED
        self.current_sweep_id: Optional[str] = None
        self.sweep_start_timestamp: Optional[float] = None
        self.recording_elapsed_sec = 0
        self.is_alarm_active = False
        self.alarm_camera_info = ""

        # Performance & Testing Metrics
        self.last_processing_time_sec = 0.0
        self.last_processing_fps = 0.0
        self.last_total_frames = 0
        self.last_processed_frames = 0

        self._lock = threading.Lock()
        self._stop_scheduler = threading.Event()
        self._manual_trigger_event = threading.Event()
        self._manual_stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._active_sweep_thread: Optional[threading.Thread] = None

        # Load persisted settings
        saved_sched = self.db_repo.get_setting("scheduled_time")
        if saved_sched:
            self.scheduled_time_str = saved_sched
        saved_dur = self.db_repo.get_setting("sweep_duration")
        if saved_dur:
            try:
                self.sweep_duration = int(saved_dur)
            except ValueError:
                pass
        saved_mode = self.db_repo.get_setting("operation_mode")
        if saved_mode in ["AUTO", "MANUAL"]:
            self.mode = saved_mode

    def start(self):
        if self._scheduler_thread is None or not self._scheduler_thread.is_alive():
            self._stop_scheduler.clear()
            self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self._scheduler_thread.start()
            logger.info(f"SweepScheduler started. Mode: {self.mode}, Schedule: {self.scheduled_time_str} IST")

    def stop(self):
        self._stop_scheduler.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=1.5)

    def set_mode(self, new_mode: str) -> None:
        """Switches between 'AUTO' and 'MANUAL' operation modes."""
        with self._lock:
            if new_mode in ["AUTO", "MANUAL"]:
                self.mode = new_mode
                self.db_repo.set_setting("operation_mode", new_mode)
                logger.info(f"Switched operation mode to: {self.mode}")
        self._emit_status_event()

    def set_scheduled_time(self, time_str: str) -> None:
        with self._lock:
            self.scheduled_time_str = time_str
            self.db_repo.set_setting("scheduled_time", time_str)
        self._emit_status_event()

    def set_sweep_duration(self, seconds: int) -> None:
        with self._lock:
            self.sweep_duration = max(5, int(seconds))
            self.db_repo.set_setting("sweep_duration", str(self.sweep_duration))
        self._emit_status_event()

    # --------- MANUAL MODE CONTROLS ---------
    def start_manual_recording(self) -> str:
        """Starts recording immediately in Manual Mode."""
        with self._lock:
            if self.current_state in ["RECORDING", "PROCESSING"]:
                raise RuntimeError(f"Sweep already running ({self.current_state})")
            
            # Start asynchronous sweep thread with large max timeout (manual stop will end it)
            self._active_sweep_thread = threading.Thread(
                target=self._execute_full_sweep,
                kwargs={"is_scheduled": False, "is_manual_controlled": True},
                daemon=True
            )
            self._active_sweep_thread.start()
        return "Manual surveillance recording initiated."

    def stop_manual_recording(self) -> str:
        """Stops active recording immediately and advances to processing."""
        with self._lock:
            if self.current_state != "RECORDING":
                raise RuntimeError("No recording is currently active to stop.")
            self.recorder.stop_active_recording()
        return "Recording stopped. Advancing to GPU processing..."

    # --------- AUTO MODE TRIGGER ---------
    def trigger_sweep_now(self) -> str:
        """Triggers an immediate automated timed sweep (e.g. 3-minute recording)."""
        with self._lock:
            if self.current_state in ["RECORDING", "PROCESSING"]:
                raise RuntimeError(f"A sweep is already running ({self.current_state})")
            
            self._active_sweep_thread = threading.Thread(
                target=self._execute_full_sweep,
                kwargs={"is_scheduled": False, "is_manual_controlled": False},
                daemon=True
            )
            self._active_sweep_thread.start()
        return "Surveillance sweep triggered."

    def silence_alarm(self) -> None:
        with self._lock:
            self.is_alarm_active = False
            if self.current_state == "ALARM_ACTIVE":
                self.current_state = "COMPLETED"
        self._broadcast("ALARM_SILENCED", {"status": "silenced"})
        self._emit_status_event()

    def flush_all_data(self) -> Dict[str, Any]:
        """Flushes all database records, recordings, captures, and resets alarm state."""
        import shutil
        with self._lock:
            self.is_alarm_active = False
            self.alarm_camera_info = ""
            self.current_state = "IDLE"
            self.current_sweep_id = None
            self.last_sweep_id = None
            self.last_processed_frames = 0
            self.last_total_frames = 0
            self.last_processing_fps = 0.0
            self.last_processing_time_sec = 0.0

        # DB clear
        db_res = self.db_repo.flush_all_history()

        # Filesystem clear for recordings and captures
        for target_dir in ["data/recordings", "data/captures"]:
            if os.path.exists(target_dir):
                for item in os.listdir(target_dir):
                    item_path = os.path.join(target_dir, item)
                    try:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path, ignore_errors=True)
                        else:
                            os.remove(item_path)
                    except Exception as err:
                        logger.warning(f"Error cleaning {item_path}: {err}")

        self._broadcast("SYSTEM_FLUSHED", {"status": "success", "db": db_res})
        self._emit_status_event()
        logger.info(f"System history and evidence captures flushed successfully: {db_res}")
        return {"status": "success", "cleared": db_res}

    def get_status(self) -> Dict[str, Any]:
        now_ist = get_ist_now()
        next_sweep_dt = self._calculate_next_scheduled_datetime()
        seconds_until_next = max(0, int((next_sweep_dt - now_ist).total_seconds()))

        elapsed_sec = 0
        remaining_sec = 0
        if self.current_state == "RECORDING" and self.sweep_start_timestamp:
            elapsed_sec = int(time.time() - self.sweep_start_timestamp)
            remaining_sec = max(0, self.sweep_duration - elapsed_sec)

        telemetry = get_system_telemetry(device_id=0)

        return {
            "mode": self.mode,
            "current_state": self.current_state,
            "current_sweep_id": self.current_sweep_id,
            "scheduled_time": self.scheduled_time_str,
            "sweep_duration_seconds": self.sweep_duration,
            "seconds_until_next_sweep": seconds_until_next,
            "next_sweep_iso": next_sweep_dt.isoformat(),
            "recording_elapsed_seconds": elapsed_sec,
            "recording_remaining_seconds": remaining_sec,
            "is_alarm_active": self.is_alarm_active,
            "alarm_camera_info": self.alarm_camera_info,
            "current_time_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S"),
            # Performance stats
            "processing_time_sec": self.last_processing_time_sec,
            "processing_fps": self.last_processing_fps,
            "total_frames": self.last_total_frames,
            "processed_frames": self.last_processed_frames,
            "telemetry": telemetry
        }

    def _calculate_next_scheduled_datetime(self) -> datetime.datetime:
        now_ist = get_ist_now()
        parts = [int(p) for p in self.scheduled_time_str.split(":")[:3]]
        hour = parts[0]
        minute = parts[1] if len(parts) > 1 else 0
        second = parts[2] if len(parts) > 2 else 0

        target_today = now_ist.replace(hour=hour, minute=minute, second=second, microsecond=0)
        if target_today > now_ist:
            return target_today
        else:
            return target_today + datetime.timedelta(days=1)

    def _scheduler_loop(self):
        """Continuous background clock checker."""
        while not self._stop_scheduler.is_set():
            now_ist = get_ist_now()

            # Timer tick broadcast if recording
            if self.current_state == "RECORDING" and self.sweep_start_timestamp:
                self.recording_elapsed_sec = int(time.time() - self.sweep_start_timestamp)
                self._broadcast("TIMER_TICK", {
                    "elapsed_seconds": self.recording_elapsed_sec,
                    "sweep_id": self.current_sweep_id,
                    "mode": self.mode
                })

            # Check Auto Mode clock schedule
            if self.mode == "AUTO":
                curr_time_str = now_ist.strftime("%H:%M:%S")
                sched_normalized = self.scheduled_time_str if len(self.scheduled_time_str.split(":")) == 3 else f"{self.scheduled_time_str}:00"
                if curr_time_str == sched_normalized and self.current_state in ["IDLE", "COMPLETED"]:
                    logger.info(f"Auto Mode triggered at {curr_time_str} IST!")
                    self.trigger_sweep_now()

            time.sleep(1.0)

    def _execute_full_sweep(self, is_scheduled: bool = False, is_manual_controlled: bool = False):
        now_ist = get_ist_now()
        sweep_id = f"sweep_{now_ist.strftime('%Y%m%d_%H%M%S')}"

        with self._lock:
            self.current_state = "RECORDING"
            self.current_sweep_id = sweep_id
            self.sweep_start_timestamp = time.time()
            self.is_alarm_active = False
            self.alarm_camera_info = ""

        # Fetch active cameras
        cameras_models = self.db_repo.get_cameras(active_only=True)
        if not cameras_models:
            self.db_repo.add_or_update_camera("cam_01", "Gate Entrance (CCTV)", "test_videos/test_cctv_gate.mp4", "Main Gate")
            self.db_repo.add_or_update_camera("cam_02", "Loading Dock Area", "test_videos/5978967-uhd_4096_2160_30fps.mp4", "Dock 1")
            self.db_repo.add_or_update_camera("cam_03", "Warehouse Corridor", "test_videos/8684258-hd_1920_1080_25fps.mp4", "Aisle 4")
            cameras_models = self.db_repo.get_cameras(active_only=True)

        cameras_list = [c.to_dict() for c in cameras_models]
        camera_names = {c["id"]: c["name"] for c in cameras_list}

        max_dur = 3600 if is_manual_controlled else self.sweep_duration

        self.db_repo.create_sweep(
            sweep_id=sweep_id,
            scheduled_time=now_ist if is_scheduled else None,
            duration_seconds=self.sweep_duration,
            total_cameras=len(cameras_list)
        )

        logger.info(f"=== SURVEILLANCE SWEEP STARTED [{sweep_id}] (Mode: {self.mode}) ===")
        self._broadcast("SWEEP_STARTED", {
            "sweep_id": sweep_id,
            "status": "RECORDING",
            "mode": self.mode,
            "cameras_count": len(cameras_list),
            "duration_seconds": self.sweep_duration
        })

        # Phase 1: Recording
        try:
            video_paths = self.recorder.record_cameras_concurrently(
                sweep_id=sweep_id,
                cameras=cameras_list,
                duration_seconds=max_dur
            )
        except Exception as rec_err:
            logger.error(f"Recording error: {rec_err}")
            self.db_repo.update_sweep_status(sweep_id, status="FAILED")
            self.current_state = "IDLE"
            self._emit_status_event()
            return

        # Phase 2: Parallel 1-FPS Processing on GPU 0
        with self._lock:
            self.current_state = "PROCESSING"

        self._broadcast("PROCESSING_STARTED", {"sweep_id": sweep_id, "status": "PROCESSING"})

        def on_proc_progress(processed, total, current_fps):
            self.last_processed_frames = processed
            self.last_total_frames = total
            self.last_processing_fps = current_fps
            self._broadcast("PROCESSING_PROGRESS", {
                "sweep_id": sweep_id,
                "processed_frames": processed,
                "total_frames": total,
                "fps": round(current_fps, 1),
                "progress_percent": round((processed / max(1, total)) * 100, 1),
                "telemetry": get_system_telemetry(0)
            })

        def on_person_found(det_dict):
            with self._lock:
                self.is_alarm_active = True
                self.alarm_camera_info = f"{det_dict['camera_name']} ({det_dict['camera_id']})"
            logger.warning(f"🚨 INTRUSION ALERT! Person detected on {det_dict['camera_name']}")
            self._broadcast("ALARM_TRIGGERED", {
                "sweep_id": sweep_id,
                "detection": det_dict,
                "camera_name": det_dict['camera_name'],
                "camera_id": det_dict['camera_id'],
                "person_count": det_dict['person_count'],
                "max_confidence": det_dict['max_confidence'],
                "capture_url": det_dict['capture_url']
            })

        try:
            summary = self.processor.process_sweep_videos(
                sweep_id=sweep_id,
                camera_video_paths=video_paths,
                camera_names=camera_names,
                on_progress=on_proc_progress,
                on_person_detected=on_person_found
            )
            self.last_processing_time_sec = summary["duration_sec"]
            self.last_processing_fps = summary["processing_fps"]
            self.last_processed_frames = summary["processed_frames"]
            self.last_total_frames = summary["total_frames"]
        except Exception as proc_err:
            logger.error(f"Processing error: {proc_err}")
            self.db_repo.update_sweep_status(sweep_id, status="FAILED")
            self.current_state = "IDLE"
            self._emit_status_event()
            return

        # Phase 3: Finalize state
        with self._lock:
            if self.is_alarm_active:
                self.current_state = "ALARM_ACTIVE"
            else:
                self.current_state = "COMPLETED"

        logger.info(f"=== SURVEILLANCE SWEEP FINISHED [{sweep_id}] ===")
        self._broadcast("SWEEP_COMPLETED", summary)
        self._emit_status_event()

        # Phase 4: FIFO Automated Storage Pruning
        self._prune_old_sweeps()

    def _prune_old_sweeps(self) -> None:
        """Prunes oldest sweep recordings, captures, and database records when exceeding max_stored_sweeps."""
        try:
            total_sweeps = self.db_repo.get_sweep_count()
            if total_sweeps > self.max_stored_sweeps:
                excess_count = total_sweeps - self.max_stored_sweeps
                logger.info(f"Storage pruning triggered: {total_sweeps} sweeps stored, limit is {self.max_stored_sweeps}. Pruning oldest {excess_count} sweeps.")
                oldest_sweeps = self.db_repo.get_oldest_sweeps(limit=excess_count)
                for old_sweep in oldest_sweeps:
                    sid = old_sweep.id
                    # Clean up recordings directory
                    rec_sweep_dir = os.path.join(self.recordings_dir, sid)
                    if os.path.exists(rec_sweep_dir):
                        try:
                            shutil.rmtree(rec_sweep_dir, ignore_errors=True)
                        except Exception as del_err:
                            logger.warning(f"Failed removing recordings dir {rec_sweep_dir}: {del_err}")
                    # Clean up captures directory
                    cap_sweep_dir = os.path.join(self.captures_dir, sid)
                    if os.path.exists(cap_sweep_dir):
                        try:
                            shutil.rmtree(cap_sweep_dir, ignore_errors=True)
                        except Exception as del_err:
                            logger.warning(f"Failed removing captures dir {cap_sweep_dir}: {del_err}")
                    # Delete from database
                    self.db_repo.delete_sweep(sid)
                    logger.info(f"Pruned old sweep {sid} successfully.")
        except Exception as prune_err:
            logger.error(f"Error during FIFO sweep pruning: {prune_err}")

    def _broadcast(self, event_type: str, data: Dict[str, Any]):
        if self.event_broadcaster:
            try:
                self.event_broadcaster(event_type, data)
            except Exception as e:
                logger.error(f"Broadcaster error {event_type}: {e}")

    def _emit_status_event(self):
        self._broadcast("STATUS_UPDATE", self.get_status())
