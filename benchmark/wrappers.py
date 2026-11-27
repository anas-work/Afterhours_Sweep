"""
Comprehensive YOLO Benchmark: ONNX Runtime CUDA FP32 vs TensorRT (FP32, FP16, INT8)
Target Hardware: NVIDIA RTX A4000 (GPU 0)
Preserves production code; runs strictly on empirical measurements.
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

# Load NVIDIA CUDA and TensorRT libs into environment
trt_libs_path = "/home/green/.pyenv/versions/3.11.15/lib/python3.11/site-packages/tensorrt_cu12_libs"
if os.path.exists(trt_libs_path):
    os.environ["LD_LIBRARY_PATH"] = f"{trt_libs_path}:" + os.environ.get("LD_LIBRARY_PATH", "")

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

def letterbox_preprocess(img, target_size=640):
    """Exact preprocessing from src/ml/yolo26_detector.py"""
    h, w = img.shape[:2]
    r = min(target_size / h, target_size / w)
    nh, nw = int(round(h * r)), int(round(w * r))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    
    canvas = np.full((target_size, target_size, 3), 114, dtype=np.uint8)
    top = (target_size - nh) // 2
    left = (target_size - nw) // 2
    canvas[top:top+nh, left:left+nw] = resized
    
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    norm = (rgb.astype(np.float32) / 255.0).transpose(2, 0, 1) # CHW
    return norm, r, left, top

def postprocess_detections(logits, pred_boxes, r, left, top, orig_w, orig_h, conf_thresh=0.45, iou_thresh=0.45):
    """
    Exact postprocessing matching src/ml/yolo26_detector.py
    Outputs: list of (box, score, class_id)
    """
    # Sigmoid on logits for class 0 (person)
    scores = 1.0 / (1.0 + np.exp(-logits[:, 0]))
    mask = scores >= conf_thresh
    filtered_scores = scores[mask]
    filtered_boxes = pred_boxes[mask]
    
    if len(filtered_scores) == 0:
        return []
        
    boxes = []
    for box in filtered_boxes:
        cx, cy, bw, bh = box
        # Scale to 640x640 canvas
        cx *= 640
        cy *= 640
        bw *= 640
        bh *= 640
        
        # Remove padding & scale back to original
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
                "box": boxes[idx],
                "score": float(filtered_scores[idx]),
                "class_id": 0
            })
    return results

class TRTWrapper:
    def __init__(self, engine_path):
        self.logger = trt.Logger(trt.Logger.WARNING)
        with open(engine_path, "rb") as f:
            self.runtime = trt.Runtime(self.logger)
            self.engine = self.runtime.deserialize_cuda_engine(f.read())
        self.context = self.engine.create_execution_context()
        self.stream = torch.cuda.Stream(device=device)
        
    def infer(self, input_tensor):
        """
        input_tensor: torch.Tensor on CUDA with shape (B, 3, 640, 640)
        Returns: logits, pred_boxes as torch.Tensors
        """
        b = input_tensor.shape[0]
        self.context.set_input_shape("pixel_values", (b, 3, 640, 640))
        
        out_logits = torch.empty((b, 300, 80), dtype=torch.float32, device=device)
        out_boxes = torch.empty((b, 300, 4), dtype=torch.float32, device=device)
        
        self.context.set_tensor_address("pixel_values", input_tensor.data_ptr())
        self.context.set_tensor_address("logits", out_logits.data_ptr())
        self.context.set_tensor_address("pred_boxes", out_boxes.data_ptr())
        
        self.context.execute_async_v3(stream_handle=self.stream.cuda_stream)
        self.stream.synchronize()
        return out_logits, out_boxes

class ONNXWrapper:
    def __init__(self, onnx_path):
        providers = [
            ("CUDAExecutionProvider", {
                "device_id": 0,
                "arena_extend_strategy": "kNextPowerOfTwo",
                "gpu_mem_limit": 8 * 1024 * 1024 * 1024,
                "cudnn_conv_algo_search": "EXHAUSTIVE",
            })
        ]
        self.session = ort.InferenceSession(onnx_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        
    def infer(self, input_numpy):
        """
        input_numpy: np.ndarray with shape (B, 3, 640, 640)
        Returns: logits, pred_boxes as np.ndarrays
        """
        outputs = self.session.run(None, {self.input_name: input_numpy})
        return outputs[0], outputs[1]
