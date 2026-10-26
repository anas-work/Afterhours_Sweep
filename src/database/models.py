import datetime
import json
from typing import Dict, Any, List
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IST")

def get_ist_now() -> datetime.datetime:
    return datetime.datetime.now(IST)

Base = declarative_base()

class CameraModel(Base):
    __tablename__ = "cameras"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    rtsp_url = Column(String(512), nullable=False)
    location = Column(String(128), default="Premises Main")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=get_ist_now)

    detections = relationship("DetectionModel", back_populates="camera", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "rtsp_url": self.rtsp_url,
            "location": self.location,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class SweepModel(Base):
    __tablename__ = "sweeps"

    id = Column(String(64), primary_key=True)  # e.g., sweep_20260929_220000
    scheduled_time = Column(DateTime, nullable=True)
    start_time = Column(DateTime, default=get_ist_now)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(32), default="SCHEDULED")  # SCHEDULED, RECORDING, PROCESSING, COMPLETED, CANCELLED, FAILED
    total_cameras = Column(Integer, default=0)
    total_frames = Column(Integer, default=0)
    processed_frames = Column(Integer, default=0)
    detections_count = Column(Integer, default=0)
    alarm_triggered = Column(Boolean, default=False)
    duration_seconds = Column(Integer, default=180)
    processing_fps = Column(Float, default=0.0)
    created_at = Column(DateTime, default=get_ist_now)

    detections = relationship("DetectionModel", back_populates="sweep", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "total_cameras": self.total_cameras,
            "total_frames": self.total_frames,
            "processed_frames": self.processed_frames,
            "detections_count": self.detections_count,
            "alarm_triggered": self.alarm_triggered,
            "duration_seconds": self.duration_seconds,
            "processing_fps": round(self.processing_fps, 1),
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class DetectionModel(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sweep_id = Column(String(64), ForeignKey("sweeps.id"), nullable=False, index=True)
    camera_id = Column(String(64), ForeignKey("cameras.id"), nullable=False, index=True)
    camera_name = Column(String(128), nullable=False)
    timestamp = Column(DateTime, default=get_ist_now, index=True)
    video_offset_sec = Column(Float, default=0.0)
    person_count = Column(Integer, default=1)
    max_confidence = Column(Float, default=0.0)
    bounding_boxes_json = Column(Text, default="[]")  # List of [x1, y1, x2, y2, conf]
    capture_path = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=get_ist_now)

    sweep = relationship("SweepModel", back_populates="detections")
    camera = relationship("CameraModel", back_populates="detections")

    def to_dict(self) -> Dict[str, Any]:
        boxes = []
        try:
            boxes = json.loads(self.bounding_boxes_json) if self.bounding_boxes_json else []
        except Exception:
            boxes = []
        return {
            "id": self.id,
            "sweep_id": self.sweep_id,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "video_offset_sec": round(self.video_offset_sec, 2),
            "person_count": self.person_count,
            "max_confidence": round(self.max_confidence, 4),
            "bounding_boxes": boxes,
            "capture_path": self.capture_path,
            "capture_url": f"/captures/{self.sweep_id}/{self.capture_path.split('/')[-1]}",
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class SystemSettingModel(Base):
    __tablename__ = "system_settings"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now)
