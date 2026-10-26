import os
import json
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
from src.database.models import Base, CameraModel, SweepModel, DetectionModel, SystemSettingModel, get_ist_now

logger = logging.getLogger("ABLBL_Afterhours.Database")

class AfterhoursRepository:
    def __init__(self, db_url: str = "sqlite:///data/afterhours.db"):
        self.db_url = db_url

        # Ensure sqlite directory exists if using sqlite
        if self.db_url.startswith("sqlite:///"):
            db_path = self.db_url.replace("sqlite:///", "")
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            connect_args = {"check_same_thread": False}
        else:
            connect_args = {}

        self.engine = create_engine(
            self.db_url,
            connect_args=connect_args,
            pool_pre_ping=True
        )

        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        logger.info(f"Database initialized with URL: {self.db_url}")

    def get_session(self) -> Session:
        return self.SessionLocal()

    # ---------------- CAMERAS ----------------
    def get_cameras(self, active_only: bool = False) -> List[CameraModel]:
        with self.get_session() as session:
            query = session.query(CameraModel)
            if active_only:
                query = query.filter(CameraModel.is_active == True)
            return query.order_by(CameraModel.name).all()

    def get_camera_by_id(self, camera_id: str) -> Optional[CameraModel]:
        with self.get_session() as session:
            return session.query(CameraModel).filter(CameraModel.id == camera_id).first()

    def add_or_update_camera(self, camera_id: str, name: str, rtsp_url: str, location: str = "Main Premises", is_active: bool = True) -> CameraModel:
        with self.get_session() as session:
            cam = session.query(CameraModel).filter(CameraModel.id == camera_id).first()
            if cam:
                cam.name = name
                cam.rtsp_url = rtsp_url
                cam.location = location
                cam.is_active = is_active
            else:
                cam = CameraModel(
                    id=camera_id,
                    name=name,
                    rtsp_url=rtsp_url,
                    location=location,
                    is_active=is_active
                )
                session.add(cam)
            session.commit()
            session.refresh(cam)
            return cam

    def delete_camera(self, camera_id: str) -> bool:
        with self.get_session() as session:
            cam = session.query(CameraModel).filter(CameraModel.id == camera_id).first()
            if cam:
                session.delete(cam)
                session.commit()
                return True
            return False

    # ---------------- SWEEPS ----------------
    def create_sweep(self, sweep_id: str, scheduled_time: Optional[Any] = None, duration_seconds: int = 180, total_cameras: int = 0) -> SweepModel:
        with self.get_session() as session:
            sweep = SweepModel(
                id=sweep_id,
                scheduled_time=scheduled_time,
                start_time=get_ist_now(),
                status="RECORDING",
                duration_seconds=duration_seconds,
                total_cameras=total_cameras,
                total_frames=0,
                processed_frames=0,
                detections_count=0,
                alarm_triggered=False
            )
            session.add(sweep)
            session.commit()
            session.refresh(sweep)
            return sweep

    def update_sweep_status(self, sweep_id: str, status: str, total_frames: Optional[int] = None, processed_frames: Optional[int] = None, processing_fps: Optional[float] = None) -> Optional[SweepModel]:
        with self.get_session() as session:
            sweep = session.query(SweepModel).filter(SweepModel.id == sweep_id).first()
            if sweep:
                sweep.status = status
                if total_frames is not None:
                    sweep.total_frames = total_frames
                if processed_frames is not None:
                    sweep.processed_frames = processed_frames
                if processing_fps is not None:
                    sweep.processing_fps = processing_fps
                if status in ["COMPLETED", "FAILED", "CANCELLED"]:
                    sweep.end_time = get_ist_now()
                session.commit()
                session.refresh(sweep)
                return sweep
            return None

    def trigger_alarm_for_sweep(self, sweep_id: str) -> None:
        with self.get_session() as session:
            sweep = session.query(SweepModel).filter(SweepModel.id == sweep_id).first()
            if sweep and not sweep.alarm_triggered:
                sweep.alarm_triggered = True
                session.commit()

    def get_sweeps(self, limit: int = 20) -> List[SweepModel]:
        with self.get_session() as session:
            return session.query(SweepModel).order_by(desc(SweepModel.start_time)).limit(limit).all()

    def get_sweep_by_id(self, sweep_id: str) -> Optional[SweepModel]:
        with self.get_session() as session:
            return session.query(SweepModel).filter(SweepModel.id == sweep_id).first()

    # ---------------- DETECTIONS ----------------
    def record_detection(
        self,
        sweep_id: str,
        camera_id: str,
        camera_name: str,
        video_offset_sec: float,
        person_count: int,
        max_confidence: float,
        bounding_boxes: List[Any],
        capture_path: str
    ) -> DetectionModel:
        with self.get_session() as session:
            det = DetectionModel(
                sweep_id=sweep_id,
                camera_id=camera_id,
                camera_name=camera_name,
                timestamp=get_ist_now(),
                video_offset_sec=video_offset_sec,
                person_count=person_count,
                max_confidence=max_confidence,
                bounding_boxes_json=json.dumps(bounding_boxes),
                capture_path=capture_path
            )
            session.add(det)

            # Increment detection count on the sweep and trip alarm
            sweep = session.query(SweepModel).filter(SweepModel.id == sweep_id).first()
            if sweep:
                sweep.detections_count += 1
                sweep.alarm_triggered = True

            session.commit()
            session.refresh(det)
            return det

    def get_detections(self, sweep_id: Optional[str] = None, camera_id: Optional[str] = None, limit: int = 150) -> List[DetectionModel]:
        with self.get_session() as session:
            query = session.query(DetectionModel)
            if sweep_id:
                query = query.filter(DetectionModel.sweep_id == sweep_id)
            if camera_id:
                query = query.filter(DetectionModel.camera_id == camera_id)
            return query.order_by(desc(DetectionModel.timestamp)).limit(limit).all()

    def get_detections_by_dock(self, sweep_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Organizes detections grouped per camera / dock.
        Consolidates continuous person appearances into a single dock intrusion record,
        selecting the peak keyframe snapshot and attaching all underlying 1-FPS frame snapshots.
        """
        with self.get_session() as session:
            query = session.query(DetectionModel)
            if sweep_id:
                query = query.filter(DetectionModel.sweep_id == sweep_id)
            detections = query.order_by(DetectionModel.video_offset_sec.asc()).all()

            docks_map: Dict[str, Dict[str, Any]] = {}
            for d in detections:
                cam = d.camera
                cam_id = d.camera_id
                if cam_id not in docks_map:
                    docks_map[cam_id] = {
                        "dock_id": cam_id,
                        "dock_name": d.camera_name,
                        "location": cam.location if cam else "Main Facility",
                        "total_frames": 0,
                        "peak_confidence": 0.0,
                        "peak_snapshot_url": "",
                        "first_offset_sec": d.video_offset_sec,
                        "last_offset_sec": d.video_offset_sec,
                        "frames": []
                    }
                entry = docks_map[cam_id]
                d_dict = d.to_dict()
                entry["frames"].append(d_dict)
                entry["total_frames"] += 1
                entry["last_offset_sec"] = d.video_offset_sec
                if d.max_confidence >= entry["peak_confidence"]:
                    entry["peak_confidence"] = round(d.max_confidence, 4)
                    entry["peak_snapshot_url"] = d_dict["capture_url"]
                    entry["peak_detection"] = d_dict

            result = []
            for cam_id, info in docks_map.items():
                duration = max(1.0, round(info["last_offset_sec"] - info["first_offset_sec"] + 1.0, 1))
                info["duration_sec"] = duration
                result.append(info)
            # Sort by total frames descending (most active docks first)
            result.sort(key=lambda x: x["total_frames"], reverse=True)
            return result

    def flush_all_history(self) -> Dict[str, int]:
        """Clears all detection records and sweep logs from the database."""
        with self.get_session() as session:
            det_count = session.query(DetectionModel).delete()
            sweep_count = session.query(SweepModel).delete()
            session.commit()
            return {"detections_cleared": det_count, "sweeps_cleared": sweep_count}

    # ---------------- SETTINGS ----------------
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.get_session() as session:
            setting = session.query(SystemSettingModel).filter(SystemSettingModel.key == key).first()
            return setting.value if setting else default

    def set_setting(self, key: str, value: str) -> None:
        with self.get_session() as session:
            setting = session.query(SystemSettingModel).filter(SystemSettingModel.key == key).first()
            if setting:
                setting.value = value
            else:
                setting = SystemSettingModel(key=key, value=value)
                session.add(setting)
            session.commit()
