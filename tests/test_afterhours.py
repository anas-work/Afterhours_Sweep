import os
import sys
import cv2
import time
import pytest
import numpy as np

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database.repository import AfterhoursRepository
from src.database.models import get_ist_now
from src.recording.rtsp_recorder import RTSPRecorder
from src.ml.model_downloader import ensure_model_exists
from src.ml.yolo26_detector import YOLO26Detector
from src.processing.sweep_processor import SweepProcessor
from src.scheduler.sweep_scheduler import SweepScheduler

TEST_DB_PATH = "data/test_afterhours.db"

@pytest.fixture(scope="session")
def db_repo():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    repo = AfterhoursRepository(db_url=f"sqlite:///{TEST_DB_PATH}")
    yield repo
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

def test_database_crud(db_repo):
    # 1. Camera CRUD
    cam = db_repo.add_or_update_camera("cam_test_01", "Test Camera 1", "demo", "Entrance")
    assert cam.id == "cam_test_01"
    assert cam.name == "Test Camera 1"

    cams = db_repo.get_cameras()
    assert len(cams) >= 1

    # 2. Sweep creation & update
    sweep = db_repo.create_sweep("sweep_test_01", duration_seconds=10, total_cameras=1)
    assert sweep.id == "sweep_test_01"
    assert sweep.status == "RECORDING"

    updated = db_repo.update_sweep_status("sweep_test_01", "COMPLETED", total_frames=10, processed_frames=10, processing_fps=120.5)
    assert updated.status == "COMPLETED"
    assert updated.processing_fps == 120.5

    # 3. Detection record
    det = db_repo.record_detection(
        sweep_id="sweep_test_01",
        camera_id="cam_test_01",
        camera_name="Test Camera 1",
        video_offset_sec=4.0,
        person_count=1,
        max_confidence=0.88,
        bounding_boxes=[[100, 120, 250, 400]],
        capture_path="data/captures/test_det.jpg"
    )
    assert det.id is not None
    assert det.person_count == 1

    dets = db_repo.get_detections(sweep_id="sweep_test_01")
    assert len(dets) == 1

    # 4. Settings
    db_repo.set_setting("test_key", "test_val")
    assert db_repo.get_setting("test_key") == "test_val"

def test_rtsp_recorder_synthetic():
    recorder = RTSPRecorder(recordings_base_dir="data/test_recordings")
    cams = [
        {"id": "cam_synth_01", "name": "Synthetic 1", "rtsp_url": "demo"},
        {"id": "cam_synth_02", "name": "Synthetic 2", "rtsp_url": "demo"}
    ]

    # Test 2 seconds recording
    results = recorder.record_cameras_concurrently("test_sweep_rec", cams, duration_seconds=2)
    assert "cam_synth_01" in results
    assert "cam_synth_02" in results

    for cam_id, p in results.items():
        assert os.path.exists(p)
        assert os.path.getsize(p) > 1000

        cap = cv2.VideoCapture(p)
        ret, frame = cap.read()
        cap.release()
        assert ret is True
        assert frame.shape == (480, 640, 3)

def test_yolo26_detector_and_batch_inference():
    # Verify model download & load
    model_path = ensure_model_exists("models/yolo26n.onnx")
    assert os.path.exists(model_path)
    assert os.path.getsize(model_path) > 1024 * 1024

    detector = YOLO26Detector(model_path=model_path, device_id=0, conf_threshold=0.3)

    # Create dummy synthetic frames
    f1 = np.full((480, 640, 3), 120, dtype=np.uint8)
    f2 = np.full((480, 640, 3), 50, dtype=np.uint8)

    # Draw simulated person on f1
    cv2.circle(f1, (300, 200), 25, (180, 160, 150), -1)
    cv2.rectangle(f1, (270, 230), (330, 340), (20, 40, 90), -1)

    batch = [f1, f2]
    batch_results = detector.detect_batch(batch)
    assert len(batch_results) == 2
    assert isinstance(batch_results[0], list)

    # Test annotation function
    annotated = detector.annotate_frame(f1, batch_results[0], camera_name="Test Cam", timestamp_str="12:00:00")
    assert annotated.shape == f1.shape

def test_sweep_processor_pipeline(db_repo):
    model_path = ensure_model_exists("models/yolo26n.onnx")
    detector = YOLO26Detector(model_path=model_path, device_id=0)

    processor = SweepProcessor(
        detector=detector,
        db_repo=db_repo,
        captures_base_dir="data/test_captures",
        batch_size=4,
        num_extraction_workers=2
    )

    recorder = RTSPRecorder(recordings_base_dir="data/test_recordings")
    cams = [{"id": "cam_proc_01", "name": "Proc Cam 1", "rtsp_url": "demo"}]
    rec_results = recorder.record_cameras_concurrently("sweep_proc_test", cams, duration_seconds=3)

    cam_names = {"cam_proc_01": "Proc Cam 1"}
    summary = processor.process_sweep_videos(
        sweep_id="sweep_proc_test",
        camera_video_paths=rec_results,
        camera_names=cam_names
    )

    assert summary["processed_frames"] >= 2
    assert summary["processing_fps"] > 0

def test_storage_pruning(db_repo, tmp_path):
    # Flush existing history in shared fixture
    db_repo.flush_all_history()

    # Setup test directories
    test_rec_dir = str(tmp_path / "recordings")
    test_cap_dir = str(tmp_path / "captures")
    os.makedirs(test_rec_dir, exist_ok=True)
    os.makedirs(test_cap_dir, exist_ok=True)

    # Insert 5 dummy sweeps
    for i in range(1, 6):
        sid = f"sweep_{i:02d}"
        db_repo.create_sweep(sid, total_cameras=1)
        os.makedirs(os.path.join(test_rec_dir, sid), exist_ok=True)
        os.makedirs(os.path.join(test_cap_dir, sid), exist_ok=True)
        # Create a dummy file in each
        with open(os.path.join(test_rec_dir, sid, "test.mp4"), "w") as f:
            f.write("dummy")
        with open(os.path.join(test_cap_dir, sid, "test.jpg"), "w") as f:
            f.write("dummy")

    assert db_repo.get_sweep_count() == 5

    # Instantiate scheduler with max_stored_sweeps = 3
    scheduler = SweepScheduler(
        recorder=None,
        processor=None,
        db_repo=db_repo,
        max_stored_sweeps=3,
        recordings_dir=test_rec_dir,
        captures_dir=test_cap_dir
    )

    # Trigger pruning
    scheduler._prune_old_sweeps()

    # Verify db count is now 3
    assert db_repo.get_sweep_count() == 3

    # Verify oldest 2 sweeps (sweep_01, sweep_02) were removed
    remaining_sweeps = [s.id for s in db_repo.get_sweeps(limit=10)]
    assert "sweep_01" not in remaining_sweeps
    assert "sweep_02" not in remaining_sweeps
    assert "sweep_05" in remaining_sweeps

    # Verify folders were pruned
    assert not os.path.exists(os.path.join(test_rec_dir, "sweep_01"))
    assert not os.path.exists(os.path.join(test_cap_dir, "sweep_01"))
    assert os.path.exists(os.path.join(test_rec_dir, "sweep_05"))

