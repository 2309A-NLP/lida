"""工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务

项目配置定义。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class GenerationConfig:
    api_key: str = os.getenv("DASHSCOPE_API_KEY", os.getenv("BAILIAN_API_KEY", ""))
    pose_endpoint: str = os.getenv(
        "BAILIAN_POSE_ENDPOINT",
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation",
    )
    endpoint: str = os.getenv(
        "BAILIAN_IMAGE_EDIT_ENDPOINT",
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2image/image-synthesis",
    )
    task_endpoint_template: str = os.getenv(
        "BAILIAN_TASK_ENDPOINT_TEMPLATE",
        "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
    )
    pose_model_id: str = os.getenv("BAILIAN_POSE_MODEL", "wan2.7-image-pro")
    pose_size: str = os.getenv("BAILIAN_POSE_SIZE", "2K")
    model_id: str = os.getenv("BAILIAN_IMAGE_MODEL", "wanx2.1-imageedit")
    width: int = int(os.getenv("SD_AGENT_WIDTH", "1024"))
    height: int = int(os.getenv("SD_AGENT_HEIGHT", "1024"))
    poll_interval_seconds: float = float(os.getenv("BAILIAN_POLL_INTERVAL_SECONDS", "2"))
    task_timeout_seconds: int = int(os.getenv("BAILIAN_TASK_TIMEOUT_SECONDS", "180"))
    request_timeout_seconds: int = int(os.getenv("BAILIAN_REQUEST_TIMEOUT_SECONDS", "60"))
    output_count: int = int(os.getenv("BAILIAN_OUTPUT_COUNT", "1"))
    expand_top_scale: float = float(os.getenv("BAILIAN_EXPAND_TOP_SCALE", "1.0"))
    expand_bottom_scale: float = float(os.getenv("BAILIAN_EXPAND_BOTTOM_SCALE", "1.6"))
    expand_left_scale: float = float(os.getenv("BAILIAN_EXPAND_LEFT_SCALE", "1.15"))
    expand_right_scale: float = float(os.getenv("BAILIAN_EXPAND_RIGHT_SCALE", "1.15"))
    negative_prompt: str = os.getenv(
        "SD_AGENT_NEGATIVE_PROMPT",
        (
            "low quality, blurry, distorted face, deformed eyes, extra eyes, extra nose, extra mouth, "
            "bad anatomy, duplicated features, warped face, oversmoothed skin, noisy background"
        ),
    )
