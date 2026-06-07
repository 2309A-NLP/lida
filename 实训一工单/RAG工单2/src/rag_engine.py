"""
RAG检索引擎 - 编排PDF解析→向量检索→LLM生成
三层缓存、Query理解、响应追踪、双语支持、评估指标
"""
import time
import threading
import hashlib
import sqlite3
import json
import re
from collections import OrderedDict
from pathlib import Path

from src.pdf_parser import PDFParser
from src.text_chunker import TextChunker
from src.embedder import Embedder
from src.vector_store import VectorStore
from src.llm_client import LLMClient
from src.evaluator import RAGEvaluator


class LRUCache:
    """线程安全LRU缓存"""
    def __init__(self, max_size: int = 200):
        self.max_size = max_size
        self._cache = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def put(self, key: str, value):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def clear(self):
        with self._lock:
            self._cache.clear()


class PersistentCache:
    """持久化SQLite缓存"""
    def __init__(self, db_path: str, max_entries: int = 200):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("""CREATE TABLE IF NOT EXISTS query_cache (
            query_hash TEXT PRIMARY KEY, result_json TEXT NOT NULL, created_at REAL NOT NULL
        )""")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON query_cache(created_at)")
        self._conn.commit()
        self._lock = threading.Lock()

    def _hash(self, question: str) -> str:
        return hashlib.sha256(question.encode("utf-8")).hexdigest()

    def get(self, question: str):
        qh = self._hash(question)
        with self._lock:
            row = self._conn.execute(
                "SELECT result_json FROM query_cache WHERE query_hash = ?", (qh,)
            ).fetchone()
            return json.loads(row[0]) if row else None

    def put(self, question: str, result: dict):
        qh = self._hash(question)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO query_cache VALUES (?, ?, ?)",
                (qh, json.dumps(result, ensure_ascii=False, default=str), time.time())
            )
            self._conn.execute(
                "DELETE FROM query_cache WHERE rowid NOT IN (SELECT rowid FROM query_cache ORDER BY created_at DESC LIMIT ?)",
                (self.max_entries,)
            )
            self._conn.commit()

    def clear(self):
        with self._lock:
            self._conn.execute("DELETE FROM query_cache")
            self._conn.commit()


class RAGEngine:
    """RAG检索引擎 - 双语支持 + 评估指标"""

    def __init__(self, config: dict):
        self.config = config
        emb_cfg = config["embedding"]
        llm_cfg = config["llm"]
        sys_cfg = config.get("system", {})
        vdb_cfg = config.get("vectordb", {})

        self.embedder = Embedder(
            backend=emb_cfg.get("backend", "onnx"),
            model_name=emb_cfg["model_name"],
            api_key=emb_cfg.get("api_key", llm_cfg.get("api_key", "")),
            base_url=emb_cfg.get("base_url", llm_cfg.get("base_url", "")),
            cache_size=sys_cfg.get("embedding_cache_size", 500),
            onnx_path=emb_cfg.get("onnx_path", ""),
            tokenizer_path=emb_cfg.get("tokenizer_path", ""),
        )
        self.chunker = TextChunker(
            chunk_size=config["chunking"]["chunk_size"],
            chunk_overlap=config["chunking"]["chunk_overlap"],
            separators=config["chunking"].get("separators"),
        )
        self.vector_store = VectorStore(
            persist_directory=config["vectordb"]["persist_directory"],
            collection_name=config["vectordb"]["collection_name"],
            hnsw_ef_search=vdb_cfg.get("hnsw_ef_search", 50),
            hnsw_ef_construction=vdb_cfg.get("hnsw_ef_construction", 100),
            hnsw_M=vdb_cfg.get("hnsw_M", 16),
        )
        self.llm = LLMClient(
            provider=config["llm"]["provider"],
            model=config["llm"]["model"],
            api_key=config["llm"]["api_key"],
            base_url=config["llm"]["base_url"],
            temperature=config["llm"]["temperature"],
            max_tokens=config["llm"]["max_tokens"],
            streaming=config["llm"].get("streaming", True),
        )

        self.top_k = config["retrieval"]["top_k"]
        self.similarity_threshold = config["retrieval"].get("similarity_threshold", 0.25)

        qu_cfg = config.get("query_understanding", {})
        self.query_understanding_enabled = qu_cfg.get("enabled", True)
        self._query_understander = None

        # 评估器
        ev_cfg = config.get("evaluation", {})
        self.evaluator = RAGEvaluator(
            precision_threshold=ev_cfg.get("precision_threshold", 0.30),
            use_llm_judge=ev_cfg.get("use_llm_judge", True),
        )
        self.evaluator.set_llm_client(self.llm)
        self._evaluation_enabled = ev_cfg.get("enabled", True)

        # 双语配置
        bi_cfg = config.get("bilingual", {})
        self._cross_retrieval = bi_cfg.get("cross_retrieval", True)

        self._cache = LRUCache(max_size=sys_cfg.get("cache_size", 200))
        self._persistent_cache = PersistentCache(
            str(Path(config["vectordb"]["persist_directory"]).parent / "query_cache.db"),
            max_entries=200
        ) if sys_cfg.get("persistent_cache", True) else None

    @property
    def query_understander(self):
        if self._query_understander is None:
            from src.query_understanding import QueryUnderstanding
            self._query_understander = QueryUnderstanding(self.llm)
        return self._query_understander

    def detect_language(self, text: str) -> str:
        """检测文本语言"""
        return 'zh' if re.search(r'[\u4e00-\u9fff]', text) else 'en'

    def _check_caches(self, question: str):
        mem = self._cache.get(question)
        if mem:
            return dict(mem)
        if self._persistent_cache:
            disk = self._persistent_cache.get(question)
            if disk:
                self._cache.put(question, disk)
                return dict(disk)
        return None

    def _store_caches(self, question: str, result: dict):
        self._cache.put(question, result)
        if self._persistent_cache:
            self._persistent_cache.put(question, result)

    def build_index(self, pdf_path: str, force_rebuild: bool = False) -> dict:
        """解析PDF并构建向量索引"""
        if self.vector_store.count() > 0 and not force_rebuild:
            return {"status": "skipped", "message": f"索引已存在，共{self.vector_store.count()}条"}

        parser = PDFParser(pdf_path)
        parsed = parser.parse()
        chunks = self.chunker.split_document(parsed)
        texts = [c["text"] for c in chunks]
        embeddings = self.embedder.encode(texts, show_progress=True)

        self.vector_store.clear()
        self.vector_store.add_documents(chunks, embeddings)

        return {
            "status": "success",
            "total_pages": parsed["total_pages"],
            "total_chunks": len(chunks),
            "embedding_dim": self.embedder.dimension,
        }

    def _retrieve(self, question: str) -> tuple[list[dict], list[int]]:
        """检索相关文档片段"""
        query_vec = self.embedder.encode_query(question)
        raw_hits = self.vector_store.search(query_vec, top_k=self.top_k)
        hits = [h for h in raw_hits if h["score"] >= self.similarity_threshold]
        pages = list(set(
            h["page_num"] for h in hits if h.get("page_num") is not None
        ))
        return hits, pages

    def _bilingual_retrieve(self, question: str, lang: str) -> tuple[list[dict], list[int]]:
        """
        双语检索：如果开启了cross_retrieval，
        中文问题同时用英文翻译检索，英文问题同时用中文翻译检索
        """
        hits, pages = self._retrieve(question)

        if not self._cross_retrieval:
            return hits, pages

        # 如果原文检索结果太少，尝试用翻译检索
        if len(hits) < 3:
            try:
                target = "en" if lang == "zh" else "zh"
                translated = self.llm.translate_query(question, target)
                if translated and translated != question:
                    trans_hits, trans_pages = self._retrieve(translated)
                    existing_texts = {h["text"] for h in hits}
                    for h in trans_hits:
                        if h["text"] not in existing_texts:
                            hits.append(h)
                            existing_texts.add(h["text"])
                    pages = list(set(pages + trans_pages))
            except Exception:
                pass

        return hits[:self.top_k * 2], pages

    def query(self, question: str, lang: str = None) -> dict:
        """执行RAG问答，含评估指标"""
        start_time = time.time()
        lang = lang or self.detect_language(question)

        cached = self._check_caches(question)
        if cached:
            cached["cached"] = True
            cached["total_time"] = round(time.time() - start_time, 3)
            if "retrieved_chunks" in cached:
                cached["pages"] = list(set(
                    c.get("page_num") for c in cached["retrieved_chunks"] if c.get("page_num")
                ))
            return cached

        # 检索
        retrieval_start = time.time()
        hits, pages = self._bilingual_retrieve(question, lang)
        retrieval_time = time.time() - retrieval_start

        # 评估检索质量
        eval_metrics = {}
        if self._evaluation_enabled:
            eval_metrics = self.evaluator.evaluate_retrieval(hits, question)

        # RAG生成
        gen_start = time.time()
        if not hits:
            answer = "I couldn't find relevant information in the document." if lang == "en" else "未在文档中找到与问题相关的信息。"
        else:
            answer = self.llm.generate_with_rag(question, hits, lang)
        gen_time = time.time() - gen_start

        # 纯LLM对比
        llm_start = time.time()
        llm_answer = self.llm.generate_directly(question, lang)
        llm_time = time.time() - llm_start

        result = {
            "question": question,
            "answer": answer,
            "llm_only_answer": llm_answer,
            "lang": lang,
            "retrieved_chunks": hits,
            "pages": pages,
            "retrieval_time": round(retrieval_time, 3),
            "generation_time": round(gen_time, 3),
            "llm_only_time": round(llm_time, 3),
            "total_time": round(time.time() - start_time, 3),
            "cached": False,
            "eval_metrics": eval_metrics,
        }

        self._store_caches(question, result)
        return result

    def query_stream(self, question: str, lang: str = None):
        """流式RAG问答，逐阶段yield状态"""
        start_time = time.time()
        lang = lang or self.detect_language(question)

        cached = self._check_caches(question)
        if cached:
            cached["cached"] = True
            cached["total_time"] = round(time.time() - start_time, 3)
            if "retrieved_chunks" in cached:
                cached["pages"] = list(set(
                    c.get("page_num") for c in cached["retrieved_chunks"] if c.get("page_num")
                ))
            yield {"type": "done", "result": cached}
            return

        # 阶段1: 检索
        yield {"type": "phase", "phase": "retrieval", "message": "检索中..." if lang == "zh" else "Retrieving..."}
        retrieval_start = time.time()
        hits, pages = self._bilingual_retrieve(question, lang)
        retrieval_time = time.time() - retrieval_start

        # 评估检索质量
        eval_metrics = {}
        if self._evaluation_enabled:
            eval_metrics = self.evaluator.evaluate_retrieval(hits, question)

        if not hits:
            msg = "未找到相关文档" if lang == "zh" else "No relevant documents found"
            yield {"type": "phase", "phase": "done", "message": msg}
            answer = "I couldn't find relevant information in the document." if lang == "en" else "未在文档中找到与问题相关的信息。"
            result = {
                "question": question, "answer": answer,
                "llm_only_answer": "", "lang": lang,
                "retrieved_chunks": [], "pages": [],
                "retrieval_time": round(retrieval_time, 3),
                "generation_time": 0, "llm_only_time": 0,
                "total_time": round(time.time() - start_time, 3),
                "cached": False, "eval_metrics": eval_metrics,
            }
            yield {"type": "done", "result": result}
            return

        yield {"type": "phase", "phase": "generating", "message": "生成回答中..." if lang == "zh" else "Generating answer..."}

        # 阶段2: 流式生成
        gen_start = time.time()
        collected_answer = []
        for token in self.llm.generate_with_rag_stream(question, hits, lang):
            collected_answer.append(token)
            yield {"type": "token", "text": token}
        gen_time = time.time() - gen_start
        answer = "".join(collected_answer)

        # 阶段3: 纯LLM对比（后台执行，不阻塞UI）
        llm_start = time.time()
        llm_answer = self.llm.generate_directly(question, lang)
        llm_time = time.time() - llm_start

        result = {
            "question": question,
            "answer": answer,
            "llm_only_answer": llm_answer,
            "lang": lang,
            "retrieved_chunks": hits,
            "pages": pages,
            "retrieval_time": round(retrieval_time, 3),
            "generation_time": round(gen_time, 3),
            "llm_only_time": round(llm_time, 3),
            "total_time": round(time.time() - start_time, 3),
            "cached": False,
            "eval_metrics": eval_metrics,
        }

        self._store_caches(question, result)
        yield {"type": "done", "result": result}

    def query_with_understanding(self, question: str, lang: str = None) -> dict:
        """带Query理解的RAG问答"""
        start_time = time.time()
        lang = lang or self.detect_language(question)

        cached = self._check_caches(question)
        if cached:
            cached["cached"] = True
            cached["total_time"] = round(time.time() - start_time, 3)
            if "retrieved_chunks" in cached:
                cached["pages"] = list(set(
                    c.get("page_num") for c in cached["retrieved_chunks"] if c.get("page_num")
                ))
            return cached

        qu_cfg = self.config.get("query_understanding", {})
        analysis = {}
        analysis_time = 0
        raw_hits = []
        is_short_query = len(question) < 15

        if self.query_understanding_enabled and qu_cfg.get("intent_recognition", True):
            if is_short_query:
                analysis = {"intent": "factual", "entities": [], "is_complex": False,
                           "sub_questions": [], "ambiguities": [], "keywords": []}
            else:
                analysis_result = {}
                def run_analysis():
                    analysis_result["data"] = self.query_understander.analyze(question)

                thread = threading.Thread(target=run_analysis)
                thread.start()

                query_vec = self.embedder.encode_query(question)
                raw_hits = self.vector_store.search(query_vec, top_k=self.top_k)
                thread.join()

                analysis = analysis_result.get("data", {})
                analysis_time = time.time() - start_time

        retrieval_time = time.time() - start_time - analysis_time

        hits = [h for h in raw_hits if h["score"] >= self.similarity_threshold] if raw_hits else []
        if not hits and not is_short_query:
            if not raw_hits:
                qvec = self.embedder.encode_query(question)
                raw_hits = self.vector_store.search(qvec, top_k=self.top_k)
                hits = [h for h in raw_hits if h["score"] >= self.similarity_threshold]
        elif not hits and is_short_query:
            qvec = self.embedder.encode_query(question)
            raw_hits = self.vector_store.search(qvec, top_k=self.top_k)
            hits = [h for h in raw_hits if h["score"] >= self.similarity_threshold]

        if qu_cfg.get("decomposition", True) and analysis.get("is_complex"):
            try:
                return self._handle_complex(question, analysis, start_time, lang)
            except Exception:
                pass

        gen_start = time.time()
        if not hits:
            answer = "I couldn't find relevant information in the document." if lang == "en" else "未在文档中找到与问题相关的信息。"
        else:
            answer = self.llm.generate_with_rag(question, hits, lang)
        gen_time = time.time() - gen_start

        llm_start = time.time()
        llm_answer = self.llm.generate_directly(question, lang)
        llm_time = time.time() - llm_start

        pages = list(set(h.get("page_num") for h in hits if h.get("page_num") is not None))

        # 评估
        eval_metrics = {}
        if self._evaluation_enabled:
            eval_metrics = self.evaluator.evaluate_retrieval(hits, question)

        result = {
            "question": question,
            "answer": answer,
            "llm_only_answer": llm_answer,
            "lang": lang,
            "analysis": analysis,
            "analysis_time": round(analysis_time, 3),
            "retrieved_chunks": hits,
            "pages": pages,
            "retrieval_time": round(retrieval_time, 3),
            "generation_time": round(gen_time, 3),
            "llm_only_time": round(llm_time, 3),
            "total_time": round(time.time() - start_time, 3),
            "cached": False,
            "eval_metrics": eval_metrics,
        }

        self._store_caches(question, result)
        return result

    def _handle_complex(self, question: str, analysis: dict, start_time: float,
                        lang: str = "zh") -> dict:
        """处理复杂问题：分解为子问题"""
        sub_questions = analysis.get("sub_questions", [])
        if not sub_questions:
            raise ValueError("无子问题")

        sub_results = []
        for sq in sub_questions[:3]:
            qv = self.embedder.encode_query(sq)
            hits = self.vector_store.search(qv, top_k=self.top_k)
            hits = [h for h in hits if h["score"] >= self.similarity_threshold]
            if hits:
                ctx = "\n\n".join([f"[第{h['page_num']}页] {h['text']}" for h in hits])
                sub_results.append(f"子问题: {sq}\n相关信息: {ctx[:300]}")

        context = "\n\n".join(sub_results)
        user_prompt = f"用户问题: {question}\n\n子问题分析:\n{context}\n\n请综合以上信息给出完整回答。"
        sys_prompt = (
            "You are a professional prospectus Q&A assistant. Synthesize sub-analysis results."
            if lang == "en" else
            "你是一个专业的招股说明书问答助手。综合子问题分析结果，回答用户问题。"
        )
        answer = self.llm.generate(sys_prompt, user_prompt)
        llm_answer = self.llm.generate_directly(question, lang)

        return {
            "question": question,
            "answer": answer,
            "llm_only_answer": llm_answer,
            "lang": lang,
            "analysis": analysis,
            "retrieved_chunks": [],
            "pages": [],
            "retrieval_time": 0,
            "generation_time": round(time.time() - start_time, 3),
            "llm_only_time": 0,
            "total_time": round(time.time() - start_time, 3),
            "cached": False,
            "eval_metrics": {},
        }

    def clear_cache(self):
        self._cache.clear()
        self.embedder.clear_cache()
        if self._persistent_cache:
            self._persistent_cache.clear()
