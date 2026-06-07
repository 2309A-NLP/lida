"""
RAG 智能问答系统 v2 - DeepSeek风格聊天界面
双语支持 + 评估指标展示 + 优化方案对比分析 + 历史会话侧边栏
"""
import json
import sys
import os
import time
import copy
import uuid
from datetime import datetime
from pathlib import Path
import streamlit as st
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from src.rag_engine import RAGEngine
from src.feedback import FeedbackManager
from src.chat_history import ChatHistoryStore

st.set_page_config(page_title="RAG 智能问答 v2", page_icon="💬", layout="wide")

# ===== DeepSeek风格CSS =====
st.markdown("""
<style>
.stApp { background: #fff; }
.main .block-container { max-width: 860px; padding: 0 !important; }
#root > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > section.main > div { padding-top: 0; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
.stApp > header { display: none; }

.chat-container { max-width: 760px; margin: 0 auto; padding: 20px 24px 140px 24px; min-height: 100vh; }

.chat-header { text-align: center; padding: 40px 0 30px 0; }
.chat-header h1 { font-size: 1.6rem; font-weight: 600; color: #1a1a1a; margin: 0; letter-spacing: -0.3px; }
.chat-header p { color: #888; font-size: 0.85rem; margin: 8px 0 0 0; }

.user-msg-wrapper { display: flex; justify-content: flex-end; margin: 18px 0; }
.user-msg {
    background: #e8f0fe; color: #1a1a1a; padding: 12px 18px;
    border-radius: 20px 20px 4px 20px; max-width: 70%;
    font-size: 0.95rem; line-height: 1.6; word-break: break-word;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}

.ai-msg-wrapper { display: flex; justify-content: flex-start; margin: 18px 0; }
.ai-msg { background: transparent; color: #1a1a1a; padding: 4px 0; max-width: 100%; font-size: 0.95rem; line-height: 1.7; word-break: break-word; }
.ai-msg p { margin: 0 0 8px 0; }
.ai-msg p:last-child { margin: 0; }

.meta-tag { display: inline-block; color: #888; font-size: 0.75rem; margin-top: 4px; margin-right: 8px; background: #f5f5f5; padding: 2px 10px; border-radius: 10px; }
.metric-tag { display: inline-block; color: #555; font-size: 0.72rem; margin-top: 2px; margin-right: 6px; background: #f0f4ff; padding: 2px 10px; border-radius: 10px; border: 1px solid #dde8ff; }

.thinking-wrapper { display: flex; align-items: center; gap: 8px; margin: 12px 0; padding: 4px 0; }
.thinking-dot { width: 6px; height: 6px; background: #999; border-radius: 50%; animation: thinking-bounce 1.4s ease-in-out infinite; }
.thinking-dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes thinking-bounce { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; } 40% { transform: scale(1.0); opacity: 1; } }
.thinking-label { color: #999; font-size: 0.85rem; margin-left: 4px; }

@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
.typing-cursor { display: inline-block; width: 2px; height: 16px; background: #1a1a1a; margin-left: 2px; animation: blink 0.8s step-end infinite; vertical-align: text-bottom; }

.input-area { position: fixed; bottom: 0; left: 0; right: 0; background: linear-gradient(transparent, #fff 30%); padding: 20px 0 16px 0; z-index: 100; }
.input-inner { max-width: 760px; margin: 0 auto; padding: 0 24px; }
.stChatFloatingInputContainer { position: relative !important; bottom: auto !important; background: transparent !important; padding: 0 !important; }
[data-testid="stChatInput"] { position: relative !important; bottom: auto !important; }
[data-testid="stChatInput"] textarea {
    background: #f5f5f5 !important; border: 1px solid #e5e5e5 !important;
    border-radius: 24px !important; color: #1a1a1a !important;
    font-size: 0.95rem !important; padding: 12px 20px !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04) !important;
    transition: box-shadow 0.2s; max-height: 120px;
}
[data-testid="stChatInput"] textarea:focus { box-shadow: 0 2px 12px rgba(0,0,0,0.08) !important; border-color: #d0d0d0 !important; }
[data-testid="stChatInput"] textarea::placeholder { color: #bbb; }
.stChatInputContainer { border: none !important; }

details.ai-details { margin: 6px 0; display: inline-block; }
details.ai-details summary { cursor: pointer; color: #999; font-size: 0.78rem; display: inline-block; padding: 2px 8px; border-radius: 6px; transition: background 0.15s; user-select: none; }
details.ai-details summary:hover { background: #f0f0f0; color: #666; }
details.ai-details[open] summary { margin-bottom: 8px; }
.details-content { font-size: 0.85rem; color: #555; line-height: 1.6; padding: 8px 0; }
.details-content .ref-item { border-left: 2px solid #ddd; padding: 6px 12px; margin: 4px 0; font-size: 0.82rem; color: #666; }

.welcome { text-align: center; padding: 100px 20px 40px 20px; }
.welcome-icon { font-size: 3rem; margin-bottom: 16px; }
.welcome h2 { font-size: 1.3rem; font-weight: 500; color: #333; margin: 0 0 8px 0; }
.welcome p { color: #999; font-size: 0.9rem; margin: 0; }
.welcome .suggestions { margin-top: 30px; display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; }
.welcome .suggestion-chip { background: #f5f5f5; border: 1px solid #eee; border-radius: 20px; padding: 8px 18px; font-size: 0.85rem; color: #666; cursor: pointer; transition: all 0.15s; }
.welcome .suggestion-chip:hover { background: #e8f0fe; border-color: #c0d8f8; color: #1a73e8; }

.opt-compare { background: #f8f9fb; border: 1px solid #e8eaee; border-radius: 12px; padding: 16px; margin: 12px 0; font-size: 0.85rem; line-height: 1.6; }
.opt-compare h4 { margin: 0 0 8px 0; font-size: 0.9rem; color: #333; }
.opt-compare table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.opt-compare th { background: #eef0f4; padding: 6px 10px; text-align: left; border: 1px solid #e0e0e0; font-weight: 500; }
.opt-compare td { padding: 6px 10px; border: 1px solid #e0e0e0; }

[data-testid="stSidebar"] { background: #fafafa; border-right: 1px solid #eee; }
[data-testid="stSidebar"] .stButton button {
    border: 1px solid #e0e0e0 !important; border-radius: 10px !important;
    background: #fff !important; color: #333 !important;
    font-size: 0.85rem !important;
}
[data-testid="stSidebar"] .stButton button:hover { border-color: #ccc !important; background: #f5f5f5 !important; }
[data-testid="stChatMessage"] { border: none; background: transparent; padding: 0; margin: 0; }

.feedback-row { margin-top: 4px; display: flex; gap: 4px; }
.feedback-btn { background: none; border: none; color: #ccc; font-size: 0.85rem; cursor: pointer; padding: 2px 6px; border-radius: 6px; transition: all 0.15s; line-height: 1; }
.feedback-btn:hover { background: #f0f0f0; color: #666; }

.msg-footer { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 6px; }

.ai-msg table { border-collapse: collapse; margin: 8px 0; font-size: 0.85rem; width: 100%; }
.ai-msg th, .ai-msg td { border: 1px solid #e0e0e0; padding: 8px 12px; text-align: left; }
.ai-msg th { background: #f5f5f5; font-weight: 500; }
.ai-msg tr:nth-child(even) td { background: #fafafa; }

/* 历史会话列表样式 */
.session-item { 
    padding: 10px 12px; margin: 4px 0; border-radius: 10px;
    cursor: pointer; font-size: 0.82rem; line-height: 1.4;
    border: 1px solid transparent; transition: all 0.15s;
    background: #fff; border-color: #eee;
}
.session-item:hover { background: #e8f0fe; border-color: #c0d8f8; }
.session-item.active { background: #e8f0fe; border-color: #90b8f8; }
.session-item .time { color: #999; font-size: 0.72rem; }
.session-item .preview { color: #444; margin-top: 2px; }
.session-item .count { color: #bbb; font-size: 0.7rem; }
</style>
""", unsafe_allow_html=True)

# ===== 工具函数 =====
@st.cache_resource
def load_config():
    p = Path(__file__).parent / "config.yaml"
    with open(p) as f:
        return yaml.safe_load(f)

def get_engine_config(provider, model, api_key, base_url):
    config = copy.deepcopy(load_config())
    config["llm"]["provider"] = provider
    config["llm"]["model"] = model
    config["llm"]["api_key"] = api_key
    config["llm"]["base_url"] = base_url
    config["embedding"]["api_key"] = ""
    config["embedding"]["base_url"] = ""
    return config

@st.cache_resource
def init_feedback():
    cfg = load_config()
    fb_cfg = cfg.get("feedback", {})
    return FeedbackManager(storage_dir=fb_cfg.get("storage_dir", "outputs"))

def format_metrics_html(eval_metrics: dict) -> str:
    """格式化评估指标为HTML标签"""
    if not eval_metrics:
        return ""
    p = eval_metrics.get("precision", 0)
    r = eval_metrics.get("recall_estimate", 0)
    f = eval_metrics.get("f1", 0)
    c = eval_metrics.get("confidence", 0)
    s = eval_metrics.get("avg_similarity", 0)
    return (
        f'<span class="metric-tag">🎯 Precision: {p:.1%}</span>'
        f'<span class="metric-tag">📊 Recall: {r:.1%}</span>'
        f'<span class="metric-tag">⚖️ F1: {f:.2f}</span>'
        f'<span class="metric-tag">🔍 置信度: {c:.1%}</span>'
        f'<span class="metric-tag">📈 AvgSim: {s:.3f}</span>'
    )

def render_optimization_comparison(result: dict, lang: str) -> str:
    """生成RAG vs 纯LLM优化方案对比分析HTML"""
    rag_answer = result.get("answer", "")
    llm_answer = result.get("llm_only_answer", "")

    if lang == "en":
        title = "📊 Optimization Comparison: RAG vs LLM Only"
    else:
        title = "📊 优化方案对比：RAG检索增强 vs 纯LLM"

    rows = []
    if lang == "en":
        rows.append(f"<tr><td>Response Time</td><td>{result.get('total_time', 'N/A')}s</td><td>{result.get('llm_only_time', 'N/A')}s</td></tr>")
        rows.append(f"<tr><td>Context Usage</td><td>{len(result.get('retrieved_chunks', []))} documents</td><td>None (knowledge only)</td></tr>")
        rows.append(f"<tr><td>Accuracy Potential</td><td>✅ High (grounded)</td><td>⚠️ Medium (no grounding)</td></tr>")
    else:
        rows.append(f"<tr><td>响应时间</td><td>{result.get('total_time', 'N/A')}秒</td><td>{result.get('llm_only_time', 'N/A')}秒</td></tr>")
        rows.append(f"<tr><td>参考文档数</td><td>{len(result.get('retrieved_chunks', []))}篇</td><td>无（仅依赖知识）</td></tr>")
        rows.append(f"<tr><td>准确率潜力</td><td>✅ 高（有据可查）</td><td>⚠️ 中（可能幻觉）</td></tr>")

    table = f"""<table>
        <tr><th></th><th>RAG（检索增强）</th><th>纯LLM（无检索）</th></tr>
        {''.join(rows)}
    </table>"""

    answer_preview = rag_answer[:200] + ("..." if len(rag_answer) > 200 else "")
    llm_preview = llm_answer[:200] + ("..." if len(llm_answer) > 200 else "")

    return f"""
    <div class="opt-compare">
        <h4>{title}</h4>
        {table}
        <div style="margin-top:10px">
            <strong>{'RAG Answer' if lang == 'en' else 'RAG回答'}：</strong> {answer_preview}
        </div>
        <div style="margin-top:6px">
            <strong>{'LLM Only Answer' if lang == 'en' else '纯LLM回答'}：</strong> {llm_preview}
        </div>
    </div>
    """

def render_message(role: str, content: str, meta: dict = None):
    """渲染单条消息HTML"""
    meta = meta or {}
    if role == "user":
        st.markdown(
            f'<div class="user-msg-wrapper"><div class="user-msg">{content}</div></div>',
            unsafe_allow_html=True
        )
    else:
        meta_html = ""
        if meta.get("pages"):
            meta_html += f'<span class="meta-tag">📄 第{", ".join(str(p) for p in sorted(meta["pages"]))}页</span>'
        if meta.get("total_time"):
            meta_html += f'<span class="meta-tag">⏱ {meta["total_time"]}秒</span>'
        if meta.get("eval_metrics"):
            meta_html += format_metrics_html(meta["eval_metrics"])

        opt_html = meta.get("optimization_html", "")

        st.markdown(
            f'<div class="ai-msg-wrapper">'
            f'<div class="ai-msg">'
            f'{content}'
            f'<div class="msg-footer">{meta_html}</div>'
            f'{opt_html}'
            f'</div></div>',
            unsafe_allow_html=True
        )

# ===== 语言检测 =====
cfg = load_config()
LANG = cfg["system"]["language"]

# ===== 会话初始化（每次打开都是全新对话）=====
if "session_initialized" not in st.session_state:
    st.session_state.fb_mgr = init_feedback()

    # 生成唯一会话ID（每次打开都不同）
    ts = int(time.time())
    short_id = uuid.uuid4().hex[:6]
    st.session_state.session_id = f"session_{ts}_{short_id}"
    st.session_state.messages = []
    st.session_state.viewing_session_id = None
    st.session_state.viewing_messages = []
    st.session_state.viewing_mode = False
    st.session_state.session_initialized = True

    # 初始化聊天记录存储
    store = ChatHistoryStore()
    connected = store.connect()
    st.session_state.chat_store = store if connected else None

if "engine" not in st.session_state:
    cfg = load_config()
    ec = get_engine_config(
        cfg["llm"]["provider"], cfg["llm"]["model"],
        cfg["llm"]["api_key"], cfg["llm"]["base_url"]
    )
    e = RAGEngine(ec)
    e.top_k = cfg["retrieval"]["top_k"]
    st.session_state.engine = e
    st.session_state.pdf_path = cfg["pdf"]["file_path"]
    st.session_state.qu_enabled = cfg.get("query_understanding", {}).get("enabled", True)

engine = st.session_state.engine

# ===== 侧边栏 =====
with st.sidebar:
    lang_label = "zh" if LANG == "zh" else "en"

    # --- 顶部：新对话按钮 ---
    btn_label = "➕ 新对话" if lang_label == "zh" else "➕ New Chat"
    if st.button(btn_label, use_container_width=True, type="primary"):
        ts = int(time.time())
        short_id = uuid.uuid4().hex[:6]
        st.session_state.session_id = f"session_{ts}_{short_id}"
        st.session_state.messages = []
        st.session_state.viewing_mode = False
        st.session_state.viewing_session_id = None
        st.rerun()

    # --- 历史会话列表 ---
    hist_title = "💬 对话历史" if lang_label == "zh" else "💬 Chat History"
    st.markdown(f"### {hist_title}")

    # 如果 chat_store 未连接成功，尝试重连
    if st.session_state.chat_store is None:
        store = ChatHistoryStore()
        connected = store.connect()
        if connected:
            st.session_state.chat_store = store

    if st.session_state.chat_store:
        sessions = st.session_state.chat_store.get_all_sessions_with_preview()
        current_sid = st.session_state.session_id

        if not sessions:
            empty_hist = "暂无历史记录" if lang_label == "zh" else "No history yet"
            st.caption(empty_hist)
        else:
            for sess in sessions:
                sid = sess["session_id"]
                # 跳过当前会话（当前会话的内容在主区域展示）
                if sid == current_sid:
                    continue

                ts_val = sess.get("last_timestamp", 0)
                if ts_val:
                    try:
                        date_str = datetime.fromtimestamp(ts_val).strftime("%m/%d %H:%M")
                    except Exception:
                        date_str = ""
                else:
                    date_str = ""

                preview = sess.get("first_query", "")
                if not preview:
                    preview = "(空)" if lang_label == "zh" else "(empty)"
                preview_display = preview[:25]

                count = sess.get("message_count", 0)
                msg_label = "条" if lang_label == "zh" else " msgs"

                # 判断是否当前正在查看这个会话
                is_viewing = (st.session_state.viewing_mode and
                              st.session_state.viewing_session_id == sid)

                active_class = "active" if is_viewing else ""

                label = f"{date_str} {preview_display}"
                if st.button(label, use_container_width=True, key=f"hist_{sid}"):
                    # 加载该会话的历史消息
                    hist = st.session_state.chat_store.get_history(sid, limit=200)
                    st.session_state.viewing_messages = [
                        {"role": h["role"], "content": h["content"],
                         "meta": json.loads(h.get("metadata", "{}")) if h.get("metadata") else {}}
                        for h in hist
                    ]
                    st.session_state.viewing_session_id = sid
                    st.session_state.viewing_mode = True
                    st.rerun()

    st.divider()

    # --- 查看历史时的返回按钮 ---
    if st.session_state.viewing_mode:
        back_label = "← 返回当前对话" if lang_label == "zh" else "← Back to Current"
        if st.button(back_label, use_container_width=True):
            st.session_state.viewing_mode = False
            st.session_state.viewing_session_id = None
            st.session_state.viewing_messages = []
            st.rerun()
        st.divider()

    # --- 原有配置项 ---
    st.markdown("### ⚙️ 配置" if lang_label == "zh" else "### ⚙️ Settings")
    tk = st.slider("检索数量 / Top-K", 1, 10, engine.top_k)
    engine.top_k = tk

    cross_retrieval = st.checkbox(
        "跨语言检索 / Cross-lingual",
        value=engine._cross_retrieval,
        help="中文问题自动用英文翻译检索，反之亦然"
    )
    engine._cross_retrieval = cross_retrieval

    st.divider()
    if st.button("🔄 重建索引 / Rebuild Index", use_container_width=True):
        with st.spinner("解析PDF中..."):
            try:
                r = engine.build_index(st.session_state.pdf_path, force_rebuild=True)
                st.success(f"完成! {r['total_chunks']} chunks, {r['total_pages']} pages")
            except Exception as e:
                st.error(str(e)[:100])

    if st.button("🗑️ 清空对话 / Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.markdown(f"**📄 {cfg['pdf']['file_path'].split('/')[-1]}**")
    st.markdown(f"**🧠 {cfg['embedding']['model_name']} ({engine.embedder.dimension}d)**")
    st.markdown(f"**💾 {engine.vector_store.count()} chunks**")

# ===== 主界面 =====
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

# 判断当前显示模式
if st.session_state.viewing_mode:
    # --- 历史会话查看模式（只读） ---
    viewing_sid = st.session_state.viewing_session_id or ""
    short_sid = viewing_sid[-12:] if len(viewing_sid) > 12 else viewing_sid
    hist_title_msg = "📜 历史对话" if lang_label == "zh" else "📜 History"
    st.markdown(
        f'<div style="text-align:center;padding:16px 0;color:#999;font-size:0.85rem;">'
        f'{hist_title_msg} · {short_sid} '
        f'（<a href="#" onclick="return false;" style="color:#1a73e8;text-decoration:none;cursor:pointer;">'
        f'{"点击返回新对话" if lang_label == "zh" else "Click to return"}</a>）'
        f'</div>',
        unsafe_allow_html=True
    )

    for msg in st.session_state.viewing_messages:
        render_message(msg["role"], msg.get("content", ""), msg.get("meta", {}))

    # 提示只读（无输入框，靠底部padding）
    st.markdown('<div style="height:60px;text-align:center;color:#ccc;font-size:0.8rem;">'
                + ("⬆ 选择左侧「新对话」开始新会话" if lang_label == "zh" else "⬆ Click 'New Chat' to start")
                + '</div>', unsafe_allow_html=True)
else:
    # --- 当前会话模式（可输入） ---
    if not st.session_state.messages:
        # 空状态欢迎页
        st.markdown("""
        <div class="welcome">
            <div class="welcome-icon">📄</div>
            <h2>招股说明书智能问答 v2</h2>
            <p>基于 RAG 的招股说明书问答 · 支持中英文 · 实时评估指标</p>
            <p style="color:#bbb;font-size:0.8rem;margin-top:12px;">输入问题开始对话</p>
            <div class="suggestions">
                <span class="suggestion-chip">📊 发行人的营业收入是多少？</span>
                <span class="suggestion-chip">🏢 公司的保荐机构是谁？</span>
                <span class="suggestion-chip">📈 What is the total revenue?</span>
                <span class="suggestion-chip">👤 公司的实际控制人是谁？</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # 渲染当前会话消息
        for msg in st.session_state.messages:
            render_message(msg["role"], msg.get("content", ""), msg.get("meta", {}))

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div style="height:100px"></div>', unsafe_allow_html=True)

    # ===== 输入 =====
    st.markdown('<div class="input-area"><div class="input-inner">', unsafe_allow_html=True)

    placeholder_text = "向招股说明书提问..." if lang_label == "zh" else "Ask the prospectus..."
    if prompt := st.chat_input(placeholder_text):
        st.session_state.messages.append({"role": "user", "content": prompt})

        if st.session_state.chat_store:
            st.session_state.chat_store.save_message(
                st.session_state.session_id, "user", prompt
            )

        st.markdown(
            f'<div class="user-msg-wrapper"><div class="user-msg">{prompt}</div></div>',
            unsafe_allow_html=True
        )

        placeholder = st.empty()

        # 检测语言
        query_lang = engine.detect_language(prompt)

        # 思考动画
        msg = "检索中..." if query_lang == "zh" else "Retrieving..."
        placeholder.markdown(
            '<div class="thinking-wrapper">'
            '<span class="thinking-dot"></span><span class="thinking-dot"></span><span class="thinking-dot"></span>'
            f'<span class="thinking-label">{msg}</span>'
            '</div>',
            unsafe_allow_html=True
        )

        try:
            if engine.vector_store.count() == 0:
                placeholder.markdown(
                    '<div class="thinking-wrapper">'
                    '<span class="thinking-dot"></span><span class="thinking-dot"></span><span class="thinking-dot"></span>'
                    '<span class="thinking-label">'
                    + ("首次使用，正在构建向量索引..." if query_lang == "zh" else "First use, building vector index...")
                    + '</span></div>',
                    unsafe_allow_html=True
                )
                engine.build_index(st.session_state.pdf_path)

            full_answer = ""
            result = None

            for event in engine.query_stream(prompt, query_lang):
                if event["type"] == "phase":
                    placeholder.markdown(
                        '<div class="thinking-wrapper">'
                        '<span class="thinking-dot"></span><span class="thinking-dot"></span><span class="thinking-dot"></span>'
                        f'<span class="thinking-label">{event["message"]}</span>'
                        '</div>',
                        unsafe_allow_html=True
                    )
                elif event["type"] == "token":
                    full_answer += event["text"]
                    display = full_answer + '<span class="typing-cursor"></span>'
                    placeholder.markdown(
                        f'<div class="ai-msg-wrapper"><div class="ai-msg">{display}</div></div>',
                        unsafe_allow_html=True
                    )
                elif event["type"] == "done":
                    result = event["result"]

            if result:
                total_time = result["total_time"]
                answer = result["answer"]
                eval_metrics = result.get("eval_metrics", {})
                pages = result.get("pages", [])

                # 元数据标签
                meta_html = ""
                if pages:
                    meta_html += f'<span class="meta-tag">📄 第{", ".join(str(p) for p in sorted(pages))}页</span>'
                meta_html += f'<span class="meta-tag">⏱ {total_time}秒</span>'
                meta_html += format_metrics_html(eval_metrics)

                # 优化方案对比（折叠）
                opt_compare = result.get("lang", "zh")
                opt_html = render_optimization_comparison(result, opt_compare)
                opt_details = f"""
                <details class="ai-details">
                    <summary>📊 {"优化方案对比分析" if opt_compare == 'zh' else 'Optimization Comparison'}</summary>
                    <div class="details-content">{opt_html}</div>
                </details>
                """

                full_html = (
                    f'<div class="ai-msg-wrapper">'
                    f'<div class="ai-msg">'
                    f'{answer}'
                    f'<div class="msg-footer">{meta_html}</div>'
                    f'{opt_details}'
                    f'</div></div>'
                )
                placeholder.markdown(full_html, unsafe_allow_html=True)

                # 保存到当前会话历史
                meta = {
                    "total_time": total_time,
                    "pages": pages,
                    "eval_metrics": eval_metrics,
                    "optimization_html": opt_details,
                }
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "meta": meta,
                })

                if st.session_state.chat_store:
                    st.session_state.chat_store.save_message(
                        st.session_state.session_id, "assistant", answer, metadata=meta
                    )

                # 反馈按钮
                fb_mgr = st.session_state.fb_mgr
                fb_key = f"fb_{hash(prompt) % 100000}"
                col1, col2, col3, _ = st.columns([1, 1, 1, 10])
                with col1:
                    if st.button("👍", key=f"{fb_key}_p", help="准确/Accurate"):
                        fb_mgr.record(prompt, answer, "positive")
                        st.toast("✅ 感谢好评")
                with col2:
                    if st.button("👎", key=f"{fb_key}_n", help="不准确/Inaccurate"):
                        fb_mgr.record(prompt, answer, "negative")
                        st.toast("📝 感谢反馈")
                with col3:
                    if st.button("🤷", key=f"{fb_key}_m", help="部分准确/Partial"):
                        fb_mgr.record(prompt, answer, "neutral")
                        st.toast("💬 已收到")

        except FileNotFoundError as e:
            placeholder.error(f"PDF文件不存在: {e}")
        except Exception as e:
            placeholder.error(f"处理出错: {str(e)[:200]}")
