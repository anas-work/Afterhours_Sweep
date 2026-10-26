import os
import shutil
import subprocess
import logging
from typing import List, Dict

logger = logging.getLogger("ABLBL_Afterhours.Streams")

ATTENDANCE_V1_DIR = "/h3/anas/ABLBL_AttendanceV1"
AFTERHOURS_DIR = "/h3/anas/ABLBL_Afterhours"
TEST_VIDEOS_DIR = os.path.join(AFTERHOURS_DIR, "test_videos")

def copy_test_videos() -> List[str]:
    """Copies sample CCTV footages from ABLBL_AttendanceV1 to ABLBL_Afterhours."""
    os.makedirs(TEST_VIDEOS_DIR, exist_ok=True)
    copied = []

    # 1. Gate CCTV video
    gate_video = os.path.join(ATTENDANCE_V1_DIR, "data", "test_videos", "test_cctv_gate.mp4")
    if os.path.exists(gate_video):
        dest = os.path.join(TEST_VIDEOS_DIR, "test_cctv_gate.mp4")
        if not os.path.exists(dest) or os.path.getsize(dest) != os.path.getsize(gate_video):
            shutil.copy2(gate_video, dest)
        copied.append(dest)

    # 2. Testing docks videos
    docks_dir = os.path.join(ATTENDANCE_V1_DIR, "Testing_Docks")
    if os.path.exists(docks_dir):
        for f in os.listdir(docks_dir):
            if f.endswith(".mp4"):
                src_path = os.path.join(docks_dir, f)
                # Normalize filename
                safe_name = f.replace(" ", "_").replace("(", "").replace(")", "")
                dest_path = os.path.join(TEST_VIDEOS_DIR, safe_name)
                if not os.path.exists(dest_path) or os.path.getsize(dest_path) != os.path.getsize(src_path):
                    shutil.copy2(src_path, dest_path)
                copied.append(dest_path)

    print(f"Copied/verified {len(copied)} test CCTV footages into {TEST_VIDEOS_DIR}")
    return copied

def get_ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or "/home/green/.local/bin/ffmpeg" or "ffmpeg"

def start_rtsp_loops() -> List[subprocess.Popen]:
    """Starts background FFmpeg processes publishing test videos to MediaMTX on port 8554."""
    videos = copy_test_videos()
    procs = []
    ffmpeg = get_ffmpeg_bin()

    for idx, v_path in enumerate(videos[:6]):
        stream_name = f"afterhours_dock{idx+1}"
        rtsp_url = f"rtsp://127.0.0.1:8554/{stream_name}"

        cmd = [
            ffmpeg,
            "-re",
            "-stream_loop", "-1",
            "-i", v_path,
            "-vf", "scale=min(1280\\,iw):-2",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-b:v", "1500k",
            "-maxrate", "2000k",
            "-bufsize", "3000k",
            "-g", "25",
            "-an",
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            rtsp_url
        ]

        try:
            p = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )
            procs.append(p)
            print(f"[*] Publishing {stream_name}: {rtsp_url} <- {os.path.basename(v_path)}")
        except Exception as e:
            print(f"[!] Error publishing {stream_name}: {e}")

    return procs

if __name__ == "__main__":
    copy_test_videos()
