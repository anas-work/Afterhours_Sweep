"""
Master Benchmark Runner
Executes:
1. Baseline: ONNX Runtime CUDA FP32
2. Engine 1: TensorRT FP32
3. Engine 2: TensorRT FP16
4. Engine 3: TensorRT INT8

Monitors: GPU util, peak/avg VRAM, CPU util, Host RAM, Temp, Power, Engine size.
Produces charts and comparison JSON.
"""

import os
import sys
import glob
import time
import json
import psutil
import numpy as np
import torch
import matplotlib.pyplot as plt

from wrappers import ONNXWrapper, TRTWrapper
from utils import get_gpu_metrics
from bench_suite import run_inference_latency_benchmark, run_end_to_end_benchmark, run_accuracy_benchmark

def main():
    print("=" * 70)
    print("STARTING COMPREHENSIVE YOLO BENCHMARK")
    print(f"Device: {torch.cuda.get_device_name(0)}")
    print("=" * 70)
    
    val_images = sorted(glob.glob("/h3/anas/ABLBL_Afterhours/benchmark_data/validation/*.jpg"))
    print(f"Loaded {len(val_images)} validation CCTV frames.")
    
    models = [
        {"name": "ONNX FP32", "type": "onnx", "path": "/h3/anas/ABLBL_Afterhours/models/yolo26n.onnx"},
        {"name": "TRT FP32", "type": "trt", "path": "/h3/anas/ABLBL_Afterhours/benchmark_engines/yolo26n_fp32.engine"},
        {"name": "TRT FP16", "type": "trt", "path": "/h3/anas/ABLBL_Afterhours/benchmark_engines/yolo26n_fp16.engine"},
        {"name": "TRT INT8", "type": "trt", "path": "/h3/anas/ABLBL_Afterhours/benchmark_engines/yolo26n_int8.engine"},
    ]
    
    results = {}
    baseline_detections = None
    
    for m in models:
        name = m["name"]
        print(f"\n>>> Running Configuration: {name} <<<")
        
        # Engine / model size
        size_mb = os.path.getsize(m["path"]) / (1024 * 1024)
        
        # System baseline memory
        init_gpu = get_gpu_metrics()
        init_host_ram = psutil.virtual_memory().used / (1024 * 1024)
        
        # Load model
        is_trt = (m["type"] == "trt")
        t_load_start = time.time()
        if is_trt:
            wrapper = TRTWrapper(m["path"])
        else:
            wrapper = ONNXWrapper(m["path"])
        load_time = time.time() - t_load_start
        
        # 1. Inference Latency & Throughput across Batch Sizes
        print("  1. Profiling Batch Inference (BS 1, 4, 8, 16)...")
        batch_results = run_inference_latency_benchmark(wrapper, is_trt=is_trt, batch_sizes=[1, 4, 8, 16], warmup=30, iterations=150)
        
        # Telemetry check under load
        mid_gpu = get_gpu_metrics()
        cpu_pct = psutil.cpu_percent(interval=0.5)
        curr_host_ram = psutil.virtual_memory().used / (1024 * 1024)
        
        # 2. End-to-End Latency (500 inferences)
        print("  2. Profiling End-to-End Pipeline (500 iterations)...")
        e2e_results = run_end_to_end_benchmark(wrapper, is_trt=is_trt, image_paths=val_images, num_iterations=500)
        
        peak_gpu = get_gpu_metrics()
        
        # 3. Accuracy Benchmark
        print("  3. Profiling Detection Accuracy & Consistency...")
        if name == "ONNX FP32":
            acc_results, baseline_detections = run_accuracy_benchmark(wrapper, is_trt, {}, val_images)
            # Baseline compared with itself
            acc_results = {
                "detections_count": acc_results["detections_count"],
                "baseline_detections_count": acc_results["detections_count"],
                "mean_iou": 1.0,
                "mean_conf_delta": 0.0,
                "precision": 1.0,
                "recall": 1.0,
                "map_50": 1.0,
                "map_50_95": 1.0
            }
        else:
            acc_results, _ = run_accuracy_benchmark(wrapper, is_trt, baseline_detections, val_images)
            
        results[name] = {
            "engine_size_mb": size_mb,
            "load_time_s": load_time,
            "batches": batch_results,
            "end_to_end": e2e_results,
            "accuracy": acc_results,
            "hardware": {
                "peak_vram_mb": max(init_gpu["vram_mb"], mid_gpu["vram_mb"], peak_gpu["vram_mb"]),
                "avg_gpu_util": float((init_gpu["gpu_util"] + mid_gpu["gpu_util"] + peak_gpu["gpu_util"]) / 3.0),
                "cpu_util_pct": float(cpu_pct),
                "host_ram_mb": float(curr_host_ram),
                "gpu_temp_c": peak_gpu["temp_c"],
                "gpu_power_w": peak_gpu["power_w"]
            }
        }
        print(f"Done testing {name}.")
        
    # Save raw results
    output_json = "/h3/anas/ABLBL_Afterhours/benchmark/results/benchmark_summary.json"
    with open(output_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[Done] Raw benchmark saved to {output_json}")
    
    # Generate Charts
    generate_charts(results)
    
def generate_charts(results):
    res_dir = "/h3/anas/ABLBL_Afterhours/benchmark/results"
    configs = list(results.keys())
    
    # 1. Latency Comparison Chart (BS 1 & BS 16)
    plt.figure(figsize=(10, 6))
    x = np.arange(len(configs))
    width = 0.35
    
    bs1_lats = [results[c]["batches"][1]["avg_ms"] for c in configs]
    bs16_lats = [results[c]["batches"][16]["avg_ms"] for c in configs]
    
    plt.bar(x - width/2, bs1_lats, width, label='Batch Size 1 (ms)', color='#3498db')
    plt.bar(x + width/2, bs16_lats, width, label='Batch Size 16 (ms)', color='#e74c3c')
    plt.ylabel('Inference Latency (ms, lower is better)', fontsize=12)
    plt.title('YOLO26n Inference Latency: ONNX Runtime vs TensorRT on RTX A4000', fontsize=14, fontweight='bold')
    plt.xticks(x, configs, fontsize=11)
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig(os.path.join(res_dir, "latency_comparison.png"), dpi=200)
    plt.close()
    
    # 2. Throughput Comparison Chart (FPS)
    plt.figure(figsize=(10, 6))
    bs1_fps = [results[c]["batches"][1]["throughput_fps"] for c in configs]
    bs16_fps = [results[c]["batches"][16]["throughput_fps"] for c in configs]
    
    plt.bar(x - width/2, bs1_fps, width, label='BS 1 Throughput (FPS)', color='#2ecc71')
    plt.bar(x + width/2, bs16_fps, width, label='BS 16 Throughput (FPS)', color='#9b59b6')
    plt.ylabel('Throughput (FPS, higher is better)', fontsize=12)
    plt.title('Throughput Across Batch Sizes on NVIDIA RTX A4000', fontsize=14, fontweight='bold')
    plt.xticks(x, configs, fontsize=11)
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig(os.path.join(res_dir, "throughput_comparison.png"), dpi=200)
    plt.close()
    
    # 3. Accuracy vs Throughput Trade-off
    plt.figure(figsize=(9, 6))
    fps_vals = [results[c]["batches"][1]["throughput_fps"] for c in configs]
    map_vals = [results[c]["accuracy"]["map_50"] * 100 for c in configs]
    
    colors = ['#34495e', '#3498db', '#2ecc71', '#e67e22']
    for i, c in enumerate(configs):
        plt.scatter(fps_vals[i], map_vals[i], s=200, color=colors[i], label=c)
        plt.annotate(c, (fps_vals[i]+5, map_vals[i]-0.1), fontsize=11, fontweight='bold')
        
    plt.xlabel('Single-Image Throughput (FPS)', fontsize=12)
    plt.ylabel('mAP@0.5 (%) relative to Baseline', fontsize=12)
    plt.title('Accuracy vs. Throughput Trade-Off on RTX A4000', fontsize=14, fontweight='bold')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.savefig(os.path.join(res_dir, "accuracy_vs_throughput.png"), dpi=200)
    plt.close()
    
    # 4. Peak VRAM & Engine Size
    plt.figure(figsize=(10, 6))
    vram = [results[c]["hardware"]["peak_vram_mb"] for c in configs]
    plt.bar(configs, vram, color=['#1abc9c', '#3498db', '#9b59b6', '#f39c12'])
    plt.ylabel('Peak VRAM Allocation (MB)', fontsize=12)
    plt.title('Peak GPU VRAM Consumption by Engine Configuration', fontsize=14, fontweight='bold')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig(os.path.join(res_dir, "vram_comparison.png"), dpi=200)
    plt.close()
    print("[Done] Generated all 4 comparison charts.")

if __name__ == "__main__":
    main()
