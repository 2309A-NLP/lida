"""
工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务
招股书RAG问答服务（基于关键词检索）
"""
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional

# 招股书文本目录
PROSPECTUS_DIRS = [
    Path("D:/Agent工单/Agent工单5/dataset_raw/pdf_txt_file"),
    Path("D:/Agent工单/Agent工单4/dataset_partial/pdf_txt_file"),
]

# CSV索引文件
CSV_PATHS = [
    Path("D:/Agent工单/Agent工单5/dataset_raw/pdf_txt_file.csv"),
    Path("D:/Agent工单/Agent工单4/dataset_partial/pdf_txt_file.csv"),
]

# 缓存
_text_cache: Dict[str, str] = {}
_company_index: Dict[str, List[str]] = {}
_loaded = False


def _find_text_dir() -> Optional[Path]:
    for p in PROSPECTUS_DIRS:
        if p.exists():
            return p
    return None


def _load_texts(max_docs: int = 30):
    global _text_cache, _company_index, _loaded
    if _loaded:
        return

    text_dir = _find_text_dir()
    if not text_dir:
        _loaded = True
        return

    files = list(text_dir.glob("*.txt"))[:max_docs]
    for f in files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            _text_cache[f.stem] = content
            # 尝试提取公司名
            m = re.search(r'([一-龥]{2,20}(?:股份|有限|集团|科技|医疗|生物|电子|能源|金融|证券|银行)[^\n]{0,10})', content[:500])
            if m:
                company = m.group(1)[:20]
                if company not in _company_index:
                    _company_index[company] = []
                _company_index[company].append(f.stem)
        except Exception:
            pass
    _loaded = True


def _search_in_text(text: str, keywords: List[str], context_size: int = 200) -> List[str]:
    """在文本中搜索关键词，返回上下文片段"""
    results = []
    for kw in keywords:
        pos = 0
        while True:
            idx = text.find(kw, pos)
            if idx == -1:
                break
            start = max(0, idx - context_size)
            end = min(len(text), idx + len(kw) + context_size)
            snippet = text[start:end].replace('\n', ' ').strip()
            if snippet and snippet not in results:
                results.append(snippet)
            pos = idx + 1
            if len(results) >= 3:
                break
    return results


def process_prospectus_question(question: str) -> Dict:
    """处理招股书问答"""
    _load_texts()

    if not _text_cache:
        return {
            "answer": "招股书知识库数据未加载。系统支持查询招股书相关信息，包括公司基本信息、业务描述、风险因素、财务数据等。",
            "success": False,
            "evidence": []
        }

    # 过滤疑问词和语气词，提取有效关键词
    stop_words = {"什么", "怎么", "如何", "是否", "多少", "哪些", "哪个", "请问", "告诉我",
                  "查询", "是什", "是哪", "有哪", "的是", "？", "?", "！", "!", "。", "，",
                  "有什", "了吗", "吗", "呢", "吧", "啊", "了", "的", "是", "有", "在",
                  "和", "与", "或", "及", "为", "对", "中", "上", "下", "了解"}

    # 提取2-8字的中文词组作为关键词
    cn_phrases = re.findall(r'[一-龥]{2,8}', question)
    keywords = []
    for phrase in cn_phrases:
        # 过滤纯疑问/虚词短语
        if phrase not in stop_words and not all(c in "什么怎么如何是否多少哪些哪个请问告诉的是有了吗呢吧啊的是在" for c in phrase):
            keywords.append(phrase)
    keywords = list(dict.fromkeys(keywords))[:6]  # 去重保序，最多6个

    # 如果没有有效关键词
    if not keywords:
        return {
            "answer": "请提供更具体的查询内容，例如：查询某公司的主营业务、募集资金用途等。",
            "success": True,
            "evidence": [],
            "total_docs": len(_text_cache)
        }

    # 搜索相关文档
    best_docs = []
    for doc_id, text in _text_cache.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            best_docs.append((score, doc_id, text))

    best_docs.sort(reverse=True)
    best_docs = best_docs[:3]

    if not best_docs:
        return {
            "answer": f"在招股书知识库中未找到与「{'、'.join(keywords[:3])}」相关的内容。知识库共包含 {len(_text_cache)} 份文档。",
            "success": True,
            "evidence": [],
            "keywords": keywords
        }

    # 从最相关文档中提取片段
    evidence = []
    answer_parts = []

    for score, doc_id, text in best_docs:
        snippets = _search_in_text(text, keywords)
        if snippets:
            evidence.append({
                "doc_id": doc_id,
                "score": score,
                "snippets": snippets[:2]
            })
            answer_parts.extend(snippets[:1])

    if answer_parts:
        answer = f"根据招股书知识库检索结果（匹配关键词：{'、'.join(keywords[:3])}）：\n\n" + "\n\n".join(f"[片段{i+1}] {s}" for i, s in enumerate(answer_parts[:3]))
    else:
        answer = f"找到{len(best_docs)}份相关文档，但未能提取到精确答案片段。请尝试更具体的关键词。"

    return {
        "answer": answer,
        "success": True,
        "evidence": evidence,
        "keywords": keywords,
        "total_docs": len(_text_cache),
        "matched_docs": len(best_docs)
    }


def get_prospectus_stats() -> Dict:
    """获取招股书知识库统计"""
    _load_texts()
    return {
        "available": bool(_text_cache),
        "total_docs": len(_text_cache),
        "text_dir": str(_find_text_dir()) if _find_text_dir() else None,
        "sample_companies": list(_company_index.keys())[:5]
    }
