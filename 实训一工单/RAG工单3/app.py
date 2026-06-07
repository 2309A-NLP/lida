#!python3
"""
RAG工单3 - FastAPI 智能问答系统
支持双PDF知识库、混合检索、SSE流式回答、多语言、精度评估、对话历史
"""
import os, sys, json, re, time, uuid, asyncio, copy
from pathlib import Path
from typing import Optional, AsyncGenerator

import fitz
import jieba
import requests
import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# ── 配置 ──
BASE_DIR = '/mnt/d/RAG工单/RAG工单3'
PDFS = [
    os.path.join(BASE_DIR, '招股说明书1-无水印.pdf'),
    os.path.join(BASE_DIR, '招股说明书2-无水印.pdf'),
]
DB_PATH = os.path.join(BASE_DIR, 'chromadb_data')
INDEX_PATH = os.path.join(BASE_DIR, 'index_data.json')
HISTORY_PATH = os.path.join(BASE_DIR, 'conversations.json')
API_KEY = 'sk-171f528187724a14a74acc98e756c1c1'
API_URL = 'https://api.deepseek.com/v1/chat/completions'
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
MAX_HISTORY = 20
TOP_K_EMBEDDING = 20
TOP_K_KEYWORD = 5
TOP_K_FINAL = 7
MAX_TOKENS = 2048
TEMPERATURE = 0.1

jieba.setLogLevel(20)

stopwords = set()
STOP_WORDS_STR = '什么 怎么 哪些 这个 那个 一个 可以 没有 我们 他们 你们 自己 如何 为什么 相关 涉及 情况 的 了 是 在 和 与 或 及 对 为 等 之 其 该 被 把 从 到 向 用 且 以 还 也 但 而 更 已 将 不 很 都 会 能 就 因 如 若 虽 然 只 要 让'
stopwords.update(STOP_WORDS_STR.split())

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_or_build_index()
    yield

# ── FastAPI ──
app = FastAPI(title='RAG工单3 - 智能问答系统', lifespan=lifespan)

template_dir = os.path.join(BASE_DIR, 'templates')
os.makedirs(template_dir, exist_ok=True)
templates = Jinja2Templates(directory=template_dir)

# ── 全局状态 ──
col = None
all_chunks_texts = []
all_chunks_sources = []
pdf_page_map = {}  # pdf_name -> list of (page_num, page_text)
start_time = time.time()

# ── 对话存储 ──
def load_conversations():
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_conversations(data):
    with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── 工具函数 ──

def detect_language(text: str) -> str:
    """检测语言"""
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'
    return 'en'

def extract_keywords(text: str, max_kw: int = 8) -> list:
    """提取中英文关键词"""
    # 中文关键词
    zh_keywords = set()
    if re.search(r'[\u4e00-\u9fff]', text):
        words = [w for w in jieba.lcut(text) if len(w) >= 2 and w not in stopwords]
        for w in sorted(words, key=lambda x: (len(x), text.count(x)), reverse=True):
            zh_keywords.add(w)
    
    # 英文关键词（名词短语、专有名词等）
    en_words = re.findall(r'[A-Z][a-zA-Z]+(?:\s+[a-z][a-zA-Z]+)*', text)
    for w in en_words:
        if len(w) >= 3:
            zh_keywords.add(w)
    
    result = sorted(zh_keywords, key=lambda x: (len(x), text.count(x)), reverse=True)
    return result[:max_kw]

def deduplicate_chunks(chunks: list, max_results: int = TOP_K_FINAL) -> list:
    """基于Jaccard去重"""
    if not chunks:
        return []
    result = [chunks[0]]
    for c in chunks[1:]:
        if len(result) >= max_results:
            break
        words_c = set(c['text'].split())
        is_dup = False
        for r in result:
            words_r = set(r['text'].split())
            union = len(words_c | words_r)
            if union and len(words_c & words_r) / union > 0.85:
                is_dup = True
                break
        if not is_dup:
            result.append(c)
    return result

def compute_metrics(query: str, retrieved: list) -> dict:
    """计算检索精度指标"""
    keywords = extract_keywords(query)
    if not keywords or not retrieved:
        return {
            'precision_pct': 100.0 if not keywords else 0.0,
            'recall_pct': 100.0 if not keywords else 0.0,
            'f1_score': 100.0 if not keywords else 0.0,
            'keyword_count': len(keywords)
        }
    
    # 精确率: retrieved chunks中有多少包含query关键词
    relevant_chunks = 0
    all_query_kw_in_retrieved = set()
    
    for r in retrieved:
        text = r['text']
        has_kw = False
        for kw in keywords:
            if kw in text:
                has_kw = True
                all_query_kw_in_retrieved.add(kw)
        if has_kw:
            relevant_chunks += 1
    
    precision = (relevant_chunks / len(retrieved)) * 100 if retrieved else 0
    
    # 召回率: query关键词有多少被retrieved chunks覆盖
    recall = (len(all_query_kw_in_retrieved) / len(keywords)) * 100
    
    # F1
    if precision + recall > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0
    
    return {
        'precision_pct': round(precision, 1),
        'recall_pct': round(recall, 1),
        'f1_score': round(f1, 1),
        'keyword_count': len(keywords)
    }

def hybrid_retrieve(query: str, n_embedding: int = TOP_K_EMBEDDING) -> list:
    """混合检索：向量 + 关键词，返回带分数的结果"""
    global col, all_chunks_texts, all_chunks_sources
    
    results = {}  # text -> {'text': ..., 'source': ..., 'score': float, 'kw_matches': int}
    
    # 1) 向量检索
    try:
        res = col.query(query_texts=[query], n_results=n_embedding)
        if res.get('documents') and res['documents'][0]:
            texts = res['documents'][0]
            distances = res.get('distances', [[]])[0] if res.get('distances') else []
            metadatas = res.get('metadatas', [[]])[0] if res.get('metadatas') else []
            
            for i, t in enumerate(texts):
                if t.strip():
                    score = 1.0 - distances[i] if i < len(distances) else 0.5
                    src = metadatas[i].get('source', 'unknown') if i < len(metadatas) else 'unknown'
                    results[t] = {'text': t, 'source': src, 'score': score, 'kw_matches': 0}
    except Exception as e:
        print(f'[检索错误] 向量检索: {e}')
    
    # 2) 关键词检索
    keywords = extract_keywords(query)
    if keywords and all_chunks_texts:
        for idx, chunk_text in enumerate(all_chunks_texts):
            if chunk_text in results:
                continue
            matched = [kw for kw in keywords if kw in chunk_text]
            if matched:
                actual_source = all_chunks_sources[idx] if idx < len(all_chunks_sources) else 'unknown'
                kw_score = len(matched) / max(len(keywords), 1)
                results[chunk_text] = {'text': chunk_text, 'source': actual_source, 'score': 0.3 + kw_score * 0.4, 'kw_matches': len(matched)}
    
    # 3) 综合评分排序
    scored = list(results.values())
    for item in scored:
        kw_bonus = item['kw_matches'] * 0.05
        item['score'] = min(item['score'] + kw_bonus, 1.0)
    
    scored.sort(key=lambda x: x['score'], reverse=True)
    scored = deduplicate_chunks(scored, max_results=TOP_K_FINAL)
    
    return scored

def build_prompt(query: str, retrieved: list, lang: str, target_lang: str = None) -> list:
    """构建DeepSeek API消息，支持目标语言覆盖"""
    # 如果指定了目标语言，使用目标语言
    response_lang = target_lang if target_lang else lang
    
    system_prompts = {
        'zh': (
            '你是一个专业的智能问答助手，基于招股说明书回答用户的问题。\n'
            '规则：\n'
            '1. 必须优先使用参考资料中的内容回答问题\n'
            '2. 如果参考资料信息充足，直接给出准确答案，引用具体数据\n'
            '3. 如果参考资料信息不足，诚实告知并补充自己的知识\n'
            '4. 答案要清晰、简洁、结构化\n'
            '5. 涉及金额、股数、比例等数据时给出具体数字\n'
            f'6. 请用中文回答用户的问题'
        ),
        'en': (
            'You are a professional Q&A assistant answering questions based on a prospectus.\n'
            'Rules:\n'
            '1. Prioritize reference material\n'
            '2. Give direct, data-rich answers\n'
            '3. Be clear and structured\n'
            '4. Include specific numbers when available\n'
            f'5. Please answer in English'
        )
    }
    
    messages = [{'role': 'system', 'content': system_prompts.get(response_lang, system_prompts['zh'])}]
    
    if retrieved:
        ctx_texts = []
        for i, r in enumerate(retrieved, 1):
            source_tag = f'[来源: {r["source"]}]' if r['source'] != 'keyword' else ''
            ctx_texts.append(f'【参考{i}】{source_tag}\n{r["text"]}')
        
        context = '\n\n'.join(ctx_texts)
        if response_lang == 'zh':
            messages.append({'role': 'user', 'content': f'以下是与问题相关的参考资料：\n\n{context[:12000]}\n\n请基于以上资料回答：{query}'})
        else:
            messages.append({'role': 'user', 'content': f'Reference material:\n\n{context[:12000]}\n\nBased on the above, answer: {query}'})
    else:
        messages.append({'role': 'user', 'content': query})
    
    return messages

async def stream_deepseek(messages: list) -> AsyncGenerator[str, None]:
    """流式调用DeepSeek API"""
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': 'deepseek-chat',
        'messages': messages,
        'temperature': TEMPERATURE,
        'max_tokens': MAX_TOKENS,
        'stream': True
    }
    
    try:
        with requests.Session() as session:
            resp = session.post(API_URL, json=payload, headers=headers, stream=True, timeout=30)
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk['choices'][0].get('delta', {}).get('content', '')
                        if delta:
                            yield delta
                    except json.JSONDecodeError:
                        continue
    except requests.exceptions.Timeout:
        yield '\n\n[请求超时，请重试]'
    except requests.exceptions.ConnectionError:
        yield '\n\n[网络连接失败，请检查网络]'
    except Exception as e:
        yield f'\n\n[请求出错: {str(e)[:50]}]'

def non_stream_deepseek(messages: list) -> str:
    """非流式调用DeepSeek API（备用）"""
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': 'deepseek-chat',
        'messages': messages,
        'temperature': TEMPERATURE,
        'max_tokens': MAX_TOKENS
    }
    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return f'抱歉，请求出错: {str(e)[:80]}'

# ── 加载索引 ──
def chunk_text_improved(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """改进分块：按段落感知分块"""
    import re
    sections = re.split(r'(第[一二三四五六七八九十]+[章节部篇]|(?<=\n)[一二三四五六七八九十]+[、．.][^\n]{2,50}\n)', text)
    
    chunks = []
    buffer = ''
    for piece in sections:
        if not piece or len(piece.strip()) < 10:
            continue
        buffer += piece
        while len(buffer) >= size:
            chunk = buffer[:size]
            cut = max(chunk.rfind('。'), chunk.rfind('\n'), chunk.rfind('；'))
            if cut > size // 2:
                chunk = buffer[:cut+1]
            else:
                cut = min(size, len(buffer))
                chunk = buffer[:cut]
            chunk = chunk.strip()
            if len(chunk) >= 30:
                chunks.append(chunk)
            buffer = buffer[len(chunk):]
    
    if buffer.strip() and len(buffer.strip()) >= 30:
        chunks.append(buffer.strip())
    
    if not chunks and len(text) >= 30:
        start = 0
        while start < len(text):
            end = start + size
            chunk = text[start:end].strip()
            if len(chunk) >= 30:
                chunks.append(chunk)
            start += size - overlap
    
    return chunks

def load_or_build_index():
    """加载或构建向量索引"""
    global col, all_chunks_texts, all_chunks_sources
    
    client = chromadb.PersistentClient(path=DB_PATH)
    
    try:
        col = client.get_collection(name='rag', embedding_function=ONNXMiniLM_L6_V2())
        print(f'[索引已加载] 记录数: {col.count()}')
    except:
        print('[构建索引中...]')
        all_text = ''
        for pdf_path in PDFS:
            if os.path.exists(pdf_path):
                doc = fitz.open(pdf_path)
                pages = [p.get_text().strip() for p in doc if p.get_text().strip()]
                doc.close()
                all_text += '\n\n'.join(pages) + '\n\n'
        
        chunks = chunk_text_improved(all_text)
        
        col = client.create_collection(name='rag', embedding_function=ONNXMiniLM_L6_V2())
        ids = [str(uuid.uuid4()) for _ in chunks]
        for i in range(0, len(chunks), 50):
            col.add(ids=ids[i:i+50], documents=chunks[i:i+50])
        print(f'[索引构建完成] {len(chunks)} 块')
    
    # 加载全量文本用于关键词检索
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        all_chunks_texts = [c['text'] for c in data['chunks']]
        all_chunks_sources = [c['source'] for c in data['chunks']]
    else:
        all_docs = col.get()['documents']
        all_chunks_texts = [d for d in all_docs if d.strip()]
        all_chunks_sources = ['unknown'] * len(all_chunks_texts)
    
    print(f'[关键词检索就绪] {len(all_chunks_texts)} 个文本块')
    
    # 构建PDF页号映射（用于参考块定位）
    build_pdf_page_map()


def build_pdf_page_map():
    """构建PDF逐页文本映射，用于参考块页号定位"""
    global pdf_page_map
    pdf_page_map = {}
    for pdf_path in PDFS:
        if os.path.exists(pdf_path):
            fname = os.path.basename(pdf_path)
            doc = fitz.open(pdf_path)
            pages = []
            for i, page in enumerate(doc):
                text = page.get_text().strip()
                if text:
                    pages.append((i + 1, text))  # 1-indexed page numbers
            doc.close()
            pdf_page_map[fname] = pages
            print(f'[PDF页号映射] {fname}: {len(pages)} 页')


def find_page_number(chunk_text: str, pdf_name: str) -> int:
    """根据文本匹配查找参考块所在PDF页号"""
    if pdf_name not in pdf_page_map:
        return 0
    # 用chunk前80字符做锚点搜索
    anchors = [chunk_text[:50].strip(), chunk_text[:80].strip(), chunk_text[:120].strip()]
    for anchor in anchors:
        if not anchor:
            continue
        for page_num, page_text in pdf_page_map[pdf_name]:
            if anchor in page_text:
                return page_num
    # 如果仍找不到，尝试用chunk中的长词匹配
    words = [w for w in chunk_text.split() if len(w) >= 3]
    for word in words[:5]:
        for page_num, page_text in pdf_page_map[pdf_name]:
            if word in page_text:
                return page_num
    return 0


# ── 路由 ──

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    html_path = os.path.join(template_dir, 'index.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return HTMLResponse(content=content)

@app.get('/api/health')
async def health():
    return {
        'status': 'ok',
        'uptime': time.time() - start_time,
        'chunks': len(all_chunks_texts),
        'version': '3.1'
    }

@app.post('/api/chat/stream')
async def chat_stream(data: dict):
    """SSE流式聊天接口"""
    query = data.get('query', '').strip()
    history = data.get('history', [])
    target_language = data.get('target_language', None)  # 可选: 'zh', 'en', 或 None(自动)
    
    if not query:
        raise HTTPException(status_code=400, detail='请输入问题')
    
    lang = detect_language(query)
    
    # 检索
    t0 = time.time()
    retrieved = hybrid_retrieve(query)
    retrieve_time = time.time() - t0
    
    # 计算精度指标
    metrics = compute_metrics(query, retrieved)
    
    # 构建上下文（支持目标语言覆盖）
    messages = build_prompt(query, retrieved, lang, target_language)
    
    # 如果有历史记录，添加
    if history:
        hist_messages = []
        current_pair = None
        for h in history[-10:]:
            if h['role'] == 'user':
                current_pair = h['content']
            elif h['role'] == 'assistant' and current_pair:
                hist_messages.append({'role': 'user', 'content': current_pair})
                hist_messages.append({'role': 'assistant', 'content': h['content']})
                current_pair = None
        if hist_messages:
            messages = [messages[0]] + hist_messages + messages[1:]
    
    async def event_stream():
        # 发送检索元数据（含精度指标）
        meta = {
            'type': 'meta',
            'retrieve_time': round(retrieve_time, 3),
            'num_chunks': len(retrieved),
            'has_context': len(retrieved) > 0,
            'language': lang,
            'target_language': target_language,
            'precision_pct': metrics['precision_pct'],
            'recall_pct': metrics['recall_pct'],
            'f1_score': metrics['f1_score'],
            'keyword_count': metrics['keyword_count']
        }
        yield f'data: {json.dumps(meta, ensure_ascii=False)}\n\n'
        
        # 发送检索到的参考块（含页号）
        if retrieved:
            chunks_data = []
            for i, r in enumerate(retrieved[:5], 1):
                page = find_page_number(r['text'], r['source'])
                src_label = r['source'].replace('.pdf', '')
                if '招股说明书1' in r['source']:
                    src_label = '力源招股书'
                elif '招股说明书2' in r['source']:
                    src_label = '兴图新科招股书'
                chunks_data.append({
                    'index': i,
                    'source': src_label,
                    'source_file': r['source'],
                    'page': page,
                    'score': round(r['score'], 3),
                    'kw_matches': r.get('kw_matches', 0),
                    'preview': r['text'][:200] + ('...' if len(r['text']) > 200 else '')
                })
            ref = {'type': 'references', 'chunks': chunks_data}
            yield f'data: {json.dumps(ref, ensure_ascii=False)}\n\n'
        
        # 流式回答
        t1 = time.time()
        full_text = ''
        try:
            async for delta in stream_deepseek(messages):
                full_text += delta
                token_data = {'type': 'token', 'content': delta}
                yield f'data: {json.dumps(token_data, ensure_ascii=False)}\n\n'
        except Exception:
            fallback = non_stream_deepseek(messages)
            token_data = {'type': 'token', 'content': fallback}
            yield f'data: {json.dumps(token_data, ensure_ascii=False)}\n\n'
            full_text = fallback
        
        llm_time = time.time() - t1
        
        # 非RAG对比：纯LLM回答（不加检索上下文）
        llm_only_text = ''
        try:
            no_context_msgs = build_prompt(query, [], lang, target_language)
            llm_only_text = non_stream_deepseek(no_context_msgs)
        except Exception:
            llm_only_text = ''
        
        # 完成信号（含RAG vs 纯LLM对比）
        total_elapsed = time.time() - t0
        done = {
            'type': 'done',
            'total_time': round(total_elapsed, 3),
            'llm_time': round(llm_time, 3),
            'total_chars': len(full_text),
            'full_text': full_text,
            'llm_only_text': llm_only_text  # 纯LLM对比回答
        }
        yield f'data: {json.dumps(done, ensure_ascii=False)}\n\n'
    
    return StreamingResponse(event_stream(), media_type='text/event-stream')

@app.post('/api/chat')
async def chat(data: dict):
    """非流式聊天接口"""
    query = data.get('query', '').strip()
    target_language = data.get('target_language', None)
    
    if not query:
        raise HTTPException(status_code=400, detail='请输入问题')
    
    lang = detect_language(query)
    
    t0 = time.time()
    retrieved = hybrid_retrieve(query)
    retrieve_time = time.time() - t0
    
    metrics = compute_metrics(query, retrieved)
    
    messages = build_prompt(query, retrieved, lang, target_language)
    
    t1 = time.time()
    answer = non_stream_deepseek(messages)
    llm_time = time.time() - t1
    
    return {
        'query': query,
        'answer': answer,
        'language': lang,
        'retrieve_time': round(retrieve_time, 3),
        'llm_time': round(llm_time, 3),
        'total_time': round(retrieve_time + llm_time, 3),
        'num_chunks': len(retrieved),
        'has_context': len(retrieved) > 0,
        'precision_pct': metrics['precision_pct'],
        'recall_pct': metrics['recall_pct'],
        'f1_score': metrics['f1_score'],
        'chunks': [{'text': r['text'][:300], 'source': r['source'], 'score': round(r['score'], 3)} for r in retrieved[:5]]
    }

# ── 对话历史 API ──

@app.post('/api/history/list')
async def history_list():
    """列出所有对话"""
    convs = load_conversations()
    items = []
    for cid, c in convs.items():
        msg_count = len(c.get('messages', [])) // 2
        preview = ''
        if c.get('messages'):
            preview = c['messages'][0].get('content', '')[:60]
        items.append({
            'id': cid,
            'title': c.get('title', f'对话 {cid[:8]}'),
            'preview': preview,
            'msg_count': msg_count,
            'created_at': c.get('created_at', 0),
            'updated_at': c.get('updated_at', 0)
        })
    items.sort(key=lambda x: x['updated_at'], reverse=True)
    return {'conversations': items}

@app.post('/api/history/get')
async def history_get(data: dict):
    """获取单个对话"""
    conv_id = data.get('id', '')
    convs = load_conversations()
    if conv_id not in convs:
        raise HTTPException(status_code=404, detail='对话不存在')
    return {'conversation': convs[conv_id]}

@app.post('/api/history/save')
async def history_save(data: dict):
    """保存/创建对话"""
    conv_id = data.get('id', '')
    messages = data.get('messages', [])
    title = data.get('title', '')
    
    convs = load_conversations()
    now = time.time()
    
    if not title and messages:
        first_q = messages[0].get('content', '')[:50]
        title = first_q if first_q else f'对话 {conv_id[:8]}'
    
    if conv_id in convs:
        convs[conv_id]['messages'] = messages
        convs[conv_id]['title'] = title or convs[conv_id].get('title', '')
        convs[conv_id]['updated_at'] = now
    else:
        convs[conv_id] = {
            'id': conv_id,
            'title': title or f'对话 {conv_id[:8]}',
            'messages': messages,
            'created_at': now,
            'updated_at': now
        }
    
    save_conversations(convs)
    return {'status': 'ok', 'id': conv_id}

@app.post('/api/history/delete')
async def history_delete(data: dict):
    """删除对话"""
    conv_id = data.get('id', '')
    convs = load_conversations()
    if conv_id in convs:
        del convs[conv_id]
        save_conversations(convs)
    return {'status': 'ok'}

@app.post('/api/history/rename')
async def history_rename(data: dict):
    """重命名对话"""
    conv_id = data.get('id', '')
    title = data.get('title', '').strip()
    if not title:
        raise HTTPException(status_code=400, detail='标题不能为空')
    convs = load_conversations()
    if conv_id not in convs:
        raise HTTPException(status_code=404, detail='对话不存在')
    convs[conv_id]['title'] = title
    convs[conv_id]['updated_at'] = time.time()
    save_conversations(convs)
    return {'status': 'ok'}

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8503)
