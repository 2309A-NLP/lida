"""工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务

图像预处理与文件保存逻辑。
"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Dict, Tuple

import cv2
import numpy as np
from PIL import Image


def load_image(image: str | Path | Image.Image) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    return Image.open(image).convert("RGB")


def image_to_data_url(image: Image.Image, image_format: str = "PNG") -> str:
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    mime = f"image/{image_format.lower()}"
    return f"data:{mime};base64,{encoded}"


def detect_primary_face_bbox(image: Image.Image) -> Tuple[int, int, int, int] | None:
    rgb = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    classifier = cv2.CascadeClassifier(cascade_path)
    faces = classifier.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
    if len(faces) == 0:
        return None

    x, y, w, h = max(faces, key=lambda item: item[2] * item[3])
    return int(x), int(y), int(w), int(h)


def crop_face_to_square(image: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    bbox = detect_primary_face_bbox(image)
    width, height = image.size

    if bbox is None:
        side = min(width, height)
        left = (width - side) // 2
        upper = (height - side) // 2
        cropped = image.crop((left, upper, left + side, upper + side))
        return cropped.resize(target_size, Image.Resampling.LANCZOS)

    x, y, w, h = bbox
    side = int(max(w, h) * 1.9)
    center_x = x + w // 2
    center_y = y + h // 2

    left = max(0, center_x - side // 2)
    top = max(0, center_y - side // 2)
    right = min(width, left + side)
    bottom = min(height, top + side)

    if right - left < side:
        left = max(0, right - side)
    if bottom - top < side:
        top = max(0, bottom - side)

    cropped = image.crop((left, top, right, bottom))
    return cropped.resize(target_size, Image.Resampling.LANCZOS)


def save_named_images(images: Dict[str, Image.Image], output_dir: Path) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    saved: Dict[str, Path] = {}
    for name, image in images.items():
        path = output_dir / f"{name}.png"
        image.save(path)
        saved[f"{name}_path"] = path
    return saved
