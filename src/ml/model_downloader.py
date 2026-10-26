import os
import urllib.request
import logging

logger = logging.getLogger("ABLBL_Afterhours.ModelDownloader")

PRIMARY_YOLO26N_URL = "https://huggingface.co/onnx-community/yolo26n-ONNX/resolve/main/onnx/model.onnx"
FP16_YOLO26N_URL = "https://huggingface.co/onnx-community/yolo26n-ONNX/resolve/main/onnx/model_fp16.onnx"

def ensure_model_exists(target_path: str = "models/yolo26n.onnx", url: str = PRIMARY_YOLO26N_URL) -> str:
    """
    Verifies that the YOLO26n ONNX model exists locally; downloads it if missing.
    """
    if os.path.exists(target_path) and os.path.getsize(target_path) > 1024 * 1024:
        logger.info(f"YOLO26n ONNX model already present at: {target_path} ({os.path.getsize(target_path)/(1024*1024):.2f} MB)")
        return target_path

    os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
    logger.info(f"Downloading YOLO26n ONNX model from {url} to {target_path}...")
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)
    
    temp_path = f"{target_path}.tmp"
    try:
        with urllib.request.urlopen(req, timeout=60) as response, open(temp_path, "wb") as out_file:
            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            block_size = 1024 * 64
            while True:
                chunk = response.read(block_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if total_size > 0 and downloaded % (1024 * 1024 * 2) < block_size:
                    logger.info(f"Downloading YOLO26n: {downloaded / (1024*1024):.1f}MB / {total_size / (1024*1024):.1f}MB")
        
        os.replace(temp_path, target_path)
        logger.info(f"YOLO26n ONNX model downloaded successfully! Size: {os.path.getsize(target_path)/(1024*1024):.2f} MB")
        return target_path
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        logger.error(f"Failed to download model from {url}: {e}")
        raise RuntimeError(f"Could not download YOLO26n model: {e}")
