"""工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务

命令行运行入口。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.pipeline import StableDiffusionFaceTurnAgent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="输入一张人脸图，输出左转、右转、端正和扩图结果。")
    parser.add_argument("--input", required=True, help="输入人脸图片路径")
    parser.add_argument("--output-dir", default="outputs", help="结果输出目录")
    parser.add_argument("--subject-hint", default="", help="人物补充描述，如性别、年龄段、风格")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    agent = StableDiffusionFaceTurnAgent()
    result = agent.run_full_workflow(
        image=Path(args.input),
        subject_hint=args.subject_hint,
        seed=args.seed,
        output_dir=Path(args.output_dir),
    )

    print("生成完成：")
    for key, value in result.items():
        if key.endswith("_path") or key == "manifest_path":
            print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
