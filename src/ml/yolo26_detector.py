import os
import sys
import glob
import ctypes

# Pre-load all NVIDIA CUDA/cuDNN/cuRAND/cuFFT shared objects into global process memory
for p in sys.path:
    nvidia_dir = os.path.join(p, "nvidia")
    if os.path.exists(nvidia_dir):
        for sub in os.listdir(nvidia_dir):
            lib_dir = os.path.join(nvidia_dir, sub, "lib")
            if os.path.exists(lib_dir):
                for so_file in sorted(os.listdir(lib_dir)):
                    if ".so" in so_file:
                        try:
                            ctypes.CDLL(os.path.join(lib_dir, so_file), mode=ctypes.RTLD_GLOBAL)
                        except Exception:
                            pass

import cv2
import numpy as np
import logging
from typing import List, Dict, Any, Tuple, Optional
import onnxruntime as ort
from src.ml.model_downloader import ensure_model_exists

logger = logging.getLogger("ABLBL_Afterhours.YOLO26Detector")

class YOLO26Detector:
    """
    High-performance batched YOLO26n detector deployed on ONNX Runtime.
    Explicitly uses GPU 0 with CUDAExecutionProvider for ultra-low latency & high throughput.
    """
    def __init__(
        self,
        model_path: str = "models/yolo26n.onnx",
        device_id: int = 0,
        conf_threshold: float = 0.45,
        iou_threshold: float = 0.45,
        input_size: Tuple[int, int] = (640, 640),
        auto_download: bool = True
    ):
        self.model_path = model_path
        self.device_id = device_id
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.input_width, self.input_height = input_size
        self.person_class_id = 0

        if auto_download and not os.path.exists(self.model_path):
            ensure_model_exists(self.model_path)

        # Configure ONNX Runtime Session Options
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        opts.intra_op_num_threads = 4

        # Configure CUDA Provider targeting GPU 0
        cuda_provider_options = {
            "device_id": self.device_id,
            "arena_extend_strategy": "kSameAsRequested",
            "gpu_mem_limit": 4 * 1024 * 1024 * 1024,  # 4GB limit on GPU 0
            "cudnn_conv_algo_search": "EXHAUSTIVE",
            "do_copy_in_default_stream": True
        }

        providers = [
            ("CUDAExecutionProvider", cuda_provider_options),
            "CPUExecutionProvider"
        ]

        logger.info(f"Initializing ONNX session with providers: {providers} on GPU {self.device_id}...")
        self.session = ort.InferenceSession(self.model_path, sess_options=opts, providers=providers)
        
        active_providers = self.session.get_providers()
        logger.info(f"Active ONNX Runtime providers: {active_providers}")
        if "CUDAExecutionProvider" in active_providers:
            logger.info(f"YOLO26n successfully running on NVIDIA GPU {self.device_id}!")
        else:
            logger.warning(f"CUDA provider not available; falling back to CPU.")

        # Cache input and output metadata
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        self.output_names = [o.name for o in self.session.get_outputs()]
        logger.info(f"Model Input: {self.input_name} {self.input_shape}, Outputs: {self.output_names}")

        # Warmup GPU 0
        self._warmup()

    def _warmup(self, warmup_runs: int = 3):
        """Warms up CUDA engine to eliminate cold-start latency."""
        try:
            logger.info("Warming up YOLO26n on GPU 0...")
            dummy_batch = np.zeros((1, 3, self.input_height, self.input_width), dtype=np.float32)
            for _ in range(warmup_runs):
                self.session.run(self.output_names, {self.input_name: dummy_batch})
            logger.info("Warmup complete. Ready for real-time surveillance sweeps.")
        except Exception as e:
            logger.warning(f"Warmup warning: {e}")

    def _preprocess_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, float, float, int, int]:
        """
        Preprocesses a single OpenCV BGR image:
        Letterbox pad & resize to (input_height, input_width), normalize to [0, 1], transpose to CHW.
        Returns:
            processed_chw (3, H, W)
            ratio, pad_x, pad_y, orig_w, orig_h
        """
        orig_h, orig_w = frame.shape[:2]
        
        # Calculate letterbox scale
        r = min(self.input_width / orig_w, self.input_height / orig_h)
        new_unpad_w = int(round(orig_w * r))
        new_unpad_h = int(round(orig_h * r))
        
        # Resize
        if (orig_w, orig_h) != (new_unpad_w, new_unpad_h):
            resized = cv2.resize(frame, (new_unpad_w, new_unpad_h), interpolation=cv2.INTER_LINEAR)
        else:
            resized = frame

        # Compute padding
        dw = self.input_width - new_unpad_w
        dh = self.input_height - new_unpad_h
        pad_x = dw // 2
        pad_y = dh // 2

        # Create padded canvas (grey 114)
        canvas = np.full((self.input_height, self.input_width, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + new_unpad_h, pad_x:pad_x + new_unpad_w] = resized

        # BGR to RGB, normalize, HWC to CHW
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        chw = rgb.astype(np.float32) / 255.0
        chw = np.transpose(chw, (2, 0, 1))

        return chw, r, pad_x, pad_y, orig_w, orig_h

    def detect_batch(self, frames: List[np.ndarray]) -> List[List[Dict[str, Any]]]:
        """
        Runs batch inference across multiple frames on GPU 0.
        Returns a list of detections for each frame:
            [
              [ {"box": [x1, y1, x2, y2], "confidence": float, "class_id": 0, "label": "person"}, ... ],
              ...
            ]
        """
        if not frames:
            return []

        batch_chw = []
        meta_list = []

        for frame in frames:
            chw, r, pad_x, pad_y, orig_w, orig_h = self._preprocess_frame(frame)
            batch_chw.append(chw)
            meta_list.append((r, pad_x, pad_y, orig_w, orig_h))

        input_tensor = np.ascontiguousarray(np.stack(batch_chw, axis=0), dtype=np.float32)

        # Execute ONNX inference on GPU 0
        raw_outputs = self.session.run(self.output_names, {self.input_name: input_tensor})

        all_results = []
        batch_size = len(frames)

        for b in range(batch_size):
            r, pad_x, pad_y, orig_w, orig_h = meta_list[b]
            frame_detections = self._parse_detections(raw_outputs, b, r, pad_x, pad_y, orig_w, orig_h)
            all_results.append(frame_detections)

        return all_results

    def _parse_detections(
        self,
        raw_outputs: List[np.ndarray],
        batch_idx: int,
        ratio: float,
        pad_x: int,
        pad_y: int,
        orig_w: int,
        orig_h: int
    ) -> List[Dict[str, Any]]:
        """
        Parses output for a single item in the batch.
        Supports:
        1. YOLO26/DETR dual outputs: raw_outputs[0]=logits (B, 300, 80), raw_outputs[1]=pred_boxes (B, 300, 4)
        2. Single output (B, N, 6) end-to-end format
        3. Single output (B, 84, 8400) standard YOLO format
        Filters specifically for person detections (class 0).
        """
        detections = []

        # Case 1: Dual outputs: logits (B, 300, 80) and pred_boxes (B, 300, 4)
        if len(raw_outputs) >= 2 and len(raw_outputs[0].shape) == 3 and len(raw_outputs[1].shape) == 3:
            logits = raw_outputs[0][batch_idx]  # (300, 80)
            pred_boxes = raw_outputs[1][batch_idx]  # (300, 4) in [cx, cy, w, h] normalized [0, 1]

            # Sigmoid activation for person class (index 0)
            person_scores = 1.0 / (1.0 + np.exp(-logits[:, self.person_class_id]))
            mask = person_scores >= self.conf_threshold

            if np.any(mask):
                valid_indices = np.where(mask)[0]
                valid_scores = person_scores[valid_indices]
                valid_boxes = pred_boxes[valid_indices]

                boxes_xyxy = []
                boxes_xywh = []
                for box in valid_boxes:
                    cx_p = box[0] * self.input_width
                    cy_p = box[1] * self.input_height
                    w_p = box[2] * self.input_width
                    h_p = box[3] * self.input_height

                    x1 = (cx_p - w_p / 2.0 - pad_x) / ratio
                    y1 = (cy_p - h_p / 2.0 - pad_y) / ratio
                    x2 = (cx_p + w_p / 2.0 - pad_x) / ratio
                    y2 = (cy_p + h_p / 2.0 - pad_y) / ratio

                    rx1 = max(0, min(orig_w - 1, int(round(x1))))
                    ry1 = max(0, min(orig_h - 1, int(round(y1))))
                    rx2 = max(0, min(orig_w - 1, int(round(x2))))
                    ry2 = max(0, min(orig_h - 1, int(round(y2))))

                    boxes_xyxy.append([rx1, ry1, rx2, ry2])
                    boxes_xywh.append([rx1, ry1, max(1, rx2 - rx1), max(1, ry2 - ry1)])

                # NMS to suppress overlapping queries
                indices = cv2.dnn.NMSBoxes(boxes_xywh, valid_scores.tolist(), self.conf_threshold, self.iou_threshold)
                if len(indices) > 0:
                    for idx in np.array(indices).flatten():
                        detections.append({
                            "box": boxes_xyxy[idx],
                            "confidence": float(valid_scores[idx]),
                            "class_id": self.person_class_id,
                            "label": "person"
                        })
            return detections

        # Case 2 & 3: Single output array
        output = raw_outputs[0]
        # Case A: (B, N, 6) where each box is [x1, y1, x2, y2, score, class_id]
        if len(output.shape) == 3 and output.shape[2] == 6:
            boxes_data = output[batch_idx]
            for row in boxes_data:
                x1, y1, x2, y2, score, cls_id = row[:6]
                if int(cls_id) == self.person_class_id and score >= self.conf_threshold:
                    box = self._rescale_box(x1, y1, x2, y2, ratio, pad_x, pad_y, orig_w, orig_h)
                    detections.append({
                        "box": box,
                        "confidence": float(score),
                        "class_id": int(cls_id),
                        "label": "person"
                    })

        # Case B: (B, 6, N)
        elif len(output.shape) == 3 and output.shape[1] == 6:
            boxes_data = np.transpose(output[batch_idx], (1, 0))
            for row in boxes_data:
                x1, y1, x2, y2, score, cls_id = row[:6]
                if int(cls_id) == self.person_class_id and score >= self.conf_threshold:
                    box = self._rescale_box(x1, y1, x2, y2, ratio, pad_x, pad_y, orig_w, orig_h)
                    detections.append({
                        "box": box,
                        "confidence": float(score),
                        "class_id": int(cls_id),
                        "label": "person"
                    })

        # Case C: Standard YOLO format (B, 84, 8400) or (B, 8400, 84)
        elif len(output.shape) == 3:
            preds = output[batch_idx]
            if preds.shape[0] < preds.shape[1]:
                preds = np.transpose(preds, (1, 0))

            boxes_xywh = preds[:, :4]
            person_scores = preds[:, 4]

            mask = person_scores >= self.conf_threshold
            if np.any(mask):
                valid_boxes = boxes_xywh[mask]
                valid_scores = person_scores[mask]

                x1 = valid_boxes[:, 0] - valid_boxes[:, 2] / 2
                y1 = valid_boxes[:, 1] - valid_boxes[:, 3] / 2
                x2 = valid_boxes[:, 0] + valid_boxes[:, 2] / 2
                y2 = valid_boxes[:, 1] + valid_boxes[:, 3] / 2

                cv_boxes = [[int(x1[i]), int(y1[i]), int(valid_boxes[i, 2]), int(valid_boxes[i, 3])] for i in range(len(valid_scores))]
                indices = cv2.dnn.NMSBoxes(cv_boxes, valid_scores.tolist(), self.conf_threshold, self.iou_threshold)

                if len(indices) > 0:
                    for idx in np.array(indices).flatten():
                        bx = self._rescale_box(x1[idx], y1[idx], x2[idx], y2[idx], ratio, pad_x, pad_y, orig_w, orig_h)
                        detections.append({
                            "box": bx,
                            "confidence": float(valid_scores[idx]),
                            "class_id": 0,
                            "label": "person"
                        })

        return detections

    def _rescale_box(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        ratio: float,
        pad_x: int,
        pad_y: int,
        orig_w: int,
        orig_h: int
    ) -> List[int]:
        """Rescales letterboxed coordinates back to original frame pixel bounds."""
        rx1 = (x1 - pad_x) / ratio
        ry1 = (y1 - pad_y) / ratio
        rx2 = (x2 - pad_x) / ratio
        ry2 = (y2 - pad_y) / ratio

        rx1 = max(0, min(orig_w - 1, int(round(rx1))))
        ry1 = max(0, min(orig_h - 1, int(round(ry1))))
        rx2 = max(0, min(orig_w - 1, int(round(rx2))))
        ry2 = max(0, min(orig_h - 1, int(round(ry2))))

        return [rx1, ry1, rx2, ry2]

    def annotate_frame(self, frame: np.ndarray, detections: List[Dict[str, Any]], camera_name: str = "", timestamp_str: str = "") -> np.ndarray:
        """
        Draws professional bounding boxes and alert overlays onto the frame.
        """
        annotated = frame.copy()
        h, w = annotated.shape[:2]

        # Top banner with security status
        banner_h = 42
        overlay = annotated.copy()
        cv2.rectangle(overlay, (0, 0), (w, banner_h), (18, 18, 28), -1)
        cv2.addWeighted(overlay, 0.75, annotated, 0.25, 0, annotated)

        # Header text
        header_text = f"ABLBL AFTERHOURS SENTINEL | {camera_name} | {timestamp_str}"
        cv2.putText(annotated, header_text, (16, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (220, 220, 220), 2, cv2.LINE_AA)

        # Draw detections
        for det in detections:
            box = det["box"]
            conf = det["confidence"]
            x1, y1, x2, y2 = box

            # Neon Red/Crimson alert box
            color = (0, 50, 255)  # Crimson Red in BGR
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)

            # Draw corner accents for high-tech HUD look
            c_len = min(20, (x2 - x1) // 4, (y2 - y1) // 4)
            corner_color = (0, 220, 255)  # Yellow/Gold accent
            # Top-left
            cv2.line(annotated, (x1, y1), (x1 + c_len, y1), corner_color, 4)
            cv2.line(annotated, (x1, y1), (x1, y1 + c_len), corner_color, 4)
            # Top-right
            cv2.line(annotated, (x2, y1), (x2 - c_len, y1), corner_color, 4)
            cv2.line(annotated, (x2, y1), (x2, y1 + c_len), corner_color, 4)
            # Bottom-left
            cv2.line(annotated, (x1, y2), (x1 + c_len, y2), corner_color, 4)
            cv2.line(annotated, (x1, y2), (x1, y2 - c_len), corner_color, 4)
            # Bottom-right
            cv2.line(annotated, (x2, y2), (x2 - c_len, y2), corner_color, 4)
            cv2.line(annotated, (x2, y2), (x2, y2 - c_len), corner_color, 4)

            # Label badge
            label_text = f"PERSON {conf * 100:.1f}%"
            (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            badge_y1 = max(0, y1 - th - 10)
            badge_y2 = y1
            cv2.rectangle(annotated, (x1, badge_y1), (x1 + tw + 12, badge_y2), color, -1)
            cv2.putText(annotated, label_text, (x1 + 6, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

        return annotated
