"""
Complete Benchmark Suite:
1. Model Inference Latency & Throughput (FPS) across Batch Sizes 1, 4, 8, 16
2. End-to-End Latency & Throughput (500 iterations: Preprocess, H2D, Inference, D2H, Postprocess)
3. Accuracy & Output Consistency Evaluation (500 Warehouse CCTV validation frames)
4. Hardware Telemetry Monitoring (GPU util, VRAM peak/avg, CPU %, Host RAM, Temp, Power)
"""

import os
import sys
import glob
import time
import json
import psutil
import cv2
import numpy as np
import torch
import onnxruntime as ort
import tensorrt as trt
import matplotlib.pyplot as plt

# Ensure TensorRT & CUDA paths
trt_libs = "/home/green/.pyenv/versions/3.11.15/lib/python3.11/site-packages/tensorrt_cu12_libs"
if os.path.exists(trt_libs):
    os.environ["LD_LIBRARY_PATH"] = f"{trt_libs}:" + os.environ.get("LD_LIBRARY_PATH", "")

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

def get_gpu_metrics():
    """Query current GPU 0 power, temperature, and memory via nvidia-smi"""
    try:
        cmd = "nvidia-smi -i 0 --query-gpu=utilization.gpu,memory.used,temperature.gpu,power.draw --format=csv,noheader,nounits"
        out = os.popen(cmd).read().strip()
        first_line = out.splitlines()[0]
        gpu_util, mem_used, temp, power = [float(x.strip()) for x in first_line.split(",")]
        return {
            "gpu_util": gpu_util,
            "vram_mb": mem_used,
            "temp_c": temp,
            "power_w": power
        }
    except Exception as e:
        return {"gpu_util": 0, "vram_mb": 0, "temp_c": 0, "power_w": 0}

def letterbox_preprocess(img, target_size=640):
    h, w = img.shape[:2]
    r = min(target_size / h, target_size / w)
    nh, nw = int(round(h * r)), int(round(w * r))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    
    canvas = np.full((target_size, target_size, 3), 114, dtype=np.uint8)
    top = (target_size - nh) // 2
    left = (target_size - nw) // 2
    canvas[top:top+nh, left:left+nw] = resized
    
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    norm = (rgb.astype(np.float32) / 255.0).transpose(2, 0, 1)
    return norm, r, left, top

def postprocess_detections(logits, pred_boxes, r, left, top, orig_w, orig_h, conf_thresh=0.45, iou_thresh=0.45):
    scores = 1.0 / (1.0 + np.exp(-logits[:, 0]))
    mask = scores >= conf_thresh
    filtered_scores = scores[mask]
    filtered_boxes = pred_boxes[mask]
    
    if len(filtered_scores) == 0:
        return []
        
    boxes = []
    for box in filtered_boxes:
        cx, cy, bw, bh = box
        cx *= 640
        cy *= 640
        bw *= 640
        bh *= 640
        
        x1 = max(0, int((cx - bw / 2 - left) / r))
        y1 = max(0, int((cy - bh / 2 - top) / r))
        x2 = min(orig_w, int((cx + bw / 2 - left) / r))
        y2 = min(orig_h, int((cy + bh / 2 - top) / r))
        boxes.append([x1, y1, x2 - x1, y2 - y1])
        
    indices = cv2.dnn.NMSBoxes(boxes, filtered_scores.tolist(), conf_thresh, iou_thresh)
    results = []
    if len(indices) > 0:
        for idx in indices.flatten():
            results.append({
                "box": boxes[idx], # [x, y, w, h]
                "score": float(filtered_scores[idx]),
                "class_id": 0
            })
    return results

def compute_iou(boxA, boxB):
    # box: [x, y, w, h]
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
    yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])
    
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = boxA[2] * boxA[3]
    boxBArea = boxB[2] * boxB[3]
    
    iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
    return iou
