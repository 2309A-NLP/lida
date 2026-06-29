"""工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务

阿里云百炼在线图像处理主流程。
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, Iterable

import requests
from PIL import Image
from requests.exceptions import ProxyError

from src.config import GenerationConfig
from src.image_utils import crop_face_to_square, image_to_data_url, load_image, save_named_images
from src.prompting import build_pose_prompts


ProgressCallback = Callable[[float, str], None]


class StableDiffusionFaceTurnAgent:
    def __init__(self, config: GenerationConfig | None = None) -> None:
        self.config = config or GenerationConfig()
        self.device = "bailian-online"
        self.session = requests.Session()
        self.session.trust_env = False

    def _require_api_key(self) -> str:
        api_key = self.config.api_key.strip()
        if not api_key:
            raise RuntimeError("未检测到百炼 API Key，请先设置 DASHSCOPE_API_KEY 或 BAILIAN_API_KEY。")
        return api_key

    def _headers(self, async_mode: bool = False) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._require_api_key()}",
            "Content-Type": "application/json",
        }
        if async_mode:
            headers["X-DashScope-Async"] = "enable"
        return headers

    @staticmethod
    def _normalize_expand_scale(value: float) -> float:
        return max(1.0, float(value))

    def _create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self.session.post(
            self.config.endpoint,
            headers=self._headers(async_mode=True),
            json=payload,
            timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def _create_pose_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self.session.post(
            self.config.pose_endpoint,
            headers=self._headers(async_mode=True),
            json=payload,
            timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def _poll_task(self, task_id: str) -> Dict[str, Any]:
        deadline = time.time() + self.config.task_timeout_seconds
        task_url = self.config.task_endpoint_template.format(task_id=task_id)
        last_payload: Dict[str, Any] | None = None

        while time.time() < deadline:
            response = self.session.get(
                task_url,
                headers={"Authorization": f"Bearer {self._require_api_key()}"},
                timeout=self.config.request_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            last_payload = payload

            status = payload.get("output", {}).get("task_status", "")
            if status == "SUCCEEDED":
                return payload
            if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                code = payload.get("output", {}).get("code") or payload.get("code") or "UnknownError"
                message = payload.get("output", {}).get("message") or payload.get("message") or "任务失败"
                raise RuntimeError(f"百炼任务失败: {code} - {message}")

            time.sleep(self.config.poll_interval_seconds)

        raise TimeoutError(
            f"百炼任务超时，{self.config.task_timeout_seconds} 秒内未完成。最近响应: {last_payload}"
        )

    def _download_image(self, image_url: str) -> Image.Image:
        try:
            response = self.session.get(image_url, timeout=self.config.request_timeout_seconds)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert("RGB")
        except ProxyError:
            fallback_session = requests.Session()
            fallback_session.trust_env = False
            response = fallback_session.get(image_url, timeout=self.config.request_timeout_seconds)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert("RGB")

    @staticmethod
    def _extract_image_url(payload: Dict[str, Any]) -> str | None:
        output = payload.get("output", {})

        for item in output.get("results", []):
            url = item.get("url")
            if url:
                return url

        for choice in output.get("choices", []):
            message = choice.get("message", {})
            for content in message.get("content", []):
                image = content.get("image")
                if image:
                    return image

        return None

    def _run_edit_task(
        self,
        *,
        image: Image.Image,
        function_name: str,
        prompt: str,
        seed: int,
        parameters: Dict[str, Any] | None = None,
    ) -> tuple[Image.Image, Dict[str, Any]]:
        payload = {
            "model": self.config.model_id,
            "input": {
                "function": function_name,
                "prompt": prompt,
                "base_image_url": image_to_data_url(image),
            },
            "parameters": {
                "n": self.config.output_count,
                "seed": seed,
                **(parameters or {}),
            },
        }

        created = self._create_task(payload)
        task_id = created.get("output", {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"创建百炼任务失败，未返回 task_id: {created}")

        finished = self._poll_task(task_id)
        image_url = self._extract_image_url(finished)
        if not image_url:
            raise RuntimeError(f"百炼任务已完成，但未返回图像 URL: {finished}")

        image_result = self._download_image(image_url)
        meta = {
            "task_id": task_id,
            "task_status": finished.get("output", {}).get("task_status"),
            "image_url": image_url,
        }
        return image_result, meta

    def preprocess(self, image: str | Path | Image.Image) -> Image.Image:
        source = load_image(image)
        return crop_face_to_square(source, target_size=(self.config.width, self.config.height))

    def generate_pose(
        self,
        reference_images: Iterable[Image.Image],
        prompt: str,
        negative_prompt: str,
        seed: int,
    ) -> tuple[Image.Image, Dict[str, Any]]:
        merged_prompt = (
            f"{prompt}. Keep the same person identity and facial geometry. "
            f"Keep the same hairstyle, same shirt and same studio background. "
            f"Must look like a real photograph captured by a camera. "
            f"Avoid: {negative_prompt}."
        )
        content: list[Dict[str, str]] = [{"image": image_to_data_url(image)} for image in reference_images]
        content.append({"text": merged_prompt})

        payload = {
            "model": self.config.pose_model_id,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": content,
                    }
                ]
            },
            "parameters": {
                "size": self.config.pose_size,
                "n": 1,
                "watermark": False,
                "seed": seed,
            },
        }

        created = self._create_pose_task(payload)
        task_id = created.get("output", {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"创建姿态任务失败，未返回 task_id: {created}")

        finished = self._poll_task(task_id)
        image_url = self._extract_image_url(finished)
        if not image_url:
            raise RuntimeError(f"姿态任务已完成，但未返回图像 URL: {finished}")

        image_result = self._download_image(image_url)
        meta = {
            "task_id": task_id,
            "task_status": finished.get("output", {}).get("task_status"),
            "image_url": image_url,
        }
        return image_result, meta

    def outpaint(self, image: Image.Image, subject_hint: str, seed: int) -> tuple[Image.Image, Dict[str, Any]]:
        prompt = (
            "Expand this studio portrait into a clean upper-body formal headshot. "
            "Extend only the shoulders, chest, clothing outline and neutral seamless background. "
            "Keep the same face identity exactly, keep the same hairstyle, keep the same expression, "
            "keep realistic proportions, keep the background plain and professional. "
            "Do not add text, symbols, wall patterns, extra people, extra limbs, props or random objects."
        )
        if subject_hint.strip():
            prompt = f"{prompt}, {subject_hint.strip()}"

        return self._run_edit_task(
            image=image,
            function_name="expand",
            prompt=prompt,
            seed=seed,
            parameters={
                "top_scale": self._normalize_expand_scale(self.config.expand_top_scale),
                "bottom_scale": self._normalize_expand_scale(self.config.expand_bottom_scale),
                "left_scale": self._normalize_expand_scale(self.config.expand_left_scale),
                "right_scale": self._normalize_expand_scale(self.config.expand_right_scale),
            },
        )

    def run_full_workflow(
        self,
        image: str | Path | Image.Image,
        subject_hint: str = "",
        seed: int = 42,
        output_dir: str | Path = "outputs",
        progress_callback: ProgressCallback | None = None,
    ) -> Dict[str, Any]:
        if progress_callback:
            progress_callback(0.05, "正在预处理原图")

        preprocessed = self.preprocess(image)
        pose_prompts = build_pose_prompts(subject_hint=subject_hint, negative_prompt=self.config.negative_prompt)
        task_records: Dict[str, Dict[str, Any]] = {}

        if progress_callback:
            progress_callback(0.18, "正在生成端正图")
        front, front_meta = self.generate_pose(
            reference_images=[preprocessed],
            prompt=pose_prompts["front"].positive,
            negative_prompt=pose_prompts["front"].negative,
            seed=seed,
        )
        task_records["front"] = front_meta

        if progress_callback:
            progress_callback(0.40, "正在生成左转图")
        left_turn, left_meta = self.generate_pose(
            reference_images=[preprocessed, front],
            prompt=pose_prompts["left_turn"].positive,
            negative_prompt=pose_prompts["left_turn"].negative,
            seed=seed + 1,
        )
        task_records["left_turn"] = left_meta

        if progress_callback:
            progress_callback(0.62, "正在生成右转图")
        right_turn, right_meta = self.generate_pose(
            reference_images=[preprocessed, front],
            prompt=pose_prompts["right_turn"].positive,
            negative_prompt=pose_prompts["right_turn"].negative,
            seed=seed + 2,
        )
        task_records["right_turn"] = right_meta

        if progress_callback:
            progress_callback(0.82, "正在生成扩图结果")
        outpaint, outpaint_meta = self.outpaint(front, subject_hint=subject_hint, seed=seed + 3)
        task_records["outpaint"] = outpaint_meta

        outputs = {
            "preprocessed": preprocessed,
            "front": front,
            "left_turn": left_turn,
            "right_turn": right_turn,
            "outpaint": outpaint,
        }

        output_dir = Path(output_dir)
        saved_paths = save_named_images(outputs, output_dir)
        manifest_path = output_dir / "result_manifest.json"

        safe_config = asdict(self.config)
        safe_config["api_key"] = "***"

        manifest = {
            "config": safe_config,
            "device": self.device,
            "seed": seed,
            "subject_hint": subject_hint,
            "tasks": task_records,
            "outputs": {key: str(path) for key, path in saved_paths.items()},
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        if progress_callback:
            progress_callback(1.0, "生成完成，结果已写入输出目录")

        return {
            **outputs,
            **saved_paths,
            "tasks": task_records,
            "manifest_path": manifest_path,
        }
