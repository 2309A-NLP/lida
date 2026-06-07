#!python3
"""
RAG工单3 - Milvus Lite 知识库索引构建
支持双PDF文档，改进的分块策略
"""
import os, sys, json, re, time, uuid
import fitz
import numpy as np
from pymilvus import MilvusClient, DataType
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

BASE_DIR = '/mnt/d/RAG工单3'
PDFS = [
    os.path.join(BASE_DIR, '招股说明书1-无水印.pdf'),
    os.path.join(BASE_DIR, '招股说明书2-无水印.pdf'),
]
DB_PATH = os.path.join(BASE_DIR, 'milvus_data_3.db')
COLLECTION_NAME = 'rag_v3_milvus'

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
MIN_CHUNK_LEN = 30
BATCH_SIZE = 50

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
            if len(chunk) >= MIN_CHUNK_LEN:
                chunks.append(chunk)
            buffer = buffer[len(chunk):]

    if buffer.strip() and len(buffer.strip()) >= MIN_CHUNK_LEN:
        chunks.append(buffer.strip())

    if not chunks and len(text) >= MIN_CHUNK_LEN:
        start = 0
        while start < len(text):
            end = start + size
            chunk = text[start:end].strip()
            if len(chunk) >= MIN_CHUNK_LEN:
                chunks.append(chunk)
            start += size - overlap

    return chunks

def extract_text_from_pdf(pdf_path):
    """从PDF提取文本"""
    try:
        doc = fitz.open(pdf_path)
        pages = []
        for page in doc:
            text = page.get_text().strip()
            if text:
                pages.append(text)
        doc.close()
        return '\n\n'.join(pages)
    except Exception as e:
        print(f'  [错误] 读取PDF失败 {pdf_path}: {e}')
        return ''

def build_index():
    print('=' * 60)
    print('RAG工单3 - Milvus Lite 知识库索引构建')
    print('=' * 60)

    # 1) 初始化Milvus Lite客户端
    client = MilvusClient(uri=DB_PATH)
    print(f'Milvus Lite数据库: {DB_PATH}')

    # 删除旧集合
    if client.has_collection(COLLECTION_NAME):
        client.drop_collection(COLLECTION_NAME)
        print('已删除旧集合')

    # 创建集合: 384维向量, IVFFlat nlist=128
    client.create_collection(
        collection_name=COLLECTION_NAME,
        dimension=384,
        auto_id=True,
        enable_dynamic_field=True,
        metric_type="IP",
        index_params={"index_type": "IVF_FLAT", "params": {"nlist": 128}}
    )
    print(f'创建集合: {COLLECTION_NAME} (384维, IVFFlat nlist=128, IP距离)')

    # 2) 读取并分块所有PDF
    all_chunks = []
    for pdf_path in PDFS:
        fname = os.path.basename(pdf_path)
        print(f'\n正在读取: {fname}')

        if not os.path.exists(pdf_path):
            print(f'  [跳过] 文件不存在: {pdf_path}')
            continue

        text = extract_text_from_pdf(pdf_path)
        if not text:
            print(f'  [跳过] 无文本内容')
            continue

        word_count = len(text)
        chunks = chunk_text_improved(text)
        print(f'  文本长度: {word_count} 字')
        print(f'  生成分块: {len(chunks)} 块')

        for i, chunk in enumerate(chunks):
            all_chunks.append({
                'source': fname,
                'chunk_id': i,
                'text': chunk
            })

    print(f'\n总计: {len(all_chunks)} 个分块')

    # 3) 生成向量并插入Milvus
    ef = ONNXMiniLM_L6_V2()
    texts = [c['text'] for c in all_chunks]
    total = len(texts)

    print('\n开始生成向量并索引...')
    for i in range(0, total, BATCH_SIZE):
        end = min(i + BATCH_SIZE, total)
        batch_texts = texts[i:end]
        batch_chunks = all_chunks[i:end]

        # 生成向量（ONNXMiniLM_L6_V2返回list of list, 已归一化）
        embeddings = ef(batch_texts)

        # 构造插入数据
        data_to_insert = []
        for j, emb in enumerate(embeddings):
            data_to_insert.append({
                'vector': emb,
                'text': batch_chunks[j]['text'],
                'source': batch_chunks[j]['source'],
                'chunk_id': batch_chunks[j]['chunk_id']
            })

        client.insert(COLLECTION_NAME, data_to_insert)
        print(f'  进度: {end}/{total} ({100*end//total}%)')

    count = client.query(COLLECTION_NAME, output_fields=['count(*)'])
    actual_count = count[0]['count(*)'] if count else 0
    print(f'\n集合中记录数: {actual_count}')

    # 4) 保存全量文本供关键词检索
    index_data = {
        'chunks': [{'source': c['source'], 'chunk_id': c['chunk_id'], 'text': c['text']} for c in all_chunks],
        'total': len(all_chunks),
        'pdfs': PDFS
    }
    index_path = os.path.join(BASE_DIR, 'index_data.json')
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False)
    print(f'\n索引数据已保存: {index_path}')
    print('构建完成!')

    client.close()

if __name__ == '__main__':
    build_index()
