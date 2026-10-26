import os
import psutil
import torch
import logging
from typing import Dict, Any

logger = logging.getLogger("ABLBL_Afterhours.Telemetry")

def get_system_telemetry(device_id: int = 0) -> Dict[str, Any]:
    """
    Returns real-time GPU 0 and system telemetry for live dashboard monitoring.
    """
    telemetry = {
        "gpu_available": False,
        "gpu_name": "N/A",
        "gpu_utilization_pct": 0,
        "gpu_memory_used_mb": 0,
        "gpu_memory_total_mb": 0,
        "gpu_memory_pct": 0.0,
        "cpu_utilization_pct": psutil.cpu_percent(interval=None),
        "ram_used_mb": round(psutil.virtual_memory().used / (1024 * 1024), 1),
        "ram_total_mb": round(psutil.virtual_memory().total / (1024 * 1024), 1),
        "ram_utilization_pct": psutil.virtual_memory().percent
    }

    if torch.cuda.is_available() and device_id < torch.cuda.device_count():
        telemetry["gpu_available"] = True
        telemetry["gpu_name"] = torch.cuda.get_device_name(device_id)

        # PyTorch memory tracking for GPU
        mem_allocated = torch.cuda.memory_allocated(device_id) / (1024 * 1024)
        mem_reserved = torch.cuda.memory_reserved(device_id) / (1024 * 1024)
        total_mem = torch.cuda.get_device_properties(device_id).total_memory / (1024 * 1024)

        # Try to read actual GPU memory from nvidia-smi if available
        try:
            import subprocess
            cmd = f"nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits -i {device_id}"
            out = subprocess.check_output(cmd.split(), timeout=0.8).decode("utf-8").strip()
            parts = [p.strip() for p in out.split(",")]
            if len(parts) >= 3:
                telemetry["gpu_utilization_pct"] = int(parts[0])
                telemetry["gpu_memory_used_mb"] = int(parts[1])
                telemetry["gpu_memory_total_mb"] = int(parts[2])
                telemetry["gpu_memory_pct"] = round((int(parts[1]) / max(1, int(parts[2]))) * 100, 1)
        except Exception:
            # Fallback to PyTorch metrics
            telemetry["gpu_memory_used_mb"] = round(mem_reserved, 1)
            telemetry["gpu_memory_total_mb"] = round(total_mem, 1)
            telemetry["gpu_memory_pct"] = round((mem_reserved / max(1.0, total_mem)) * 100, 1)

    return telemetry
