"""FastAPI entrypoint for the fund QA project."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from fund_qa.service.answering import build_service


app = FastAPI(title="基金数据问答智能体", version="0.1.0")
service = build_service()


class AskRequest(BaseModel):
    question: str
    question_id: int | None = None


HOME_PAGE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>基金数据问答智能体</title>
  <style>
    :root {
      --bg: #020913;
      --bg-soft: #071220;
      --line: rgba(79, 214, 255, 0.18);
      --line-strong: rgba(79, 214, 255, 0.32);
      --panel: rgba(5, 17, 31, 0.86);
      --panel-alt: rgba(8, 24, 41, 0.92);
      --panel-deep: rgba(2, 10, 19, 0.94);
      --text: #eaf8ff;
      --muted: #89adc4;
      --brand: #4fd6ff;
      --brand-strong: #18aef0;
      --gold: #f7c65e;
      --green: #31e7a7;
      --shadow: 0 24px 80px rgba(0, 0, 0, 0.40);
      --radius-xl: 28px;
      --radius-lg: 20px;
      --radius-md: 14px;
      --mono: "Consolas", "SFMono-Regular", monospace;
      --sans: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }

    html {
      scroll-behavior: smooth;
    }

    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      font-family: var(--sans);
      line-height: 1.65;
      background:
        radial-gradient(circle at 20% 0%, rgba(79, 214, 255, 0.12), transparent 24%),
        radial-gradient(circle at 90% 8%, rgba(247, 198, 94, 0.10), transparent 18%),
        linear-gradient(180deg, #01050b 0%, #05111d 36%, #020913 100%);
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(79, 214, 255, 0.08) 1px, transparent 1px),
        linear-gradient(90deg, rgba(79, 214, 255, 0.08) 1px, transparent 1px);
      background-size: 40px 40px;
      opacity: 0.42;
      mask-image: linear-gradient(180deg, rgba(0,0,0,0.92), transparent 86%);
    }

    a {
      color: inherit;
      text-decoration: none;
    }

    h1, h2, h3, p {
      margin-top: 0;
    }

    .shell {
      width: min(1440px, calc(100% - 20px));
      margin: 0 auto;
      padding: 14px 0 24px;
    }

    .screen {
      display: grid;
      gap: 14px;
    }

    .topbar,
    .hero,
    .ops-row,
    .workspace,
    .footer-grid {
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      background: var(--panel);
      backdrop-filter: blur(10px);
      box-shadow: var(--shadow);
    }

    .topbar {
      display: grid;
      grid-template-columns: 1.2fr 1fr;
      gap: 14px;
      padding: 14px 18px;
      background: linear-gradient(180deg, rgba(5, 17, 31, 0.96), rgba(3, 12, 23, 0.92));
    }

    .brandline,
    .topstats {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .brandmark {
      width: 52px;
      height: 52px;
      border-radius: 16px;
      display: grid;
      place-items: center;
      color: #02101c;
      font-size: 18px;
      font-weight: 900;
      background: linear-gradient(135deg, var(--brand), #91ebff);
      box-shadow: 0 12px 28px rgba(24, 174, 240, 0.24);
      flex: 0 0 auto;
    }

    .brandcopy strong,
    .brandcopy span {
      display: block;
    }

    .brandcopy strong {
      font-size: 16px;
      letter-spacing: 0.04em;
    }

    .brandcopy span,
    .hero-copy,
    .hero-note,
    .metric span,
    .module-copy,
    .subtle,
    .footer-card p,
    .statusbar {
      color: var(--muted);
    }

    .topstats {
      justify-content: flex-end;
      flex-wrap: wrap;
    }

    .ticker {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 12px;
      border-radius: 999px;
      border: 1px solid rgba(79, 214, 255, 0.16);
      background: rgba(255, 255, 255, 0.03);
      font-size: 13px;
      white-space: nowrap;
    }

    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 0 5px rgba(49, 231, 167, 0.12);
      flex: 0 0 auto;
    }

    .hero {
      position: relative;
      overflow: hidden;
      padding: 20px;
      background:
        linear-gradient(135deg, rgba(79, 214, 255, 0.10), transparent 36%),
        linear-gradient(180deg, rgba(7, 21, 37, 0.96), rgba(3, 12, 23, 0.96));
    }

    .hero::after {
      content: "";
      position: absolute;
      right: -80px;
      top: -70px;
      width: 300px;
      height: 300px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(79, 214, 255, 0.20), transparent 72%);
      pointer-events: none;
    }

    .hero-layout {
      display: grid;
      grid-template-columns: minmax(0, 1.18fr) 320px;
      gap: 16px;
    }

    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 8px 14px;
      border-radius: 999px;
      border: 1px solid rgba(79, 214, 255, 0.20);
      background: rgba(79, 214, 255, 0.08);
      color: var(--brand);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }

    .hero-title {
      margin: 16px 0 12px;
      max-width: 900px;
      font-size: clamp(38px, 5.6vw, 74px);
      line-height: 0.94;
      letter-spacing: -0.06em;
    }

    .hero-copy {
      max-width: 820px;
      font-size: 16px;
      margin-bottom: 18px;
    }

    .hero-note {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      font-size: 13px;
    }

    .signal-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid rgba(79, 214, 255, 0.14);
      background: rgba(255, 255, 255, 0.03);
      white-space: nowrap;
    }

    .hero-metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }

    .metric {
      padding: 16px;
      border-radius: 20px;
      border: 1px solid rgba(79, 214, 255, 0.14);
      background:
        linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02));
    }

    .metric strong {
      display: block;
      font-size: 30px;
      line-height: 1;
      color: var(--brand);
      margin-bottom: 6px;
    }

    .right-rail {
      display: grid;
      gap: 10px;
    }

    .rail-card,
    .module,
    .summary-card,
    .detail-card,
    .footer-card {
      border-radius: 20px;
      border: 1px solid rgba(79, 214, 255, 0.14);
      background: var(--panel-alt);
    }

    .rail-card {
      padding: 16px;
    }

    .rail-card h3,
    .footer-card h3 {
      margin-bottom: 8px;
      font-size: 15px;
    }

    .rail-table {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }

    .rail-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 9px 10px;
      border-radius: 14px;
      background: rgba(255,255,255,0.03);
      font-size: 13px;
    }

    .rail-row strong {
      color: var(--text);
      font-size: 13px;
      font-weight: 700;
    }

    .workspace {
      display: grid;
      grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
      overflow: hidden;
      margin-bottom: 14px;
      background:
        linear-gradient(180deg, rgba(7, 21, 37, 0.98), rgba(3, 12, 23, 0.98));
    }

    .composer-side,
    .result-side {
      padding: 20px;
    }

    .result-side {
      border-left: 1px solid var(--line);
      background:
        linear-gradient(180deg, rgba(8, 24, 41, 0.90), rgba(3, 12, 23, 0.98));
    }

    .ops-row {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      padding: 14px;
      margin-bottom: 14px;
      background: linear-gradient(180deg, rgba(6, 18, 31, 0.96), rgba(4, 14, 25, 0.98));
    }

    .section-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 16px;
    }

    .section-title {
      margin-bottom: 8px;
      font-size: 30px;
      line-height: 1.04;
      letter-spacing: -0.04em;
    }

    .module {
      padding: 18px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.015));
    }

    .module-copy {
      font-size: 14px;
      margin-bottom: 0;
    }

    .kbd {
      padding: 7px 10px;
      border-radius: 12px;
      border: 1px solid rgba(79, 214, 255, 0.14);
      background: rgba(255,255,255,0.04);
      font-family: var(--mono);
      font-size: 12px;
      color: var(--muted);
      white-space: nowrap;
    }

    .question-shell {
      position: relative;
      overflow: hidden;
    }

    .question-shell::after {
      content: "";
      position: absolute;
      inset: auto -30px -50px auto;
      width: 160px;
      height: 160px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(247, 198, 94, 0.12), transparent 68%);
      pointer-events: none;
    }

    .composer-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 12px;
    }

    .composer-label {
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--brand);
    }

    .counter {
      font-size: 12px;
      color: var(--muted);
    }

    textarea,
    pre {
      width: 100%;
      box-sizing: border-box;
      border-radius: 18px;
    }

    textarea {
      min-height: 264px;
      resize: vertical;
      padding: 18px;
      background: rgba(1, 10, 18, 0.92);
      color: var(--text);
      border: 1px solid rgba(79, 214, 255, 0.14);
      outline: none;
      font-family: var(--sans);
      font-size: 15px;
      line-height: 1.8;
      transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
    }

    textarea:focus {
      border-color: rgba(79, 214, 255, 0.34);
      box-shadow: 0 0 0 4px rgba(24, 174, 240, 0.10);
      transform: translateY(-1px);
    }

    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      margin-top: 14px;
    }

    button {
      appearance: none;
      border: none;
      border-radius: 16px;
      padding: 13px 18px;
      font-family: inherit;
      font-size: 14px;
      font-weight: 800;
      cursor: pointer;
      transition: transform 0.18s ease, box-shadow 0.18s ease, opacity 0.18s ease;
    }

    button:hover {
      transform: translateY(-1px);
    }

    button:disabled {
      opacity: 0.68;
      cursor: wait;
      transform: none;
      box-shadow: none;
    }

    .primary {
      color: #031018;
      background: linear-gradient(135deg, var(--brand), var(--brand-strong));
      box-shadow: 0 14px 26px rgba(24, 174, 240, 0.22);
    }

    .secondary {
      color: var(--text);
      border: 1px solid rgba(79, 214, 255, 0.14);
      background: rgba(255,255,255,0.04);
    }

    .statusbar {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      min-height: 44px;
      padding: 0 14px;
      border-radius: 999px;
      border: 1px solid rgba(79, 214, 255, 0.14);
      background: rgba(255,255,255,0.04);
      font-size: 13px;
    }

    .statusbar strong {
      color: var(--text);
      font-size: 13px;
    }

    .sample-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 14px;
    }

    .chip {
      width: 100%;
      text-align: left;
      padding: 16px;
      color: var(--text);
      border-radius: 18px;
      border: 1px solid rgba(79, 214, 255, 0.14);
      background:
        linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
    }

    .chip span {
      display: block;
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 500;
    }

    .result-shell {
      display: grid;
      gap: 12px;
    }

    .console-banner {
      padding: 18px 20px;
      border-radius: 22px;
      border: 1px solid rgba(79, 214, 255, 0.18);
      background:
        radial-gradient(circle at top right, rgba(79, 214, 255, 0.16), transparent 30%),
        linear-gradient(135deg, rgba(2, 10, 19, 0.98), rgba(8, 24, 41, 0.96));
    }

    .console-banner h3 {
      margin-bottom: 6px;
      font-size: 14px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--brand);
    }

    .answer {
      margin: 0;
      font-size: 22px;
      line-height: 1.65;
      font-weight: 800;
      word-break: break-word;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }

    .summary-card,
    .detail-card {
      padding: 16px;
    }

    .summary-card .label,
    .detail-card .label {
      display: inline-block;
      margin-bottom: 10px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .summary-card strong {
      display: block;
      font-size: 16px;
      color: var(--text);
      word-break: break-word;
    }

    pre {
      margin: 0;
      padding: 14px;
      background: rgba(1, 10, 18, 0.80);
      border: 1px solid rgba(79, 214, 255, 0.10);
      color: #dff4ff;
      white-space: pre-wrap;
      word-break: break-word;
      overflow-x: auto;
      font-size: 13px;
      line-height: 1.7;
      font-family: var(--mono);
    }

    .footer-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      padding: 18px;
      background:
        linear-gradient(180deg, rgba(6, 18, 31, 0.94), rgba(2, 10, 19, 0.98));
    }

    .footer-card {
      padding: 18px;
    }

    .footer-card h3 {
      margin-bottom: 8px;
      font-size: 15px;
    }

    .footer-card a {
      color: var(--brand);
      font-weight: 700;
    }

    .ops-card {
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid rgba(79, 214, 255, 0.14);
      background: rgba(255,255,255,0.03);
    }

    .ops-card .label {
      display: inline-block;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      font-weight: 800;
    }

    .ops-card strong {
      display: block;
      font-size: 22px;
      line-height: 1.1;
      color: var(--brand);
    }

    .ops-card span {
      display: block;
      margin-top: 5px;
      color: var(--muted);
      font-size: 13px;
    }

    .fade-in {
      animation: rise 0.35s ease;
    }

    @keyframes rise {
      from {
        opacity: 0;
        transform: translateY(8px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    @media (max-width: 1120px) {
      .topbar,
      .hero-layout,
      .ops-row,
      .workspace,
      .footer-grid,
      .hero-metrics,
      .sample-grid,
      .summary-grid {
        grid-template-columns: 1fr;
      }

      .topstats {
        justify-content: flex-start;
      }

      .result-side {
        border-left: none;
        border-top: 1px solid var(--line);
      }
    }

    @media (max-width: 760px) {
      .shell {
        width: min(100% - 18px, 1280px);
      }

      .hero,
      .composer-side,
      .result-side,
      .footer-grid {
        padding: 18px;
      }

      .section-head,
      .composer-top,
      .brandline,
      .topstats {
        display: block;
      }

      .brandmark {
        margin-bottom: 12px;
      }

      .hero-title {
        font-size: 36px;
      }

      .answer {
        font-size: 18px;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="screen">
      <section class="topbar">
        <div class="brandline">
          <div class="brandmark">FI</div>
          <div class="brandcopy">
            <strong>基金数据问答智能体</strong>
            <span>金融大屏演示版 / Fund Intelligence Big Screen</span>
          </div>
        </div>
        <div class="topstats">
          <div class="ticker"><span class="dot"></span>服务端口 8000</div>
          <div class="ticker">首页提问已启用</div>
          <div class="ticker">支持 SQL / 招股书双链路</div>
          <div class="ticker">保留 /docs /redoc /health</div>
        </div>
      </section>

      <section class="hero">
        <div class="hero-layout">
          <div>
            <div class="eyebrow">Real-time Finance QA Dashboard</div>
            <h1 class="hero-title">把基金问答页面做成一块能演示、能验收、也更像金融大屏的工作台。</h1>
            <p class="hero-copy">
              当前页面直连你的项目接口，围绕 PDF 需求里的基金、股票、债券、行业与招股书问答能力做集中展示。
              我保留了原有问答链路，只把首页气质重构成更强展示感的大屏版本。
            </p>
            <div class="hero-note">
              <div class="signal-pill">唯一访问地址：127.0.0.1:8000</div>
              <div class="signal-pill">支持桌面演示和移动端浏览</div>
              <div class="signal-pill">首页直接提问，不需要额外页面跳转</div>
            </div>
            <div class="hero-metrics">
              <div class="metric">
                <strong>1000</strong>
                <span>测试问题已生成答案</span>
              </div>
              <div class="metric">
                <strong>10</strong>
                <span>SQLite 业务表已接入</span>
              </div>
              <div class="metric">
                <strong>80</strong>
                <span>招股书文本已入检索</span>
              </div>
              <div class="metric">
                <strong>1</strong>
                <span>统一对外服务端口</span>
              </div>
            </div>
          </div>

          <div class="right-rail">
            <div class="rail-card">
              <h3>运行状态</h3>
              <div class="rail-table">
                <div class="rail-row"><span>主页入口</span><strong>/</strong></div>
                <div class="rail-row"><span>问答接口</span><strong>POST /ask</strong></div>
                <div class="rail-row"><span>健康检查</span><strong>/health</strong></div>
                <div class="rail-row"><span>服务端口</span><strong>8000</strong></div>
              </div>
            </div>
            <div class="rail-card">
              <h3>联调入口</h3>
              <p class="subtle">需要查接口时，继续保留官方调试页。</p>
              <div class="rail-table">
                <div class="rail-row"><span>Swagger</span><strong>/docs</strong></div>
                <div class="rail-row"><span>Redoc</span><strong>/redoc</strong></div>
                <div class="rail-row"><span>Health</span><strong>/health</strong></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="ops-row">
        <div class="ops-card">
          <div class="label">Data Scope</div>
          <strong>基金 / 股票 / 债券</strong>
          <span>覆盖结构化行情、持仓、净值和行业统计</span>
        </div>
        <div class="ops-card">
          <div class="label">Text Search</div>
          <strong>招股书问答</strong>
          <span>支持文本检索与证据片段展示</span>
        </div>
        <div class="ops-card">
          <div class="label">Delivery</div>
          <strong>页面可直接演示</strong>
          <span>答案、SQL、证据、原始响应一页展示</span>
        </div>
        <div class="ops-card">
          <div class="label">Operation</div>
          <strong>单端口运行</strong>
          <span>避免多个端口和多个页面造成混乱</span>
        </div>
      </section>

      <section class="workspace">
        <div class="composer-side">
          <div class="section-head">
            <div>
              <h2 class="section-title">提问大屏</h2>
              <p class="module-copy">输入 PDF 里的真实测试题，系统会自动判定走 SQL 路由还是招股书检索路由。</p>
            </div>
            <div class="kbd">Ctrl / Cmd + Enter</div>
          </div>

          <div class="module question-shell">
            <div class="composer-top">
              <div class="composer-label">Question Input</div>
              <div class="counter"><span id="charCount">0</span> 字</div>
            </div>
            <textarea id="question" placeholder="请输入基金数据、股票行业、债券持仓或招股书相关问题">请问2019年三季度有多少家基金是净申购?它们的净申购份额加起来是多少?请四舍五入保留小数点两位。</textarea>
            <div class="toolbar">
              <button class="primary" id="submitBtn" onclick="askQuestion()">立即分析</button>
              <button class="secondary" type="button" onclick="useRandomExample()">随机示例</button>
              <button class="secondary" type="button" onclick="clearQuestion()">清空输入</button>
              <div class="statusbar">
                <strong id="statusText">等待提问</strong>
                <span id="statusExtra">大屏已就绪</span>
              </div>
            </div>
          </div>

          <div class="module">
            <div class="section-head">
              <div>
                <div class="composer-label">Quick Cases</div>
                <p class="module-copy">点击示例即可一键填入，适合做现场演示和需求核对。</p>
              </div>
            </div>
            <div class="sample-grid">
              <button class="chip" type="button" onclick="fillExample(0)">
                行业涨幅统计
                <span>20210415 建筑材料一级行业涨幅超过 5% 的股票数量</span>
              </button>
              <button class="chip" type="button" onclick="fillExample(1)">
                发起人检索
                <span>湖南长远锂科股份有限公司变更设立时作为发起人的法人有哪些</span>
              </button>
              <button class="chip" type="button" onclick="fillExample(2)">
                净申购统计
                <span>2019 年三季度净申购基金数量与总申购份额</span>
              </button>
              <button class="chip" type="button" onclick="fillExample(3)">
                综合金融涨跌幅
                <span>20210105 综合金融行业涨跌幅最大股票的代码与涨跌幅</span>
              </button>
            </div>
          </div>

        </div>

        <div class="result-side">
          <div class="section-head">
            <div>
              <h2 class="section-title">结果大屏</h2>
              <p class="module-copy">答案、SQL、证据、备注和原始响应同屏展示，更适合汇报和验收。</p>
            </div>
          </div>

          <div class="result-shell fade-in" id="resultShell">
            <div class="console-banner">
              <h3>Answer Output</h3>
              <p class="answer" id="answerText">等待提问...</p>
            </div>

            <div class="summary-grid">
              <div class="summary-card">
                <div class="label">路由类型</div>
                <strong id="routeText">-</strong>
              </div>
              <div class="summary-card">
                <div class="label">问题编号</div>
                <strong id="questionIdText">-</strong>
              </div>
              <div class="summary-card">
                <div class="label">本次耗时</div>
                <strong id="elapsedText">-</strong>
              </div>
            </div>

            <div class="detail-card">
              <div class="label">SQL</div>
              <pre id="sqlText">等待执行...</pre>
            </div>

            <div class="detail-card">
              <div class="label">证据 / 明细</div>
              <pre id="evidenceText">暂无结果</pre>
            </div>

            <div class="detail-card">
              <div class="label">备注</div>
              <pre id="notesText">暂无备注</pre>
            </div>

            <div class="detail-card">
              <div class="label">原始响应</div>
              <pre id="resultBox">{
  "question": "请问2019年三季度有多少家基金是净申购?它们的净申购份额加起来是多少?请四舍五入保留小数点两位。",
  "question_id": 11
}</pre>
            </div>
          </div>
        </div>
      </section>

      <section class="footer-grid">
        <div class="footer-card">
          <h3>大屏定位</h3>
          <p>这一版更适合在会议室投屏、需求验收和现场演示时使用，信息密度更高，也更像金融项目。</p>
        </div>
        <div class="footer-card">
          <h3>接口说明</h3>
          <p>`POST /ask` 继续保留，联调时可以直接去 <a href="/docs" target="_blank">/docs</a> 试接口。</p>
        </div>
        <div class="footer-card">
          <h3>访问地址</h3>
          <p>统一入口：<a href="http://127.0.0.1:8000/" target="_blank">http://127.0.0.1:8000/</a></p>
        </div>
      </section>
    </div>
  </div>

  <script>
    const examples = [
      "请帮我查询出20210415日，建筑材料一级行业涨幅超过5%（不包含）的股票数量。",
      "湖南长远锂科股份有限公司变更设立时作为发起人的法人有哪些？",
      "请问2019年三季度有多少家基金是净申购?它们的净申购份额加起来是多少?请四舍五入保留小数点两位。",
      "请帮我计算，在20210105，中信行业分类划分的一级行业为综合金融行业中，涨跌幅最大股票的股票代码是？涨跌幅是多少？百分数保留两位小数。股票涨跌幅定义为：（收盘价 - 前一日收盘价 / 前一日收盘价）* 100%。"
    ];

    const questionEl = document.getElementById("question");
    const charCountEl = document.getElementById("charCount");
    const resultShellEl = document.getElementById("resultShell");

    function syncCount() {
      charCountEl.textContent = questionEl.value.trim().length;
    }

    function setStatus(main, extra) {
      document.getElementById("statusText").textContent = main;
      document.getElementById("statusExtra").textContent = extra;
    }

    function fillExample(index) {
      questionEl.value = examples[index];
      syncCount();
      questionEl.focus();
    }

    function useRandomExample() {
      const index = Math.floor(Math.random() * examples.length);
      fillExample(index);
    }

    function clearQuestion() {
      questionEl.value = "";
      syncCount();
      questionEl.focus();
      setStatus("等待提问", "输入已清空");
    }

    function renderNotes(notes) {
      if (!notes || !notes.length) {
        return "暂无备注";
      }
      return notes.map((item, index) => `备注${index + 1}: ${item}`).join("\\n");
    }

    function renderEvidence(data) {
      if (data.evidences && data.evidences.length) {
        return data.evidences.map((item, index) =>
          `证据${index + 1}\\n来源: ${item.source}\\n相关度: ${item.score}\\n片段: ${item.snippet}`
        ).join("\\n\\n");
      }
      if (data.rows && data.rows.length) {
        return JSON.stringify(data.rows, null, 2);
      }
      return "暂无额外证据";
    }

    function resetPanels() {
      document.getElementById("routeText").textContent = "-";
      document.getElementById("questionIdText").textContent = "-";
      document.getElementById("elapsedText").textContent = "-";
      document.getElementById("sqlText").textContent = "正在生成...";
      document.getElementById("evidenceText").textContent = "正在整理...";
      document.getElementById("notesText").textContent = "正在整理...";
      document.getElementById("resultBox").textContent = "正在等待响应...";
      document.getElementById("answerText").textContent = "正在分析问题并检索答案...";
    }

    async function askQuestion() {
      const question = questionEl.value.trim();
      const button = document.getElementById("submitBtn");

      if (!question) {
        document.getElementById("answerText").textContent = "请输入问题后再提交。";
        setStatus("等待提问", "请输入有效问题");
        return;
      }

      button.disabled = true;
      resetPanels();
      setStatus("正在查询", "系统正在判定路由并执行问答");

      const started = performance.now();

      try {
        const response = await fetch("/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question })
        });

        const data = await response.json();
        const elapsed = ((performance.now() - started) / 1000).toFixed(2) + " 秒";

        document.getElementById("answerText").textContent = data.answer || "未返回答案";
        document.getElementById("routeText").textContent = data.route || "-";
        document.getElementById("questionIdText").textContent = data.question_id ?? "-";
        document.getElementById("elapsedText").textContent = elapsed;
        document.getElementById("sqlText").textContent = data.sql || "本次未执行结构化 SQL。";
        document.getElementById("evidenceText").textContent = renderEvidence(data);
        document.getElementById("notesText").textContent = renderNotes(data.notes);
        document.getElementById("resultBox").textContent = JSON.stringify(data, null, 2);

        resultShellEl.classList.remove("fade-in");
        void resultShellEl.offsetWidth;
        resultShellEl.classList.add("fade-in");

        setStatus("查询完成", `本次响应耗时 ${elapsed}`);
      } catch (error) {
        document.getElementById("answerText").textContent = "请求失败，请检查服务是否正常运行。";
        document.getElementById("sqlText").textContent = "请求失败";
        document.getElementById("evidenceText").textContent = String(error);
        document.getElementById("notesText").textContent = "前端请求异常";
        document.getElementById("resultBox").textContent = String(error);
        document.getElementById("elapsedText").textContent = "-";
        setStatus("请求失败", "请稍后重试或检查后端服务");
      } finally {
        button.disabled = false;
      }
    }

    questionEl.addEventListener("input", syncCount);
    questionEl.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        askQuestion();
      }
    });

    syncCount();
  </script>
</body>
</html>
"""


ASK_HELP_PAGE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>/ask 使用说明</title>
  <style>
    body {
      margin: 0;
      background: linear-gradient(180deg, #fbf6ee 0%, #f2e7d7 100%);
      color: #231a14;
      font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    }
    .wrap {
      width: min(900px, calc(100% - 28px));
      margin: 32px auto;
      padding: 28px;
      border-radius: 28px;
      background: rgba(255, 251, 245, 0.86);
      border: 1px solid rgba(77, 55, 34, 0.12);
      box-shadow: 0 26px 70px rgba(82, 56, 28, 0.12);
    }
    h1, h2, p, pre { margin-top: 0; }
    pre, code {
      font-family: "Consolas", "SFMono-Regular", monospace;
    }
    pre {
      padding: 16px;
      border-radius: 18px;
      background: #fffdf9;
      border: 1px solid rgba(77, 55, 34, 0.10);
      white-space: pre-wrap;
      word-break: break-word;
    }
    a {
      color: #8f381a;
      text-decoration: none;
      font-weight: 700;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>/ask 使用说明</h1>
    <p>当前地址只用于说明接口使用方法。真正的问答调用方式是向 <code>/ask</code> 发送 <strong>POST</strong> 请求。</p>
    <p>如果你想直接在网页里提问，请回到 <a href="/">首页</a>。如果你要调试接口参数，也可以打开 <a href="/docs" target="_blank">/docs</a>。</p>
    <h2>请求体示例</h2>
    <pre>{
  "question": "湖南长远锂科股份有限公司变更设立时作为发起人的法人有哪些？",
  "question_id": 1
}</pre>
  </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return HOME_PAGE


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ask", response_class=HTMLResponse)
def ask_help() -> str:
    return ASK_HELP_PAGE


@app.post("/ask")
def ask(request: AskRequest) -> dict:
    result = service.answer(request.question, request.question_id)
    return {
        "question_id": result.question_id,
        "question": result.question,
        "route": result.route,
        "answer": result.answer,
        "sql": result.sql,
        "rows": result.rows,
        "evidences": [
            {"source": item.source, "score": item.score, "snippet": item.snippet}
            for item in result.evidences
        ],
        "notes": result.notes,
    }
