"""
RAG工单6 v3.0 - Milvus智能问答系统
三模型切换 + 策略对比 + 历史搜索 + RAGvsLLM对比 + 中英互查
"""
import os
os.environ.setdefault('DEEPSEEK_API_KEY', '')

import json, re, time, uuid, asyncio
from typing import AsyncGenerator, Optional

import jieba
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn

from pymilvus import MilvusClient, DataType
from retrieval_engine import RetrievalEngine, RETRIEVAL_STRATEGIES, EMBEDDING_MODELS, API_KEY

BASE_DIR = '/mnt/d/RAG工单/RAG工单6'
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
MILVUS_PATH = os.path.join(BASE_DIR, 'milvus_v6.db')
SESSIONS_COLLECTION = 'sessions_v6'

API_URL = 'https://api.deepseek.com/v1/chat/completions'

MAX_TOKENS = 2048
TEMPERATURE = 0.1
SESSION_EXPIRE_SECONDS = 3600 * 24 * 7
MAX_SESSION_MESSAGES = 50
MAX_SESSIONS = 100
FLUSH_INTERVAL = 60

jieba.setLogLevel(20)

engine = RetrievalEngine()

sessions_client = None
_last_flush = 0


def _should_flush():
    global _last_flush
    now = time.time()
    if now - _last_flush > FLUSH_INTERVAL:
        _last_flush = now
        return True
    return False


def init_sessions_collection():
    global sessions_client
    sessions_client = MilvusClient(MILVUS_PATH)
    if sessions_client.has_collection(SESSIONS_COLLECTION):
        sessions_client.load_collection(SESSIONS_COLLECTION)
        print(f'[会话集合已存在] {SESSIONS_COLLECTION}')
        return
    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=True)
    schema.add_field(field_name="session_id", datatype=DataType.VARCHAR, max_length=64, is_primary=True)
    schema.add_field(field_name="messages", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="created", datatype=DataType.FLOAT)
    schema.add_field(field_name="updated", datatype=DataType.FLOAT)
    schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=200)
    schema.add_field(field_name="_dummy_vec", datatype=DataType.FLOAT_VECTOR, dim=1)
    index_params = sessions_client.prepare_index_params()
    index_params.add_index(field_name="_dummy_vec", index_type="FLAT", metric_type="L2")
    sessions_client.create_collection(collection_name=SESSIONS_COLLECTION, schema=schema, index_params=index_params)
    sessions_client.load_collection(SESSIONS_COLLECTION)
    print(f'[会话集合已创建] {SESSIONS_COLLECTION}')


def _session_entity(sid: str, messages: list, created: float = None, updated: float = None, title: str = ''):
    return {
        'session_id': sid,
        'messages': json.dumps(messages[-MAX_SESSION_MESSAGES:] if len(messages) > MAX_SESSION_MESSAGES else messages,
                               ensure_ascii=False),
        'created': created or time.time(),
        'updated': updated or time.time(),
        'title': title or '',
        '_dummy_vec': [0.0],
    }


def get_or_create_session(session_id: str = None):
    global sessions_client
    if session_id:
        res = sessions_client.get(collection_name=SESSIONS_COLLECTION, ids=[session_id])
        if res:
            entity = res[0]
            messages = json.loads(entity.get('messages', '[]'))
            now = time.time()
            sessions_client.upsert(
                collection_name=SESSIONS_COLLECTION,
                data=[_session_entity(session_id, messages, created=entity.get('created', now), updated=now,
                                      title=entity.get('title', ''))]
            )
            if _should_flush():
                sessions_client.flush(SESSIONS_COLLECTION)
            return session_id, messages
    new_id = session_id if session_id else uuid.uuid4().hex[:16]
    now = time.time()
    sessions_client.insert(
        collection_name=SESSIONS_COLLECTION,
        data=[_session_entity(new_id, [], created=now, updated=now)]
    )
    if _should_flush():
        sessions_client.flush(SESSIONS_COLLECTION)
    return new_id, []


def save_session_messages(sid: str, messages: list):
    global sessions_client
    if not sid:
        return
    now = time.time()
    title = ''
    created = None
    res = sessions_client.get(collection_name=SESSIONS_COLLECTION, ids=[sid])
    if res:
        title = res[0].get('title', '')
        created = res[0].get('created', None)
    if not title:
        for m in messages:
            if m['role'] == 'user':
                title = m['content'][:40] + ('...' if len(m['content']) > 40 else '')
                break
    sessions_client.upsert(
        collection_name=SESSIONS_COLLECTION,
        data=[_session_entity(sid, messages, created=created, updated=now, title=title)]
    )
    if _should_flush():
        sessions_client.flush(SESSIONS_COLLECTION)


def list_all_sessions():
    global sessions_client
    res = sessions_client.query(
        collection_name=SESSIONS_COLLECTION,
        output_fields=['session_id', 'title', 'created', 'updated', 'messages'],
        limit=10000,
    )
    session_list = []
    for r in res:
        msgs = json.loads(r.get('messages', '[]'))
        title = r.get('title', '')
        if not title:
            for m in msgs:
                if m['role'] == 'user':
                    title = m['content'][:40] + ('...' if len(m['content']) > 40 else '')
                    break
        session_list.append({
            'id': r['session_id'],
            'title': title or '新对话',
            'message_count': len(msgs),
            'created': r.get('created', 0),
            'updated': r.get('updated', 0),
        })
    session_list.sort(key=lambda x: x.get('updated', 0), reverse=True)
    return {'sessions': session_list}


def search_sessions(query: str) -> list:
    """搜索历史对话内容"""
    global sessions_client
    res = sessions_client.query(
        collection_name=SESSIONS_COLLECTION,
        output_fields=['session_id', 'title', 'created', 'updated', 'messages'],
        limit=10000,
    )
    q_lower = query.lower()
    matches = []
    for r in res:
        msgs = json.loads(r.get('messages', '[]'))
        title = r.get('title', '')
        score = 0
        matched_msgs = []
        for m in msgs:
            content = m.get('content', '')
            if q_lower in content.lower():
                score += 1
                matched_msgs.append({
                    'role': m['role'],
                    'content': content[:200] + ('...' if len(content) > 200 else ''),
                    'matched': True,
                })
        if score > 0:
            matches.append({
                'id': r['session_id'],
                'title': title or '新对话',
                'score': score,
                'updated': r.get('updated', 0),
                'matched_messages': matched_msgs[:5],
            })
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches[:20]


def cleanup_expired_sessions():
    global sessions_client
    now = time.time()
    cutoff = now - SESSION_EXPIRE_SECONDS
    try:
        res = sessions_client.query(
            collection_name=SESSIONS_COLLECTION,
            filter=f'updated < {cutoff}',
            output_fields=['session_id'],
            limit=10000,
        )
        expired_ids = [r['session_id'] for r in res if 'session_id' in r]
        if expired_ids:
            sessions_client.delete(collection_name=SESSIONS_COLLECTION, ids=expired_ids)
            print(f'[会话清理] 删除 {len(expired_ids)} 个过期会话')
        sessions_client.flush(SESSIONS_COLLECTION)
    except Exception as e:
        print(f'[会话清理错误] {e}')


async def cleanup_loop():
    while True:
        await asyncio.sleep(3600)
        cleanup_expired_sessions()


def generate_session_id() -> str:
    return uuid.uuid4().hex[:16]


# FastAPI
app = FastAPI(title='RAG工单6 v3 - 检索策略优化系统')
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
os.makedirs(TEMPLATE_DIR, exist_ok=True)


@app.on_event('startup')
async def startup():
    engine.load()
    init_sessions_collection()
    asyncio.create_task(cleanup_loop())


# ── 工具函数 ──

def detect_language(text: str) -> str:
    return 'zh' if re.search(r'[\u4e00-\u9fff]', text) else 'en'


def translate_query(query: str) -> str:
    """中英互查：中文→英文关键词，英文→中文关键词"""
    lang = detect_language(query)
    if lang == 'zh':
        # 中文问题：把关键词翻译成英文，追加到查询
        zh_kw = extract_keywords_simple(query, max_kw=5)
        en_kw = []
        zh_to_en = {v: k for k, v in EN_TO_ZH.items() for v in v.split()}
        for kw in zh_kw:
            for zh_word, en_word in zh_to_en.items():
                if zh_word in kw or kw in zh_word:
                    en_kw.append(en_word)
                    break
        if en_kw:
            query += ' ' + ' '.join(set(en_kw))
    else:
        # 英文问题：补充中文翻译
        query += ' ' + ' '.join(EN_TO_ZH.values())
    return query


EN_TO_ZH_REV = {
    '营业收入': 'revenue', '收入': 'income', '利润': 'profit',
    '公司': 'company', '董事长': 'chairman', '法定代表人': 'CEO',
    '股份': 'share', '股票': 'stock', '技术': 'technology',
    '专利': 'patent', '风险': 'risk', '资产': 'asset',
    '产品': 'product', '业务': 'business', '客户': 'customer',
    '市场': 'market', '招股说明书': 'prospectus',
}

STOP_WORDS = set(
    '的 了 是 在 和 与 或 及 对 为 等 之 其 该 被 把 从 到 向 用 且 以 还 也 但 而 更 已 将 不 很 都 会 能 就 因 如 若 虽 然 只 要 让 吗 呢 呀 哦 嗯 啊 哈 什么 怎么 哪些 这个 那个 一个 可以 没有 我们 他们 你们 自己 如何 为什么 相关 涉及 情况'.split()
)


def extract_keywords_simple(text: str, max_kw: int = 8) -> list:
    words = [w for w in jieba.lcut(text) if len(w) >= 2 and w not in STOP_WORDS]
    seen = set()
    result = []
    for w in sorted(words, key=lambda x: (len(x), text.count(x)), reverse=True):
        if w not in seen:
            seen.add(w)
            result.append(w)
    return result[:max_kw]


def build_prompt(query: str, retrieved: list, lang: str, history: list = None, strategy: str = 'hybrid',
                 model_name: str = '') -> list:
    strategy_names = {
        'vector': '向量检索', 'fulltext': '全文检索', 'hybrid': '混合检索',
    }
    strategy_name = strategy_names.get(strategy, strategy)
    model_info = f' (模型: {model_name})' if model_name else ''

    system_prompts = {
        'zh': (
            f'你是一个专业的智能问答助手，基于招股说明书回答用户的问题。\n'
            f'当前检索策略：{strategy_name}{model_info}\n'
            f'规则：\n'
            f'1. 必须优先使用参考资料中的内容回答问题\n'
            f'2. 如果参考资料信息充足，直接给出准确答案，引用具体数据\n'
            f'3. 如果参考资料信息不足，诚实告知并补充自己的知识\n'
            f'4. 答案要清晰、简洁、结构化\n'
            f'5. 涉及金额、股数、比例等数据时给出具体数字\n'
            f'6. 这是多轮对话，注意理解代词在前文中的指代\n'
            f'7. 如果用户问省略问题，结合历史对话理解完整意图'
        ),
        'en': (
            f'You are a professional Q&A assistant for a prospectus. Current strategy: {strategy_name}{model_info}.\n'
            f'Rules:\n'
            f'1. Use reference material first\n'
            f'2. Provide direct, data-rich answers with specific numbers\n'
            f'3. This is a multi-turn conversation\n'
        ),
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
            source_tag = f'[{r.get("pdf", "?")} 第{r.get("page", "?")}页]'
            ctx_texts.append(f'【参考{i}】{source_tag}\n{r["text"]}')
        context = '\n\n'.join(ctx_texts)

        if lang == 'zh':
            messages.append({
                'role': 'user',
                'content': f'以下是与问题相关的参考资料（检索策略：{strategy_name}）：\n\n{context[:12000]}\n\n请基于以上资料回答：{query}'
            })
        else:
            messages.append({
                'role': 'user',
                'content': f'Reference material (strategy: {strategy_name}):\n\n{context[:12000]}\n\nBased on the above, answer: {query}'
            })
    else:
        messages.append({'role': 'user', 'content': query})

    return messages


def build_llm_only_prompt(query: str, lang: str, history: list = None) -> list:
    """纯LLM回答（无RAG）"""
    system_prompts = {
        'zh': '你是一个专业的智能问答助手。请直接回答用户的问题，如果你不确定，请诚实告知。',
        'en': 'You are a professional Q&A assistant. Answer the user\'s question directly. If you\'re unsure, be honest.',
    }
    messages = [{'role': 'system', 'content': system_prompts.get(lang, system_prompts['zh'])}]
    if history:
        for h in history[-10:]:
            role = h.get('role', 'user')
            content = h.get('content', '')
            if content.strip():
                messages.append({'role': role, 'content': content})
    messages.append({'role': 'user', 'content': query})
    return messages


async def stream_deepseek(messages: list) -> AsyncGenerator[str, None]:
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': 'deepseek-chat',
        'messages': messages,
        'temperature': TEMPERATURE,
        'max_tokens': MAX_TOKENS,
        'stream': True,
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
        'Content-Type': 'application/json',
    }
    payload = {
        'model': 'deepseek-chat',
        'messages': messages,
        'temperature': TEMPERATURE,
        'max_tokens': MAX_TOKENS,
    }
    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return f'抱歉，请求出错: {str(e)[:80]}'


# ─────────────────────────
# API 路由
# ─────────────────────────

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    html_path = os.path.join(TEMPLATE_DIR, 'index.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return HTMLResponse(content=content, headers={
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
    })


@app.get('/api/health')
async def health():
    return {
        'status': 'ok',
        'version': '6.3',
        'strategy': engine.strategy,
        'reranker': engine.reranker,
        'model': engine.embedding_model,
        'vector_count': engine.vector_count,
        'engine': 'milvus',
    }


# ── 策略配置 ──

@app.get('/api/strategies')
async def get_strategies():
    return {
        'strategies': RETRIEVAL_STRATEGIES,
        'current_strategy': engine.strategy,
        'embedding_models': EMBEDDING_MODELS,
        'current_model': engine.embedding_model,
        'rerankers': [
            {'id': 'llm', 'name': '基于LLM的重排器'},
            {'id': 'tfidf', 'name': '基于TF-IDF的重排器'},
            {'id': 'adaptive', 'name': '自适应重排器'},
        ],
        'current_reranker': engine.reranker,
        'config': {
            'vector_weight': engine.vector_weight,
            'fulltext_weight': engine.fulltext_weight,
            'top_k_recall': engine.top_k_recall,
            'top_k_final': engine.top_k_final,
        },
    }


@app.post('/api/strategies/set')
async def set_strategy(data: dict):
    strategy = data.get('strategy')
    if strategy and strategy in RETRIEVAL_STRATEGIES:
        engine.set_strategy(strategy)
        return {'status': 'ok', 'strategy': strategy, 'name': RETRIEVAL_STRATEGIES[strategy]['name']}
    raise HTTPException(status_code=400, detail=f'不支持的检索策略: {strategy}')


@app.post('/api/strategies/reranker')
async def set_reranker(data: dict):
    reranker = data.get('reranker')
    if reranker and engine.set_reranker(reranker):
        return {'status': 'ok', 'reranker': reranker}
    raise HTTPException(status_code=400, detail=f'不支持的重排器: {reranker}')


@app.post('/api/strategies/weights')
async def set_weights(data: dict):
    vw = data.get('vector_weight', engine.vector_weight)
    fw = data.get('fulltext_weight', engine.fulltext_weight)
    engine.set_weights(vw, fw)
    return {'status': 'ok', 'vector_weight': engine.vector_weight, 'fulltext_weight': engine.fulltext_weight}


@app.post('/api/strategies/topk')
async def set_topk(data: dict):
    recall = data.get('top_k_recall')
    final = data.get('top_k_final')
    engine.set_top_k(recall, final)
    return {'status': 'ok', 'top_k_recall': engine.top_k_recall, 'top_k_final': engine.top_k_final}


# ── 嵌入模型切换 ──

@app.get('/api/models')
async def get_models():
    return {
        'models': EMBEDDING_MODELS,
        'current_model': engine.embedding_model,
        'collections': {m['id']: {'collection': f'docs_v6_{m["id"]}', 'dim': m['dim'],
                                   'vector_count': engine.vector_count if m['id'] == engine.embedding_model else 0}
                        for m in EMBEDDING_MODELS},
    }


@app.post('/api/model/set')
async def set_model(data: dict):
    model_id = data.get('model')
    if not model_id:
        raise HTTPException(status_code=400, detail='请指定模型ID')
    result = engine.switch_model(model_id)
    if result['status'] == 'error':
        raise HTTPException(status_code=400, detail=result['message'])
    return result


# ── 策略对比 ──

@app.post('/api/compare')
async def compare_strategies(data: dict):
    query = data.get('query', '').strip()
    if not query:
        raise HTTPException(status_code=400, detail='请输入查询')
    result = engine.compare_strategies(query)
    return result


# ── 纯LLM回答（用于RAGvsLLM对比）──

@app.post('/api/llm-only')
async def llm_only(data: dict):
    query = data.get('query', '').strip()
    session_id = data.get('session_id', '')
    if not query:
        raise HTTPException(status_code=400, detail='请输入问题')
    lang = detect_language(query)
    sid = session_id or generate_session_id()
    messages = build_llm_only_prompt(query, lang)
    t0 = time.time()
    answer = non_stream_deepseek(messages)
    llm_time = time.time() - t0
    return {
        'query': query,
        'answer': answer,
        'language': lang,
        'llm_time': round(llm_time, 3),
        'session_id': sid,
    }


# ── 搜索 ──

@app.post('/api/search')
async def search(data: dict):
    query = data.get('query', '').strip()
    strategy = data.get('strategy', engine.strategy)
    reranker = data.get('reranker', engine.reranker)
    if not query:
        raise HTTPException(status_code=400, detail='请输入查询')
    old_s = engine.strategy
    old_r = engine.reranker
    engine.set_strategy(strategy)
    engine.set_reranker(reranker)
    result = engine.search(query)
    # 添加评估指标
    metrics = engine.compute_metrics(query, result['results'])
    result['metrics'] = metrics
    engine.set_strategy(old_s)
    engine.set_reranker(old_r)
    return result


# ── 会话管理 ──

@app.post('/api/session/new')
async def create_session():
    return {'session_id': generate_session_id(), 'title': '新对话'}


@app.get('/api/session/list')
async def list_sessions():
    return list_all_sessions()


@app.get('/api/session/{session_id}/history')
async def get_session_history(session_id: str):
    _, messages = get_or_create_session(session_id)
    return {'messages': messages}


@app.post('/api/session/{session_id}/clear')
async def clear_session(session_id: str):
    save_session_messages(session_id, [])
    return {'status': 'ok'}


@app.delete('/api/session/{session_id}')
async def delete_session(session_id: str):
    global sessions_client
    sessions_client.delete(collection_name=SESSIONS_COLLECTION, ids=[session_id])
    sessions_client.flush(SESSIONS_COLLECTION)
    return {'status': 'ok'}


@app.post('/api/session/rename')
async def rename_session(data: dict):
    sid = data.get('session_id', '')
    title = data.get('title', '')
    if not sid:
        return {'status': 'ok'}
    res = sessions_client.get(collection_name=SESSIONS_COLLECTION, ids=[sid])
    if res:
        e = res[0]
        msgs = json.loads(e.get('messages', '[]'))
        save_session_messages(sid, msgs)
        sessions_client.upsert(
            collection_name=SESSIONS_COLLECTION,
            data=[_session_entity(sid, msgs, created=e.get('created'), updated=time.time(), title=title)]
        )
        if _should_flush():
            sessions_client.flush(SESSIONS_COLLECTION)
    return {'status': 'ok', 'title': title or '新对话'}


# ── 历史搜索 ──

@app.post('/api/history/search')
async def history_search(data: dict):
    query = data.get('query', '').strip()
    if not query:
        return {'matches': []}
    matches = search_sessions(query)
    return {'matches': matches, 'query': query}


# ── 聊天流式API ──

@app.post('/api/chat/stream')
async def chat_stream(data: dict):
    query = data.get('query', '').strip()
    session_id = data.get('session_id', '')

    if not query:
        raise HTTPException(status_code=400, detail='请输入问题')

    lang = detect_language(query)
    sid = session_id or generate_session_id()
    sid, history = get_or_create_session(sid)

    t0 = time.time()
    result = engine.search(query)
    retrieve_time = result['stats']['total_time']
    retrieved = result['results']
    metrics = engine.compute_metrics(query, retrieved)

    # 构建参考块
    references = []
    for i, r in enumerate(retrieved, 1):
        references.append({
            'index': i,
            'text': r['text'],
            'pdf': r.get('pdf', ''),
            'page': r.get('page', 0),
            'score': round(r.get('score', 0), 4),
            'source': r.get('source', ''),
        })

    messages = build_prompt(query, retrieved, lang, history, engine.strategy, engine.embedding_model)

    async def event_stream():
        meta = {
            'type': 'meta',
            'session_id': sid,
            'language': lang,
            'strategy': engine.strategy,
            'reranker': engine.reranker,
            'model': engine.embedding_model,
            'retrieve_time': retrieve_time,
            'num_chunks': len(retrieved),
            'vector_count': result['stats']['vector_count'],
            'fulltext_count': result['stats']['fulltext_count'],
            'metrics': metrics,
            'references': references,
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

        llm_time = time.time() - t1

        if query and full_text:
            history.append({'role': 'user', 'content': query})
            history.append({'role': 'assistant', 'content': full_text})
            save_session_messages(sid, history)

        done = {
            'type': 'done',
            'total_time': round(llm_time, 3),
            'retrieve_time': retrieve_time,
            'total_chars': len(full_text),
            'full_text': full_text,
        }
        yield f'data: {json.dumps(done, ensure_ascii=False)}\n\n'

    return StreamingResponse(event_stream(), media_type='text/event-stream')


# ── 非流式聊天 ──

@app.post('/api/chat')
async def chat(data: dict):
    query = data.get('query', '').strip()
    session_id = data.get('session_id', '')

    if not query:
        raise HTTPException(status_code=400, detail='请输入问题')

    lang = detect_language(query)
    sid = session_id or generate_session_id()
    sid, history = get_or_create_session(sid)

    t0 = time.time()
    result = engine.search(query)
    retrieve_time = time.time() - t0
    retrieved = result['results']
    metrics = engine.compute_metrics(query, retrieved)

    references = []
    for i, r in enumerate(retrieved, 1):
        references.append({
            'index': i,
            'text': r['text'][:200],
            'pdf': r.get('pdf', ''),
            'page': r.get('page', 0),
            'score': round(r.get('score', 0), 4),
        })

    messages = build_prompt(query, retrieved, lang, history, engine.strategy, engine.embedding_model)

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
        'language': lang,
        'strategy': engine.strategy,
        'reranker': engine.reranker,
        'model': engine.embedding_model,
        'retrieve_time': round(retrieve_time, 3),
        'llm_time': round(llm_time, 3),
        'total_time': round(retrieve_time + llm_time, 3),
        'num_chunks': len(retrieved),
        'session_id': sid,
        'retrieval_stats': result['stats'],
        'metrics': metrics,
        'references': references,
    }


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8506))
    uvicorn.run(app, host='0.0.0.0', port=port)
