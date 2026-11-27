"""
TensorRT Engine Builder for YOLO26n (DETR architecture)
Supports FP32, FP16, and INT8 precision modes with dynamic batching.
Uses PyTorch CUDA tensors for memory allocation and buffer management.
"""

import os
import sys
import glob
import time
import cv2
import numpy as np
import torch
import tensorrt as trt

TRT_LOGGER = trt.Logger(trt.Logger.INFO)

class YOLOINT8Calibrator(trt.IInt8EntropyCalibrator2):
    def __init__(self, calibration_images, cache_file, batch_size=8, input_shape=(3, 640, 640)):
        super().__init__()
        self.cache_file = cache_file
        self.image_paths = calibration_images
        self.batch_size = batch_size
        self.input_shape = input_shape
        self.current_index = 0
        
        # Allocate device memory via torch on RTX A4000
        self.device_tensor = torch.zeros((batch_size, *input_shape), dtype=torch.float32, device="cuda:0")
        self.device_ptr = int(self.device_tensor.data_ptr())
        print(f"[Calibrator] Initialized with {len(self.image_paths)} images, batch size {batch_size}, cache: {cache_file}")

    def preprocess_image(self, img_path):
        """Exact letterbox preprocessing matching yolo26_detector.py"""
        img = cv2.imread(img_path)
        if img is None:
            return np.zeros((3, 640, 640), dtype=np.float32)
        h, w = img.shape[:2]
        r = min(640 / h, 640 / w)
        nh, nw = int(round(h * r)), int(round(w * r))
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        
        # Letterbox padding with 114
        canvas = np.full((640, 640, 3), 114, dtype=np.uint8)
        top = (640 - nh) // 2
        left = (640 - nw) // 2
        canvas[top:top+nh, left:left+nw] = resized
        
        # BGR -> RGB, [0, 1] scale, HWC -> CHW
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        norm = (rgb.astype(np.float32) / 255.0).transpose(2, 0, 1)
        return norm

    def get_batch_size(self):
        return self.batch_size

    def get_batch(self, names):
        if self.current_index + self.batch_size > len(self.image_paths):
            return None
        
        batch_paths = self.image_paths[self.current_index:self.current_index + self.batch_size]
        batch_data = np.stack([self.preprocess_image(p) for p in batch_paths], axis=0)
        
        # Copy to device tensor
        host_tensor = torch.from_numpy(batch_data).float()
        self.device_tensor.copy_(host_tensor)
        
        self.current_index += self.batch_size
        if self.current_index % 80 == 0:
            print(f"[Calibrator] Calibrated {self.current_index}/{len(self.image_paths)} images...")
        return [self.device_ptr]

    def read_calibration_cache(self):
        if os.path.exists(self.cache_file):
            print(f"[Calibrator] Loading cached calibration from {self.cache_file}")
            with open(self.cache_file, "rb") as f:
                return f.read()
        return None

    def write_calibration_cache(self, cache):
        print(f"[Calibrator] Writing calibration cache to {self.cache_file}")
        with open(self.cache_file, "wb") as f:
            f.write(cache)


def build_engine(onnx_path, engine_path, precision="FP32", calibrator=None):
    print(f"\n=======================================================")
    print(f"Building TensorRT Engine: {precision}")
    print(f"ONNX: {onnx_path}")
    print(f"Output: {engine_path}")
    print(f"=======================================================")
    start_time = time.time()
    
    builder = trt.Builder(TRT_LOGGER)
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    parser = trt.OnnxParser(network, TRT_LOGGER)
    
    with open(onnx_path, 'rb') as model:
        if not parser.parse(model.read()):
            print("ERROR: Failed to parse the ONNX file.")
            for error in range(parser.num_errors):
                print(parser.get_error(error))
            return None
            
    config = builder.create_builder_config()
    
    # 4GB workspace
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 4 * 1024 * 1024 * 1024)
    
    # Setup optimization profile for dynamic batch sizes: min 1, opt 8, max 16
    profile = builder.create_optimization_profile()
    input_name = network.get_input(0).name
    profile.set_shape(input_name, (1, 3, 640, 640), (8, 3, 640, 640), (16, 3, 640, 640))
    config.add_optimization_profile(profile)
    
    if precision == "FP16":
        if builder.platform_has_fast_fp16:
            config.set_flag(trt.BuilderFlag.FP16)
            print("[Build] Enabled FP16 precision")
        else:
            print("[Build] WARNING: Platform does not have fast FP16")
    elif precision == "INT8":
        if builder.platform_has_fast_int8:
            config.set_flag(trt.BuilderFlag.INT8)
            config.set_flag(trt.BuilderFlag.FP16) # Fallback to FP16 for sensitive layers
            if calibrator is not None:
                config.int8_calibrator = calibrator
                print("[Build] Enabled INT8 precision with EntropyCalibrator2")
            else:
                print("[Build] ERROR: Calibrator required for INT8!")
                return None
        else:
            print("[Build] WARNING: Platform does not support fast INT8")

    # Serialize engine
    print(f"[Build] Compiling engine (this may take 2-4 minutes)...")
    serialized_engine = builder.build_serialized_network(network, config)
    if serialized_engine is None:
        print("[Build] ERROR: Failed to build serialized engine!")
        return None
        
    with open(engine_path, "wb") as f:
        f.write(serialized_engine)
        
    elapsed = time.time() - start_time
    size_mb = os.path.getsize(engine_path) / (1024 * 1024)
    print(f"[Build] Finished in {elapsed:.1f}s | Built {engine_path} ({size_mb:.2f} MB)")
    return engine_path, elapsed, size_mb


if __name__ == "__main__":
    onnx_file = "/h3/anas/ABLBL_Afterhours/models/yolo26n.onnx"
    output_dir = "/h3/anas/ABLBL_Afterhours/benchmark_engines"
    calib_dir = "/h3/anas/ABLBL_Afterhours/benchmark_data/calibration"
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. FP32 Engine
    fp32_engine = os.path.join(output_dir, "yolo26n_fp32.engine")
    if not os.path.exists(fp32_engine):
        build_engine(onnx_file, fp32_engine, precision="FP32")
    else:
        print(f"[Skip] FP32 engine already exists: {fp32_engine}")

    # 2. FP16 Engine
    fp16_engine = os.path.join(output_dir, "yolo26n_fp16.engine")
    if not os.path.exists(fp16_engine):
        build_engine(onnx_file, fp16_engine, precision="FP16")
    else:
        print(f"[Skip] FP16 engine already exists: {fp16_engine}")

    # 3. INT8 Engine
    int8_engine = os.path.join(output_dir, "yolo26n_int8.engine")
    cache_file = os.path.join(output_dir, "yolo26n_int8.cache")
    if not os.path.exists(int8_engine):
        calib_images = sorted(glob.glob(os.path.join(calib_dir, "*.jpg")))
        print(f"[INT8] Found {len(calib_images)} calibration images")
        calibrator = YOLOINT8Calibrator(calib_images, cache_file=cache_file, batch_size=8)
        build_engine(onnx_file, int8_engine, precision="INT8", calibrator=calibrator)
    else:
        print(f"[Skip] INT8 engine already exists: {int8_engine}")
