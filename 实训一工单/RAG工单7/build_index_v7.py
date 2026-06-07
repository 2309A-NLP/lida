"""RAG工单7 - Milvus多PDF金融年报索引构建
使用 BAAI/bge-small-zh-v1.5 中文嵌入模型
分块策略: 600字窗口 + 200重叠
从 pdf/ 目录读取所有PDF文件
"""
import os, json, re, time
import fitz
from pymilvus import MilvusClient, DataType
from fastembed import TextEmbedding

BASE_DIR = '/mnt/d/RAG工单/RAG工单7'
PDF_DIR = os.path.join(BASE_DIR, 'pdf')
MILVUS_PATH = os.path.join(BASE_DIR, 'milvus_v7.db')
INDEX_PATH = os.path.join(BASE_DIR, 'index_data_v7.json')
COLLECTION_NAME = 'docs_v7'
EMBED_DIM = 512
CHUNK_SIZE = 600
CHUNK_OVERLAP = 200

embed_fn = TextEmbedding(model_name="BAAI/bge-small-zh-v1.5", max_length=512)

SECTION_PATTERNS = [
    r'^第[一二三四五六七八九十百千]+[章节编部篇]',
    r'^第\d+[章节编部篇]',
    r'^[一二三四五六七八九十]+[、．.]',
    r'^（[一二三四五六七八九十]+）',
    r'^\([一二三四五六七八九十]+\)',
    r'^\d+[、．.]',
    r'^[A-Z]\.[\s]',
    r'^[0-9]+\.[0-9]+',
    r'^[1-9]\d{0,2}\.\s',
    r'^【',
    r'^（\d+）',
    r'^[\(（]\d+[\)）]',
]

def is_section_start(text: str) -> bool:
    text = text.strip()
    if len(text) > 80:
        return False
    for p in SECTION_PATTERNS:
        if re.match(p, text):
            return True
    return False

def extract_text_from_pdf(pdf_path: str) -> list:
    doc = fitz.open(pdf_path)
    pdf_name = os.path.basename(pdf_path)
    pages = []
    for page_num, page in enumerate(doc, 1):
        text = page.get_text().strip()
        if text:
            pages.append({'pdf': pdf_name, 'page': page_num, 'text': text})
    doc.close()
    return pages

def chunk_text(pages: list) -> list:
    chunks = []
    chunk_id = 0
    buffer = ''
    current_section = ''
    current_page = 1
    current_pdf = ''

    for page in pages:
        pdf_name = page['pdf']
        page_num = page['page']
        text = page['text']

        if pdf_name != current_pdf:
            if buffer.strip():
                chunks.append({
                    'id': chunk_id,
                    'pdf': current_pdf,
                    'page': current_page,
                    'section': current_section,
                    'text': buffer.strip()
                })
                chunk_id += 1
            buffer = ''
            current_pdf = pdf_name
            current_page = page_num
            current_section = ''

        if page_num != current_page:
            if buffer.strip():
                chunks.append({
                    'id': chunk_id,
                    'pdf': current_pdf,
                    'page': current_page,
                    'section': current_section,
                    'text': buffer.strip()
                })
                chunk_id += 1
                buffer = ''
            current_page = page_num

        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if is_section_start(line):
                current_section = line[:100]
            buffer += line + '\n'

            if len(buffer) > CHUNK_SIZE:
                chunks.append({
                    'id': chunk_id,
                    'pdf': current_pdf,
                    'page': current_page,
                    'section': current_section,
                    'text': buffer.strip()
                })
                chunk_id += 1
                # 取最后 CHUNK_OVERLAP 字作为重叠
                overlap_start = max(0, len(buffer) - CHUNK_OVERLAP)
                buffer = buffer[overlap_start:]

    if buffer.strip():
        chunks.append({
            'id': chunk_id,
            'pdf': current_pdf,
            'page': current_page,
            'section': current_section,
            'text': buffer.strip()
        })
    return chunks

def init_milvus():
    client = MilvusClient(MILVUS_PATH)
    index_params = client.prepare_index_params()
    index_params.add_index(field_name="embedding", index_type="IVF_FLAT", metric_type="IP", params={"nlist": 128})

    if client.has_collection(COLLECTION_NAME):
        client.drop_collection(COLLECTION_NAME)

    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=True)
    schema.add_field(field_name="chunk_id", datatype=DataType.INT64, is_primary=True)
    schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=EMBED_DIM)
    schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="pdf", datatype=DataType.VARCHAR, max_length=200)
    schema.add_field(field_name="page", datatype=DataType.INT64)
    schema.add_field(field_name="section", datatype=DataType.VARCHAR, max_length=200)

    client.create_collection(collection_name=COLLECTION_NAME, schema=schema, index_params=index_params)
    client.load_collection(COLLECTION_NAME)
    return client

def compute_embeddings(texts: list) -> list:
    """bge-small-zh-v1.5 outputs normalized vectors by default"""
    vecs = list(embed_fn.embed(texts))
    import numpy as np
    arr = np.array(vecs, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    arr = arr / norms
    return arr.tolist()

def main():
    print('[构建索引] 开始...')
    print(f'  嵌入模型: BAAI/bge-small-zh-v1.5 ({EMBED_DIM}维)')
    print(f'  分块策略: {CHUNK_SIZE}字窗口 + {CHUNK_OVERLAP}重叠')
    t0 = time.time()

    all_pages = []
    pdfs = [f for f in os.listdir(PDF_DIR) if f.endswith('.pdf')]
    for pdf_name in sorted(pdfs):
        pdf_path = os.path.join(PDF_DIR, pdf_name)
        print(f'  提取: {pdf_name}')
        pages = extract_text_from_pdf(pdf_path)
        all_pages.extend(pages)
        print(f'    → {len(pages)} 页')

    print(f'\n[分块] 总共 {len(all_pages)} 页...')
    chunks = chunk_text(all_pages)
    print(f'  → {len(chunks)} 个文本块')

    meta = []
    for c in chunks:
        meta.append({
            'id': c['id'],
            'pdf': c['pdf'],
            'page': c['page'],
            'section': c['section'],
            'text': c['text'][:200],
        })
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f'  元数据已保存到 {INDEX_PATH}')

    print(f'\n[Milvus] 初始化向量库 (dim={EMBED_DIM})...')
    client = init_milvus()
    print(f'  集合 {COLLECTION_NAME} 已创建')

    texts = [c['text'] for c in chunks]
    BATCH = 32
    total = len(texts)
    inserted = 0

    for i in range(0, total, BATCH):
        batch_texts = texts[i:i + BATCH]
        batch_chunks = chunks[i:i + BATCH]
        batch_vecs = compute_embeddings(batch_texts)
        entities = []
        for j, c in enumerate(batch_chunks):
            entities.append({
                'chunk_id': c['id'],
                'embedding': batch_vecs[j],
                'text': c['text'],
                'pdf': c['pdf'],
                'page': c['page'],
                'section': c.get('section', ''),
            })
        client.insert(COLLECTION_NAME, entities)
        inserted += len(entities)
        print(f'  进度: {inserted}/{total}', end='\r')

    client.flush(COLLECTION_NAME)
    print(f'\n  全部 {inserted} 条向量已写入并刷盘')

    elapsed = time.time() - t0
    print(f'\n[完成] 耗时 {elapsed:.1f}s')
    print(f'  Milvus DB: {MILVUS_PATH}')
    stats = client.query(collection_name=COLLECTION_NAME, output_fields=['chunk_id'], limit=10000)
    print(f'  总文档数: {len(stats)}')

if __name__ == '__main__':
    main()
