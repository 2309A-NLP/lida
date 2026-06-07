"""
工单编号：人工智能NLP-RAG-Query理解优化任务
RAG工单5 - 多轮对话智能问答系统（Milvus存储，含会话持久化）
基于双PDF招股说明书知识库，支持多轮对话、会话管理、混合检索、SSE流式回答

核心架构：
  1. 前端 -> SSE流式 -> FastAPI后端 -> DeepSeek API
  2. 双路检索：Milvus向量检索(IP余弦相似度) + jieba关键词检索
  3. 会话持久化：Milvus Lite文件数据库（不依赖外部服务）
  4. 数据存储：索引构建时一次写入，运行时只读检索 + 会话读写

v5.1 新增功能：
  - 双语互查：中文问题自动翻译成英文检索，英文问题翻译成中文检索
  - RAG评估指标：每条回答显示精确率、召回率、F1分数
  - 参考块展示：显示引用段落的来源文件、页码、文本摘要
  - 会话搜索：按关键字搜索历史对话
  - RAG vs 纯LLM对比
"""
import os, json, re, time, uuid, asyncio
from typing import AsyncGenerator
from contextlib import asynccontextmanager

import fitz          # PyMuPDF：PDF文本提取
import jieba         # 中文分词，用于关键词检索和停用词过滤
import requests      # 调用DeepSeek API的HTTP客户端
from pymilvus import MilvusClient, DataType  # Milvus Lite：嵌入式向量数据库
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2  # 本地ONNX嵌入模型（384维）

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn      # ASGI服务器

# ── 配置 ──
# 项目文件路径：知识库PDF、Milvus数据库目录、关键词索引JSON
BASE_DIR = '/mnt/d/RAG工单/RAG工单5'
MILVUS_PATH = os.path.join(BASE_DIR, 'milvus_data_5.db')
INDEX_PATH = os.path.join(BASE_DIR, 'index_data_5.json')
COLLECTION_NAME = 'rag_v5_milvus'
SESSIONS_COLLECTION = 'rag_v5_sessions'
EMBED_DIM = 384

# DeepSeek API
API_KEY = 'sk-171f528187724a14a74acc98e756c1c1'
API_URL = 'https://api.deepseek.com/v1/chat/completions'

# 检索参数
MAX_SESSION_MESSAGES = 50
MAX_SESSIONS = 100
TOP_K_EMBEDDING = 20
TOP_K_KEYWORD = 5
TOP_K_FINAL = 7

# LLM生成参数
MAX_TOKENS = 2048
TEMPERATURE = 0.1
SESSION_EXPIRE_SECONDS = 3600 * 24 * 7

jieba.setLogLevel(20)

# 停用词表
stopwords = set()
STOP_WORDS_STR = '什么 怎么 哪些 这个 那个 一个 可以 没有 我们 他们 你们 自己 如何 为什么 相关 涉及 情况 的 了 是 在 和 与 或 及 对 为 等 之 其 该 被 把 从 到 向 用 且 以 还 也 但 而 更 已 将 不 很 都 会 能 就 因 如 若 虽 然 只 要 让 吗 呢 呀 哦 嗯 啊 哈'
stopwords.update(STOP_WORDS_STR.split())

embed_fn = ONNXMiniLM_L6_V2()

# ── FastAPI ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_or_build_index()
    asyncio.create_task(cleanup_expired_sessions_loop())
    yield
    global milvus_client
    if milvus_client:
        try:
            _flush_sessions()
            milvus_client.close()
        except Exception:
            pass
        print('[Milvus已关闭，数据已刷盘]')

app = FastAPI(title='RAG工单5 - 多轮对话智能问答系统 (Milvus)', lifespan=lifespan)

template_dir = os.path.join(BASE_DIR, 'templates')
os.makedirs(template_dir, exist_ok=True)

# ── 全局状态 ──
milvus_client = None
all_chunks_texts = []        # 全量文本块列表，用于关键词检索
all_chunks_meta = []         # 全量文本块元数据（含source, page），用于参考展示
start_time = time.time()

# ── 翻译服务（使用DeepSeek API） ──
TRANSLATE_SYSTEM = {
    'zh2en': 'You are a translator. Translate the following Chinese text to English. Return ONLY the translated text, nothing else.',
    'en2zh': 'You are a translator. Translate the following English text to Chinese. Return ONLY the translated text, nothing else.',
}

def translate_text(text: str, direction: str) -> str:
    """使用DeepSeek API进行中英互译"""
    if direction not in TRANSLATE_SYSTEM:
        return text
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': 'deepseek-v4-flash',
        'messages': [
            {'role': 'system', 'content': TRANSLATE_SYSTEM[direction]},
            {'role': 'user', 'content': text}
        ],
        'temperature': 0.1,
        'max_tokens': 1024
    }
    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=15)
        return resp.json()['choices'][0]['message']['content'].strip()
    except Exception:
        return text

# ── RAG评估指标计算 ──
def compute_metrics(retrieved: list, query: str) -> dict:
    """计算检索质量指标：精确率、召回率、F1分数
    
    基于查询关键词在检索结果中的覆盖情况估算：
    - 精确率(Precision)：检索到的结果中，与查询相关的比例（含至少1个关键词）
    - 召回率(Recall)：查询中的关键词，被检索结果覆盖的比例
    - F1分数：精确率和召回率的调和平均值
    """
    keywords = extract_keywords(query)
    if not keywords or not retrieved:
        return {"precision": 0, "recall": 0, "f1": 0, "keyword_coverage": 0, "total_keywords": len(keywords) if keywords else 0}
    
    # 精确率：检索到的块中，含至少一个关键词的比例
    relevant_retrieved = sum(1 for r in retrieved if any(kw in r['text'] for kw in keywords))
    precision = relevant_retrieved / len(retrieved) if retrieved else 0
    
    # 召回率：查询关键词中被检索结果覆盖的比例
    covered_kws = set()
    for r in retrieved:
        for kw in keywords:
            if kw in r['text']:
                covered_kws.add(kw)
    recall = len(covered_kws) / len(keywords) if keywords else 0
    
    # F1
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "keyword_coverage": len(covered_kws),
        "total_keywords": len(keywords)
    }

# ── 会话管理（Milvus持久化） ──

def generate_session_id() -> str:
    return uuid.uuid4().hex[:16]

def _init_sessions_collection():
    global milvus_client
    if not milvus_client.has_collection(SESSIONS_COLLECTION):
        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field(field_name="session_id", datatype=DataType.VARCHAR, max_length=64, is_primary=True)
        schema.add_field(field_name="messages", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="created", datatype=DataType.FLOAT)
        schema.add_field(field_name="updated", datatype=DataType.FLOAT)
        schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=200)
        schema.add_field(field_name="_dummy_vec", datatype=DataType.FLOAT_VECTOR, dim=1)
        index_params = milvus_client.prepare_index_params()
        index_params.add_index(field_name="_dummy_vec", index_type="FLAT", metric_type="L2")
        milvus_client.create_collection(
            collection_name=SESSIONS_COLLECTION,
            schema=schema,
            index_params=index_params,
        )
        milvus_client.load_collection(SESSIONS_COLLECTION)
        print(f'[会话集合已创建] {SESSIONS_COLLECTION}')
    else:
        milvus_client.load_collection(SESSIONS_COLLECTION)
        print(f'[会话集合已存在] {SESSIONS_COLLECTION}')

def _session_to_entity(sid: str, messages: list, created: float = None, updated: float = None,
                       title: str = '') -> dict:
    return {
        'session_id': sid,
        'messages': json.dumps(messages[-MAX_SESSION_MESSAGES:] if len(messages) > MAX_SESSION_MESSAGES else messages, ensure_ascii=False),
        'created': created or time.time(),
        'updated': updated or time.time(),
        'title': title,
        '_dummy_vec': [0.0],
    }

def _flush_sessions():
    global milvus_client
    try:
        milvus_client.flush(collection_name=SESSIONS_COLLECTION)
        milvus_client.load_collection(SESSIONS_COLLECTION)
    except Exception:
        pass

def get_or_create_session(session_id: str = None) -> tuple:
    global milvus_client
    if session_id:
        res = milvus_client.get(
            collection_name=SESSIONS_COLLECTION,
            ids=[session_id],
        )
        if res:
            entity = res[0]
            messages = json.loads(entity.get('messages', '[]'))
            now = time.time()
            milvus_client.upsert(
                collection_name=SESSIONS_COLLECTION,
                data=[_session_to_entity(
                    session_id, messages,
                    created=entity.get('created', now),
                    updated=now,
                    title=entity.get('title', ''),
                )]
            )
            _flush_sessions()
            return session_id, messages
    new_id = session_id if session_id else generate_session_id()
    now = time.time()
    milvus_client.insert(
        collection_name=SESSIONS_COLLECTION,
        data=[_session_to_entity(new_id, [], created=now, updated=now)]
    )
    _flush_sessions()
    return new_id, []

def cleanup_expired_sessions():
    global milvus_client
    now = time.time()
    cutoff = now - SESSION_EXPIRE_SECONDS
    try:
        res = milvus_client.query(
            collection_name=SESSIONS_COLLECTION,
            filter=f'updated < {cutoff}',
            output_fields=['session_id'],
            limit=10000,
        )
        expired_ids = [r['session_id'] for r in res if 'session_id' in r]
        if expired_ids:
            milvus_client.delete(
                collection_name=SESSIONS_COLLECTION,
                ids=expired_ids,
            )
            print(f'[会话清理] 删除 {len(expired_ids)} 个过期会话')
        count_res = milvus_client.query(
            collection_name=SESSIONS_COLLECTION,
            output_fields=['session_id'],
            limit=10000,
        )
        total = len(count_res)
        if total > MAX_SESSIONS:
            all_sessions = milvus_client.query(
                collection_name=SESSIONS_COLLECTION,
                output_fields=['session_id', 'updated'],
                limit=10000,
            )
            all_sessions.sort(key=lambda x: x.get('updated', 0))
            to_delete = [s['session_id'] for s in all_sessions[:total - MAX_SESSIONS]]
            if to_delete:
                milvus_client.delete(
                    collection_name=SESSIONS_COLLECTION,
                    ids=to_delete,
                )
                print(f'[会话清理] 超量删除 {len(to_delete)} 个最旧会话')
        _flush_sessions()
    except Exception as e:
        print(f'[会话清理错误] {e}')

async def cleanup_expired_sessions_loop():
    while True:
        await asyncio.sleep(3600)
        cleanup_expired_sessions()

def save_session_messages(sid: str, messages: list):
    global milvus_client
    if not sid:
        return
    now = time.time()
    title = ''
    created = None
    res = milvus_client.get(
        collection_name=SESSIONS_COLLECTION,
        ids=[sid],
    )
    if res:
        title = res[0].get('title', '')
        created = res[0].get('created', None)
    if not title:
        for m in messages:
            if m['role'] == 'user':
                title = m['content'][:40] + ('...' if len(m['content']) > 40 else '')
                break
    milvus_client.upsert(
        collection_name=SESSIONS_COLLECTION,
        data=[_session_to_entity(sid, messages, created=created, updated=now, title=title)]
    )
    _flush_sessions()

# ── 语言检测 ──
def detect_language(text: str) -> str:
    return 'zh' if re.search(r'[\u4e00-\u9fff]', text) else 'en'

# ── 关键词提取（jieba分词 + 停用词过滤） ──
def extract_keywords(text: str, max_kw: int = 8) -> list:
    words = [w for w in jieba.lcut(text) if len(w) >= 2 and w not in stopwords]
    seen = set()
    result = []
    for w in sorted(words, key=lambda x: (len(x), text.count(x)), reverse=True):
        if w not in seen:
            seen.add(w)
            result.append(w)
    return result[:max_kw]

def deduplicate_chunks(chunks: list, max_results: int = TOP_K_FINAL) -> list:
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

# ── Milvus 混合检索（向量 + 关键词双路召回） ──
def hybrid_retrieve(query: str) -> list:
    """混合检索：向量检索 + 关键词检索，返回带元数据的块"""
    global milvus_client, all_chunks_texts, all_chunks_meta
    
    results = {}
    
    # 1) Milvus 向量检索
    try:
        query_vec = embed_fn([query])[0]
        qv = query_vec.tolist() if hasattr(query_vec, 'tolist') else query_vec
        
        search_res = milvus_client.search(
            collection_name=COLLECTION_NAME,
            data=[qv],
            anns_field="vector",
            search_params={"metric_type": "IP", "params": {"nprobe": 10}},
            limit=TOP_K_EMBEDDING,
            output_fields=["text", "source", "page", "type"],
        )
        
        if search_res and search_res[0]:
            for hit in search_res[0]:
                t = hit['entity']['text']
                score = hit['distance']
                if t.strip() and t not in results:
                    results[t] = {
                        'text': t,
                        'source': 'vector',
                        'score': score,
                        'kw_matches': 0,
                        'source_file': hit['entity'].get('source', ''),
                        'page': hit['entity'].get('page', 0),
                        'type': 'text',
                    }
    except Exception as e:
        print(f'[检索错误] Milvus: {e}')
    
    # 2) 关键词检索
    keywords = extract_keywords(query)
    if keywords and all_chunks_texts:
        for i, chunk_text in enumerate(all_chunks_texts):
            if chunk_text in results:
                continue
            matched = [kw for kw in keywords if kw in chunk_text]
            if matched:
                kw_score = len(matched) / max(len(keywords), 1)
                meta = all_chunks_meta[i] if i < len(all_chunks_meta) else {}
                results[chunk_text] = {
                    'text': chunk_text,
                    'source': 'keyword',
                    'score': 0.3 + kw_score * 0.4,
                    'kw_matches': len(matched),
                    'source_file': meta.get('source', ''),
                    'page': meta.get('page', 0),
                    'type': 'text',
                }
    
    # 3) 综合评分
    scored = list(results.values())
    for item in scored:
        kw_bonus = item['kw_matches'] * 0.05
        item['score'] = min(item['score'] + kw_bonus, 1.0)
    
    scored.sort(key=lambda x: x['score'], reverse=True)
    scored = deduplicate_chunks(scored, max_results=TOP_K_FINAL)
    return scored

# ── 构建提示词（含多轮历史 + 检索上下文） ──
def build_prompt(query: str, retrieved: list, lang: str, history: list = None) -> list:
    system_prompts = {
        'zh': (
            '你是一个专业的智能问答助手，基于招股说明书回答用户的问题。\n'
            '规则：\n'
            '1. 必须优先使用参考资料中的内容回答问题\n'
            '2. 如果参考资料信息充足，直接给出准确答案，引用具体数据\n'
            '3. 如果参考资料信息不足，诚实告知并补充自己的知识\n'
            '4. 答案要清晰、简洁、结构化\n'
            '5. 涉及金额、股数、比例等数据时给出具体数字\n'
            '6. 这是多轮对话，注意理解代词（"他"、"这个公司"、"那家公司"等）在前文中的指代\n'
            '7. 如果用户问"那XX呢"或类似的省略问题，结合历史对话理解完整意图'
        ),
        'en': (
            'You are a professional Q&A assistant for a prospectus. This is a multi-turn conversation.\n'
            'Rules:\n'
            '1. Use reference material first\n'
            '2. Understand pronouns like "he", "they", "that company" from context\n'
            '3. Give direct, data-rich answers\n'
            '4. Include specific numbers when available'
        )
    }
    
    messages = [{'role': 'system', 'content': system_prompts.get(lang, system_prompts['zh'])}]
    
    if history:
        for h in history[-10:]:
            role = h.get('role', 'user')
            content = h.get('content', '')
            if content.strip():
                messages.append({'role': role, 'content': content})
    
    if retrieved:
        ctx_texts = []
        for i, r in enumerate(retrieved, 1):
            source_tag = f'[来源: {r["source"]}]' if r['source'] != 'keyword' else ''
            ref_info = f'[文档: {r.get("source_file", "N/A")}] [页码: {r.get("page", "N/A")}]'
            ctx_texts.append(f'【参考{i}】{source_tag} {ref_info}\n{r["text"]}')
        
        context = '\n\n'.join(ctx_texts)
        if lang == 'zh':
            messages.append({'role': 'user', 'content': f'以下是与问题相关的参考资料：\n\n{context[:12000]}\n\n请基于以上资料回答：{query}'})
        else:
            messages.append({'role': 'user', 'content': f'Reference material:\n\n{context[:12000]}\n\nBased on the above, answer: {query}'})
    else:
        messages.append({'role': 'user', 'content': query})
    
    return messages

# ── DeepSeek API 流式调用 ──
async def stream_deepseek(messages: list) -> AsyncGenerator[str, None]:
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': 'deepseek-v4-flash',
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
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': 'deepseek-v4-flash',
        'messages': messages,
        'temperature': TEMPERATURE,
        'max_tokens': MAX_TOKENS
    }
    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=60)
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return f'抱歉，请求出错: {str(e)[:80]}'

# ── 索引加载 / 初始化 ──
def load_or_build_index():
    global milvus_client, all_chunks_texts, all_chunks_meta
    
    milvus_client = MilvusClient(MILVUS_PATH)
    
    if milvus_client.has_collection(COLLECTION_NAME):
        count_res = milvus_client.query(collection_name=COLLECTION_NAME, output_fields=["count(*)"], limit=1)
        count = count_res[0]['count(*)'] if count_res else 0
        print(f'[Milvus索引已加载] {count} 条记录')
    else:
        print('[Milvus索引不存在，需要先运行 build_index_milvus.py]')
        schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=True)
        schema.add_field(field_name="id", datatype="INT64", is_primary=True)
        schema.add_field(field_name="vector", datatype="FLOAT_VECTOR", dim=EMBED_DIM)
        schema.add_field(field_name="text", datatype="VARCHAR", max_length=65535)
        schema.add_field(field_name="source", datatype="VARCHAR", max_length=100)
        schema.add_field(field_name="page", datatype=DataType.INT32)
        schema.add_field(field_name="type", datatype="VARCHAR", max_length=50)
        index_params = milvus_client.prepare_index_params()
        index_params.add_index(field_name="vector", index_type="IVF_FLAT", metric_type="IP", params={"nlist": 128})
        milvus_client.create_collection(collection_name=COLLECTION_NAME, schema=schema, index_params=index_params)
        print(f'  已创建空集合 {COLLECTION_NAME}')
    
    # 加载全量文本
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        all_chunks_texts = [c['text'] for c in data['chunks']]
        all_chunks_meta = [{'source': c.get('source', ''), 'page': c.get('page', 0)} for c in data['chunks']]
    else:
        try:
            results = milvus_client.query(
                collection_name=COLLECTION_NAME,
                output_fields=["text", "source", "page"],
                limit=10000,
            )
            all_chunks_texts = [r['text'] for r in results if 'text' in r]
            all_chunks_meta = [{'source': r.get('source', ''), 'page': r.get('page', 0)} for r in results]
        except:
            all_chunks_texts = []
            all_chunks_meta = []
    
    _init_sessions_collection()
    
    print(f'[检索就绪] 文本块: {len(all_chunks_texts)}, 向量库: Milvus, 会话持久化: Milvus')

# ============================================================
# API 路由
# ============================================================

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    html_path = os.path.join(template_dir, 'index.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return HTMLResponse(content=content, headers={
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
    })

@app.get('/api/health')
async def health():
    count = 0
    session_count = 0
    try:
        if milvus_client and milvus_client.has_collection(COLLECTION_NAME):
            cr = milvus_client.query(collection_name=COLLECTION_NAME, output_fields=["count(*)"], limit=1)
            count = cr[0]['count(*)'] if cr else 0
        if milvus_client and milvus_client.has_collection(SESSIONS_COLLECTION):
            sr = milvus_client.query(collection_name=SESSIONS_COLLECTION, output_fields=["session_id"], limit=10000)
            session_count = len(sr) if sr else 0
    except:
        pass
    return {
        'status': 'ok',
        'uptime': time.time() - start_time,
        'chunks': count,
        'active_sessions': session_count,
        'version': '5.1-milvus',
        'storage': 'milvus',
        'session_persistence': 'milvus',
        'features': 'bilingual_retrieval,metrics,references,search,compare',
        'work_order': '人工智能NLP-RAG-Query理解优化任务'
    }

@app.post('/api/session/new')
async def create_session():
    new_id = generate_session_id()
    return {'session_id': new_id, 'title': '新对话'}

@app.get('/api/session/list')
async def list_sessions():
    global milvus_client
    session_list = []
    try:
        res = milvus_client.query(
            collection_name=SESSIONS_COLLECTION,
            output_fields=['session_id', 'messages', 'created', 'updated', 'title'],
            limit=10000,
        )
        res.sort(key=lambda x: x.get('updated', 0), reverse=True)
        for entity in res[:50]:
            sid = entity.get('session_id', '')
            if not sid:
                continue
            messages = json.loads(entity.get('messages', '[]'))
            title = entity.get('title', '')
            if not title:
                for m in messages:
                    if m['role'] == 'user':
                        title = m['content'][:40] + ('...' if len(m['content']) > 40 else '')
                        break
            session_list.append({
                'id': sid,
                'title': title or '新对话',
                'message_count': len(messages),
                'created': entity.get('created', 0),
                'updated': entity.get('updated', 0),
            })
    except Exception as e:
        print(f'[会话列表错误] {e}')
    return {'sessions': session_list}

@app.post('/api/session/delete')
async def delete_session(data: dict):
    sid = data.get('session_id', '')
    if not sid:
        raise HTTPException(status_code=400, detail='缺少session_id')
    res = milvus_client.get(
        collection_name=SESSIONS_COLLECTION,
        ids=[sid],
    )
    if not res:
        raise HTTPException(status_code=404, detail='会话不存在')
    milvus_client.delete(
        collection_name=SESSIONS_COLLECTION,
        ids=[sid],
    )
    _flush_sessions()
    return {'status': 'ok'}

@app.post('/api/session/rename')
async def rename_session(data: dict):
    sid = data.get('session_id', '')
    title = data.get('title', '')
    if not sid or not title:
        return {'status': 'ok'}
    res = milvus_client.get(
        collection_name=SESSIONS_COLLECTION,
        ids=[sid],
    )
    if res:
        entity = res[0]
        messages = json.loads(entity.get('messages', '[]'))
        milvus_client.upsert(
            collection_name=SESSIONS_COLLECTION,
            data=[_session_to_entity(
                sid, messages,
                created=entity.get('created', time.time()),
                updated=time.time(),
                title=title,
            )]
        )
        _flush_sessions()
    return {'status': 'ok', 'title': title}

@app.get('/api/session/{session_id}/history')
async def get_session_history(session_id: str):
    global milvus_client
    res = milvus_client.get(
        collection_name=SESSIONS_COLLECTION,
        ids=[session_id],
    )
    if not res:
        return {'messages': []}
    entity = res[0]
    messages = json.loads(entity.get('messages', '[]'))
    return {'messages': messages}

@app.post('/api/session/{session_id}/clear')
async def clear_session_history(session_id: str):
    global milvus_client
    res = milvus_client.get(
        collection_name=SESSIONS_COLLECTION,
        ids=[session_id],
    )
    if res:
        entity = res[0]
        now = time.time()
        milvus_client.upsert(
            collection_name=SESSIONS_COLLECTION,
            data=[_session_to_entity(
                session_id, [],
                created=entity.get('created', now),
                updated=now,
                title='新对话',
            )]
        )
        _flush_sessions()
    return {'status': 'ok'}

@app.delete('/api/session/{session_id}')
async def delete_session_by_path(session_id: str):
    res = milvus_client.get(
        collection_name=SESSIONS_COLLECTION,
        ids=[session_id],
    )
    if not res:
        raise HTTPException(status_code=404, detail='会话不存在')
    milvus_client.delete(
        collection_name=SESSIONS_COLLECTION,
        ids=[session_id],
    )
    _flush_sessions()
    return {'status': 'ok'}

# ── 会话搜索（像DeepSeek那样检索历史对话） ──
@app.get('/api/session/search')
async def search_sessions(q: str = Query('', description='搜索关键词')):
    """搜索历史对话：按标题和消息内容匹配关键词"""
    if not q.strip():
        return {'results': []}
    
    q_lower = q.lower()
    try:
        res = milvus_client.query(
            collection_name=SESSIONS_COLLECTION,
            output_fields=['session_id', 'messages', 'created', 'updated', 'title'],
            limit=10000,
        )
    except:
        return {'results': []}
    
    results = []
    for entity in res:
        sid = entity.get('session_id', '')
        title = entity.get('title', '')
        messages = json.loads(entity.get('messages', '[]'))
        
        # 匹配标题
        title_match = q_lower in title.lower() if title else False
        
        # 匹配消息内容
        content_matches = []
        for m in messages:
            content = m.get('content', '')
            if q_lower in content.lower():
                content_matches.append({
                    'role': m.get('role', 'user'),
                    'content': content[:200] + ('...' if len(content) > 200 else ''),
                    'matched': True,
                })
        
        if title_match or content_matches:
            results.append({
                'id': sid,
                'title': title or '新对话',
                'message_count': len(messages),
                'created': entity.get('created', 0),
                'updated': entity.get('updated', 0),
                'title_matched': title_match,
                'matched_messages': content_matches[:3],  # 最多展示3条匹配
            })
    
    # 按匹配度排序：标题匹配 > 消息匹配数
    results.sort(key=lambda x: (x['title_matched'], len(x['matched_messages'])), reverse=True)
    
    return {'results': results[:20], 'query': q}

# ── 聊天接口（流式） ──
@app.post('/api/chat/stream')
async def chat_stream(data: dict):
    """流式聊天接口（SSE），支持双语互查、RAG评估指标、参考块展示
    
    SSE事件类型：
      - meta: 元数据（检索耗时、文档块数、session_id等）
      - token: 逐步生成的文本片段
      - done: 完成标志（含总耗时、总指标、参考块等）
    
    双语互查逻辑：
      - 中文问题 → 翻译成英文 → 用英文检索中文PDF文本 → 中文回答
      - 英文问题 → 翻译成中文 → 用中文检索PDF文本 → 英文回答
    """
    query = data.get('query', '').strip()
    session_id = data.get('session_id', '')
    
    if not query:
        raise HTTPException(status_code=400, detail='请输入问题')
    
    query_lang = detect_language(query)
    sid, history = get_or_create_session(session_id)
    
    t0 = time.time()
    
    # 双语互查：将问题翻译成另一种语言后检索，以获得更丰富的跨语言信息
    if query_lang == 'zh':
        translated_query = translate_text(query, 'zh2en')
    else:
        translated_query = translate_text(query, 'en2zh')
    
    # 用原语言和翻译语言分别检索，合并结果
    retrieved_orig = hybrid_retrieve(query)
    retrieved_trans = hybrid_retrieve(translated_query) if translated_query != query else []
    
    # 合并去重（按text去重）
    seen_texts = set(r['text'] for r in retrieved_orig)
    for r in retrieved_trans:
        if r['text'] not in seen_texts:
            seen_texts.add(r['text'])
            retrieved_orig.append(r)
    
    # 重新排序并截取前TOP_K_FINAL个
    retrieved_orig.sort(key=lambda x: x['score'], reverse=True)
    retrieved = retrieved_orig[:TOP_K_FINAL]
    
    retrieve_time = time.time() - t0
    
    # 计算评估指标
    metrics_data = compute_metrics(retrieved, query)
    
    # 构建参考块信息（用于前端展示）
    references = []
    for i, r in enumerate(retrieved, 1):
        references.append({
            'index': i,
            'score': round(r.get('score', 0), 3),
            'source': r.get('source', ''),
            'source_file': r.get('source_file', ''),
            'page': r.get('page', 0),
            'text_preview': r['text'][:150] + ('...' if len(r['text']) > 150 else ''),
        })
    
    messages = build_prompt(query, retrieved, query_lang, history)
    
    async def event_stream():
        meta = {
            'type': 'meta',
            'retrieve_time': round(retrieve_time, 3),
            'num_chunks': len(retrieved),
            'session_id': sid,
            'language': query_lang,
            'version': '5.1-milvus',
            'persistence': 'milvus',
            'translated_query': translated_query,
        }
        yield f'data: {json.dumps(meta, ensure_ascii=False)}\n\n'
        
        t1 = time.time()
        full_text = ''
        try:
            async for delta in stream_deepseek(messages):
                full_text += delta
                yield f'data: {json.dumps({"type": "token", "content": delta}, ensure_ascii=False)}\n\n'
        except Exception:
            fallback = non_stream_deepseek(messages)
            yield f'data: {json.dumps({"type": "token", "content": fallback}, ensure_ascii=False)}\n\n'
            full_text = fallback
        
        total_time = time.time() - t1
        
        if query and full_text:
            history.append({'role': 'user', 'content': query})
            history.append({'role': 'assistant', 'content': full_text})
            save_session_messages(sid, history)
        
        done = {
            'type': 'done',
            'total_time': round(total_time, 3),
            'total_chars': len(full_text),
            'full_text': full_text,
            'metrics': metrics_data,
            'references': references,
        }
        yield f'data: {json.dumps(done, ensure_ascii=False)}\n\n'
    
    return StreamingResponse(event_stream(), media_type='text/event-stream')

# ── 聊天接口（非流式） ──
@app.post('/api/chat')
async def chat(data: dict):
    """非流式聊天接口，含双语互查、评估指标、参考块展示"""
    query = data.get('query', '').strip()
    session_id = data.get('session_id', '')
    
    if not query:
        raise HTTPException(status_code=400, detail='请输入问题')
    
    query_lang = detect_language(query)
    sid, history = get_or_create_session(session_id)
    
    t0 = time.time()
    
    # 双语互查
    if query_lang == 'zh':
        translated_query = translate_text(query, 'zh2en')
    else:
        translated_query = translate_text(query, 'en2zh')
    
    retrieved_orig = hybrid_retrieve(query)
    retrieved_trans = hybrid_retrieve(translated_query) if translated_query != query else []
    
    seen_texts = set(r['text'] for r in retrieved_orig)
    for r in retrieved_trans:
        if r['text'] not in seen_texts:
            seen_texts.add(r['text'])
            retrieved_orig.append(r)
    
    retrieved_orig.sort(key=lambda x: x['score'], reverse=True)
    retrieved = retrieved_orig[:TOP_K_FINAL]
    
    retrieve_time = time.time() - t0
    
    # 评估指标
    metrics_data = compute_metrics(retrieved, query)
    
    # 参考块信息
    references = []
    for i, r in enumerate(retrieved, 1):
        references.append({
            'index': i,
            'score': round(r.get('score', 0), 3),
            'source': r.get('source', ''),
            'source_file': r.get('source_file', ''),
            'page': r.get('page', 0),
            'text_preview': r['text'][:150] + ('...' if len(r['text']) > 150 else ''),
        })
    
    messages = build_prompt(query, retrieved, query_lang, history)
    
    t1 = time.time()
    answer = non_stream_deepseek(messages)
    llm_time = time.time() - t1
    
    if query and answer:
        history.append({'role': 'user', 'content': query})
        history.append({'role': 'assistant', 'content': answer})
        save_session_messages(sid, history)
    
    return {
        'query': query,
        'answer': answer,
        'language': query_lang,
        'translated_query': translated_query,
        'retrieve_time': round(retrieve_time, 3),
        'llm_time': round(llm_time, 3),
        'total_time': round(retrieve_time + llm_time, 3),
        'num_chunks': len(retrieved),
        'has_context': len(retrieved) > 0,
        'session_id': sid,
        'persistence': 'milvus',
        'metrics': metrics_data,
        'references': references,
    }

# ── RAG vs 纯LLM对比接口 ──
@app.post('/api/chat/compare')
async def chat_compare(data: dict):
    """同时返回RAG回答和纯LLM回答，方便对比效果"""
    query = data.get('query', '').strip()
    session_id = data.get('session_id', '')
    
    if not query:
        raise HTTPException(status_code=400, detail='请输入问题')
    
    query_lang = detect_language(query)
    sid, history = get_or_create_session(session_id)
    
    # === RAG检索 ===
    t0 = time.time()
    
    if query_lang == 'zh':
        translated_query = translate_text(query, 'zh2en')
    else:
        translated_query = translate_text(query, 'en2zh')
    
    retrieved_orig = hybrid_retrieve(query)
    retrieved_trans = hybrid_retrieve(translated_query) if translated_query != query else []
    
    seen_texts = set(r['text'] for r in retrieved_orig)
    for r in retrieved_trans:
        if r['text'] not in seen_texts:
            seen_texts.add(r['text'])
            retrieved_orig.append(r)
    
    retrieved_orig.sort(key=lambda x: x['score'], reverse=True)
    retrieved = retrieved_orig[:TOP_K_FINAL]
    
    retrieve_time = time.time() - t0
    rag_messages = build_prompt(query, retrieved, query_lang, history)
    metrics_data = compute_metrics(retrieved, query)
    
    references = []
    for i, r in enumerate(retrieved, 1):
        references.append({
            'index': i,
            'score': round(r.get('score', 0), 3),
            'source': r.get('source', ''),
            'source_file': r.get('source_file', ''),
            'page': r.get('page', 0),
            'text_preview': r['text'][:150] + ('...' if len(r['text']) > 150 else ''),
        })
    
    # === 纯LLM回答（无检索上下文） ===
    pure_messages = [{'role': 'system', 'content': '你是一个专业的智能问答助手。请直接回答用户的问题。'}]
    if history:
        for h in history[-10:]:
            role = h.get('role', 'user')
            content = h.get('content', '')
            if content.strip():
                pure_messages.append({'role': role, 'content': content})
    pure_messages.append({'role': 'user', 'content': query})
    
    t1 = time.time()
    rag_answer = non_stream_deepseek(rag_messages)
    rag_time = time.time() - t1
    
    t2 = time.time()
    pure_answer = non_stream_deepseek(pure_messages)
    pure_time = time.time() - t2
    
    # 保存RAG回答到会话（纯LLM回答不保存）
    if query and rag_answer:
        history.append({'role': 'user', 'content': query})
        history.append({'role': 'assistant', 'content': rag_answer + f'\n\n[注：此回答基于RAG检索，纯LLM回答见对比面板]'})
        save_session_messages(sid, history)
    
    return {
        'query': query,
        'rag': {
            'answer': rag_answer,
            'time': round(rag_time, 3),
            'retrieve_time': round(retrieve_time, 3),
            'total_time': round(retrieve_time + rag_time, 3),
            'num_chunks': len(retrieved),
            'metrics': metrics_data,
            'references': references,
            'translated_query': translated_query,
        },
        'pure_llm': {
            'answer': pure_answer,
            'time': round(pure_time, 3),
        },
        'language': query_lang,
        'session_id': sid,
    }

# ── 批量评估接口 ──
@app.post('/api/evaluate')
async def evaluate(data: dict):
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
        
        metrics_data = compute_metrics(retrieved, question)
        
        if metrics_data['f1'] >= 0.5:
            accuracy_count += 1
        
        results.append({
            'id': qid,
            'question': question,
            'answer': answer,
            'retrieve_time': round(retrieve_time, 3),
            'llm_time': round(llm_time, 3),
            'total_time': round(retrieve_time + llm_time, 3),
            'num_chunks': len(retrieved),
            'metrics': metrics_data,
            'language': lang,
        })
    
    avg_retrieve = round(total_retrieve_time / max(total_answers, 1), 3)
    avg_llm = round(total_llm_time / max(total_answers, 1), 3)
    overall_accuracy = round(accuracy_count / max(total_answers, 1) * 100, 1)
    
    return {
        'total_questions': total_answers,
        'accuracy_pct': overall_accuracy,
        'avg_retrieve_time': avg_retrieve,
        'avg_llm_time': avg_llm,
        'avg_total_time': round(avg_retrieve + avg_llm, 3),
        'results': results,
        'storage': 'milvus',
        'session_persistence': 'milvus',
    }

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8505)
