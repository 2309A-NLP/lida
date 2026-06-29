"""工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务"""

from src.prompting import build_pose_prompts


def test_build_pose_prompts_contains_required_views():
    prompts = build_pose_prompts("asian male, short hair", "blurry")
    assert set(prompts.keys()) == {"front", "left_turn", "right_turn"}


def test_build_pose_prompts_keeps_subject_hint():
    prompts = build_pose_prompts("freckles, glasses", "blurry")
    assert "freckles, glasses" in prompts["front"].positive
    assert prompts["left_turn"].negative.startswith("blurry")


def test_build_pose_prompts_targets_studio_portrait_style():
    prompts = build_pose_prompts("", "blurry")
    assert "neutral gray background" in prompts["front"].positive
    assert "studio portrait" in prompts["left_turn"].positive
    assert "not frontal" in prompts["left_turn"].positive
