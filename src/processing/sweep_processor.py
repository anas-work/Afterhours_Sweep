import os
import cv2
import time
import queue
import logging
import threading
import numpy as np
from typing import Dict, Any, List, Optional, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor

from src.ml.yolo26_detector import YOLO26Detector
from src.database.repository import AfterhoursRepository

logger = logging.getLogger("ABLBL_Afterhours.SweepProcessor")

class SweepProcessor:
    """
    High-throughput parallel 1-FPS video processing engine.
    Overlaps multi-threaded frame extraction across 200 camera videos with batched GPU 0 inference.
    """
    def __init__(
        self,
        detector: YOLO26Detector,
        db_repo: AfterhoursRepository,
        captures_base_dir: str = "data/captures",
        batch_size: int = 16,
        num_extraction_workers: int = 8
    ):
        self.detector = detector
        self.db_repo = db_repo
        self.captures_base_dir = captures_base_dir
        self.batch_size = batch_size
        self.num_extraction_workers = num_extraction_workers
        os.makedirs(self.captures_base_dir, exist_ok=True)

    def process_sweep_videos(
        self,
        sweep_id: str,
        camera_video_paths: Dict[str, str],
        camera_names: Dict[str, str],
        on_progress: Optional[Callable[[int, int, float], None]] = None,
        on_person_detected: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Processes recorded videos from all cameras at ~1 FPS using GPU 0 YOLO26n.
        
        Args:
            sweep_id: Identifier of the active surveillance sweep
            camera_video_paths: Dict of {camera_id: video_file_path}
            camera_names: Dict of {camera_id: camera_name}
            on_progress: Callback(processed_frames, total_frames, current_fps)
            on_person_detected: Callback(detection_dict)
        """
        sweep_captures_dir = os.path.join(self.captures_base_dir, sweep_id)
        os.makedirs(sweep_captures_dir, exist_ok=True)

        logger.info(f"Starting 1-FPS Sweep Processing for Sweep: {sweep_id} ({len(camera_video_paths)} cameras)...")
        start_time = time.time()

        # Step 1: Pre-calculate total 1-FPS frames to process
        total_expected_frames = 0
        camera_frame_metadata: Dict[str, List[Tuple[float, int]]] = {}

        for cam_id, video_path in camera_video_paths.items():
            if not os.path.exists(video_path):
                continue
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                continue
            
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            duration_sec = total_video_frames / max(1.0, fps)
            cap.release()

            # Schedule 1 frame per second of footage: s = 0, 1, 2, ..., int(duration_sec)
            steps = []
            for sec in range(int(np.ceil(duration_sec))):
                frame_idx = int(sec * fps)
                if frame_idx < total_video_frames:
                    steps.append((float(sec), frame_idx))
            
            camera_frame_metadata[cam_id] = steps
            total_expected_frames += len(steps)

        logger.info(f"Total 1-FPS frames scheduled across {len(camera_frame_metadata)} cameras: {total_expected_frames}")
        self.db_repo.update_sweep_status(sweep_id, status="PROCESSING", total_frames=total_expected_frames, processed_frames=0)

        # Producer-Consumer Queue: Extraction threads -> GPU Batch Processor
        frame_queue: queue.Queue = queue.Queue(maxsize=self.batch_size * 8)
        extraction_done = threading.Event()

        # Step 2: Overlapped frame extraction workers
        def extractor_worker():
            with ThreadPoolExecutor(max_workers=self.num_extraction_workers) as executor:
                def extract_camera_frames(cam_id: str):
                    v_path = camera_video_paths[cam_id]
                    c_name = camera_names.get(cam_id, cam_id)
                    steps = camera_frame_metadata.get(cam_id, [])

                    cap = cv2.VideoCapture(v_path)
                    if not cap.isOpened():
                        return

                    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                    step_frame_delta = int(round(fps))

                    for sec, frame_idx in steps:
                        # Direct seek for high performance
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            # Push to queue (blocks if queue is full to bound memory)
                            frame_queue.put({
                                "cam_id": cam_id,
                                "cam_name": c_name,
                                "sec": sec,
                                "frame": frame
                            })
                    cap.release()

                list(executor.map(extract_camera_frames, list(camera_frame_metadata.keys())))
            extraction_done.set()

        extractor_thread = threading.Thread(target=extractor_worker, daemon=True)
        extractor_thread.start()

        # Step 3: GPU Batch Inference loop
        processed_frames_count = 0
        total_person_detections = 0
        batch_items = []
        camera_last_captured_sec: Dict[str, float] = {}
        camera_last_alerted_sec: Dict[str, float] = {}

        last_progress_update = time.time()

        while not (extraction_done.is_set() and frame_queue.empty() and len(batch_items) == 0):
            # Fill batch
            while len(batch_items) < self.batch_size:
                try:
                    item = frame_queue.get(timeout=0.1)
                    batch_items.append(item)
                except queue.Empty:
                    if extraction_done.is_set():
                        break

            if not batch_items:
                continue

            # Run batched inference on GPU 0
            frames_to_infer = [it["frame"] for it in batch_items]
            batch_results = self.detector.detect_batch(frames_to_infer)

            # Process detection results
            for idx, item in enumerate(batch_items):
                cam_id = item["cam_id"]
                c_name = item["cam_name"]
                sec = item["sec"]
                orig_frame = item["frame"]
                dets = batch_results[idx]

                if len(dets) > 0:
                    # 5-second pause after person detection before capturing next frame on this camera
                    last_captured = camera_last_captured_sec.get(cam_id)
                    if last_captured is not None and (sec - last_captured) < 5.0:
                        continue

                    camera_last_captured_sec[cam_id] = sec
                    total_person_detections += len(dets)
                    max_conf = max(d["confidence"] for d in dets)
                    boxes = [d["box"] for d in dets]

                    # Annotate frame
                    time_str = f"+{int(sec//60):02d}:{int(sec%60):02d}s"
                    annotated_frame = self.detector.annotate_frame(orig_frame, dets, camera_name=c_name, timestamp_str=time_str)

                    # Save capture snapshot
                    capture_filename = f"{cam_id}_sec{int(sec):03d}_p{len(dets)}.jpg"
                    capture_path = os.path.join(sweep_captures_dir, capture_filename)
                    cv2.imwrite(capture_path, annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

                    # Record in DB
                    db_det = self.db_repo.record_detection(
                        sweep_id=sweep_id,
                        camera_id=cam_id,
                        camera_name=c_name,
                        video_offset_sec=sec,
                        person_count=len(dets),
                        max_confidence=max_conf,
                        bounding_boxes=boxes,
                        capture_path=capture_path
                    )

                    # Broadcast alarm detection event (with 5-second pause cooldown)
                    if on_person_detected:
                        last_alert_sec = camera_last_alerted_sec.get(cam_id)
                        if last_alert_sec is None or (sec - last_alert_sec) >= 5.0:
                            camera_last_alerted_sec[cam_id] = sec
                            try:
                                on_person_detected(db_det.to_dict())
                            except Exception as cb_err:
                                logger.error(f"Error in on_person_detected callback: {cb_err}")

            processed_frames_count += len(batch_items)
            batch_items.clear()

            # Throttled progress update
            now = time.time()
            if now - last_progress_update >= 0.25 or processed_frames_count == total_expected_frames:
                elapsed = max(0.01, now - start_time)
                current_fps = processed_frames_count / elapsed
                self.db_repo.update_sweep_status(
                    sweep_id=sweep_id,
                    status="PROCESSING",
                    processed_frames=processed_frames_count,
                    processing_fps=current_fps
                )
                if on_progress:
                    on_progress(processed_frames_count, total_expected_frames, current_fps)
                last_progress_update = now

        extractor_thread.join()

        total_elapsed = max(0.01, time.time() - start_time)
        final_fps = processed_frames_count / total_elapsed
        logger.info(f"Sweep {sweep_id} processing complete: {processed_frames_count} frames processed in {total_elapsed:.2f}s ({final_fps:.1f} FPS on GPU 0). Person detections: {total_person_detections}")

        self.db_repo.update_sweep_status(
            sweep_id=sweep_id,
            status="COMPLETED",
            processed_frames=processed_frames_count,
            processing_fps=final_fps
        )

        return {
            "sweep_id": sweep_id,
            "processed_frames": processed_frames_count,
            "total_frames": total_expected_frames,
            "detections_count": total_person_detections,
            "duration_sec": round(total_elapsed, 2),
            "processing_fps": round(final_fps, 1),
            "alarm_triggered": total_person_detections > 0
        }
