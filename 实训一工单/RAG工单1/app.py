"""
RAG 智能问答系统 - DeepSeek风格聊天界面
流式输出，思考动画，表格感知
"""
import json
import sys
import os
import time
import copy
from pathlib import Path
import streamlit as st
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from src.rag_engine import RAGEngine
from src.feedback import FeedbackManager
from src.chat_history import ChatHistoryStore

st.set_page_config(page_title="RAG 智能问答", page_icon="💬", layout="wide")

# ===== DeepSeek风格CSS =====
st.markdown("""
<style>
/* Reset */
.stApp { background: #fff; }
.main .block-container { max-width: 860px; padding: 0 !important; }
#root > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > section.main > div { padding-top: 0; }

/* 隐藏Streamlit默认元素 */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
.stApp > header { display: none; }

/* 聊天容器 */
.chat-container {
    max-width: 760px;
    margin: 0 auto;
    padding: 20px 24px 140px 24px;
    min-height: 100vh;
}

/* 顶部标题 */
.chat-header {
    text-align: center;
    padding: 40px 0 30px 0;
    border-bottom: none;
}
.chat-header h1 {
    font-size: 1.6rem;
    font-weight: 600;
    color: #1a1a1a;
    margin: 0;
    letter-spacing: -0.3px;
}
.chat-header p {
    color: #888;
    font-size: 0.85rem;
    margin: 8px 0 0 0;
}

/* 用户消息 */
.user-msg-wrapper {
    display: flex;
    justify-content: flex-end;
    margin: 18px 0;
}
.user-msg {
    background: #e8f0fe;
    color: #1a1a1a;
    padding: 12px 18px;
    border-radius: 20px 20px 4px 20px;
    max-width: 70%;
    font-size: 0.95rem;
    line-height: 1.6;
    word-break: break-word;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}

/* AI消息 - 左对齐白底 */
.ai-msg-wrapper {
    display: flex;
    justify-content: flex-start;
    margin: 18px 0;
}
.ai-msg {
    background: transparent;
    color: #1a1a1a;
    padding: 4px 0;
    max-width: 85%;
    font-size: 0.95rem;
    line-height: 1.7;
    word-break: break-word;
}
.ai-msg p { margin: 0 0 8px 0; }
.ai-msg p:last-child { margin: 0; }

/* 来源和响应时间标签 */
.meta-tag {
    display: inline-block;
    color: #999;
    font-size: 0.75rem;
    margin-top: 6px;
    margin-right: 12px;
    background: #f5f5f5;
    padding: 2px 10px;
    border-radius: 10px;
}

/* 思考中动画 */
.thinking-wrapper {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 12px 0;
    padding: 4px 0;
}
.thinking-dot {
    width: 6px;
    height: 6px;
    background: #999;
    border-radius: 50%;
    animation: thinking-bounce 1.4s ease-in-out infinite;
}
.thinking-dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes thinking-bounce {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
    40% { transform: scale(1.0); opacity: 1; }
}
.thinking-label {
    color: #999;
    font-size: 0.85rem;
    margin-left: 4px;
}

/* 打字光标 */
@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}
.typing-cursor {
    display: inline-block;
    width: 2px;
    height: 16px;
    background: #1a1a1a;
    margin-left: 2px;
    animation: blink 0.8s step-end infinite;
    vertical-align: text-bottom;
}

/* 输入框 - 底部固定圆角 */
.input-area {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: linear-gradient(transparent, #fff 30%);
    padding: 20px 0 16px 0;
    z-index: 100;
}
.input-inner {
    max-width: 760px;
    margin: 0 auto;
    padding: 0 24px;
}
.stChatFloatingInputContainer {
    position: relative !important;
    bottom: auto !important;
    background: transparent !important;
    padding: 0 !important;
}
[data-testid="stChatInput"] {
    position: relative !important;
    bottom: auto !important;
}
[data-testid="stChatInput"] textarea {
    background: #f5f5f5 !important;
    border: 1px solid #e5e5e5 !important;
    border-radius: 24px !important;
    color: #1a1a1a !important;
    font-size: 0.95rem !important;
    padding: 12px 20px !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04) !important;
    transition: box-shadow 0.2s;
    max-height: 120px;
}
[data-testid="stChatInput"] textarea:focus {
    box-shadow: 0 2px 12px rgba(0,0,0,0.08) !important;
    border-color: #d0d0d0 !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: #bbb; }
.stChatInputContainer { border: none !important; }

/* 折叠面板 */
details.ai-details {
    margin: 6px 0;
    display: inline-block;
}
details.ai-details summary {
    cursor: pointer;
    color: #999;
    font-size: 0.78rem;
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    transition: background 0.15s;
    user-select: none;
}
details.ai-details summary:hover {
    background: #f0f0f0;
    color: #666;
}
details.ai-details[open] summary {
    margin-bottom: 8px;
}
.details-content {
    font-size: 0.85rem;
    color: #555;
    line-height: 1.6;
    padding: 8px 0;
}
.details-content .ref-item {
    border-left: 2px solid #ddd;
    padding: 6px 12px;
    margin: 4px 0;
    font-size: 0.82rem;
    color: #666;
}

/* 空状态 - 欢迎页 */
.welcome {
    text-align: center;
    padding: 100px 20px 40px 20px;
}
.welcome-icon {
    font-size: 3rem;
    margin-bottom: 16px;
}
.welcome h2 {
    font-size: 1.3rem;
    font-weight: 500;
    color: #333;
    margin: 0 0 8px 0;
}
.welcome p {
    color: #999;
    font-size: 0.9rem;
    margin: 0;
}
.welcome .suggestions {
    margin-top: 30px;
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 10px;
}
.welcome .suggestion-chip {
    background: #f5f5f5;
    border: 1px solid #eee;
    border-radius: 20px;
    padding: 8px 18px;
    font-size: 0.85rem;
    color: #666;
    cursor: pointer;
    transition: all 0.15s;
}
.welcome .suggestion-chip:hover {
    background: #e8f0fe;
    border-color: #c0d8f8;
    color: #1a73e8;
}

/* 侧边栏 */
[data-testid="stSidebar"] { background: #fafafa; border-right: 1px solid #eee; }
[data-testid="stSidebar"] .stButton button {
    border: 1px solid #e0e0e0 !important;
    border-radius: 10px !important;
    background: #fff !important;
    color: #333 !important;
    font-size: 0.85rem !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    border-color: #ccc !important;
    background: #f5f5f5 !important;
}

/* 隐藏Streamlit默认消息 - 只隐藏原始的st.chat_message框架，不隐藏内容 */
[data-testid="stChatMessage"] { border: none; background: transparent; padding: 0; margin: 0; }

/* 反馈按钮 */
.feedback-row {
    margin-top: 4px;
    display: flex;
    gap: 4px;
}
.feedback-btn {
    background: none;
    border: none;
    color: #ccc;
    font-size: 0.85rem;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 6px;
    transition: all 0.15s;
    line-height: 1;
}
.feedback-btn:hover {
    background: #f0f0f0;
    color: #666;
}

/* 消息底部元数据 */
.msg-footer {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 8px;
}

/* 表格样式 */
.ai-msg table {
    border-collapse: collapse;
    margin: 8px 0;
    font-size: 0.85rem;
    width: 100%;
}
.ai-msg th, .ai-msg td {
    border: 1px solid #e0e0e0;
    padding: 8px 12px;
    text-align: left;
}
.ai-msg th {
    background: #f5f5f5;
    font-weight: 500;
}
.ai-msg tr:nth-child(even) td {
    background: #fafafa;
}
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

# ===== 初始化 =====
if "messages" not in st.session_state:
    st.session_state.fb_mgr = init_feedback()
    st.session_state.session_id = "rag_user_main"  # 固定ID，保持跨刷新对话持久

    # 初始化Milvus Lite并加载历史
    store = ChatHistoryStore()
    connected = store.connect()
    st.session_state.chat_store = store if connected else None

    if connected:
        history = store.get_history(st.session_state.session_id, limit=100)
        st.session_state.messages = [
            {"role": h["role"], "content": h["content"],
             "meta": json.loads(h.get("metadata", "{}")) if h.get("metadata") else {}}
            for h in history
        ]
    else:
        st.session_state.messages = []

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
    st.markdown("### 配置")
    tk = st.slider("检索数量", 1, 10, engine.top_k)
    engine.top_k = tk
    st.divider()
    if st.button("重建索引", use_container_width=True):
        with st.spinner("解析PDF中..."):
            try:
                r = engine.build_index(st.session_state.pdf_path, force_rebuild=True)
                st.success(f"完成！{r['total_chunks']}个文本块，{r['total_pages']}页")
            except Exception as e:
                st.error(str(e)[:100])
    if st.button("清空对话", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ===== 主界面 =====
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

if not st.session_state.messages:
    # 空状态欢迎页
    st.markdown("""
    <div class="welcome">
        <div class="welcome-icon">📄</div>
        <h2>招股说明书智能问答</h2>
        <p>基于招股说明书 PDF 的 RAG 问答系统</p>
        <p style="color:#bbb;font-size:0.8rem;margin-top:12px;">输入问题开始对话</p>
        <div class="suggestions">
            <span class="suggestion-chip">发行人的营业收入是多少？</span>
            <span class="suggestion-chip">公司的保荐机构是谁？</span>
            <span class="suggestion-chip">本次发行股票数量是多少？</span>
            <span class="suggestion-chip">公司的实际控制人是谁？</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    # 渲染历史消息
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg.get("content", "")
        meta = msg.get("meta", {})

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

            st.markdown(
                f'<div class="ai-msg-wrapper">'
                f'<div class="ai-msg">'
                f'{content}'
                f'<div class="msg-footer">{meta_html}</div>'
                f'</div></div>',
                unsafe_allow_html=True
            )

st.markdown('</div>', unsafe_allow_html=True)

# ===== 底部安全区 =====
st.markdown('<div style="height:100px"></div>', unsafe_allow_html=True)

# ===== 输入 =====
st.markdown('<div class="input-area"><div class="input-inner">', unsafe_allow_html=True)

if prompt := st.chat_input("向招股说明书提问..."):
    # 用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})

    if st.session_state.chat_store:
        st.session_state.chat_store.save_message(
            st.session_state.session_id, "user", prompt
        )

    # 显示用户消息（直接st.markdown，不包st.chat_message）
    st.markdown(
        f'<div class="user-msg-wrapper"><div class="user-msg">{prompt}</div></div>',
        unsafe_allow_html=True
    )

    # 处理回答 - 流式（直接st.markdown，不包st.chat_message）
    placeholder = st.empty()

    # 阶段1：显示思考动画
    placeholder.markdown(
        '<div class="thinking-wrapper">'
        '<span class="thinking-dot"></span><span class="thinking-dot"></span><span class="thinking-dot"></span>'
        '<span class="thinking-label">正在检索...</span>'
        '</div>',
        unsafe_allow_html=True
    )

    try:
        if engine.vector_store.count() == 0:
            placeholder.markdown(
                '<div class="thinking-wrapper">'
                '<span class="thinking-dot"></span><span class="thinking-dot"></span><span class="thinking-dot"></span>'
                '<span class="thinking-label">首次使用，正在构建向量索引...</span>'
                '</div>',
                unsafe_allow_html=True
            )
            engine.build_index(st.session_state.pdf_path)

        full_answer = ""
        result = None

        # 流式处理
        for event in engine.query_stream(prompt):
            if event["type"] == "phase":
                # 更新阶段状态
                placeholder.markdown(
                    '<div class="thinking-wrapper">'
                    '<span class="thinking-dot"></span><span class="thinking-dot"></span><span class="thinking-dot"></span>'
                    f'<span class="thinking-label">{event["message"]}</span>'
                    '</div>',
                    unsafe_allow_html=True
                )
            elif event["type"] == "token":
                full_answer += event["text"]
                # 显示已生成的内容 + 打字光标
                display = full_answer + '<span class="typing-cursor"></span>'
                placeholder.markdown(
                    f'<div class="ai-msg-wrapper"><div class="ai-msg">{display}</div></div>',
                    unsafe_allow_html=True
                )
            elif event["type"] == "done":
                result = event["result"]

        # 生成完成，去掉光标，显示元数据
        if result:
            total_time = result["total_time"]
            answer = result["answer"]

            meta_html = ""
            pages = result.get("pages", [])
            if pages:
                meta_html += f'<span class="meta-tag">📄 第{", ".join(str(p) for p in sorted(pages))}页</span>'
            meta_html += f'<span class="meta-tag">⏱ {total_time}秒</span>'

            full_html = (
                f'<div class="ai-msg-wrapper">'
                f'<div class="ai-msg">'
                f'{answer}'
                f'<div class="msg-footer">{meta_html}</div>'
                f'</div></div>'
            )
            placeholder.markdown(full_html, unsafe_allow_html=True)

            # 保存到历史
            meta = {"total_time": total_time, "pages": pages}
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "meta": meta,
            })

            # 反馈按钮
            fb_mgr = st.session_state.fb_mgr
            fb_key = f"fb_{hash(prompt) % 100000}"
            col1, col2, col3, _ = st.columns([1, 1, 1, 10])
            with col1:
                if st.button("👍", key=f"{fb_key}_p", help="准确"):
                    fb_mgr.record(prompt, answer, "positive")
                    st.toast("✅ 感谢好评")
            with col2:
                if st.button("👎", key=f"{fb_key}_n", help="不准确"):
                    fb_mgr.record(prompt, answer, "negative")
                    st.toast("📝 感谢反馈")
            with col3:
                if st.button("🤷", key=f"{fb_key}_m", help="部分准确"):
                    fb_mgr.record(prompt, answer, "neutral")
                    st.toast("💬 已收到")

    except FileNotFoundError as e:
        placeholder.error(f"PDF文件不存在：{e}")
    except Exception as e:
        placeholder.error(f"处理出错：{str(e)[:200]}")
