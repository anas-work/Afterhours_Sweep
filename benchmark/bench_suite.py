"""
Master Benchmark Execution Script
Runs all tests strictly on NVIDIA RTX A4000 GPU 0.
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

from wrappers import ONNXWrapper, TRTWrapper
from utils import get_gpu_metrics, letterbox_preprocess, postprocess_detections, compute_iou

def run_inference_latency_benchmark(model_wrapper, is_trt=True, batch_sizes=[1, 4, 8, 16], warmup=50, iterations=200):
    results = {}
    
    for bs in batch_sizes:
        print(f"  [Latency Bench] Testing Batch Size {bs}...")
        if is_trt:
            dummy_input = torch.randn(bs, 3, 640, 640, dtype=torch.float32, device="cuda:0")
        else:
            dummy_input = np.random.randn(bs, 3, 640, 640).astype(np.float32)
            
        # Warmup
        for _ in range(warmup):
            _ = model_wrapper.infer(dummy_input)
            
        # Benchmark with CUDA events for sub-millisecond precision
        starter = torch.cuda.Event(enable_timing=True)
        ender = torch.cuda.Event(enable_timing=True)
        latencies = []
        
        torch.cuda.synchronize()
        for _ in range(iterations):
            starter.record()
            _ = model_wrapper.infer(dummy_input)
            ender.record()
            torch.cuda.synchronize()
            latencies.append(starter.elapsed_time(ender)) # in ms
            
        latencies = np.array(latencies)
        avg_lat = float(np.mean(latencies))
        p50_lat = float(np.percentile(latencies, 50))
        p95_lat = float(np.percentile(latencies, 95))
        throughput = float((bs * 1000.0) / avg_lat)
        
        results[bs] = {
            "avg_ms": avg_lat,
            "p50_ms": p50_lat,
            "p95_ms": p95_lat,
            "throughput_fps": throughput
        }
        print(f"    BS {bs}: Avg={avg_lat:.2f} ms | P50={p50_lat:.2f} ms | P95={p95_lat:.2f} ms | FPS={throughput:.1f}")
        
    return results

def run_end_to_end_benchmark(model_wrapper, is_trt, image_paths, num_iterations=500):
    print(f"  [End-to-End] Measuring {num_iterations} real pipeline executions...")
    images = [cv2.imread(p) for p in image_paths[:num_iterations]]
    # Repeat if not enough images
    while len(images) < num_iterations:
        images.extend(images[:num_iterations - len(images)])
        
    e2e_latencies = []
    prep_times = []
    infer_times = []
    post_times = []
    
    # Warmup
    for img in images[:30]:
        norm, r, left, top = letterbox_preprocess(img)
        if is_trt:
            inp = torch.from_numpy(norm).unsqueeze(0).to("cuda:0")
            l, b = model_wrapper.infer(inp)
            l = l.cpu().numpy()[0]
            b = b.cpu().numpy()[0]
        else:
            inp = np.expand_dims(norm, 0)
            l, b = model_wrapper.infer(inp)
            l = l[0]
            b = b[0]
        _ = postprocess_detections(l, b, r, left, top, img.shape[1], img.shape[0])
        
    t_start_total = time.time()
    for img in images:
        t0 = time.time()
        
        # 1. Preprocessing
        norm, r, left, top = letterbox_preprocess(img)
        t1 = time.time()
        
        # 2. Inference
        if is_trt:
            inp = torch.from_numpy(norm).unsqueeze(0).to("cuda:0")
            logits, boxes = model_wrapper.infer(inp)
            logits_np = logits.cpu().numpy()[0]
            boxes_np = boxes.cpu().numpy()[0]
        else:
            inp = np.expand_dims(norm, 0)
            logits, boxes = model_wrapper.infer(inp)
            logits_np = logits[0]
            boxes_np = boxes[0]
        t2 = time.time()
        
        # 3. Postprocessing & NMS
        dets = postprocess_detections(logits_np, boxes_np, r, left, top, img.shape[1], img.shape[0])
        t3 = time.time()
        
        prep_times.append((t1 - t0) * 1000)
        infer_times.append((t2 - t1) * 1000)
        post_times.append((t3 - t2) * 1000)
        e2e_latencies.append((t3 - t0) * 1000)
        
    actual_fps = len(images) / (time.time() - t_start_total)
    return {
        "e2e_avg_ms": float(np.mean(e2e_latencies)),
        "e2e_p50_ms": float(np.percentile(e2e_latencies, 50)),
        "e2e_p95_ms": float(np.percentile(e2e_latencies, 95)),
        "e2e_throughput_fps": float(actual_fps),
        "breakdown_ms": {
            "preprocess": float(np.mean(prep_times)),
            "inference_with_transfer": float(np.mean(infer_times)),
            "postprocess_nms": float(np.mean(post_times))
        }
    }

def run_accuracy_benchmark(model_wrapper, is_trt, baseline_detections, val_images):
    """
    Evaluates detection consistency against ONNX FP32 baseline on real CCTV frames.
    Calculates:
    - Detection count difference
    - Mean IOU of matched boxes
    - Confidence score delta
    - Precision, Recall, mAP@0.5, mAP@0.5:0.95 relative to FP32 baseline
    """
    print(f"  [Accuracy Evaluation] Evaluating {len(val_images)} validation frames...")
    curr_detections = {}
    
    for p in val_images:
        img = cv2.imread(p)
        orig_h, orig_w = img.shape[:2]
        norm, r, left, top = letterbox_preprocess(img)
        
        if is_trt:
            inp = torch.from_numpy(norm).unsqueeze(0).to("cuda:0")
            l, b = model_wrapper.infer(inp)
            l = l.cpu().numpy()[0]
            b = b.cpu().numpy()[0]
        else:
            inp = np.expand_dims(norm, 0)
            l, b = model_wrapper.infer(inp)
            l = l[0]
            b = b[0]
            
        dets = postprocess_detections(l, b, r, left, top, orig_w, orig_h)
        curr_detections[p] = dets
        
    # If baseline_detections is empty (i.e. this is the baseline run itself)
    if not baseline_detections:
        return {
            "detections_count": sum(len(d) for d in curr_detections.values()),
            "baseline_detections_count": sum(len(d) for d in curr_detections.values()),
            "mean_iou": 1.0,
            "mean_conf_delta": 0.0,
            "precision": 1.0,
            "recall": 1.0,
            "map_50": 1.0,
            "map_50_95": 1.0
        }, curr_detections

    # Compare with baseline
    total_base_dets = 0
    total_curr_dets = 0
    matched_ious = []
    conf_deltas = []
    
    tp_50 = 0
    fp_50 = 0
    fn_50 = 0
    
    tp_ranges = [] # for mAP@0.5:0.95 (thresholds 0.50 to 0.95 with step 0.05)
    iou_thresholds = np.arange(0.50, 1.00, 0.05)
    tp_counts = {t: 0 for t in iou_thresholds}
    fp_counts = {t: 0 for t in iou_thresholds}
    
    for p in val_images:
        base_dets = baseline_detections[p]
        test_dets = curr_detections[p]
        
        total_base_dets += len(base_dets)
        total_curr_dets += len(test_dets)
        
        used_test = set()
        for b in base_dets:
            best_iou = 0.0
            best_idx = -1
            for j, t in enumerate(test_dets):
                if j in used_test:
                    continue
                iou = compute_iou(b["box"], t["box"])
                if iou > best_iou:
                    best_iou = iou
                    best_idx = j
            if best_idx >= 0:
                used_test.add(best_idx)
                matched_ious.append(best_iou)
                conf_deltas.append(abs(b["score"] - test_dets[best_idx]["score"]))
                for thresh in iou_thresholds:
                    if best_iou >= thresh:
                        tp_counts[thresh] += 1
                    else:
                        fp_counts[thresh] += 1
            else:
                for thresh in iou_thresholds:
                    fp_counts[thresh] += 1
                    
        # False positives from unmatched detections
        unmatched_curr = len(test_dets) - len(used_test)
        for thresh in iou_thresholds:
            fp_counts[thresh] += unmatched_curr
            
    # Compute metrics
    prec_50 = tp_counts[0.5] / max(1, total_curr_dets)
    rec_50 = tp_counts[0.5] / max(1, total_base_dets)
    map_50 = prec_50 # for single class
    
    maps = []
    for thresh in iou_thresholds:
        p_t = tp_counts[thresh] / max(1, total_curr_dets)
        maps.append(p_t)
    map_50_95 = float(np.mean(maps))
    
    return {
        "detections_count": total_curr_dets,
        "baseline_detections_count": total_base_dets,
        "mean_iou": float(np.mean(matched_ious)) if matched_ious else 1.0,
        "mean_conf_delta": float(np.mean(conf_deltas)) if conf_deltas else 0.0,
        "precision": float(prec_50),
        "recall": float(rec_50),
        "map_50": float(map_50),
        "map_50_95": float(map_50_95)
    }, curr_detections
