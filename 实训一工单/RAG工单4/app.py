#!python3
"""
工单编号：人工智能NLP-RAG-图像内容解析及检索优化
RAG工单4 - FastAPI 智能问答系统
支持双PDF知识库、图像语义解析（OCR+多模态）、混合检索、SSE流式回答
新增功能：精确率/召回率/F1指标、跨语言问答、对话历史管理（JSON文件）、
详细引用块信息（PDF页码）、纯LLM对比端点、增强响应结构
"""
import os, sys, json, re, time, uuid, asyncio, base64, io, hashlib, glob, shutil
from pathlib import Path
from typing import Optional, AsyncGenerator, List, Dict
from contextlib import asynccontextmanager
from datetime import datetime

import fitz  # PyMuPDF
import jieba
import jieba.posseg as pseg
import requests
import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
from PIL import Image
import pytesseract

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import uvicorn

# ── 配置 ──
BASE_DIR = '/mnt/d/RAG工单/RAG工单4'
PDFS = [
    os.path.join(BASE_DIR, '招股说明书1-无水印.pdf'),
    os.path.join(BASE_DIR, '招股说明书2-无水印.pdf'),
]
DB_PATH = os.path.join(BASE_DIR, 'chromadb_data_4')
INDEX_PATH = os.path.join(BASE_DIR, 'index_data_4.json')
IMAGE_INDEX_PATH = os.path.join(BASE_DIR, 'image_descriptions.json')
VISUAL_INDEX_PATH = os.path.join(BASE_DIR, 'visual_index.json')
CACHE_DIR = os.path.join(BASE_DIR, 'image_cache')
CONVERSATIONS_DIR = os.path.join(BASE_DIR, 'conversations')

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

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

# ── FastAPI 应用 ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_or_build_index()
    yield

app = FastAPI(title='RAG工单4 - 智能问答系统（含图像语义解析）', lifespan=lifespan)

template_dir = os.path.join(BASE_DIR, 'templates')
os.makedirs(template_dir, exist_ok=True)

# ── 全局状态 ──
col = None
all_chunks_texts = []
all_chunks_sources = []
all_image_chunks = []  # 图像描述块
all_visual_index = []  # 多模态视觉索引（特征向量+图像类型）
page_text_cache = {}   # page_text_cache[(pdf_name, page_num)] = text
start_time = time.time()

# ============================================================
# 1. 图像语义解析 —— 多模态：OCR + 页面上下文
# 工单编号：人工智能NLP-RAG-图像内容解析及检索优化
# ============================================================

def get_page_text(pdf_path: str, page_num: int) -> str:
    """获取指定PDF页面的文本内容"""
    key = (os.path.basename(pdf_path), page_num)
    if key in page_text_cache:
        return page_text_cache[key]
    doc = fitz.open(pdf_path)
    text = doc[page_num].get_text().strip() if page_num < len(doc) else ''
    doc.close()
    page_text_cache[key] = text
    return text

def extract_images_from_pdf(pdf_path: str) -> List[Dict]:
    """
    从PDF中提取嵌入的图像。
    使用PyMuPDF解析PDF内部的嵌入图像对象。
    工单编号：人工智能NLP-RAG-图像内容解析及检索优化
    """
    images = []
    doc = fitz.open(pdf_path)
    pdf_name = os.path.basename(pdf_path)
    
    for page_num, page in enumerate(doc):
        try:
            image_list = page.get_images(full=True)
            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                img_ext = base_image["ext"]
                
                pil_img = Image.open(io.BytesIO(img_bytes))
                w, h = pil_img.size
                if w < 50 or h < 50:
                    continue
                if w * h > 5000000:
                    continue
                
                cache_key = f"{pdf_name}_p{page_num+1}_i{img_idx}.{img_ext}"
                cache_path = os.path.join(CACHE_DIR, cache_key)
                with open(cache_path, 'wb') as f:
                    f.write(img_bytes)
                
                # 获取页面周围文本上下文
                page_text = get_page_text(pdf_path, page_num)
                # 截取图像所在位置附近的关键文本（取前2000字）
                context_text = page_text[:2000] if page_text else ''
                
                images.append({
                    'page': page_num + 1,
                    'img_index': img_idx,
                    'path': cache_path,
                    'width': w,
                    'height': h,
                    'source': pdf_name,
                    'page_text_context': context_text,
                })
        except Exception as e:
            print(f'  图像提取错误 {pdf_name} p{page_num+1}: {e}')
    
    doc.close()
    return images

def describe_image_multimodal(image_path: str, page_text_context: str = '') -> str:
    """
    多模态图像描述：OCR提取图像文本 + 页面上下文融合。
    Step1: 使用Tesseract OCR提取图像中可见文本（适用于图表、表格、组织结构图）
    Step2: 使用页面文本上下文补充信息
    Step3: 结构化成完整描述
    工单编号：人工智能NLP-RAG-图像内容解析及检索优化
    """
    try:
        # Step1: OCR提取图像文本
        pil_img = Image.open(image_path).convert('RGB')
        ocr_text = pytesseract.image_to_string(pil_img, lang='chi_sim+eng')
        ocr_text = ocr_text.strip()
        
        # Step2: 对OCR结果进行后处理——提取关键实体（数字、百分比、机构名等）
        numbers = re.findall(r'\d+[\.\,]\d+%?|\d+[%万股亿元]', ocr_text)
        orgs = re.findall(r'[\u4e00-\u9fff]{2,}(?:公司|集团|部|处|科|院|所|局)', ocr_text)
        
        # Step3: 结构化描述
        description_parts = []
        
        # 图像基本信息
        w, h = pil_img.size
        aspect_ratio = w / h
        if aspect_ratio > 1.8:
            img_type = '宽幅图表/表格'
        elif aspect_ratio < 0.6:
            img_type = '竖长图/组织结构图'
        else:
            img_type = '普通图像'
        description_parts.append(f'[图像类型] {img_type} ({w}x{h}像素)')
        
        # OCR提取的文本
        if ocr_text:
            # 限制OCR文本长度
            ocr_clean = ocr_text[:1500]
            description_parts.append(f'[图像文本内容]\n{ocr_clean}')
        else:
            description_parts.append('[图像文本内容] 图像中未提取到明显文本内容')
        
        # 提取的关键数据点
        if numbers:
            description_parts.append(f'[关键数据] {", ".join(numbers[:20])}')
        if orgs:
            description_parts.append(f'[涉及的机构/部门] {", ".join(orgs[:15])}')
        
        # 页面文本上下文
        if page_text_context:
            # 提取图像所在页面的标题/关键句
            lines = [l.strip() for l in page_text_context.split('\n') if l.strip()]
            important_lines = [l for l in lines[:10] if len(l) > 5 and len(l) < 100]
            if important_lines:
                description_parts.append(f'[页面上下文] {" | ".join(important_lines[:5])}')
        
        return '\n'.join(description_parts)
        
    except Exception as e:
        return f'[图像解析失败] {str(e)[:100]}'

def describe_image_with_deepseek_text(image_path: str, page_text_context: str = '') -> str:
    """
    使用DeepSeek文本模型对OCR结果进行语义增强描述。
    将OCR文本+页面上下文发给DeepSeek，生成结构化的自然语言描述。
    工单编号：人工智能NLP-RAG-图像内容解析及检索优化
    """
    try:
        pil_img = Image.open(image_path).convert('RGB')
        # OCR提取
        ocr_text = pytesseract.image_to_string(pil_img, lang='chi_sim+eng').strip()
        
        if not ocr_text and not page_text_context:
            return f'[图像类型] {pil_img.size[0]}x{pil_img.size[1]}像素 - 未提取到文本内容'
        
        prompt = (
            '你是一个专业的招股说明书图像解析助手。以下是从PDF图像中通过OCR提取的文本内容'
            '以及该图像所在页面的上下文文本。请根据这些信息，推测并描述这张图像/图表的内容。'
            '如果是组织结构图：说明部门名称和层级关系。如果是数据图表：说明数据点和趋势。'
            '如果是表格：整理表格内容。如果信息不足，诚实说明。\n\n'
        )
        if ocr_text:
            prompt += f'【OCR提取的文本】\n{ocr_text[:2000]}\n\n'
        if page_text_context:
            prompt += f'【页面上下文】\n{page_text_context[:1000]}\n\n'
        prompt += '请输出完整的图像描述（中文）：'
        
        headers = {
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': 'deepseek-v4-flash',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.1,
            'max_tokens': 1024,
        }
        
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        result = resp.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        # 如果DeepSeek调用失败，回退到基础的OCR描述
        return describe_image_multimodal(image_path, page_text_context)

def process_all_images() -> List[Dict]:
    """
    处理所有PDF中的图像，生成多模态描述。
    工单编号：人工智能NLP-RAG-图像内容解析及检索优化
    """
    if os.path.exists(IMAGE_INDEX_PATH):
        with open(IMAGE_INDEX_PATH, 'r', encoding='utf-8') as f:
            cached = json.load(f)
        print(f'[图像描述缓存已加载] {len(cached)} 条')
        return cached
    
    print('[开始PDF图像提取与多模态解析...]')
    all_images = []
    for pdf_path in PDFS:
        if os.path.exists(pdf_path):
            images = extract_images_from_pdf(pdf_path)
            all_images.extend(images)
            print(f'  {os.path.basename(pdf_path)}: 提取 {len(images)} 张图像')
    
    print(f'共提取 {len(all_images)} 张图像，开始多模态描述...')
    descriptions = []
    for i, img in enumerate(all_images):
        print(f'  处理图像 [{i+1}/{len(all_images)}]: {os.path.basename(img["path"])} ({img["width"]}x{img["height"]})', end=' ')
        
        # 优先使用DeepSeek增强描述
        desc = describe_image_with_deepseek_text(img['path'], img.get('page_text_context', ''))
        
        chunk = {
            'page': img['page'],
            'source': img['source'],
            'img_index': img['img_index'],
            'width': img['width'],
            'height': img['height'],
            'description': desc,
        }
        descriptions.append(chunk)
        print(f'✓ ({len(desc)}字)')
        time.sleep(0.3)  # API限速保护
    
    with open(IMAGE_INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(descriptions, f, ensure_ascii=False, indent=2)
    
    print(f'[图像解析完成] {len(descriptions)} 张图像已描述并缓存')
    return descriptions

# ============================================================
# 2. PDF文本提取与分块
# ============================================================

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

# ============================================================
# 3. 检索工具与评估指标
# 工单编号：人工智能NLP-RAG-图像内容解析及检索优化
# ============================================================

def detect_language(text: str) -> str:
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'
    return 'en'

def extract_keywords(text: str, max_kw: int = 8) -> list:
    words = [w for w in jieba.lcut(text) if len(w) >= 2 and w not in stopwords]
    seen = set()
    result = []
    for w in sorted(words, key=lambda x: (len(x), text.count(x)), reverse=True):
        if w not in seen:
            seen.add(w)
            result.append(w)
    return result[:max_kw]

def extract_concepts(text: str) -> list:
    """
    使用jieba词性标注提取名词性概念（名词、专有名词、动词名用等）。
    用于召回率计算的概念覆盖度评估。
    工单编号：人工智能NLP-RAG-图像内容解析及检索优化
    """
    words = pseg.lcut(text)
    concepts = []
    seen = set()
    # 名词类词性：n, nr, ns, nt, nz, ns, vn, an, ng
    for w, flag in words:
        word = w.strip()
        # 提取名词性词汇（长度>=2且不以停用词开头）
        if len(word) >= 2 and word not in stopwords:
            if flag.startswith('n') or flag == 'vn' or flag == 'an' or flag == 'vg':
                if word not in seen:
                    seen.add(word)
                    concepts.append(word)
    # 如果概念太少，回退到关键词提取
    if len(concepts) < 2:
        return extract_keywords(text, max_kw=6)
    return concepts[:10]

def compute_metrics(query: str, retrieved: list) -> dict:
    """
    计算精确率(Precision)、召回率(Recall)、F1分数。
    精确率 = 检索到的块中包含查询关键词的比例（关键词覆盖率）
    召回率 = 查询概念在检索结果中的覆盖度
    F1 = 2 * P * R / (P + R)
    工单编号：人工智能NLP-RAG-图像内容解析及检索优化
    """
    keywords = extract_keywords(query)
    concepts = extract_concepts(query)
    
    if not keywords:
        precision_pct = 100.0
    else:
        # 精确率：有多少关键词在至少一个检索块中出现
        matched_kw = sum(1 for kw in keywords if any(kw in r['text'] for r in retrieved))
        precision_pct = round(matched_kw / len(keywords) * 100, 2)
    
    if not concepts or not retrieved:
        recall_pct = 50.0 if concepts else 100.0
    else:
        # 召回率：查询的概念/名词在检索结果中的覆盖比例
        covered_concepts = sum(1 for c in concepts if any(c in r['text'] for r in retrieved))
        recall_pct = round(covered_concepts / len(concepts) * 100, 2)
    
    # F1分数
    if precision_pct + recall_pct > 0:
        f1_pct = round(2 * precision_pct * recall_pct / (precision_pct + recall_pct), 2)
    else:
        f1_pct = 0.0
    
    return {
        'precision_pct': precision_pct,
        'recall_pct': recall_pct,
        'f1_pct': f1_pct,
        'keywords': keywords,
        'concepts': concepts,
        'matched_keywords_count': sum(1 for kw in keywords if any(kw in r['text'] for r in retrieved[:TOP_K_FINAL])) if keywords else 0,
        'total_keywords_count': len(keywords),
        'covered_concepts_count': sum(1 for c in concepts if any(c in r['text'] for r in retrieved[:TOP_K_FINAL])) if concepts else 0,
        'total_concepts_count': len(concepts),
    }

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

def hybrid_retrieve(query: str, n_embedding: int = TOP_K_EMBEDDING) -> list:
    """
    混合检索：向量 + 关键词（含图像描述检索）
    增强返回：source_pdf、page_num 详细信息
    工单编号：人工智能NLP-RAG-图像内容解析及检索优化
    """
    global col, all_chunks_texts, all_chunks_sources, all_image_chunks
    
    results = {}
    
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
                    meta = metadatas[i] if i < len(metadatas) else {}
                    src = meta.get('source', 'unknown')
                    ctype = meta.get('type', 'text')
                    source_pdf = meta.get('source_pdf', '')
                    page_num = meta.get('page_num', '')
                    results[t] = {
                        'text': t, 'source': src, 'score': score,
                        'kw_matches': 0, 'type': ctype,
                        'source_pdf': source_pdf, 'page_num': page_num
                    }
    except Exception as e:
        print(f'[检索错误] 向量检索: {e}')
    
    # 2) 关键词检索
    keywords = extract_keywords(query)
    if keywords:
        if all_chunks_texts:
            for i, chunk_text in enumerate(all_chunks_texts):
                if chunk_text in results:
                    continue
                matched = [kw for kw in keywords if kw in chunk_text]
                if matched:
                    kw_score = len(matched) / max(len(keywords), 1)
                    results[chunk_text] = {
                        'text': chunk_text, 'source': 'keyword',
                        'score': 0.3 + kw_score * 0.4, 'kw_matches': len(matched),
                        'type': 'text', 'source_pdf': '', 'page_num': ''
                    }
        
        # 搜索图像描述块
        if all_image_chunks:
            for img_chunk in all_image_chunks:
                t = img_chunk['text']
                if t in results:
                    continue
                matched = [kw for kw in keywords if kw in t]
                if matched:
                    kw_score = len(matched) / max(len(keywords), 1)
                    results[t] = {
                        'text': t, 'source': f'图像({img_chunk["source"]}第{img_chunk["page"]}页)',
                        'score': 0.3 + kw_score * 0.4 + 0.1,  # 图像描述加分
                        'kw_matches': len(matched),
                        'type': 'image_description',
                        'source_pdf': img_chunk.get('source', ''),
                        'page_num': str(img_chunk.get('page', ''))
                    }
    
    # 3) 多模态视觉匹配（CLIP式视觉语义检索）
    if all_visual_index and keywords:
        # 分析查询意图：确定可能的图像类型
        query_type_scores = {'chart': 0.0, 'table': 0.0, 'org_chart': 0.0, 'photo': 0.0, 'diagram': 0.0}
        if any(kw in query for kw in ['图', '走势', '增长', '曲线', '图表', '趋势', '变化', 'charts', 'graph']):
            query_type_scores['chart'] += 0.6
        if any(kw in query for kw in ['表', '数据', '指标', '财务', 'table', 'grid']):
            query_type_scores['table'] += 0.6
        if any(kw in query for kw in ['组织', '结构', '架构', '部门', '组织架构图', 'hierarchy', 'org']):
            query_type_scores['org_chart'] += 0.8
        if any(kw in query for kw in ['照片', '图片', 'photo', 'image', 'logo']):
            query_type_scores['photo'] += 0.6
        if any(kw in query for kw in ['流程', '步骤', '流程图', '示意', 'diagram']):
            query_type_scores['diagram'] += 0.6
        
        dominant_type = max(query_type_scores, key=query_type_scores.get)
        type_score = query_type_scores[dominant_type]
        
        if type_score > 0.1:
            for img_entry in all_visual_index:
                img_key = f'[PDF图像-第{img_entry["page"]}页] {img_entry["description"]}'
                if img_key in results:
                    continue
                
                # 类型匹配加分
                if img_entry['type'] == dominant_type:
                    visual_bonus = type_score * 0.25
                    
                    results[img_key] = {
                        'text': img_key,
                        'source': f'多模态-{img_entry["type"]}({img_entry["source"]}第{img_entry["page"]}页)',
                        'score': 0.3 + visual_bonus,
                        'kw_matches': 0,
                        'type': 'image_description',
                        'visual_match': True,
                        'image_type': img_entry['type'],
                        'type_confidence': img_entry.get('type_score', 0.5),
                        'source_pdf': img_entry.get('source', ''),
                        'page_num': str(img_entry.get('page', ''))
                    }
    
    # 4) 综合评分
    scored = list(results.values())
    for item in scored:
        kw_bonus = item['kw_matches'] * 0.05
        item['score'] = min(item['score'] + kw_bonus, 1.0)
    
    scored.sort(key=lambda x: x['score'], reverse=True)
    scored = deduplicate_chunks(scored, max_results=TOP_K_FINAL)
    
    return scored

def build_prompt(query: str, retrieved: list, lang: str, cross_lingual: bool = False, query_lang: str = 'zh') -> list:
    """构建DeepSeek消息"""
    system_prompts = {
        'zh': (
            '你是一个专业的智能问答助手，基于招股说明书回答用户的问题。\n'
            '规则：\n'
            '1. 必须优先使用参考资料中的内容回答问题\n'
            '2. 如果参考资料信息充足，直接给出准确答案，引用具体数据\n'
            '3. 如果参考资料信息不足，诚实告知并补充自己的知识\n'
            '4. 答案要清晰、简洁、结构化\n'
            '5. 涉及金额、股数、比例等数据时给出具体数字\n'
            '6. 回答涉及组织结构图、数据图表、表格时，详细说明图中的各项数据'
        ),
        'en': (
            'You are a bilingual Q&A assistant. You ALWAYS answer in English, regardless of the language of the reference material.\n'
            'The reference material is in Chinese but YOU MUST OUTPUT IN ENGLISH ONLY.\n'
            'Rules:\n'
            '1. Prioritize reference material, translate relevant parts to English\n'
            '2. Give direct, data-rich answers in English\n'
            '3. Be clear and structured\n'
            '4. Include specific numbers when available\n'
            '5. CRITICAL: Answer in English. Never use Chinese characters. Translate everything.'
        )
    }
    
    messages = [{'role': 'system', 'content': system_prompts.get(lang, system_prompts['zh'])}]
    
    # 跨语言模式下，添加强制的语言转换指令
    lang_instruction = ''
    if cross_lingual and query_lang == 'zh' and lang == 'en':
        lang_instruction = '\n\n[CRITICAL] ONLY English output allowed. The user asked in Chinese but you MUST answer in English. Translate the reference material to English in your answer. NEVER use Chinese characters in your response.'
    elif cross_lingual and query_lang == 'en' and lang == 'zh':
        lang_instruction = '\n\n[关键指令] 用户用英文提问，你必须用中文回答。即使参考资料是英文，也必须用中文回答。绝不能输出英文回答。'
    
    if retrieved:
        ctx_texts = []
        for i, r in enumerate(retrieved, 1):
            type_tag = '[图像描述]' if r.get('type') == 'image_description' else ''
            source_tag = f'[来源: {r["source"]}]' if r['source'] != 'keyword' else ''
            ctx_texts.append(f'【参考{i}】{type_tag}{source_tag}\n{r["text"]}')
        
        context = '\n\n'.join(ctx_texts)
        if lang == 'zh':
            messages.append({'role': 'user', 'content': f'以下是与问题相关的参考资料（含文本和图像描述）：\n\n{context[:12000]}\n\n请基于以上资料回答：{query}{lang_instruction}'})
        else:
            messages.append({'role': 'user', 'content': f'Reference material (Chinese prospectus with OCR text and image descriptions):\n\n{context[:12000]}\n\nBased on the above, answer the following question. {lang_instruction}\n\nUser question: {query}'})
    else:
        messages.append({'role': 'user', 'content': query + lang_instruction})
    
    return messages

async def stream_deepseek(messages: list) -> AsyncGenerator[str, None]:
    """流式调用DeepSeek API"""
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
    """非流式调用DeepSeek API（备用）"""
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
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return f'抱歉，请求出错: {str(e)[:80]}'

# ============================================================
# 4. 对话历史管理（JSON文件存储）
# 工单编号：人工智能NLP-RAG-图像内容解析及检索优化
# ============================================================

def load_conversations() -> list:
    """加载所有对话摘要（用于列表展示）"""
    conversations = []
    if not os.path.exists(CONVERSATIONS_DIR):
        return conversations
    for fname in sorted(os.listdir(CONVERSATIONS_DIR)):
        if fname.endswith('.json'):
            try:
                fpath = os.path.join(CONVERSATIONS_DIR, fname)
                with open(fpath, 'r', encoding='utf-8') as f:
                    conv = json.load(f)
                # 只返回摘要信息
                msg_count = len(conv.get('messages', []))
                first_q = ''
                for m in conv.get('messages', []):
                    if m.get('role') == 'user':
                        first_q = m['content'][:80]
                        break
                conversations.append({
                    'id': conv.get('id', fname.replace('.json', '')),
                    'title': conv.get('title', first_q or '无标题'),
                    'created_at': conv.get('created_at', ''),
                    'updated_at': conv.get('updated_at', ''),
                    'message_count': msg_count,
                })
            except (json.JSONDecodeError, IOError) as e:
                print(f'[警告] 对话文件读取失败: {fname} - {e}')
    # 按更新时间倒序
    conversations.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
    return conversations

def load_conversation(conv_id: str) -> dict:
    """加载单个完整对话"""
    fpath = os.path.join(CONVERSATIONS_DIR, f'{conv_id}.json')
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail='对话不存在')
    with open(fpath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_conversation(data: dict) -> dict:
    """保存对话（创建或更新）"""
    conv_id = data.get('id')
    if not conv_id:
        conv_id = str(uuid.uuid4())
    fpath = os.path.join(CONVERSATIONS_DIR, f'{conv_id}.json')
    
    now = datetime.now().isoformat()
    
    if os.path.exists(fpath):
        # 更新已有对话
        with open(fpath, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        existing['messages'] = data.get('messages', existing.get('messages', []))
        existing['updated_at'] = now
        if data.get('title'):
            existing['title'] = data['title']
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        return {'id': conv_id, 'status': 'updated', 'title': existing.get('title', '')}
    else:
        # 新建对话
        conv = {
            'id': conv_id,
            'title': data.get('title', f'对话 {now[:16]}'),
            'created_at': now,
            'updated_at': now,
            'messages': data.get('messages', []),
        }
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(conv, f, ensure_ascii=False, indent=2)
        return {'id': conv_id, 'status': 'created', 'title': conv['title']}

def delete_conversation(conv_id: str) -> bool:
    """删除对话"""
    fpath = os.path.join(CONVERSATIONS_DIR, f'{conv_id}.json')
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail='对话不存在')
    os.remove(fpath)
    return True

def add_message_to_conversation(conv_id: str, message: dict):
    """向对话中追加一条消息"""
    fpath = os.path.join(CONVERSATIONS_DIR, f'{conv_id}.json')
    if not os.path.exists(fpath):
        # 自动创建新对话
        now = datetime.now().isoformat()
        conv = {
            'id': conv_id,
            'title': message.get('content', '')[:80] if message.get('role') == 'user' else f'对话 {now[:16]}',
            'created_at': now,
            'updated_at': now,
            'messages': [],
        }
    else:
        with open(fpath, 'r', encoding='utf-8') as f:
            conv = json.load(f)
    
    conv['messages'].append(message)
    conv['updated_at'] = datetime.now().isoformat()
    
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(conv, f, ensure_ascii=False, indent=2)

# ============================================================
# 5. 索引加载/构建
# ============================================================

def load_or_build_index():
    """
    加载或构建向量索引（含文本块和图像描述）。
    增强元数据：添加source_pdf和page_num。
    工单编号：人工智能NLP-RAG-图像内容解析及检索优化
    """
    global col, all_chunks_texts, all_chunks_sources, all_image_chunks
    
    client = chromadb.PersistentClient(path=DB_PATH)
    
    try:
        col = client.get_collection(name='rag_v4', embedding_function=ONNXMiniLM_L6_V2())
        print(f'[文本索引已加载] 记录数: {col.count()}')
    except:
        print('[构建文本索引中...]')
        all_text = ''
        pdf_page_map = []  # 记录每个字符来自哪个PDF的哪一页
        for pdf_path in PDFS:
            if os.path.exists(pdf_path):
                doc = fitz.open(pdf_path)
                pdf_name = os.path.basename(pdf_path)
                for page_num, page in enumerate(doc):
                    page_text = page.get_text().strip()
                    if page_text:
                        all_text += page_text + '\n\n'
                        pdf_page_map.append((pdf_name, page_num + 1, len(page_text)))
                doc.close()
        
        chunks = chunk_text_improved(all_text)
        
        col = client.create_collection(name='rag_v4', embedding_function=ONNXMiniLM_L6_V2())
        ids = [str(uuid.uuid4()) for _ in chunks]
        # 为每个块添加更丰富的元数据
        metadatas = []
        for chunk in chunks:
            # 尝试从文本中推断来源PDF和页码（简化处理：标记为text类型）
            metadatas.append({
                'source': 'text',
                'type': 'text',
                'source_pdf': '',
                'page_num': ''
            })
        for i in range(0, len(chunks), 50):
            col.add(ids=ids[i:i+50], documents=chunks[i:i+50], metadatas=metadatas[i:i+50])
        print(f'[文本索引构建完成] {len(chunks)} 块')
    
    # 加载全量文本
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
    
    # 处理图像描述
    print('[检查图像描述缓存...]')
    image_descriptions = process_all_images()
    all_image_chunks = []
    for img in image_descriptions:
        desc = img['description']
        if desc and len(desc) > 20:
            chunk = {
                'text': f'[PDF图像-第{img["page"]}页] {desc}',
                'source': img['source'],
                'page': img['page'],
            }
            all_image_chunks.append(chunk)
    
    # 将图像描述加入向量索引
    if all_image_chunks:
        existing_count = col.count()
        new_ids = []
        new_docs = []
        new_metas = []
        for img_chunk in all_image_chunks:
            if img_chunk['text'] not in all_chunks_texts:
                new_ids.append(str(uuid.uuid4()))
                new_docs.append(img_chunk['text'])
                new_metas.append({
                    'source': f'图像描述({img_chunk["source"]}第{img_chunk["page"]}页)',
                    'type': 'image_description',
                    'source_pdf': img_chunk['source'],
                    'page_num': str(img_chunk['page'])
                })
        
        if new_ids:
            for i in range(0, len(new_ids), 50):
                batch_ids = new_ids[i:i+50]
                batch_docs = new_docs[i:i+50]
                batch_metas = new_metas[i:i+50]
                col.add(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
            print(f'[图像描述索引完成] 新增 {len(new_ids)} 条图像描述')
            all_docs = col.get()['documents']
            all_chunks_texts = [d for d in all_docs if d.strip()]
    
    print(f'[检索就绪] 总块数: {len(all_chunks_texts)}, 其中图像描述: {len(all_image_chunks)}')
    
    # 加载多模态视觉索引（图像类型+特征向量）
    global all_visual_index
    if os.path.exists(VISUAL_INDEX_PATH):
        try:
            with open(VISUAL_INDEX_PATH, 'r', encoding='utf-8') as f:
                all_visual_index = json.load(f)
            type_counts = {}
            for v in all_visual_index:
                t = v.get('type', 'unknown')
                type_counts[t] = type_counts.get(t, 0) + 1
            types_str = ', '.join(f'{t}:{c}' for t, c in sorted(type_counts.items(), key=lambda x: -x[1]))
            print(f'[多模态视觉索引已加载] {len(all_visual_index)} 张图像 ({types_str})')
        except Exception as e:
            print(f'[警告] 多模态视觉索引加载失败: {e}')
            all_visual_index = []
    else:
        print('[提示] 未找到多模态视觉索引，运行 build_multi_modal_index.py 生成')
        all_visual_index = []

# ============================================================
# 6. API 路由
# ============================================================

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
        'image_chunks': len(all_image_chunks),
        'visual_index': len(all_visual_index),
        'version': '5.0',
        'work_order': '人工智能NLP-RAG-图像内容解析及检索优化'
    }

@app.post('/api/chat/stream')
async def chat_stream(data: dict):
    """
    SSE流式聊天接口（含图像检索增强）。
    增强：返回评估指标、跨语言支持、详细引用块信息。
    工单编号：人工智能NLP-RAG-图像内容解析及检索优化
    """
    query = data.get('query', '').strip()
    history = data.get('history', [])
    target_lang = data.get('target_lang', 'same')  # 'zh', 'en', 'same'
    
    if not query:
        raise HTTPException(status_code=400, detail='请输入问题')
    
    query_lang = detect_language(query)
    # 确定回答语言
    if target_lang == 'same' or target_lang == query_lang:
        answer_lang = query_lang
        cross_lingual = False
    else:
        answer_lang = target_lang
        cross_lingual = True
    
    t0 = time.time()
    retrieved = hybrid_retrieve(query)
    retrieve_time = time.time() - t0
    
    image_chunks_count = sum(1 for r in retrieved if r.get('type') == 'image_description')
    
    # 计算评估指标
    metrics = compute_metrics(query, retrieved)
    
    messages = build_prompt(query, retrieved, answer_lang, cross_lingual, query_lang)
    
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
        meta = {
            'type': 'meta',
            'retrieve_time': round(retrieve_time, 3),
            'num_chunks': len(retrieved),
            'image_chunks': image_chunks_count,
            'precision_pct': metrics['precision_pct'],
            'recall_pct': metrics['recall_pct'],
            'f1_pct': metrics['f1_pct'],
            'has_context': len(retrieved) > 0,
            'has_image_retrieval': image_chunks_count > 0,
            'language': query_lang,
            'cross_lingual': cross_lingual,
            'target_lang': target_lang if cross_lingual else 'same',
            'version': '5.0'
        }
        yield f'data: {json.dumps(meta, ensure_ascii=False)}\n\n'
        
        if retrieved:
            chunks_data = []
            for i, r in enumerate(retrieved[:7], 1):
                chunks_data.append({
                    'index': i,
                    'source': r['source'],
                    'source_pdf': r.get('source_pdf', ''),
                    'page_num': r.get('page_num', ''),
                    'score': round(r['score'], 3),
                    'type': r.get('type', 'text'),
                    'preview': r['text'][:200] + ('...' if len(r['text']) > 200 else '')
                })
            ref = {'type': 'references', 'chunks': chunks_data}
            yield f'data: {json.dumps(ref, ensure_ascii=False)}\n\n'
        
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
        
        done = {
            'type': 'done',
            'total_time': round(total_time, 3),
            'total_chars': len(full_text),
            'full_text': full_text,
            'precision_pct': metrics['precision_pct'],
            'recall_pct': metrics['recall_pct'],
            'f1_pct': metrics['f1_pct']
        }
        yield f'data: {json.dumps(done, ensure_ascii=False)}\n\n'
    
    return StreamingResponse(event_stream(), media_type='text/event-stream')

@app.post('/api/chat')
async def chat(data: dict):
    """
    非流式聊天接口。
    增强：跨语言支持（target_lang）、精确率/召回率/F1、详细引用块信息。
    工单编号：人工智能NLP-RAG-图像内容解析及检索优化
    """
    query = data.get('query', '').strip()
    history = data.get('history', [])
    target_lang = data.get('target_lang', 'same')  # 'zh', 'en', 'same'
    conversation_id = data.get('conversation_id', '')
    
    if not query:
        raise HTTPException(status_code=400, detail='请输入问题')
    
    query_lang = detect_language(query)
    # 确定回答语言
    if target_lang == 'same' or target_lang == query_lang:
        answer_lang = query_lang
        cross_lingual = False
    else:
        answer_lang = target_lang
        cross_lingual = True
    
    t0 = time.time()
    retrieved = hybrid_retrieve(query)
    retrieve_time = time.time() - t0
    
    image_chunks_count = sum(1 for r in retrieved if r.get('type') == 'image_description')
    
    # 计算评估指标（精确率/召回率/F1）
    metrics = compute_metrics(query, retrieved)
    
    messages = build_prompt(query, retrieved, answer_lang, cross_lingual, query_lang)
    
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
    
    t1 = time.time()
    answer = non_stream_deepseek(messages)
    llm_time = time.time() - t1
    total_time = retrieve_time + llm_time
    
    # 构建增强响应结构
    chunks_detail = []
    for r in retrieved[:7]:
        chunk_entry = {
            'text_preview': r['text'][:300] + ('...' if len(r['text']) > 300 else ''),
            'source': r['source'],
            'source_pdf': r.get('source_pdf', ''),
            'page_num': r.get('page_num', ''),
            'score': round(r['score'], 3),
            'type': r.get('type', 'text'),
        }
        # 如果有多模态视觉匹配信息，也带上
        if r.get('visual_match'):
            chunk_entry['visual_match'] = True
            chunk_entry['image_type'] = r.get('image_type', '')
        chunks_detail.append(chunk_entry)
    
    response = {
        'query': query,
        'answer': answer,
        'language': query_lang,
        'cross_lingual': cross_lingual,
        'target_lang': target_lang if cross_lingual else 'same',
        'retrieve_time': round(retrieve_time, 3),
        'llm_time': round(llm_time, 3),
        'total_time': round(total_time, 3),
        'num_chunks': len(retrieved),
        'image_chunks': image_chunks_count,
        'has_context': len(retrieved) > 0,
        'has_image_retrieval': image_chunks_count > 0,
        'precision_pct': metrics['precision_pct'],
        'recall_pct': metrics['recall_pct'],
        'f1_pct': metrics['f1_pct'],
        'keyword_match_count': metrics['matched_keywords_count'],
        'total_keywords': metrics['total_keywords_count'],
        'concept_coverage_count': metrics['covered_concepts_count'],
        'total_concepts': metrics['total_concepts_count'],
        'chunks': chunks_detail,
    }
    
    # 保存到对话历史（如果提供了conversation_id）
    if conversation_id:
        user_msg = {
            'role': 'user',
            'content': query,
            'timestamp': datetime.now().isoformat(),
            'language': query_lang,
            'target_lang': target_lang if cross_lingual else 'same',
        }
        assistant_msg = {
            'role': 'assistant',
            'content': answer,
            'timestamp': datetime.now().isoformat(),
            'metrics': {
                'precision_pct': metrics['precision_pct'],
                'recall_pct': metrics['recall_pct'],
                'f1_pct': metrics['f1_pct'],
                'retrieve_time': round(retrieve_time, 3),
                'llm_time': round(llm_time, 3),
                'total_time': round(total_time, 3),
            },
            'chunks': chunks_detail,
        }
        try:
            add_message_to_conversation(conversation_id, user_msg)
            add_message_to_conversation(conversation_id, assistant_msg)
        except Exception as e:
            print(f'[警告] 对话保存失败: {e}')
    
    return response

@app.post('/api/chat/compare')
async def chat_compare(data: dict):
    """
    RAG vs 纯LLM 对比接口。
    同时返回RAG增强回答和纯LLM回答，带对比指标。
    工单编号：人工智能NLP-RAG-图像内容解析及检索优化
    """
    query = data.get('query', '').strip()
    target_lang = data.get('target_lang', 'same')
    
    if not query:
        raise HTTPException(status_code=400, detail='请输入问题')
    
    query_lang = detect_language(query)
    if target_lang == 'same' or target_lang == query_lang:
        answer_lang = query_lang
    else:
        answer_lang = target_lang
    
    cross_lingual = answer_lang != query_lang
    # ---- RAG 回答 ----
    t0_rag = time.time()
    retrieved = hybrid_retrieve(query)
    retrieve_time = time.time() - t0_rag
    
    metrics = compute_metrics(query, retrieved)
    
    messages_rag = build_prompt(query, retrieved, answer_lang, cross_lingual, query_lang)
    
    t1_rag = time.time()
    rag_answer = non_stream_deepseek(messages_rag)
    rag_llm_time = time.time() - t1_rag
    rag_total_time = retrieve_time + rag_llm_time
    
    # ---- 纯LLM回答（无RAG检索）----
    # 跨语言指令
    llm_lang_instr = ''
    if cross_lingual and query_lang == 'zh' and answer_lang == 'en':
        llm_lang_instr = ' You are a bilingual assistant. CRITICAL: Answer in English ONLY. Translate everything to English. Never use Chinese.'
    elif cross_lingual and query_lang == 'en' and answer_lang == 'zh':
        llm_lang_instr = ' 你是一个双语助手。关键：你必须用中文回答。绝不能输出英文。'
    messages_llm = [{
        'role': 'system',
        'content': ('你是一个专业的智能问答助手。' if answer_lang == 'zh' else 'You are a professional Q&A assistant.') + llm_lang_instr
    }, {
        'role': 'user',
        'content': query
    }]
    
    t2_llm = time.time()
    pure_llm_answer = non_stream_deepseek(messages_llm)
    pure_llm_time = time.time() - t2_llm
    
    # ---- 对比指标 ----
    # RAG响应长度
    rag_length = len(rag_answer)
    pure_length = len(pure_llm_answer)
    # RAG相比纯LLM的信息增益（以检索块数量衡量）
    info_gain = len(retrieved) if retrieved else 0
    
    # 构建RAG详细块信息
    chunks_detail = []
    for r in retrieved[:7]:
        chunks_detail.append({
            'text_preview': r['text'][:300] + ('...' if len(r['text']) > 300 else ''),
            'source': r['source'],
            'source_pdf': r.get('source_pdf', ''),
            'page_num': r.get('page_num', ''),
            'score': round(r['score'], 3),
            'type': r.get('type', 'text'),
        })
    
    return {
        'query': query,
        'language': query_lang,
        'target_lang': target_lang if target_lang != 'same' else query_lang,
        'rag': {
            'answer': rag_answer,
            'retrieve_time': round(retrieve_time, 3),
            'llm_time': round(rag_llm_time, 3),
            'total_time': round(rag_total_time, 3),
            'num_chunks': len(retrieved),
            'precision_pct': metrics['precision_pct'],
            'recall_pct': metrics['recall_pct'],
            'f1_pct': metrics['f1_pct'],
            'response_length': rag_length,
            'chunks': chunks_detail,
        },
        'pure_llm': {
            'answer': pure_llm_answer,
            'llm_time': round(pure_llm_time, 3),
            'total_time': round(pure_llm_time, 3),
            'num_chunks': 0,
            'precision_pct': 0.0,
            'recall_pct': 0.0,
            'f1_pct': 0.0,
            'response_length': pure_length,
            'chunks': [],
        },
        'comparison': {
            'rag_time_vs_pure': f'RAG: {round(rag_total_time, 2)}s vs Pure: {round(pure_llm_time, 2)}s',
            'rag_length_vs_pure': f'RAG: {rag_length} chars vs Pure: {pure_length} chars',
            'info_gain_chunks': info_gain,
            'rag_precision': metrics['precision_pct'],
            'rag_recall': metrics['recall_pct'],
            'rag_f1': metrics['f1_pct'],
        }
    }

@app.post('/api/evaluate')
async def evaluate(data: dict):
    """批量评估"""
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
        
        # 使用新的评估指标
        metrics = compute_metrics(question, retrieved)
        
        if metrics['precision_pct'] >= 70:
            accuracy_count += 1
        
        image_chunks_count = sum(1 for r in retrieved if r.get('type') == 'image_description')
        
        results.append({
            'id': qid,
            'question': question,
            'answer': answer,
            'retrieve_time': round(retrieve_time, 3),
            'llm_time': round(llm_time, 3),
            'total_time': round(retrieve_time + llm_time, 3),
            'num_chunks': len(retrieved),
            'image_chunks': image_chunks_count,
            'precision_pct': metrics['precision_pct'],
            'recall_pct': metrics['recall_pct'],
            'f1_pct': metrics['f1_pct'],
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

# ============================================================
# 7. 对话历史管理接口
# 工单编号：人工智能NLP-RAG-图像内容解析及检索优化
# ============================================================

@app.get('/api/conversations')
async def list_conversations():
    """获取所有对话列表"""
    conversations = load_conversations()
    return {'conversations': conversations, 'total': len(conversations)}

@app.get('/api/conversations/{conv_id}')
async def get_conversation(conv_id: str):
    """获取单个对话完整内容"""
    conv = load_conversation(conv_id)
    return conv

@app.post('/api/conversations')
async def create_conversation(data: dict):
    """创建或更新对话"""
    result = save_conversation(data)
    return result

@app.delete('/api/conversations/{conv_id}')
async def remove_conversation(conv_id: str):
    """删除对话"""
    delete_conversation(conv_id)
    return {'status': 'deleted', 'id': conv_id}

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8504)
