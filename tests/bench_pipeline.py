"""
Micro-benchmark testing SweepProcessor pipeline throughput:
Simulates a sweep with test video to measure exact FPS before and after fixing comment 3.
"""
import os
import sys
import time
import shutil

sys.path.insert(0, "/h3/anas/ABLBL_Afterhours")

from src.database.repository import AfterhoursRepository
from src.ml.yolo26_detector import YOLO26Detector
from src.processing.sweep_processor import SweepProcessor

def run_test():
    test_db = "data/bench_test.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    repo = AfterhoursRepository(f"sqlite:///{test_db}")
    
    detector = YOLO26Detector(model_path="models/yolo26n.onnx", device_id=0, conf_threshold=0.35)
    
    # 4 video sources (test videos in test_videos/)
    videos = {
        "cam_01": "test_videos/test_cctv_gate.mp4",
        "cam_02": "test_videos/dock_09.mp4",
        "cam_03": "test_videos/dock_10.mp4",
        "cam_04": "test_videos/dock_11.mp4",
    }
    names = {k: f"Camera {k}" for k in videos}
    
    processor = SweepProcessor(
        detector=detector,
        db_repo=repo,
        captures_base_dir="data/test_captures_bench",
        batch_size=16,
        num_extraction_workers=4
    )
    
    # Create sweep
    repo.create_sweep("bench_sweep_1", duration_seconds=60, total_cameras=len(videos))
    
    t0 = time.time()
    res = processor.process_sweep_videos(
        sweep_id="bench_sweep_1",
        camera_video_paths=videos,
        camera_names=names
    )
    t1 = time.time()
    
    print("\n" + "=" * 50)
    print("BENCHMARK RESULT:")
    print(f"Total Frames Processed: {res['processed_frames']}")
    print(f"Total Duration: {res['duration_sec']} s")
    print(f"Processing FPS: {res['processing_fps']} FPS")
    print(f"Detections Count: {res['detections_count']}")
    print("=" * 50)

if __name__ == "__main__":
    run_test()
