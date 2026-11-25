import subprocess
import time
import os
import signal
import sys

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEST_VIDS = os.path.join(REPO_DIR, "test_videos")

STREAMS = [
    {
        "name": "dock1",
        "url": "rtsp://127.0.0.1:8554/afterhours/dock1",
        "video": os.path.join(TEST_VIDS, "test_cctv_gate.mp4"),
        "description": "Warehouse CCTV Dock Gate 1 (test_cctv_gate.mp4)"
    },
    {
        "name": "dock2",
        "url": "rtsp://127.0.0.1:8554/afterhours/dock2",
        "video": os.path.join(TEST_VIDS, "5978967-uhd_4096_2160_30fps.mp4"),
        "description": "Warehouse CCTV Dock Gate 2 (5978967)"
    },
    {
        "name": "dock3",
        "url": "rtsp://127.0.0.1:8554/afterhours/dock3",
        "video": os.path.join(TEST_VIDS, "6194923-uhd_2160_3840_25fps.mp4"),
        "description": "Warehouse CCTV Dock Gate 3 (6194923)"
    },
    {
        "name": "dock4",
        "url": "rtsp://127.0.0.1:8554/afterhours/dock4",
        "video": os.path.join(TEST_VIDS, "7807218-uhd_2160_4096_25fps_1.mp4"),
        "description": "Warehouse CCTV Dock Gate 4 (7807218)"
    },
    {
        "name": "dock5",
        "url": "rtsp://127.0.0.1:8554/afterhours/dock5",
        "video": os.path.join(TEST_VIDS, "8051644-uhd_2160_3840_24fps_1.mp4"),
        "description": "Warehouse CCTV Dock Gate 5 (8051644)"
    },
    {
        "name": "dock6",
        "url": "rtsp://127.0.0.1:8554/afterhours/dock6",
        "video": os.path.join(TEST_VIDS, "8344640-uhd_2560_1440_25fps.mp4"),
        "description": "Warehouse CCTV Dock Gate 6 (8344640)"
    },
    {
        "name": "dock7",
        "url": "rtsp://127.0.0.1:8554/afterhours/dock7",
        "video": os.path.join(TEST_VIDS, "8513143-uhd_2160_3840_30fps.mp4"),
        "description": "Warehouse CCTV Dock Gate 7 (8513143)"
    },
    {
        "name": "dock8",
        "url": "rtsp://127.0.0.1:8554/afterhours/dock8",
        "video": os.path.join(TEST_VIDS, "8684258-hd_1920_1080_25fps.mp4"),
        "description": "Warehouse CCTV Dock Gate 8 (8684258)"
    },
    {
        "name": "dock9",
        "url": "rtsp://127.0.0.1:8554/afterhours/dock9",
        "video": os.path.join(TEST_VIDS, "dock_09.mp4"),
        "description": "Warehouse CCTV Dock Gate 9 (Testing_Videos2)"
    },
    {
        "name": "dock10",
        "url": "rtsp://127.0.0.1:8554/afterhours/dock10",
        "video": os.path.join(TEST_VIDS, "dock_10.mp4"),
        "description": "Warehouse CCTV Dock Gate 10 (Testing_Videos2)"
    },
    {
        "name": "dock11",
        "url": "rtsp://127.0.0.1:8554/afterhours/dock11",
        "video": os.path.join(TEST_VIDS, "dock_11.mp4"),
        "description": "Warehouse CCTV Dock Gate 11 (Testing_Videos2)"
    },
]

def get_ffmpeg_bin():
    import shutil
    return shutil.which("ffmpeg") or "/home/green/.local/bin/ffmpeg" or "ffmpeg"

def build_cmd(item):
    return [
        get_ffmpeg_bin(),
        "-re",
        "-stream_loop", "-1",
        "-i", item["video"],
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
        item["url"]
    ]

def main():
    procs = []
    print("=" * 70)
    print("STARTING PERSISTENT DEMO RTSP PUBLISHERS (MEDIAMTX)")
    print("=" * 70)

    for item in STREAMS:
        if not os.path.exists(item["video"]):
            print(f"[!] Warning: Video file {item['video']} not found, skipping {item['name']}")
            continue

        cmd = build_cmd(item)
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )
        procs.append((item, p))
        print(f"[*] Publishing {item['name']}: {item['url']} <- {os.path.basename(item['video'])}")

    print("\nAll demo RTSP streams active and looping indefinitely.")
    print("Press Ctrl+C to terminate all streams.")

    def handle_sig(sig, frame):
        print("\nStopping all RTSP streams...")
        for _, p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    while True:
        time.sleep(1)
        # Auto-restart if any process dies
        for idx, (item, p) in enumerate(procs):
            if p.poll() is not None:
                cmd = build_cmd(item)
                new_p = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )
                procs[idx] = (item, new_p)

if __name__ == "__main__":
    main()
