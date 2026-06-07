#!python3
"""
RAG工单3 - FastAPI 智能问答系统 (Milvus Lite版)
支持双PDF知识库、混合检索、SSE流式回答、多语言、精度评估
"""
import os, sys, json, re, time, uuid, asyncio
from pathlib import Path
from typing import Optional, AsyncGenerator

import fitz
import jieba
import requests
import numpy as np
from pymilvus import MilvusClient, DataType
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import uvicorn

# ── 配置 ──
BASE_DIR = '/mnt/d/RAG工单3'
PDFS = [
    os.path.join(BASE_DIR, '招股说明书1-无水印.pdf'),
    os.path.join(BASE_DIR, '招股说明书2-无水印.pdf'),
]
DB_PATH = os.path.join(BASE_DIR, 'milvus_data_3.db')
COLLECTION_NAME = 'rag_v3_milvus'
SESSION_COLLECTION = 'rag_v3_sessions'
INDEX_PATH = os.path.join(BASE_DIR, 'index_data.json')
API_KEY = 'sk-171...c1c1'
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

# ── 全局状态 ──
milvus_client = None
ef = ONNXMiniLM_L6_V2()
all_chunks_texts = []
all_chunks_sources = []
start_time = time.time()

# ── 工具函数 ──

def detect_language(text: str) -> str:
    """检测语言"""
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'
    return 'en'

def extract_keywords(text: str, max_kw: int = 8) -> list:
    """提取中文关键词，支持2字以上"""
    if not re.search(r'[\u4e00-\u9fff]', text):
        return []
    words = [w for w in jieba.lcut(text) if len(w) >= 2 and w not in stopwords]
    seen = set()
    result = []
    for w in sorted(words, key=lambda x: (len(x), text.count(x)), reverse=True):
        if w not in seen:
            seen.add(w)
            result.append(w)
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

def get_embedding(text: str) -> list:
    """生成384维归一化向量"""
    emb = ef([text])[0]
    return emb

def hybrid_retrieve(query: str, n_embedding: int = TOP_K_EMBEDDING) -> list:
    """混合检索：向量(Milvus) + 关键词，返回带分数的结果"""
    global milvus_client, all_chunks_texts, all_chunks_sources

    results = {}  # text -> {'text': ..., 'source': ..., 'score': float, 'kw_matches': int}

    # 1) 向量检索 (Milvus Lite)
    try:
        emb = get_embedding(query)
        search_res = milvus_client.search(
            collection_name=COLLECTION_NAME,
            data=[emb],
            limit=n_embedding,
            output_fields=['text', 'source']
        )
        if search_res and search_res[0]:
            for hit in search_res[0]:
                t = hit['entity']['text']
                src = hit['entity'].get('source', 'unknown')
                score = float(hit['distance'])  # IP距离，已归一化向量相当于cosine
                if t.strip():
                    results[t] = {'text': t, 'source': src, 'score': score, 'kw_matches': 0}
    except Exception as e:
        print(f'[检索错误] 向量检索: {e}')

    # 2) 关键词检索
    keywords = extract_keywords(query)
    if keywords and all_chunks_texts:
        for chunk_text in all_chunks_texts:
            if chunk_text in results:
                continue
            matched = [kw for kw in keywords if kw in chunk_text]
            if matched:
                kw_score = len(matched) / max(len(keywords), 1)
                results[chunk_text] = {'text': chunk_text, 'source': 'keyword', 'score': 0.3 + kw_score * 0.4, 'kw_matches': len(matched)}

    # 3) 综合评分排序
    scored = list(results.values())
    for item in scored:
        kw_bonus = item['kw_matches'] * 0.05
        item['score'] = min(item['score'] + kw_bonus, 1.0)

    scored.sort(key=lambda x: x['score'], reverse=True)
    scored = deduplicate_chunks(scored, max_results=TOP_K_FINAL)

    return scored

# ── Session管理 ──

def init_session_collection():
    """初始化会话集合"""
    global milvus_client
    if milvus_client is None:
        return
    if not milvus_client.has_collection(SESSION_COLLECTION):
        schema = milvus_client.create_schema(auto_id=True, enable_dynamic_field=True)
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="dummy_vec", datatype=DataType.FLOAT_VECTOR, dim=1)
        schema.add_field(field_name="session_id", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=255)
        schema.add_field(field_name="messages", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="created_at", datatype=DataType.INT64)
        schema.add_field(field_name="updated_at", datatype=DataType.INT64)
        milvus_client.create_collection(collection_name=SESSION_COLLECTION, schema=schema)
        print(f'[会话集合已创建] {SESSION_COLLECTION}')

def create_session(title: str = "新对话") -> dict:
    """创建新会话"""
    session_id = str(uuid.uuid4())
    now = int(time.time())
    milvus_client.insert(SESSION_COLLECTION, {
        'dummy_vec': [0.0],
        'session_id': session_id,
        'title': title,
        'messages': '[]',
        'created_at': now,
        'updated_at': now
    })
    return {'session_id': session_id, 'title': title, 'created_at': now}

def list_sessions(limit: int = 50) -> list:
    """列出所有会话"""
    sessions = milvus_client.query(
        SESSION_COLLECTION,
        output_fields=['session_id', 'title', 'created_at', 'updated_at'],
        limit=limit,
        sort='updated_at desc'
    )
    return sessions

def get_session(session_id: str) -> Optional[dict]:
    """获取会话"""
    results = milvus_client.query(
        SESSION_COLLECTION,
        filter=f'session_id == "{session_id}"',
        limit=1
    )
    if results:
        return results[0]
    return None

def update_session_messages(session_id: str, messages: list):
    """更新会话消息"""
    now = int(time.time())
    milvus_client.query(
        SESSION_COLLECTION,
        expr=f'session_id == "{session_id}"',
        output_fields=['id']
    )
    # 用upsert更新
    sessions = milvus_client.query(
        SESSION_COLLECTION,
        filter=f'session_id == "{session_id}"',
        output_fields=['id'],
        limit=1
    )
    if sessions:
        sid = sessions[0]['id']
        # MilvusClient doesn't have update, so we use upsert
        milvus_client.delete(SESSION_COLLECTION, filter=f'id == {sid}')
        milvus_client.insert(SESSION_COLLECTION, {
            'dummy_vec': [0.0],
            'id': sid,
            'session_id': session_id,
            'messages': json.dumps(messages, ensure_ascii=False),
            'updated_at': now
        })

def delete_session(session_id: str):
    """删除会话"""
    milvus_client.query(
        SESSION_COLLECTION,
        expr=f'session_id == "{session_id}"',
        output_fields=['id']
    )
    milvus_client.delete(SESSION_COLLECTION, filter=f'session_id == "{session_id}"')

# ── Prompt & API ──

def build_prompt(query: str, retrieved: list, lang: str) -> list:
    """构建DeepSeek API消息"""
    system_prompts = {
        'zh': (
            '你是一个专业的智能问答助手，基于招股说明书回答用户的问题。\n'
            '规则：\n'
            '1. 必须优先使用参考资料中的内容回答问题\n'
            '2. 如果参考资料信息充足，直接给出准确答案，引用具体数据\n'
            '3. 如果参考资料信息不足，诚实告知并补充自己的知识\n'
            '4. 答案要清晰、简洁、结构化\n'
            '5. 涉及金额、股数、比例等数据时给出具体数字'
        ),
        'en': (
            'You are a professional Q&A assistant answering questions based on a prospectus.\n'
            'Rules:\n'
            '1. Prioritize reference material\n'
            '2. Give direct, data-rich answers\n'
            '3. Be clear and structured\n'
            '4. Include specific numbers when available'
        )
    }

    messages = [{'role': 'system', 'content': system_prompts.get(lang, system_prompts['zh'])}]

    if retrieved:
        ctx_texts = []
        for i, r in enumerate(retrieved, 1):
            source_tag = f'[来源: {r["source"]}]' if r['source'] != 'keyword' else ''
            ctx_texts.append(f'【参考{i}】{source_tag}\n{r["text"]}')

        context = '\n\n'.join(ctx_texts)
        if lang == 'zh':
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

# ── 索引加载 ──

def chunk_text_improved(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """改进分块：按段落感知分块"""
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
    """加载Milvus索引和关键词数据"""
    global milvus_client, all_chunks_texts, all_chunks_sources

    # 初始化Milvus Lite
    milvus_client = MilvusClient(uri=DB_PATH)

    # 检查集合是否存在
    if not milvus_client.has_collection(COLLECTION_NAME):
        print('[Milvus索引不存在，尝试重建]')
        # 构建索引
        create_milvus_index()

    # 查询集合状态
    count = milvus_client.query(COLLECTION_NAME, output_fields=['count(*)'])
    actual_count = count[0]['count(*)'] if count else 0
    # 加载集合到内存
    milvus_client.load_collection(COLLECTION_NAME)
    print(f'[Milvus索引已加载] 记录数: {actual_count}')

    # 初始化会话集合
    init_session_collection()

    # 加载全量文本用于关键词检索
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        all_chunks_texts = [c['text'] for c in data['chunks']]
        all_chunks_sources = [c['source'] for c in data['chunks']]
    else:
        # 从Milvus中加载所有文本
        try:
            all_data = milvus_client.query(
                COLLECTION_NAME,
                output_fields=['text', 'source'],
                limit=100000
            )
            all_chunks_texts = [d['text'] for d in all_data if d.get('text', '').strip()]
            all_chunks_sources = [d.get('source', 'unknown') for d in all_data if d.get('text', '').strip()]
        except Exception as e:
            print(f'[警告] 无法从Milvus加载文本: {e}')
            all_chunks_texts = []
            all_chunks_sources = []

    print(f'[关键词检索就绪] {len(all_chunks_texts)} 个文本块')

def create_milvus_index():
    """从头构建Milvus索引（从PDF读取）"""
    global milvus_client, all_chunks_texts, all_chunks_sources

    client = milvus_client
    if client.has_collection(COLLECTION_NAME):
        client.drop_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        dimension=384,
        auto_id=True,
        enable_dynamic_field=True,
        metric_type="IP",
        index_params={"index_type": "IVF_FLAT", "params": {"nlist": 128}}
    )

    # 读取PDF并分块
    all_chunks = []
    for pdf_path in PDFS:
        if os.path.exists(pdf_path):
            doc = fitz.open(pdf_path)
            pages = [p.get_text().strip() for p in doc if p.get_text().strip()]
            doc.close()
            text = '\n\n'.join(pages)
            chunks = chunk_text_improved(text)
            fname = os.path.basename(pdf_path)
            for i, chunk in enumerate(chunks):
                all_chunks.append({'source': fname, 'chunk_id': i, 'text': chunk})
            print(f'  读取: {fname} -> {len(chunks)} 块')

    if not all_chunks:
        print('[错误] 没有读取到任何文本')
        return

    # 分批插入
    texts = [c['text'] for c in all_chunks]
    BATCH_SIZE = 50
    for i in range(0, len(texts), BATCH_SIZE):
        end = min(i + BATCH_SIZE, len(texts))
        batch_texts = texts[i:end]
        batch_chunks = all_chunks[i:end]
        embeddings = ef(batch_texts)
        data_to_insert = []
        for j, emb in enumerate(embeddings):
            data_to_insert.append({
                'vector': emb,
                'text': batch_chunks[j]['text'],
                'source': batch_chunks[j]['source'],
                'chunk_id': batch_chunks[j]['chunk_id']
            })
        client.insert(COLLECTION_NAME, data_to_insert)
        print(f'  索引进度: {end}/{len(texts)} ({100*end//len(texts)}%)')

    # 保存index_data.json
    index_data = {
        'chunks': [{'source': c['source'], 'chunk_id': c['chunk_id'], 'text': c['text']} for c in all_chunks],
        'total': len(all_chunks),
        'pdfs': PDFS
    }
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False)

    # 更新全局关键词列表
    all_chunks_texts = [c['text'] for c in all_chunks]
    all_chunks_sources = [c['source'] for c in all_chunks]

    print(f'[索引构建完成] {len(all_chunks)} 块')

# ── 生命周期 ──

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_or_build_index()
    yield

# ── FastAPI ──
app = FastAPI(title='RAG工单3 - 智能问答系统 (Milvus)', lifespan=lifespan)

template_dir = os.path.join(BASE_DIR, 'templates')
os.makedirs(template_dir, exist_ok=True)
templates = Jinja2Templates(directory=template_dir)

# ── 路由 ──

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    html_path = os.path.join(template_dir, 'index.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return HTMLResponse(content=content)

@app.get('/api/health')
async def health():
    count = 0
    try:
        cnt = milvus_client.query(COLLECTION_NAME, output_fields=['count(*)'])
        count = cnt[0]['count(*)'] if cnt else 0
    except:
        pass
    return {
        'status': 'ok',
        'uptime': time.time() - start_time,
        'chunks': count,
        'version': '3.0-milvus'
    }

# ── 会话路由 ──

@app.post('/api/session/new')
async def session_new(data: dict = {}):
    title = data.get('title', '新对话')
    sess = create_session(title)
    return {'status': 'ok', 'session': sess}

@app.get('/api/session/list')
async def session_list():
    sessions = list_sessions()
    # 格式化输出
    result = []
    for s in sessions:
        result.append({
            'session_id': s.get('session_id', ''),
            'title': s.get('title', '新对话'),
            'created_at': s.get('created_at', 0),
            'updated_at': s.get('updated_at', 0)
        })
    return {'status': 'ok', 'sessions': result}

@app.post('/api/session/get')
async def session_get(data: dict):
    session_id = data.get('session_id', '')
    if not session_id:
        raise HTTPException(status_code=400, detail='缺少session_id')
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail='会话不存在')
    messages = json.loads(sess.get('messages', '[]'))
    return {
        'status': 'ok',
        'session': {
            'session_id': sess.get('session_id', ''),
            'title': sess.get('title', '新对话'),
            'messages': messages,
            'created_at': sess.get('created_at', 0),
            'updated_at': sess.get('updated_at', 0)
        }
    }

@app.post('/api/session/delete')
async def session_delete_api(data: dict):
    session_id = data.get('session_id', '')
    if not session_id:
        raise HTTPException(status_code=400, detail='缺少session_id')
    delete_session(session_id)
    return {'status': 'ok', 'message': '会话已删除'}

@app.post('/api/session/clear')
async def session_clear():
    """清空所有会话"""
    sessions = list_sessions(limit=10000)
    for s in sessions:
        sid = s.get('session_id', '')
        if sid:
            delete_session(sid)
    return {'status': 'ok', 'message': '所有会话已清空'}

# ── 聊天路由 ──

@app.post('/api/chat/stream')
async def chat_stream(data: dict):
    """SSE流式聊天接口"""
    query = data.get('query', '').strip()
    history = data.get('history', [])
    session_id = data.get('session_id', None)

    if not query:
        raise HTTPException(status_code=400, detail='请输入问题')

    lang = detect_language(query)

    # 检索
    t0 = time.time()
    retrieved = hybrid_retrieve(query)
    retrieve_time = time.time() - t0

    # 评分分析
    relevance_pct = 0.0
    if retrieved:
        matched_keywords = extract_keywords(query)
        if matched_keywords:
            match_count = 0
            for r in retrieved:
                if any(kw in r['text'] for kw in matched_keywords):
                    match_count += 1
            relevance_pct = round(match_count / len(retrieved) * 100, 1)

    # 构建上下文
    messages = build_prompt(query, retrieved, lang)

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
        # 发送检索元数据
        meta = {
            'type': 'meta',
            'retrieve_time': round(retrieve_time, 3),
            'num_chunks': len(retrieved),
            'relevance_pct': relevance_pct,
            'has_context': len(retrieved) > 0,
            'language': lang
        }
        yield f'data: {json.dumps(meta, ensure_ascii=False)}\n\n'

        # 发送检索到的参考块
        if retrieved:
            chunks_data = []
            for i, r in enumerate(retrieved[:5], 1):
                chunks_data.append({
                    'index': i,
                    'source': r['source'],
                    'score': round(r['score'], 3),
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

        total_time = time.time() - t1

        # 保存会话消息
        if session_id:
            sess = get_session(session_id)
            if sess:
                try:
                    sess_messages = json.loads(sess.get('messages', '[]'))
                except:
                    sess_messages = []
                sess_messages.append({'role': 'user', 'content': query})
                sess_messages.append({'role': 'assistant', 'content': full_text})
                if len(sess_messages) > MAX_HISTORY * 2:
                    sess_messages = sess_messages[-(MAX_HISTORY * 2):]
                update_session_messages(session_id, sess_messages)

        # 完成信号
        done = {
            'type': 'done',
            'total_time': round(total_time, 3),
            'total_chars': len(full_text),
            'full_text': full_text
        }
        yield f'data: {json.dumps(done, ensure_ascii=False)}\n\n'

    return StreamingResponse(event_stream(), media_type='text/event-stream')

@app.post('/api/chat')
async def chat(data: dict):
    """非流式聊天接口"""
    query = data.get('query', '').strip()

    if not query:
        raise HTTPException(status_code=400, detail='请输入问题')

    lang = detect_language(query)

    t0 = time.time()
    retrieved = hybrid_retrieve(query)
    retrieve_time = time.time() - t0

    messages = build_prompt(query, retrieved, lang)

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
        'chunks': [{'text': r['text'][:300], 'source': r['source'], 'score': round(r['score'], 3)} for r in retrieved[:5]]
    }

@app.post('/api/evaluate')
async def evaluate(data: dict):
    """评估：批量测试问题并返回精度"""
    questions = data.get('questions', [])

    if not questions:
        raise HTTPException(status_code=400, detail='请提供测试问题列表')

    results = []
    total_retrieve_time = 0
    total_llm_time = 0
    total_answers = 0
    accuracy_count = 0

    for q in questions:
        qid = q.get('id', '?')
        question = q.get('question', '')

        print(f'[评估] Q{qid}: {question[:50]}...')

        lang = detect_language(question)

        t0 = time.time()
        retrieved = hybrid_retrieve(question)
        retrieve_time = time.time() - t0

        messages = build_prompt(question, retrieved, lang)

        t1 = time.time()
        answer = non_stream_deepseek(messages)
        llm_time = time.time() - t1

        total_retrieve_time += retrieve_time
        total_llm_time += llm_time
        total_answers += 1

        # 计算检索精度
        expected_keywords = extract_keywords(question)
        if expected_keywords and retrieved:
            match_count = sum(1 for kw in expected_keywords if any(kw in r['text'] for r in retrieved))
            precision = match_count / len(expected_keywords) * 100
        else:
            precision = 100.0 if expected_keywords else 50.0

        if precision >= 70:
            accuracy_count += 1

        results.append({
            'id': qid,
            'question': question,
            'answer': answer,
            'retrieve_time': round(retrieve_time, 3),
            'llm_time': round(llm_time, 3),
            'total_time': round(retrieve_time + llm_time, 3),
            'num_chunks': len(retrieved),
            'precision_pct': round(precision, 1),
            'language': lang,
            'chunks_preview': [r['text'][:150] for r in retrieved[:3]]
        })

    avg_retrieve = round(total_retrieve_time / max(total_answers, 1), 3)
    avg_llm = round(total_llm_time / max(total_answers, 1), 3)
    overall_precision = round(accuracy_count / max(total_answers, 1) * 100, 1)

    return {
        'total_questions': total_answers,
        'accuracy_pct': overall_precision,
        'avg_retrieve_time': avg_retrieve,
        'avg_llm_time': avg_llm,
        'avg_total_time': round(avg_retrieve + avg_llm, 3),
        'results': results
    }

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8503)
