"""工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务

提示词构建逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True, slots=True)
class PosePrompt:
    key: str
    label: str
    positive: str
    negative: str


def build_pose_prompts(subject_hint: str, negative_prompt: str) -> Dict[str, PosePrompt]:
    base = (
        "real studio portrait, neutral gray background, formal ID-photo composition, realistic face, "
        "keep the same identity, preserve facial structure, preserve eye shape, preserve skin tone, "
        "preserve hairstyle, preserve ears, preserve jawline, preserve nose bridge, "
        "clean lighting, centered upper-body framing, natural skin texture, no beauty filter"
    )
    if subject_hint.strip():
        base = f"{base}, {subject_hint.strip()}"

    return {
        "front": PosePrompt(
            key="front",
            label="端正",
            positive=(
                f"{base}, facing camera, straight head pose, direct gaze, symmetrical face, "
                "formal studio portrait, shoulders visible, photorealistic, natural skin pores, "
                "real camera portrait, crisp facial detail"
            ),
            negative=negative_prompt,
        ),
        "left_turn": PosePrompt(
            key="left_turn",
            label="左转",
            positive=(
                f"{base}, realistic studio portrait of the same person, three-quarter view, "
                "head turned about 25 to 30 degrees to the subject's left, nose clearly pointing left, "
                "left cheek and left jaw contour more visible, far eye slightly narrower because of perspective, "
                "same person, same shirt and tie, same neutral gray background, "
                "obvious left-facing angle, photorealistic, real camera portrait, not frontal"
            ),
            negative=(
                f"{negative_prompt}, front-facing symmetry, mirrored face, fake side face, "
                "cartoon skin, plastic skin, distorted mouth, warped cheek"
            ),
        ),
        "right_turn": PosePrompt(
            key="right_turn",
            label="右转",
            positive=(
                f"{base}, realistic studio portrait of the same person, three-quarter view, "
                "head turned about 25 to 30 degrees to the subject's right, nose clearly pointing right, "
                "right cheek and right jaw contour more visible, far eye slightly narrower because of perspective, "
                "same person, same shirt and tie, same neutral gray background, "
                "obvious right-facing angle, photorealistic, real camera portrait, not frontal"
            ),
            negative=(
                f"{negative_prompt}, front-facing symmetry, mirrored face, fake side face, "
                "cartoon skin, plastic skin, distorted mouth, warped cheek"
            ),
        ),
    }
