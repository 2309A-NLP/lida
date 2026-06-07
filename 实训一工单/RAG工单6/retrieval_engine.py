"""RAG工单6 v3.0 - Milvus检索引擎
支持三模型切换: bge_small_zh / bge_m3 / m3e
支持向量/全文/混合检索 + 策略对比 + 中英互查
"""
import os, json, re, time, gc, copy
import numpy as np
from pymilvus import MilvusClient, DataType
import jieba

# 国内镜像 + 离线缓存
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('HUGGINGFACE_HUB_CACHE', os.path.expanduser('~/.cache/fastembed'))

BASE_DIR = '/mnt/d/RAG工单/RAG工单6'
MILVUS_PATH = os.path.join(BASE_DIR, 'milvus_v6.db')
INDEX_PATH = os.path.join(BASE_DIR, 'index_data_v6.json')

jieba.setLogLevel(20)

STOP_WORDS = set(
    '的 了 是 在 和 与 或 及 对 为 等 之 其 该 被 把 从 到 向 用 且 以 还 也 但 而 更 已 将 不 很 都 会 能 就 因 如 若 虽 然 只 要 让 吗 呢 呀 哦 嗯 啊 哈 什么 怎么 哪些 这个 那个 一个 可以 没有 我们 他们 你们 自己 如何 为什么 相关 涉及 情况'.split()
)

SYNONYM_MAP = {
    '法人': ['法定代表人', '法人代表'],
    '老板': ['法定代表人', '实际控制人', '控股股东', '董事长'],
    '公司': ['发行人', '本公司', '股份有限公司', '企业'],
    '收入': ['营业收入', '营收', '销售收入', '主营业务收入'],
    '利润': ['净利润', '盈利', '收益', '利润总额'],
    '资产': ['总资产', '净资产', '资产总额'],
    '股东': ['持股', '股权', '股份', '股本'],
    '股票': ['股份', '股权', '股本', '发行'],
    'CEO': ['法定代表人', '总经理', '董事长', '高管'],
    '董事长': ['法定代表人', '董事', '董事长兼总经理'],
    '发行': ['上市', 'IPO', '公开发行', '募集'],
    '募集': ['募资', '筹资', '融资', '资金用途'],
    '产品': ['业务', '主营', '技术', '解决方案', '服务'],
    '技术': ['核心技术', '专利', '研发', '知识产权', '创新'],
    '客户': ['用户', '合作方', '下游', '军队', '军用', '国防'],
    '供应商': ['采购', '上游', '供货'],
    '风险': ['不确定性', '挑战', '不利', '因素'],
    '增长': ['增长', '提高', '增加', '上升', '扩大', '增长趋势'],
    '军事': ['军用', '军队', '国防', '作战', '指挥'],
}

RETRIEVAL_STRATEGIES = {
    'vector': {'name': '向量检索（召回+重排）', 'desc': 'Milvus向量相似度搜索 + 重排精选'},
    'fulltext': {'name': '全文检索', 'desc': 'jieba关键词+同义词扩展搜索'},
    'hybrid': {'name': '混合检索', 'desc': '向量 + 全文加权融合'},
}

# 模型定义
EMBEDDING_MODELS = [
    {'id': 'bge_small_zh', 'name': 'BAAI/bge-small-zh-v1.5', 'dim': 512, 'desc': 'FastEmbed 本地缓存'},
    {'id': 'bge_m3',       'name': 'BAAI/bge-m3',             'dim': 1024, 'desc': '本地 BGE-M3 模型'},
    {'id': 'm3e',          'name': 'moka-ai/m3e-base',        'dim': 768, 'desc': '本地 M3E 模型'},
]

MODEL_COLLECTIONS = {
    'bge_small_zh': 'docs_v6_bge',
    'bge_m3': 'docs_v6_bgem3',
    'm3e': 'docs_v6_m3e',
}

# English→Chinese keyword translation
EN_TO_ZH = {
    'revenue': '营业收入', 'income': '收入', 'profit': '利润',
    'total': '合计总额', 'company': '公司发行人', 'chairman': '董事长',
    'CEO': '法定代表人', 'share': '股份', 'stock': '股票',
    'fiscal': '会计年度', 'year': '年度', 'technology': '技术',
    'patent': '专利', 'risk': '风险', 'asset': '资产',
    'product': '产品', 'business': '业务主营', 'customer': '客户',
    'market': '市场', 'prospectus': '招股说明书',
}

PRONOUN_EXPANSIONS = {
    '他': ['程家明', '法定代表人', '实际控制人', '董事长'],
    '她': ['程家明', '法定代表人', '实际控制人'],
    '它': ['公司', '发行人', '本公司', '武汉兴图新科'],
    '他们': ['公司', '发行人', '程家明', '高管'],
    '其': ['公司', '发行人', '程家明'],
}

API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
API_URL = 'https://api.deepseek.com/v1/chat/completions'


class EmbeddingBackend:
    """统一嵌入后端：支持 fastembed 和 sentence-transformers"""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self._model = None
        self._dim = None
        self._load()

    def _load(self):
        for m in EMBEDDING_MODELS:
            if m['id'] == self.model_id:
                self._dim = m['dim']
                break

        if self.model_id == 'bge_small_zh':
            from fastembed import TextEmbedding
            self._model = TextEmbedding(
                model_name="BAAI/bge-small-zh-v1.5", max_length=512,
                cache_dir=os.path.expanduser('~/.cache/fastembed')
            )
        elif self.model_id == 'bge_m3':
            from sentence_transformers import SentenceTransformer
            model_path = '/mnt/d/BGE-M3'
            self._model = SentenceTransformer(model_path, device='cpu')
            self._model.max_seq_length = 8192
        elif self.model_id == 'm3e':
            from sentence_transformers import SentenceTransformer
            model_path = '/mnt/d/M3E-base/NLP专高2日周月考附件 m3e-base/m3e-base'
            self._model = SentenceTransformer(model_path, device='cpu')
        else:
            raise ValueError(f'Unknown model: {self.model_id}')

    def encode(self, text: str) -> list:
        if self.model_id == 'bge_small_zh':
            vec = list(self._model.embed([text]))[0]
            arr = np.array(vec, dtype=np.float32)
        else:
            vec = self._model.encode(text, normalize_embeddings=True)
            arr = np.array(vec, dtype=np.float32)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr.tolist()

    @property
    def dim(self) -> int:
        return self._dim

    def unload(self):
        del self._model
        self._model = None
        gc.collect()


class RetrievalEngine:
    def __init__(self):
        self._embedding = None
        self.client = None
        self.all_chunks = []
        self.strategy = 'hybrid'
        self.reranker = 'tfidf'
        self.vector_weight = 0.7
        self.fulltext_weight = 0.3
        self.top_k_recall = 50
        self.top_k_final = 7
        self.embedding_model = 'bge_small_zh'
        self.vector_count = 0
        self._feedback_history = []

    # ── 嵌入模型管理 ──

    def _get_embedding(self, model_id: str = None) -> EmbeddingBackend:
        mid = model_id or self.embedding_model
        if self._embedding is None or self._embedding.model_id != mid:
            if self._embedding is not None:
                self._embedding.unload()
            self._embedding = EmbeddingBackend(mid)
        return self._embedding

    def switch_model(self, model_id: str) -> dict:
        """切换嵌入模型"""
        valid_ids = [m['id'] for m in EMBEDDING_MODELS]
        if model_id not in valid_ids:
            return {'status': 'error', 'message': f'不支持的模型: {model_id}'}
        self.embedding_model = model_id
        # 强制重新加载
        if self._embedding is not None:
            self._embedding.unload()
            self._embedding = None
        emb = self._get_embedding()
        # 切换集合
        collection = MODEL_COLLECTIONS[model_id]
        dim = emb.dim
        self._ensure_collection(collection, dim)
        self.client.load_collection(collection)
        # 更新计数
        try:
            stats = self.client.query(collection_name=collection, output_fields=['chunk_id'], limit=10000)
            self.vector_count = len(stats)
        except:
            self.vector_count = 0
        return {
            'status': 'ok',
            'model': model_id,
            'dim': dim,
            'collection': collection,
            'vector_count': self.vector_count,
        }

    def _ensure_collection(self, collection_name: str, dim: int):
        if not self.client.has_collection(collection_name):
            schema = MilvusClient.create_schema(
                auto_id=True, enable_dynamic_field=True
            )
            schema.add_field(field_name="chunk_id", datatype=DataType.INT64, is_primary=True, auto_id=True)
            schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
            schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dim)
            schema.add_field(field_name="pdf", datatype=DataType.VARCHAR, max_length=200)
            schema.add_field(field_name="page", datatype=DataType.INT64)
            schema.add_field(field_name="section", datatype=DataType.VARCHAR, max_length=200)
            index_params = self.client.prepare_index_params()
            index_params.add_index(field_name="vector", index_type="IVF_FLAT", metric_type="IP", params={"nlist": 128})
            self.client.create_collection(
                collection_name=collection_name, schema=schema, index_params=index_params
            )

    # ── 加载 ──

    def load(self):
        self.client = MilvusClient(MILVUS_PATH)
        collection = MODEL_COLLECTIONS[self.embedding_model]
        self._ensure_collection(collection, self._get_embedding().dim)
        self.client.load_collection(collection)
        self.vector_count = 0
        try:
            stats = self.client.query(collection_name=collection, output_fields=['chunk_id'], limit=10000)
            self.vector_count = len(stats)
        except:
            pass
        if os.path.exists(INDEX_PATH):
            with open(INDEX_PATH, 'r', encoding='utf-8') as f:
                self.all_chunks = json.load(f)
            print(f'[引擎] 加载 {len(self.all_chunks)} 块元数据, Milvus {self.vector_count} 向量, 模型={self.embedding_model}')

    # ── 嵌入计算 ──

    def compute_embedding(self, text: str) -> list:
        emb = self._get_embedding()
        return emb.encode(text)

    # ── 关键词提取 ──

    def extract_keywords(self, text: str, max_kw: int = 10) -> list:
        is_english = bool(re.search(r'[a-zA-Z]{3,}', text)) and not re.search(r'[\u4e00-\u9fff]', text)
        zh_expansions = []
        if is_english:
            text_lower = text.lower()
            for en_word, zh_expansion in EN_TO_ZH.items():
                if en_word in text_lower:
                    text += ' ' + zh_expansion
                    zh_expansions.append(zh_expansion)
            max_kw = max(max_kw, 20)

        expanded_query = text
        for pronoun, expansions in PRONOUN_EXPANSIONS.items():
            if pronoun in text:
                expanded_query += ' ' + ' '.join(expansions)
                break

        words = [w for w in jieba.lcut(expanded_query) if len(w) >= 2 and w not in STOP_WORDS]
        seen = set()
        result = []
        for w in sorted(words, key=lambda x: (len(x), text.count(x)), reverse=True):
            if w not in seen:
                seen.add(w)
                result.append(w)
        for zh in zh_expansions:
            expanded_terms = list(jieba.cut(zh))
            for term in expanded_terms:
                if len(term) >= 2 and term not in seen:
                    seen.add(term)
                    result.append(term)
        expanded = []
        for w in result:
            expanded.append(w)
            if w in SYNONYM_MAP:
                for syn in SYNONYM_MAP[w]:
                    if syn not in seen:
                        seen.add(syn)
                        expanded.append(syn)
        return expanded[:max_kw]

    # ── 检索核心方法 ──

    def vector_retrieve(self, query: str) -> list:
        collection = MODEL_COLLECTIONS[self.embedding_model]
        vec = self.compute_embedding(query)
        results = self.client.search(
            collection_name=collection,
            data=[vec],
            search_params={"metric_type": "IP", "params": {"nprobe": 32}},
            limit=self.top_k_recall,
            output_fields=["text", "pdf", "page", "section"],
        )
        hits = []
        if results and results[0]:
            for r in results[0]:
                hits.append({
                    'text': r['entity'].get('text', ''),
                    'pdf': r['entity'].get('pdf', ''),
                    'page': r['entity'].get('page', 0),
                    'section': r['entity'].get('section', ''),
                    'score': float(r['distance']),
                    'source': 'vector',
                })
        return hits

    def fulltext_retrieve(self, query: str) -> list:
        keywords = self.extract_keywords(query)
        if not keywords:
            return []
        scored = []
        for chunk in self.all_chunks:
            text = chunk.get('text', '')
            score = 0
            matched_kws = 0
            for kw in keywords:
                count = text.count(kw)
                if count > 0:
                    score += count * (len(kw) ** 1.3)
                    matched_kws += 1
            if matched_kws > 0:
                score *= (1 + 0.2 * matched_kws)
            if score > 0:
                scored.append({
                    'text': text,
                    'pdf': chunk.get('pdf', ''),
                    'page': chunk.get('page', 0),
                    'section': chunk.get('section', ''),
                    'score': score,
                    'source': 'fulltext',
                })
        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored[:self.top_k_recall]

    def hybrid_retrieve(self, query: str) -> list:
        v_results = self.vector_retrieve(query)
        f_results = self.fulltext_retrieve(query)
        all_scores = {}
        for r in v_results:
            all_scores[r['text'][:100]] = {'vec': r['score'], 'full': 0, 'data': r}
        for r in f_results:
            key = r['text'][:100]
            if key in all_scores:
                all_scores[key]['full'] = r['score']
            else:
                all_scores[key] = {'vec': 0, 'full': r['score'], 'data': r}

        w_vec = self.vector_weight
        w_full = self.fulltext_weight

        vec_items = [(k, v) for k, v in all_scores.items() if v['vec'] > 0]
        full_items = [(k, v) for k, v in all_scores.items() if v['full'] > 0]

        vec_items.sort(key=lambda x: x[1]['vec'], reverse=True)
        full_items.sort(key=lambda x: x[1]['full'], reverse=True)

        vec_ranks = {k: i + 1 for i, (k, _) in enumerate(vec_items)}
        full_ranks = {k: i + 1 for i, (k, _) in enumerate(full_items)}

        combined = []
        K = 60

        for key, v in all_scores.items():
            rrf_vec = 1.0 / (K + vec_ranks.get(key, K + len(vec_items) + 1)) if v['vec'] > 0 else 0
            rrf_full = 1.0 / (K + full_ranks.get(key, K + len(full_items) + 1)) if v['full'] > 0 else 0

            vec_max = max([x[1]['vec'] for x in vec_items]) if vec_items else 1
            full_max = max([x[1]['full'] for x in full_items]) if full_items else 1

            n_vec = v['vec'] / vec_max if vec_max > 0 else 0
            n_full = v['full'] / full_max if full_max > 0 else 0

            fusion_score = w_vec * (rrf_vec + n_vec * 0.3) + w_full * (rrf_full + n_full * 0.3)

            combined.append({
                **v['data'],
                'score': fusion_score,
            })

        combined.sort(key=lambda x: x['score'], reverse=True)
        return combined[:self.top_k_recall]

    # ── 重排器 ──

    def tfidf_rerank(self, query: str, candidates: list) -> list:
        if not candidates:
            return candidates
        query_grams = set()
        for n in range(2, 6):
            for i in range(len(query) - n + 1):
                query_grams.add(query[i:i + n])
        if not query_grams:
            for c in candidates:
                c['rerank_score'] = c.get('score', 0)
            return candidates
        doc_gram_sets = []
        for c in candidates:
            grams = set()
            text = c['text']
            for n in range(2, 6):
                for i in range(len(text) - n + 1):
                    grams.add(text[i:i + n])
            doc_gram_sets.append(grams)
        N = len(candidates)
        idf = {}
        for gram in query_grams:
            df = sum(1 for gs in doc_gram_sets if gram in gs)
            idf[gram] = np.log((N + 1) / (df + 1)) + 1
        for i, c in enumerate(candidates):
            text_grams = doc_gram_sets[i]
            overlap = query_grams & text_grams
            score = sum(idf.get(g, 0) for g in overlap)
            c['rerank_score'] = score * (1 + c.get('score', 0) * 0.2)
        candidates.sort(key=lambda x: x['rerank_score'], reverse=True)
        return candidates

    def llm_rerank(self, query: str, candidates: list, top_n: int = 5) -> list:
        if not candidates or not API_KEY:
            return candidates
        top_candidates = candidates[:top_n]
        for c in top_candidates:
            prompt = (
                f"请判断以下文档片段与用户问题的相关程度，只输出一个0-1之间的数字代表相关度：\n"
                f"问题：{query}\n"
                f"文档：{c['text'][:1000]}\n"
                f"相关度评分："
            )
            try:
                import requests
                resp = requests.post(
                    API_URL,
                    json={'model': 'deepseek-chat', 'messages': [
                        {'role': 'system', 'content': '你是一个相关性评估器，只输出数字。'},
                        {'role': 'user', 'content': prompt},
                    ], 'temperature': 0.1, 'max_tokens': 10},
                    headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'},
                    timeout=10,
                )
                llm_score = float(resp.json()['choices'][0]['message']['content'].strip())
                c['rerank_score'] = min(max(llm_score, 0), 1) * 10
            except Exception:
                c['rerank_score'] = c.get('score', 0)
        reranked = {c['text'][:100]: c['rerank_score'] for c in top_candidates}
        for c in candidates:
            key = c['text'][:100]
            if key in reranked:
                c['rerank_score'] = reranked[key]
            else:
                c['rerank_score'] = c.get('score', 0)
        candidates.sort(key=lambda x: x['rerank_score'], reverse=True)
        return candidates

    def adaptive_rerank(self, query: str, candidates: list) -> list:
        if not candidates or not API_KEY:
            return candidates
        tfidf = self.tfidf_rerank(query, candidates)
        top5 = tfidf[:5]
        for c in top5:
            prompt = (
                f"请判断以下文档片段与用户问题的相关程度（0表示完全不相关，10表示完全相关），只输出一个0-10之间的整数：\n"
                f"问题：{query}\n"
                f"文档：{c['text'][:800]}\n"
                f"评分："
            )
            try:
                import requests
                resp = requests.post(
                    API_URL,
                    json={'model': 'deepseek-chat', 'messages': [
                        {'role': 'user', 'content': prompt},
                    ], 'temperature': 0.1, 'max_tokens': 5},
                    headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'},
                    timeout=10,
                )
                score = float(resp.json()['choices'][0]['message']['content'].strip())
                c['rerank_score'] = min(max(score, 0), 10)
            except Exception:
                c['rerank_score'] = c.get('rerank_score', c.get('score', 0))
        llm_keys = {c['text'][:100]: c['rerank_score'] for c in top5}
        for c in tfidf:
            key = c['text'][:100]
            if key in llm_keys:
                c['rerank_score'] = llm_keys[key]
        tfidf.sort(key=lambda x: x['rerank_score'], reverse=True)
        return tfidf

    # ── 配置方法 ──

    def set_strategy(self, strategy: str):
        if strategy in RETRIEVAL_STRATEGIES:
            self.strategy = strategy

    def set_reranker(self, reranker: str) -> bool:
        if reranker in ('llm', 'tfidf', 'adaptive'):
            self.reranker = reranker
            return True
        return False

    def set_weights(self, vec_w: float, full_w: float):
        total = vec_w + full_w
        if total > 0:
            self.vector_weight = vec_w / total
            self.fulltext_weight = full_w / total

    def set_top_k(self, recall: int = None, final: int = None):
        if recall is not None:
            self.top_k_recall = min(max(recall, 5), 100)
        if final is not None:
            self.top_k_final = min(max(final, 1), 50)

    def _expand_query_for_rerank(self, query: str) -> str:
        if re.search(r'[a-zA-Z]{3,}', query) and not re.search(r'[\u4e00-\u9fff]', query):
            text_lower = query.lower()
            expanded = query
            for en_word, zh_expansion in EN_TO_ZH.items():
                if en_word in text_lower:
                    expanded += ' ' + zh_expansion
            return expanded
        return query

    # ── 主搜索 ──

    def search(self, query: str) -> dict:
        t0 = time.time()
        if self.strategy == 'vector':
            results = self.vector_retrieve(query)
            vector_count = len(results)
            fulltext_count = 0
        elif self.strategy == 'fulltext':
            results = self.fulltext_retrieve(query)
            vector_count = 0
            fulltext_count = len(results)
        else:
            results = self.hybrid_retrieve(query)
            vector_count = min(self.top_k_recall, self.vector_count)
            fulltext_count = self.top_k_recall
        retrieve_time = time.time() - t0

        rerank_query = self._expand_query_for_rerank(query)
        if self.reranker == 'llm':
            results = self.llm_rerank(rerank_query, results)
        elif self.reranker == 'adaptive':
            results = self.adaptive_rerank(rerank_query, results)
        else:
            results = self.tfidf_rerank(rerank_query, results)
        rerank_time = time.time() - t0 - retrieve_time
        final = results[:self.top_k_final]

        return {
            'results': final,
            'stats': {
                'total_time': round(time.time() - t0, 4),
                'retrieve_time': round(retrieve_time, 4),
                'rerank_time': round(rerank_time, 4),
                'vector_count': vector_count,
                'fulltext_count': fulltext_count,
                'final_count': len(final),
                'strategy': self.strategy,
                'reranker': self.reranker,
                'model': self.embedding_model,
            },
        }

    # ── 策略对比 ──

    def compare_strategies(self, query: str) -> dict:
        """在同一个模型下对比三种检索策略的结果"""
        old_strategy = self.strategy
        old_reranker = self.reranker

        comparison = {}
        for strategy in ['vector', 'fulltext', 'hybrid']:
            self.set_strategy(strategy)
            result = self.search(query)
            comparison[strategy] = {
                'name': RETRIEVAL_STRATEGIES[strategy]['name'],
                'results': result['results'],
                'stats': result['stats'],
            }

        self.set_strategy(old_strategy)
        self.set_reranker(old_reranker)

        return {
            'query': query,
            'model': self.embedding_model,
            'comparison': comparison,
        }

    # ── 评估指标 ──

    def compute_metrics(self, query: str, results: list) -> dict:
        """估算检索结果的精确率和召回率"""
        keywords = self.extract_keywords(query, max_kw=15)
        if not keywords:
            return {'precision': 0, 'recall': 0, 'f1': 0, 'keywords': []}

        retrieved_texts = [r['text'] for r in results]

        # 精确率: 检索结果中相关关键词的覆盖率
        kw_hits = sum(1 for kw in keywords if any(kw in t for t in retrieved_texts))
        precision = kw_hits / max(len(keywords), 1)

        # 召回率: 关键词在所有文档中的出现 vs 在检索结果中的出现
        all_keyword_counts = {}
        for chunk in self.all_chunks:
            text = chunk.get('text', '')
            for kw in keywords:
                if kw in text:
                    all_keyword_counts[kw] = all_keyword_counts.get(kw, 0) + text.count(kw)

        retrieved_keyword_counts = {}
        for t in retrieved_texts:
            for kw in keywords:
                if kw in t:
                    retrieved_keyword_counts[kw] = retrieved_keyword_counts.get(kw, 0) + t.count(kw)

        if all_keyword_counts:
            recall = sum(retrieved_keyword_counts.get(kw, 0) for kw in keywords) / \
                     max(sum(all_keyword_counts.get(kw, 0) for kw in keywords), 1)
        else:
            recall = 0

        recall = min(recall, 1.0)
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        return {
            'precision': round(precision * 100, 1),
            'recall': round(recall * 100, 1),
            'f1': round(f1 * 100, 1),
            'keywords': keywords[:10],
        }
