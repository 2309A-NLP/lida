"""RAG工单7 - Milvus金融年报检索引擎 (优化版)
- 嵌入模型: BAAI/bge-small-zh-v1.5 (512维)
- 查询扩展: 同义词/keyword扩展
- 检索参数: top_k_recall=50, final=7, vector_weight=0.7
- 优化全文检索: 使用段落级配分
"""
import os, json, re, time, requests
import numpy as np
from pymilvus import MilvusClient
import jieba
from fastembed import TextEmbedding

BASE_DIR = '/mnt/d/RAG工单/RAG工单7'
MILVUS_PATH = os.path.join(BASE_DIR, 'milvus_v7.db')
INDEX_PATH = os.path.join(BASE_DIR, 'index_data_v7.json')
COLLECTION_NAME = 'docs_v7'
EMBED_DIM = 512

jieba.setLogLevel(20)

STOP_WORDS = set(
    '的 了 是 在 和 与 或 及 对 为 等 之 其 该 被 把 从 到 向 用 且 以 还 也 但 而 更 已 将 不 很 都 会 能 就 因 如 若 虽 然 只 要 让 吗 呢 呀 哦 嗯 啊 哈 什么 怎么 哪些 这个 那个 一个 可以 没有 我们 他们 你们 自己 如何 为什么 相关 涉及 情况'.split()
)

# 金融/年报同义词扩展
SYNONYM_MAP = {
    '法人': ['法定代表人', '法人代表'],
    '老板': ['法定代表人', '实际控制人', '控股股东', '董事长'],
    '公司': ['本公司', '股份有限公司', '企业', '集团'],
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
    '客户': ['用户', '合作方', '下游'],
    '供应商': ['采购', '上游', '供货'],
    '风险': ['不确定性', '挑战', '不利', '因素'],
    '增长': ['增长', '提高', '增加', '上升', '扩大', '增长趋势'],
}

RETRIEVAL_STRATEGIES = {
    'vector': {'name': '向量检索（召回+重排）', 'desc': 'Milvus向量相似度搜索 + 重排精选'},
    'fulltext': {'name': '全文检索', 'desc': 'jieba关键词+同义词扩展搜索'},
    'hybrid': {'name': '混合检索', 'desc': '向量召回 + 全文召回 + RRF融合'},
}

EMBEDDING_MODELS = [
    {'id': 'bge_small_zh', 'name': 'BAAI/bge-small-zh-v1.5 (512维)', 'dim': 512},
]

# 延迟加载嵌入模型，避免启动时卡在网络连接
_embed_fn = None
def get_embed_fn():
    global _embed_fn
    if _embed_fn is None:
        _embed_fn = TextEmbedding(model_name="BAAI/bge-small-zh-v1.5", max_length=512)
    return _embed_fn

# API key 统一从环境变量读取
API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
API_URL = 'https://api.deepseek.com/v1/chat/completions'

# 英文→中文关键词翻译（处理英文查询）
EN_TO_ZH = {
    'revenue': '营业收入',
    'income': '收入',
    'profit': '利润',
    'total': '合计总额',
    'company': '公司',
    'chairman': '董事长',
    'CEO': '法定代表人',
    'share': '股份',
    'stock': '股票',
    'fiscal': '会计年度',
    'year': '年度',
    'technology': '技术',
    'patent': '专利',
    'risk': '风险',
    'asset': '资产',
    'product': '产品',
    'business': '业务主营',
    'customer': '客户',
    'market': '市场',
    'annual_report': '年度报告年报',
}

# 代词→实体扩展（单轮对话中指代消解）
PRONOUN_EXPANSIONS = {
    '他': ['法定代表人', '实际控制人', '董事长', '总经理'],
    '她': ['法定代表人', '实际控制人', '董事长', '总经理'],
    '它': ['公司', '本公司', '国泰君安'],
    '他们': ['公司', '国泰君安', '高管'],
    '其': ['公司', '国泰君安'],
}


class RetrievalEngine:
    def __init__(self):
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

    def load(self):
        self.client = MilvusClient(MILVUS_PATH)
        self.client.load_collection(COLLECTION_NAME)
        self.vector_count = 0
        try:
            stats = self.client.query(collection_name=COLLECTION_NAME, output_fields=['chunk_id'], limit=10000)
            self.vector_count = len(stats)
        except:
            self.vector_count = 0
        if os.path.exists(INDEX_PATH):
            with open(INDEX_PATH, 'r', encoding='utf-8') as f:
                self.all_chunks = json.load(f)
            print(f'[引擎] 加载 {len(self.all_chunks)} 块元数据, Milvus {self.vector_count} 向量')

    def compute_embedding(self, text: str) -> list:
        vec = list(get_embed_fn().embed([text]))[0]
        arr = np.array(vec, dtype=np.float32)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr.tolist()

    def extract_keywords(self, text: str, max_kw: int = 10) -> list:
        """提取关键词 + 同义词扩展 + 代词消解 + 英文支持"""
        # 检测英文查询 → 翻译为中文关键词
        is_english = bool(re.search(r'[a-zA-Z]{3,}', text)) and not re.search(r'[\u4e00-\u9fff]', text)
        zh_expansions = []
        if is_english:
            text_lower = text.lower()
            for en_word, zh_expansion in EN_TO_ZH.items():
                if en_word in text_lower:
                    text += ' ' + zh_expansion
                    zh_expansions.append(zh_expansion)
            # 英文查询多提一些关键词
            max_kw = max(max_kw, 20)

        # 代词消解：把"他/她/它/他们/其"替换为具体实体
        expanded_query = text
        for pronoun, expansions in PRONOUN_EXPANSIONS.items():
            if pronoun in text:
                expanded_query += ' ' + ' '.join(expansions)
                break

        words = [w for w in jieba.lcut(expanded_query) if len(w) >= 2 and w not in STOP_WORDS]
        seen = set()
        result = []
        # 原词按长度和频次排序
        for w in sorted(words, key=lambda x: (len(x), text.count(x)), reverse=True):
            if w not in seen:
                seen.add(w)
                result.append(w)
        # 确保中文翻译词始终在关键词列表中
        for zh in zh_expansions:
            expanded_terms = list(jieba.cut(zh))
            for term in expanded_terms:
                if len(term) >= 2 and term not in seen:
                    seen.add(term)
                    result.append(term)
        # 同义词扩展
        expanded = []
        for w in result:
            expanded.append(w)
            if w in SYNONYM_MAP:
                for syn in SYNONYM_MAP[w]:
                    if syn not in seen:
                        seen.add(syn)
                        expanded.append(syn)
        return expanded[:max_kw]

    def vector_retrieve(self, query: str) -> list:
        vec = self.compute_embedding(query)
        results = self.client.search(
            collection_name=COLLECTION_NAME,
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
            # 奖励同时匹配到多个关键词
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

        # RRF融合 (加权)
        w_vec = self.vector_weight
        w_full = self.fulltext_weight

        # 对每个源内的分数做排序位置融合（RRF）
        vec_items = [(k, v) for k, v in all_scores.items() if v['vec'] > 0]
        full_items = [(k, v) for k, v in all_scores.items() if v['full'] > 0]

        # 分别按分数排序得排名
        vec_items.sort(key=lambda x: x[1]['vec'], reverse=True)
        full_items.sort(key=lambda x: x[1]['full'], reverse=True)

        vec_ranks = {k: i+1 for i, (k, _) in enumerate(vec_items)}
        full_ranks = {k: i+1 for i, (k, _) in enumerate(full_items)}

        combined = []
        K = 60  # RRF常数

        for key, v in all_scores.items():
            rrf_vec = 1.0 / (K + vec_ranks.get(key, K + len(vec_items) + 1)) if v['vec'] > 0 else 0
            rrf_full = 1.0 / (K + full_ranks.get(key, K + len(full_items) + 1)) if v['full'] > 0 else 0

            # 归一化向量分数作为辅助
            vec_max = max([x[1]['vec'] for x in vec_items]) if vec_items else 1
            full_max = max([x[1]['full'] for x in full_items]) if full_items else 1

            n_vec = v['vec'] / vec_max if vec_max > 0 else 0
            n_full = v['full'] / full_max if full_max > 0 else 0

            # 组合: RRF + 分数加权
            fusion_score = w_vec * (rrf_vec + n_vec * 0.3) + w_full * (rrf_full + n_full * 0.3)

            combined.append({
                **v['data'],
                'score': fusion_score,
            })

        combined.sort(key=lambda x: x['score'], reverse=True)
        return combined[:self.top_k_recall]

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
        """Expand English queries with Chinese translations for better reranking"""
        if re.search(r'[a-zA-Z]{3,}', query) and not re.search(r'[\u4e00-\u9fff]', query):
            text_lower = query.lower()
            expanded = query
            for en_word, zh_expansion in EN_TO_ZH.items():
                if en_word in text_lower:
                    expanded += ' ' + zh_expansion
            return expanded
        return query

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
        # 英文查询需要扩展后传重排器（否则 n-gram 不匹配中文文档）
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
            },
        }
