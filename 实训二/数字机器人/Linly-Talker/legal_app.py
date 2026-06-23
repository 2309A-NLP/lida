#!/usr/bin/env python3
"""
法小助 - 法律数字人咨询系统 (高级版)
独立HTTP服务 + 高级前端页面，无需Gradio
"""
import os
import sys
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, quote
from typing import Any

PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))
os.environ["WEBUI"] = "true"

from LLM import LLM

print("正在初始化法小助法律咨询系统...")
llm_class = LLM(mode='offline')
llm = llm_class.init_model('LegalRAG')
print("法小助已就绪！")

API_HOST = "0.0.0.0"
API_PORT = 7860

# ====== 高级前端页面 ======
INDEX_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>法小助 - 法律数字人咨询系统</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700;900&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0f0f1a;--surface:#1a1a2e;--surface2:#252540;--accent:#4f8cff;--accent2:#7b68ee;--accent3:#e8a838;--text:#e8e8f0;--muted:#8a8aa0;--border:rgba(255,255,255,0.06);--radius:16px;--shadow:0 25px 60px rgba(0,0,0,0.5)}
body{font-family:'Noto Sans SC','Plus Jakarta Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;overflow-x:hidden}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 80% 50% at 50% -20%,rgba(79,140,255,0.12),transparent),radial-gradient(ellipse 60% 40% at 80% 80%,rgba(123,104,238,0.08),transparent);pointer-events:none;z-index:0}
.app-shell{position:relative;z-index:1;width:min(1400px,calc(100vw-32px));margin:0 auto;padding:24px 0 40px}

/* Header */
.header{display:flex;align-items:center;justify-content:space-between;padding:18px 28px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);backdrop-filter:blur(20px);margin-bottom:20px}
.header-left{display:flex;align-items:center;gap:14px}
.logo{width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;font-size:22px}
.header h1{font-size:20px;font-weight:700;letter-spacing:-0.3px}
.header h1 span{color:var(--accent3)}
.header-badge{padding:6px 14px;border-radius:999px;background:rgba(79,140,255,0.12);color:var(--accent);font-size:12px;font-weight:600;letter-spacing:0.3px}
.header-status{display:flex;align-items:center;gap:8px;padding:8px 16px;border-radius:999px;background:rgba(79,140,255,0.08);font-size:13px;color:var(--muted)}
.status-dot{width:8px;height:8px;border-radius:50%;background:#4ade80;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}

/* Layout */
.layout{display:grid;grid-template-columns:minmax(0,1.4fr) 380px;gap:20px;align-items:start}

/* Chat Panel */
.chat-panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;display:flex;flex-direction:column;min-height:680px}
.chat-header{padding:20px 24px 14px;display:flex;align-items:center;justify-content:space-between}
.chat-header h2{font-size:17px;font-weight:600}
.chat-header-actions{display:flex;gap:8px}
.chat-header-actions button{padding:6px 14px;border-radius:8px;border:0;background:var(--surface2);color:var(--muted);font-size:12px;cursor:pointer;transition:all .2s}
.chat-header-actions button:hover{background:rgba(79,140,255,0.15);color:var(--accent)}

/* Message Area */
.messages{flex:1;padding:8px 20px 12px;overflow-y:auto;display:flex;flex-direction:column;gap:12px;min-height:400px;max-height:520px;scroll-behavior:smooth}
.messages::-webkit-scrollbar{width:4px}
.messages::-webkit-scrollbar-track{background:transparent}
.messages::-webkit-scrollbar-thumb{background:var(--surface2);border-radius:4px}
.msg{display:flex;gap:10px;animation:fadeIn .3s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.msg-avatar{width:32px;height:32px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:14px;margin-top:2px}
.msg.user{flex-direction:row-reverse}
.msg.user .msg-avatar{background:linear-gradient(135deg,var(--accent),var(--accent2))}
.msg.assistant .msg-avatar{background:var(--surface2);border:1px solid var(--border)}
.msg.system .msg-avatar{background:transparent;border:1px dashed var(--border)}
.msg-content{max-width:82%;padding:12px 16px;border-radius:14px;line-height:1.7;font-size:14px;white-space:pre-wrap;word-break:break-word}
.msg.user .msg-content{background:linear-gradient(135deg,rgba(79,140,255,0.2),rgba(123,104,238,0.15));border:1px solid rgba(79,140,255,0.15);color:var(--text)}
.msg.assistant .msg-content{background:var(--surface2);border:1px solid var(--border);color:var(--text)}
.msg.system .msg-content{background:rgba(232,168,56,0.06);border:1px solid rgba(232,168,56,0.1);font-size:13px;color:var(--accent3)}
.msg-label{font-size:11px;font-weight:600;color:var(--muted);margin-bottom:4px;letter-spacing:0.3px}
.msg.user .msg-label{text-align:right}

/* Reference cards */
.ref-card{margin-top:10px;padding:10px 12px;border-radius:10px;background:rgba(79,140,255,0.06);border:1px solid rgba(79,140,255,0.1);font-size:12px;line-height:1.6}
.ref-card strong{color:var(--accent)}

/* Quick actions */
.quick-actions{display:flex;flex-wrap:wrap;gap:8px;padding:4px 20px 10px}
.quick-btn{padding:7px 14px;border-radius:999px;border:1px solid var(--border);background:var(--surface2);color:var(--muted);font-size:12px;cursor:pointer;transition:all .2s;font-family:inherit}
.quick-btn:hover{border-color:var(--accent);color:var(--accent);background:rgba(79,140,255,0.08)}

/* Input */
.input-area{padding:14px 20px 18px;border-top:1px solid var(--border);background:rgba(15,15,26,0.5)}
.input-row{display:flex;gap:10px}
.input-row textarea{flex:1;padding:14px 16px;border-radius:12px;border:1px solid var(--border);background:var(--surface2);color:var(--text);font-size:14px;font-family:inherit;resize:none;min-height:52px;max-height:120px;outline:none;transition:border .2s}
.input-row textarea:focus{border-color:var(--accent)}
.send-btn{width:52px;height:52px;border-radius:12px;border:0;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;font-size:20px;cursor:pointer;transition:transform .2s;flex-shrink:0;display:flex;align-items:center;justify-content:center}
.send-btn:hover{transform:scale(1.05)}
.send-btn:active{transform:scale(0.95)}
.send-btn.loading{opacity:0.6;pointer-events:none}

/* Side Panel */
.side-panel{display:flex;flex-direction:column;gap:16px}
.panel-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:20px 22px}
.panel-card h3{font-size:15px;font-weight:600;margin-bottom:4px}
.panel-card p{font-size:13px;color:var(--muted);margin-bottom:14px;line-height:1.6}

/* Law list */
.law-list{display:grid;gap:8px}
.law-item{display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:10px;background:var(--surface2);border:1px solid var(--border);font-size:13px;transition:all .2s;cursor:default}
.law-item:hover{border-color:rgba(79,140,255,0.2)}
.law-icon{width:28px;height:28px;border-radius:8px;background:linear-gradient(135deg,rgba(79,140,255,0.15),rgba(123,104,238,0.1));display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0}
.law-name{flex:1}
.law-check{color:#4ade80;font-size:12px}

/* FAQ list */
.faq-list{display:grid;gap:6px}
.faq-item{padding:10px 14px;border-radius:10px;background:var(--surface2);border:1px solid var(--border);font-size:13px;cursor:pointer;transition:all .2s;line-height:1.5}
.faq-item:hover{border-color:var(--accent);background:rgba(79,140,255,0.06)}
.faq-item code{color:var(--accent);font-family:inherit}

/* Disclaimer */
.disclaimer{padding:12px 14px;border-radius:10px;background:rgba(232,168,56,0.06);border:1px solid rgba(232,168,56,0.1);font-size:12px;color:var(--accent3);line-height:1.7}

/* Footer */
.footer{text-align:center;padding:20px 0 10px;font-size:12px;color:var(--muted)}
.footer a{color:var(--accent);text-decoration:none}

/* Loading dots */
.typing-dots{display:inline-flex;gap:4px;align-items:center;padding:4px 0}
.typing-dots span{width:6px;height:6px;border-radius:50%;background:var(--muted);animation:bounce 1.4s ease-in-out infinite}
.typing-dots span:nth-child(2){animation-delay:.2s}
.typing-dots span:nth-child(3){animation-delay:.4s}
@keyframes bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-6px)}}

/* Responsive */
@media(max-width:860px){.layout{grid-template-columns:1fr}.side-panel{display:none}}
</style>
</head>
<body>
<div class="app-shell">
  <div class="header">
    <div class="header-left">
      <div class="logo">⚖️</div>
      <div><h1>法<span>小</span>助</h1></div>
      <span class="header-badge">LEGAL AI</span>
    </div>
    <div class="header-status">
      <span class="status-dot"></span>
      <span id="status-text">连接中...</span>
    </div>
  </div>

  <div class="layout">
    <div class="chat-panel">
      <div class="chat-header">
        <h2>💬 法律咨询</h2>
        <div class="chat-header-actions">
          <button onclick="clearChat()">清空对话</button>
        </div>
      </div>

      <div class="messages" id="messages">
        <div class="msg system">
          <div class="msg-avatar">ℹ️</div>
          <div class="msg-content">
            <div class="msg-label">系统</div>
            ⚖️ 您好！我是<b>法小助</b>，您的AI法律咨询助手。<br>
            已收录 <b>9部核心法律</b>、<b id="article-count">180+</b> 条法律条款。<br>
            请描述您遇到的法律问题，我会为您检索相关法条并给出参考。
          </div>
        </div>
      </div>

      <div class="quick-actions" id="quick-actions"></div>

      <div class="input-area">
        <div class="input-row">
          <textarea id="input" rows="1" placeholder="描述您的法律问题..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send()}"></textarea>
          <button class="send-btn" id="send-btn" onclick="send()">➤</button>
        </div>
      </div>
    </div>

    <div class="side-panel">
      <div class="panel-card">
        <h3>📚 法律知识库</h3>
        <p>已收录以下核心法律，支持RAG检索增强问答</p>
        <div class="law-list" id="law-list">
          <div class="law-item"><div class="law-icon">🏛️</div><span class="law-name">中华人民共和国民法典</span><span class="law-check">✓</span></div>
          <div class="law-item"><div class="law-icon">⚖️</div><span class="law-name">中华人民共和国刑法</span><span class="law-check">✓</span></div>
          <div class="law-item"><div class="law-icon">💼</div><span class="law-name">中华人民共和国劳动法</span><span class="law-check">✓</span></div>
          <div class="law-item"><div class="law-icon">📋</div><span class="law-name">中华人民共和国劳动合同法</span><span class="law-check">✓</span></div>
          <div class="law-item"><div class="law-icon">🛒</div><span class="law-name">消费者权益保护法</span><span class="law-check">✓</span></div>
          <div class="law-item"><div class="law-icon">🏢</div><span class="law-name">中华人民共和国公司法</span><span class="law-check">✓</span></div>
          <div class="law-item"><div class="law-icon">🚗</div><span class="law-name">道路交通安全法</span><span class="law-check">✓</span></div>
          <div class="law-item"><div class="law-icon">🏥</div><span class="law-name">中华人民共和国社会保险法</span><span class="law-check">✓</span></div>
          <div class="law-item"><div class="law-icon">👮</div><span class="law-name">治安管理处罚法</span><span class="law-check">✓</span></div>
        </div>
      </div>

      <div class="panel-card">
        <h3>❓ 常见问题</h3>
        <p>点击即可快速提问</p>
        <div class="faq-list" id="faq-list"></div>
      </div>

      <div class="panel-card">
        <h3>⚖️ 免责声明</h3>
        <div class="disclaimer">
          本系统提供的法律信息仅供参考，不构成正式法律意见。<br>
          如涉及重大法律事务，请咨询专业律师。<br>
          📞 全国法律服务热线：<b>12348</b>
        </div>
      </div>
    </div>
  </div>

  <div class="footer">Powered by <a href="#">LegalRAG</a> · 法小助法律咨询系统 v2.0</div>
</div>

<script>
const FAQ = [
  "离婚财产怎么分割？","公司拖欠工资怎么办？","工作中受伤算工伤吗？",
  "喝酒开车会怎么处罚？","打架会被拘留吗？","试用期被辞退有赔偿吗？",
  "网购可以七天无理由退货吗？","遗产继承的顺序是什么？","消费者欺诈怎么赔偿？",
  "正当防卫怎么认定？","盗窃罪判几年？","加班费怎么算？"
];

const QUICK = ["离婚财产怎么分割？","公司拖欠工资怎么办？","工作中受伤算工伤吗？","喝酒开车会怎么处罚？"];

const msgs = document.getElementById('messages');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send-btn');
const statusText = document.getElementById('status-text');
const articleCount = document.getElementById('article-count');

function init() {
  const faq = document.getElementById('faq-list');
  FAQ.forEach(q => {
    const d = document.createElement('div'); d.className = 'faq-item';
    d.innerHTML = `<code>${q}</code>`;
    d.onclick = () => ask(q);
    faq.appendChild(d);
  });
  const qa = document.getElementById('quick-actions');
  QUICK.forEach(q => {
    const b = document.createElement('button'); b.className = 'quick-btn';
    b.textContent = q; b.onclick = () => ask(q);
    qa.appendChild(b);
  });
  checkHealth();
}
init();

async function checkHealth() {
  try {
    const r = await fetch('/api/health');
    const d = await r.json();
    statusText.textContent = `已连接 · ${d.legal_kb || 197} 条法条`;
    if(d.legal_kb) articleCount.textContent = d.legal_kb;
  } catch {
    statusText.textContent = '未连接后端';
  }
}

function addMsg(role, text) {
  const div = document.createElement('div'); div.className = `msg ${role}`;
  const labels = {user:'您', assistant:'法小助', system:'系统'};
  const icons = {user:'👤', assistant:'⚖️', system:'ℹ️'};
  div.innerHTML = `<div class="msg-avatar">${icons[role]||'?'}</div><div class="msg-content"><div class="msg-label">${labels[role]||role}</div>${text}</div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function showTyping() {
  const div = document.createElement('div'); div.className = 'msg assistant'; div.id = 'typing';
  div.innerHTML = `<div class="msg-avatar">⚖️</div><div class="msg-content"><div class="typing-dots"><span></span><span></span><span></span></div></div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function hideTyping() {
  const t = document.getElementById('typing');
  if(t) t.remove();
}

function clearChat() {
  msgs.innerHTML = '';
  addMsg('system', '对话已清空，您可以继续提问。');
}

async function ask(q) {
  input.value = q;
  await send();
}

async function send() {
  const text = input.value.trim();
  if(!text) return;
  input.value = '';
  addMsg('user', text);
  showTyping();
  sendBtn.classList.add('loading');
  try {
    const r = await fetch('/api/chat', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({question: text})
    });
    const d = await r.json();
    hideTyping();
    let html = d.answer;
    if(d.references && d.references.length > 0) {
      const refs = d.references.filter(x => x.score > 0.1).slice(0,3);
      if(refs.length > 0) {
        html += '<div class="ref-card"><strong>📚 相关法条：</strong><br>';
        refs.forEach(r => { html += `<div style="margin-top:6px">• 《${r.law}》${r.article} <span style="color:var(--muted);font-size:11px">(相关度:${r.score})</span></div>`; });
        html += '</div>';
      }
    }
    addMsg('assistant', html);
  } catch(e) {
    hideTyping();
    addMsg('system', `请求失败：${e.message}`);
  }
  sendBtn.classList.remove('loading');
}
</script>
</body>
</html>'''

# ====== HTTP Server ======
def json_resp(h, payload, status=200):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(body)))
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "Content-Type")
    h.end_headers()
    h.wfile.write(body)

class LegalHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            kb = llm.retriever.documents if hasattr(llm, 'retriever') and llm.retriever else None
            json_resp(self, {
                "ok": True, "service": "法小助法律咨询系统",
                "legal_kb": len(kb) if kb else 0,
                "laws": 9
            })
            return
        self.serve_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        payload = self._read_json()
        if parsed.path == "/api/chat":
            question = payload.get("question", "").strip()
            if not question:
                json_resp(self, {"error": "请输入问题"}, 400)
                return
            retrieved = llm.retriever.retrieve(question, top_k=5) if hasattr(llm, 'retriever') and llm.retriever else []
            seen = set()
            uniq = []
            for d in retrieved:
                k = f"{d['metadata']['law']}|{d['metadata']['article']}"
                if k not in seen: seen.add(k); uniq.append(d)
            answer = llm.generate(question)
            json_resp(self, {
                "answer": answer,
                "references": [{"law":r["metadata"]["law"],"article":r["metadata"]["article"],"text":r["text"][:200],"score":round(r["score"],3)} for r in uniq[:5]]
            })
            return
        json_resp(self, {"error": "Not Found"}, 404)

    def serve_static(self, path):
        if path == "/" or path == "":
            path = "/index.html"
        req_path = path.lstrip("/")
        file_path = PROJECT_DIR / req_path
        try:
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(PROJECT_DIR.resolve())):
                return json_resp(self, {"error":"Forbidden"}, 403)
        except:
            return json_resp(self, {"error":"Forbidden"}, 403)

        if path == "/index.html":
            # 直接返回内嵌HTML
            content = INDEX_HTML.encode('utf-8')
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
            return

        if not file_path.exists() or not file_path.is_file():
            return json_resp(self, {"error":"Not Found"}, 404)
        mime, _ = mimetypes.guess_type(str(file_path))
        try:
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            json_resp(self, {"error":str(e)}, 500)

    def log_message(self, fmt, *args):
        pass

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=7860)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("0.0.0.0", args.port), LegalHandler)
    print(f"⚖️ 法小助启动中... http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print("已停止。")