import os
import time
import cv2
import shutil
import subprocess
import numpy as np
import logging
import threading
from typing import Dict, Any, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("ABLBL_Afterhours.RTSPRecorder")

DOCK_VIDEO_MAP = {
    "cctv_dock_01": "test_videos/test_cctv_gate.mp4",
    "cctv_dock_02": "test_videos/5978967-uhd_4096_2160_30fps.mp4",
    "cctv_dock_03": "test_videos/6194923-uhd_2160_3840_25fps.mp4",
    "cctv_dock_04": "test_videos/7807218-uhd_2160_4096_25fps_1.mp4",
    "cctv_dock_05": "test_videos/8051644-uhd_2160_3840_24fps_1.mp4",
    "cctv_dock_06": "test_videos/8344640-uhd_2560_1440_25fps.mp4",
    "cctv_dock_07": "test_videos/8513143-uhd_2160_3840_30fps.mp4",
    "cctv_dock_08": "test_videos/8684258-hd_1920_1080_25fps.mp4",
    "cctv_dock_09": "test_videos/dock_09.mp4",
    "cctv_dock_10": "test_videos/dock_10.mp4",
    "cctv_dock_11": "test_videos/dock_11.mp4",
}

class RTSPRecorder:
    """
    Concurrent multi-camera recording engine.
    Supports both timed auto mode and manual Start/Stop recording control.
    Can ingest from live RTSP feeds, MediaMTX streams, or local CCTV test video clips.
    """
    def __init__(self, recordings_base_dir: str = "data/recordings", max_workers: int = 32):
        self.recordings_base_dir = recordings_base_dir
        self.max_workers = max_workers
        self._stop_event = threading.Event()
        self._is_recording = False
        self._lock = threading.Lock()
        os.makedirs(self.recordings_base_dir, exist_ok=True)

    def stop_active_recording(self):
        """Immediately interrupts all active camera recording threads for manual mode stop."""
        with self._lock:
            self._stop_event.set()
            logger.info("Stop recording signal received. Finalizing all camera clips...")

    def is_currently_recording(self) -> bool:
        return self._is_recording

    def record_cameras_concurrently(
        self,
        sweep_id: str,
        cameras: List[Dict[str, Any]],
        duration_seconds: int = 180,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, str]:
        """
        Records all provided cameras concurrently until duration expires or stop_active_recording() is triggered.
        """
        sweep_dir = os.path.join(self.recordings_base_dir, sweep_id)
        os.makedirs(sweep_dir, exist_ok=True)

        self._stop_event.clear()
        self._is_recording = True
        results: Dict[str, str] = {}
        completed_cameras = 0
        total_cameras = len(cameras)

        logger.info(f"Starting recording across {total_cameras} cameras (Max duration: {duration_seconds}s, Sweep: {sweep_id})...")

        try:
            with ThreadPoolExecutor(max_workers=min(self.max_workers, max(1, total_cameras))) as executor:
                futures = {}
                for cam in cameras:
                    cam_id = cam["id"]
                    cam_name = cam.get("name", cam_id)
                    rtsp_url = cam["rtsp_url"]
                    output_path = os.path.join(sweep_dir, f"{cam_id}.mp4")

                    f = executor.submit(
                        self._record_single_camera,
                        cam_id=cam_id,
                        cam_name=cam_name,
                        rtsp_url=rtsp_url,
                        output_path=output_path,
                        max_duration_seconds=duration_seconds
                    )
                    futures[f] = cam_id

                for future in futures:
                    cam_id = futures[future]
                    try:
                        out_path = future.result()
                        if out_path and os.path.exists(out_path):
                            results[cam_id] = out_path
                        completed_cameras += 1
                        if progress_callback:
                            progress_callback(completed_cameras, total_cameras)
                    except Exception as e:
                        logger.error(f"Error recording camera {cam_id}: {e}")
        finally:
            self._is_recording = False

        logger.info(f"Recording finalized: {len(results)}/{total_cameras} camera video files saved.")
        return results

    def _record_single_camera(
        self,
        cam_id: str,
        cam_name: str,
        rtsp_url: str,
        output_path: str,
        max_duration_seconds: int
    ) -> str:
        """
        Records from RTSP URL, or slices from a test video file if provided.
        Stops if self._stop_event is set.
        """
        # Case 1: rtsp_url is a direct file path to test_videos/
        if os.path.exists(rtsp_url):
            return self._slice_local_video(rtsp_url, output_path, max_duration_seconds)

        # Case 2: Check if test_videos has a corresponding video file
        potential_test_path = os.path.join("test_videos", os.path.basename(rtsp_url))
        if os.path.exists(potential_test_path):
            return self._slice_local_video(potential_test_path, output_path, max_duration_seconds)

        # Case 3: Simulation or demo stream fallback
        if rtsp_url.startswith("sim://") or rtsp_url.startswith("synthetic://") or rtsp_url == "demo":
            return self._generate_synthetic_video(cam_id, cam_name, output_path, max_duration_seconds)

        # Case 4: Real RTSP feed (e.g., rtsp://127.0.0.1:8554/... or external camera)
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;tcp|timeout;2000000|stimeout;2000000|max_delay;0|fflags;nobuffer|flags;low_delay"
        )
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap = cv2.VideoCapture(rtsp_url)

        if not cap.isOpened():
            # Check dock mapping first
            mapped_src = DOCK_VIDEO_MAP.get(cam_id)
            if mapped_src and os.path.exists(mapped_src):
                logger.info(f"Using mapped dock video for {cam_id}: {mapped_src}")
                return self._slice_local_video(mapped_src, output_path, max_duration_seconds)

            # Check if any test video can be used as fallback
            test_vids = [os.path.join("test_videos", f) for f in os.listdir("test_videos") if f.endswith(".mp4")] if os.path.exists("test_videos") else []
            if test_vids:
                chosen = test_vids[hash(cam_id) % len(test_vids)]
                logger.info(f"RTSP stream {rtsp_url} offline for {cam_id}. Using test video source: {chosen}")
                return self._slice_local_video(chosen, output_path, max_duration_seconds)
            else:
                logger.warning(f"RTSP stream offline for {cam_id} ({rtsp_url}). Generating synthetic surveillance video.")
                return self._generate_synthetic_video(cam_id, cam_name, output_path, max_duration_seconds)

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        fps = min(max(fps, 10.0), 30.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        start_time = time.time()
        frames_written = 0

        try:
            while not self._stop_event.is_set() and (time.time() - start_time) < max_duration_seconds:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.04)
                    continue
                writer.write(frame)
                frames_written += 1
        finally:
            cap.release()
            writer.release()

        if frames_written == 0:
            logger.warning(f"RTSP stream {rtsp_url} produced 0 frames for {cam_id}. Slicing mapped dock video.")
            mapped_src = DOCK_VIDEO_MAP.get(cam_id)
            if mapped_src and os.path.exists(mapped_src):
                return self._slice_local_video(mapped_src, output_path, max_duration_seconds)

        logger.info(f"Saved {frames_written} frames from RTSP {cam_id} to {output_path}")
        return self._ensure_web_compatible_h264(output_path)

    def _slice_local_video(self, source_path: str, output_path: str, max_duration_seconds: int) -> str:
        """
        Slices up to max_duration_seconds from an existing video (looping if necessary).
        Respects self._stop_event for immediate manual stop.
        """
        cap = cv2.VideoCapture(source_path)
        if not cap.isOpened():
            return self._generate_synthetic_video("cam", "Camera", output_path, max_duration_seconds)

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        start_time = time.time()
        frames_written = 0

        try:
            while not self._stop_event.is_set() and (time.time() - start_time) < max_duration_seconds:
                ret, frame = cap.read()
                if not ret:
                    # Loop video from beginning
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        break
                writer.write(frame)
                frames_written += 1
                # Small yield to simulate real-time ingestion rate
                time.sleep(1.0 / (fps * 2))
        finally:
            cap.release()
            writer.release()

        logger.info(f"Ingested {frames_written} frames for test video {source_path} to {output_path}")
        return self._ensure_web_compatible_h264(output_path)

    def _generate_synthetic_video(self, cam_id: str, cam_name: str, output_path: str, max_duration_seconds: int) -> str:
        fps = 10.0
        width, height = 640, 480
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        has_intruder = True
        start_time = time.time()
        f_idx = 0

        try:
            while not self._stop_event.is_set() and (time.time() - start_time) < max_duration_seconds:
                frame = np.full((height, width, 3), 32, dtype=np.uint8)
                # Wall
                cv2.rectangle(frame, (0, 0), (width, int(height * 0.65)), (45, 48, 55), -1)
                # Floor
                cv2.rectangle(frame, (0, int(height * 0.65)), (width, height), (70, 75, 82), -1)
                for line_x in range(0, width, 80):
                    cv2.line(frame, (line_x, int(height * 0.65)), (int(line_x * 1.4 - width * 0.2), height), (85, 90, 98), 1)

                curr_sec = f_idx / fps
                timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S')
                cv2.putText(frame, f"[CAM: {cam_name.upper()}]  {timestamp_str}  REC", (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

                if has_intruder:
                    px = int(100 + (f_idx % 200) * 2)
                    py = int(height * 0.58)
                    cv2.circle(frame, (px, py - 60), 16, (170, 150, 140), -1)
                    cv2.rectangle(frame, (px - 18, py - 44), (px + 18, py + 10), (30, 60, 120), -1)
                    leg_swing = int(np.sin(f_idx * 0.8) * 12)
                    cv2.line(frame, (px - 10, py + 10), (px - 10 + leg_swing, py + 55), (40, 45, 55), 7)
                    cv2.line(frame, (px + 10, py + 10), (px + 10 - leg_swing, py + 55), (40, 45, 55), 7)

                writer.write(frame)
                f_idx += 1
                time.sleep(1.0 / (fps * 2))
        finally:
            writer.release()

        return self._ensure_web_compatible_h264(output_path)

    def _ensure_web_compatible_h264(self, video_path: str) -> str:
        """
        Ensures the recorded video is encoded in H.264 (AVC1, YUV420P) with +faststart moov atom
        for instant, native HTML5 streaming playback in modern web browsers.
        """
        if not video_path or not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
            return video_path

        ffmpeg_bin = shutil.which("ffmpeg") or "/home/green/.local/bin/ffmpeg"
        if not shutil.which(ffmpeg_bin) and not os.path.exists(ffmpeg_bin):
            return video_path

        tmp_path = f"{video_path}.h264.mp4"
        cmd = [
            ffmpeg_bin, "-y",
            "-i", video_path,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            tmp_path
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
            if res.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                os.replace(tmp_path, video_path)
                logger.debug(f"Remuxed {video_path} to browser-compatible H.264 (+faststart).")
        except Exception as e:
            logger.debug(f"H.264 browser remux notice for {video_path}: {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        return video_path
