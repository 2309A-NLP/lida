"""工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务

Gradio 演示入口。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from PIL import Image

from src.pipeline import StableDiffusionFaceTurnAgent


LOG_DIR = Path.cwd() / "runtime"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "agent.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
    force=True,
)
LOGGER = logging.getLogger("agent_workorder_3")


PAGE_CSS = """
:root {
  --bg-cream: #f3eadc;
  --bg-paper: rgba(255, 249, 240, 0.9);
  --ink: #171515;
  --muted: #61584f;
  --line: rgba(23, 21, 21, 0.14);
  --gold: #b87a3d;
  --rust: #7f3f24;
  --card-shadow: 0 18px 55px rgba(58, 36, 21, 0.14);
}

body, .gradio-container {
  background:
    radial-gradient(circle at 12% 8%, rgba(184, 122, 61, 0.16), transparent 22%),
    radial-gradient(circle at 88% 16%, rgba(127, 63, 36, 0.10), transparent 20%),
    linear-gradient(180deg, #f7f0e5 0%, #efe3d2 52%, #f4ebde 100%);
  color: var(--ink);
  font-family: "Avenir Next", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.gradio-container {
  max-width: 1280px !important;
  padding: 24px 18px 42px !important;
}

.stage-hero {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.65);
  border-radius: 30px;
  padding: 28px 30px 30px;
  background:
    linear-gradient(140deg, rgba(255,255,255,0.82), rgba(243,232,216,0.76)),
    repeating-linear-gradient(
      90deg,
      rgba(23,21,21,0.015) 0,
      rgba(23,21,21,0.015) 2px,
      transparent 2px,
      transparent 14px
    );
  box-shadow: var(--card-shadow);
}

.stage-hero::before {
  content: "";
  position: absolute;
  inset: 14px;
  border: 1px solid rgba(23, 21, 21, 0.08);
  border-radius: 22px;
  pointer-events: none;
}

.hero-strip {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(255,255,255,0.62);
  border: 1px solid rgba(127, 63, 36, 0.18);
  color: var(--rust);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.hero-grid {
  display: grid;
  grid-template-columns: 1.4fr 0.8fr;
  gap: 24px;
  margin-top: 18px;
}

.hero-title {
  margin: 0;
  max-width: 760px;
  font-family: "Georgia", "Source Han Serif SC", "Songti SC", serif;
  font-size: clamp(38px, 5.2vw, 64px);
  line-height: 0.98;
  letter-spacing: -0.03em;
  color: #171515;
}

.hero-desc {
  margin: 18px 0 0;
  max-width: 700px;
  color: var(--muted);
  font-size: 16px;
  line-height: 1.85;
}

.frame-board {
  align-self: stretch;
  border-radius: 24px;
  background:
    linear-gradient(180deg, rgba(28, 24, 21, 0.94), rgba(51, 39, 30, 0.92));
  color: #f7eedf;
  padding: 18px;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08);
}

.frame-board-title {
  margin: 0 0 12px;
  font-family: "Georgia", "Source Han Serif SC", "Songti SC", serif;
  font-size: 24px;
  color: #fff2df;
}

.frame-cells {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.frame-cell {
  min-height: 112px;
  border-radius: 16px;
  padding: 12px;
  background:
    linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02));
  border: 1px solid rgba(255,255,255,0.09);
}

.frame-label {
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(255, 233, 204, 0.82);
}

.frame-text {
  margin-top: 10px;
  font-size: 14px;
  line-height: 1.6;
  color: rgba(247, 238, 223, 0.9);
}

.metric-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 18px;
}

.metric-pill {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255,255,255,0.74);
  border: 1px solid rgba(23,21,21,0.1);
  color: #44392f;
  font-size: 13px;
}

.panel {
  border-radius: 26px !important;
  border: 1px solid var(--line) !important;
  background: var(--bg-paper) !important;
  box-shadow: var(--card-shadow) !important;
}

.input-card, .notes-card, .gallery-card {
  padding: 18px !important;
}

.section-title {
  margin: 0 0 14px !important;
  font-family: "Georgia", "Source Han Serif SC", "Songti SC", serif;
  font-size: 28px !important;
  color: #171515;
}

.section-copy {
  margin: 0 0 18px;
  color: var(--muted);
  line-height: 1.8;
}

.notes-card h3 {
  margin: 0 0 12px;
  font-family: "Georgia", "Source Han Serif SC", "Songti SC", serif;
  font-size: 24px;
}

.notes-list {
  margin: 0;
  padding-left: 18px;
  color: var(--muted);
  line-height: 1.9;
}

.notes-list li {
  margin-bottom: 8px;
}

.result-copy {
  margin-top: 8px;
  color: var(--muted);
  font-size: 14px;
}

.status-box textarea {
  font-size: 14px !important;
}

button.primary, .primary {
  background: linear-gradient(135deg, var(--gold) 0%, var(--rust) 100%) !important;
  border: none !important;
  border-radius: 16px !important;
  box-shadow: 0 12px 28px rgba(127, 63, 36, 0.25) !important;
}

.gr-button {
  min-height: 50px !important;
}

.gr-box, .gr-form, .gr-panel {
  border-radius: 18px !important;
}

footer {
  display: none !important;
}

@media (max-width: 980px) {
  .hero-grid {
    grid-template-columns: 1fr;
  }

  .stage-hero {
    padding: 22px 18px 22px;
    border-radius: 24px;
  }

  .hero-title {
    font-size: 40px;
  }
}
"""


def build_demo():
    try:
        import gradio as gr
    except ImportError as exc:
        raise SystemExit("未安装 gradio，请先执行 `pip install -r requirements.txt`。") from exc

    agent = StableDiffusionFaceTurnAgent()

    def infer(
        image: Image.Image,
        subject_hint: str,
        seed: int,
        output_dir: str,
        progress=gr.Progress(track_tqdm=False),
    ) -> Tuple[List[str], str, str]:
        if image is None:
            raise gr.Error("请先上传一张人脸图片。")

        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        target_dir = Path(output_dir).expanduser().resolve() if output_dir else Path.cwd() / "outputs"
        LOGGER.info("run_id=%s start output_dir=%s seed=%s subject_hint=%s", run_id, target_dir, seed, subject_hint)

        def on_progress(value: float, desc: str) -> None:
            LOGGER.info("run_id=%s progress=%.2f desc=%s", run_id, value, desc)
            progress(value, desc=desc)

        try:
            result = agent.run_full_workflow(
                image=image,
                subject_hint=subject_hint,
                seed=seed,
                output_dir=target_dir,
                progress_callback=on_progress,
            )
        except Exception as exc:
            LOGGER.exception("run_id=%s failed", run_id)
            raise gr.Error(f"本次任务失败，详情请查看日志：{LOG_PATH}") from exc

        gallery = [
            str(result["preprocessed_path"]),
            str(result["front_path"]),
            str(result["left_turn_path"]),
            str(result["right_turn_path"]),
            str(result["outpaint_path"]),
        ]
        status = (
            "本次任务已完成。\n"
            f"运行编号: {run_id}\n"
            f"输出目录: {target_dir}\n"
            f"端正图: {result['front_path']}\n"
            f"左转图: {result['left_turn_path']}\n"
            f"右转图: {result['right_turn_path']}\n"
            f"扩图结果: {result['outpaint_path']}\n"
            f"运行日志: {LOG_PATH}"
        )
        LOGGER.info("run_id=%s success manifest=%s", run_id, result["manifest_path"])
        return gallery, str(result["manifest_path"]), status

    with gr.Blocks(title="Agent工单3 - 文生图智能体") as demo:
        gr.HTML(
            """
            <section class="stage-hero">
              <div class="hero-strip">Concept Room / Agent Workorder 03</div>
              <div class="hero-grid">
                <div>
                  <h1 class="hero-title">把上传、转脸、扩图这件事，做成一块像电影概念设计台一样的工作界面。</h1>
                  <p class="hero-desc">
                    这不是传统数字人产品的官网拼装页，而是一块偏向分镜、设定、试拍逻辑的生成面板。
                    你给一张人物图，我们围绕同一身份做正面、左右转向和外扩画幅，重点是把结果组织得像一套镜头方案。
                  </p>
                  <div class="metric-row">
                    <span class="metric-pill">身份一致性优先</span>
                    <span class="metric-pill">三视角镜头推演</span>
                    <span class="metric-pill">扩图补全画幅</span>
                    <span class="metric-pill">在线百炼任务流</span>
                  </div>
                </div>
                <aside class="frame-board">
                  <h2 class="frame-board-title">镜头板</h2>
                  <div class="frame-cells">
                    <div class="frame-cell">
                      <div class="frame-label">Frame 01</div>
                      <div class="frame-text">正面建模，锁定角色身份、眼神和光线基调。</div>
                    </div>
                    <div class="frame-cell">
                      <div class="frame-label">Frame 02</div>
                      <div class="frame-text">左转视角，强调轮廓转折和面部透视变化。</div>
                    </div>
                    <div class="frame-cell">
                      <div class="frame-label">Frame 03</div>
                      <div class="frame-text">右转视角，验证双侧特征与五官连贯性。</div>
                    </div>
                    <div class="frame-cell">
                      <div class="frame-label">Frame 04</div>
                      <div class="frame-text">扩展画幅，补全肩颈、服装与背景氛围。</div>
                    </div>
                  </div>
                </aside>
              </div>
            </section>
            """
        )

        with gr.Row():
            with gr.Column(scale=7):
                with gr.Group(elem_classes=["panel", "input-card"]):
                    gr.Markdown("## 角色输入台", elem_classes=["section-title"])
                    gr.HTML(
                        "<p class='section-copy'>上传一张单人照片，补充人物与镜头风格描述，然后发起整组生成任务。</p>"
                    )
                    with gr.Row():
                        image_input = gr.Image(type="pil", label="上传原图")
                        with gr.Column():
                            subject_hint = gr.Textbox(
                                label="人物补充描述",
                                value="natural portrait, consistent facial features, realistic lighting",
                                lines=4,
                                placeholder="例如：cinematic portrait, soft key light, realistic skin texture, clean costume silhouette",
                            )
                            seed = gr.Number(label="随机种子", value=42, precision=0)
                            output_dir = gr.Textbox(label="输出目录", value=str(Path.cwd() / "outputs"))
                            submit = gr.Button("生成整组镜头", variant="primary")

            with gr.Column(scale=5):
                with gr.Group(elem_classes=["panel", "notes-card"]):
                    gr.HTML(
                        """
                        <h3>导演笔记</h3>
                        <ol class="notes-list">
                          <li>优先上传正脸或近正脸图，避免大面积遮挡，这样三视角更容易保持同一人。</li>
                          <li>描述里可以写光线、年龄感、服装轮廓、镜头气质，但不要堆太多相互冲突的风格词。</li>
                          <li>在线生成会按整组任务返回，等待时间通常比单张图更长，但结果组织更完整。</li>
                          <li>如果生成气质不对，我会继续调提示词方向，让它更像概念稿，而不是常规美颜海报。</li>
                        </ol>
                        """
                    )

        with gr.Group(elem_classes=["panel", "gallery-card"]):
            gr.Markdown("## 分镜结果墙", elem_classes=["section-title"])
            gallery = gr.Gallery(label="生成结果", columns=3, object_fit="contain", height="auto")
            gr.HTML("<p class='result-copy'>预览顺序：预处理图、端正图、左转图、右转图、扩图结果。</p>")
            manifest_path = gr.Textbox(label="结果清单路径")
            status_text = gr.Textbox(label="运行状态", lines=8, elem_classes=["status-box"])

        submit.click(
            infer,
            inputs=[image_input, subject_hint, seed, output_dir],
            outputs=[gallery, manifest_path, status_text],
        )

    return demo


if __name__ == "__main__":
    demo = build_demo()
    server_name = os.getenv("SD_AGENT_HOST", "127.0.0.1")
    server_port = int(os.getenv("SD_AGENT_PORT", "7860"))
    demo.launch(server_name=server_name, server_port=server_port, css=PAGE_CSS)
