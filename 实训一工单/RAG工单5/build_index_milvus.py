"""
工单编号：人工智能NLP-RAG-Query理解优化任务
RAG工单5 - 双PDF向量索引构建（Milvus存储，含来源文件和页码信息）
"""
import os, json, re, uuid, fitz, jieba
from pymilvus import MilvusClient, DataType
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

BASE_DIR = '/mnt/d/RAG工单/RAG工单5'
PDFS = [
    os.path.join(BASE_DIR, '招股说明书1-无水印.pdf'),
    os.path.join(BASE_DIR, '招股说明书2--无水印.pdf'),
]
MILVUS_PATH = os.path.join(BASE_DIR, 'milvus_data_5.db')
INDEX_PATH = os.path.join(BASE_DIR, 'index_data_5.json')
COLLECTION_NAME = 'rag_v5_milvus'
DIMENSION = 384

jieba.setLogLevel(20)
embed_fn = ONNXMiniLM_L6_V2()

def extract_chunks_with_metadata(pdf_path, size=1000, overlap=200):
    """提取PDF内容并分块，每块记录来源文件名和页码范围"""
    doc = fitz.open(pdf_path)
    basename = os.path.basename(pdf_path)
    chunks_with_meta = []

    for page_num, page in enumerate(doc, 1):
        text = page.get_text().strip()
        if not text or len(text) < 30:
            continue
        
        # 对本页文本分块
        sections = re.split(r'(第[一二三四五六七八九十]+[章节部篇]|(?<=\n)[一二三四五六七八九十]+[、．.][^\n]{2,50}\n)', text)
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
                    chunks_with_meta.append({
                        'text': chunk,
                        'source': basename,
                        'page': page_num,
                        'type': 'text',
                    })
                buffer = buffer[len(chunk):]
        if buffer.strip() and len(buffer.strip()) >= 30:
            chunks_with_meta.append({
                'text': buffer.strip(),
                'source': basename,
                'page': page_num,
                'type': 'text',
            })
    
    doc.close()
    return chunks_with_meta

def build_index():
    print('[开始构建索引 (Milvus) - 含来源文件和页码信息...]')
    
    all_chunks = []
    for pdf_path in PDFS:
        if os.path.exists(pdf_path):
            chunks = extract_chunks_with_metadata(pdf_path)
            all_chunks.extend(chunks)
            print(f'  {os.path.basename(pdf_path)}: {len(chunks)} 块')
    
    print(f'  总分块: {len(all_chunks)} 块')
    
    # 计算向量
    print('  计算向量嵌入...')
    all_vectors = []
    texts = [c['text'] for c in all_chunks]
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        batch_vectors = embed_fn(batch)
        all_vectors.extend(batch_vectors)
        print(f'    已处理 {min(i+batch_size, len(texts))}/{len(texts)}')
    
    # 初始化 Milvus Lite
    client = MilvusClient(MILVUS_PATH)
    
    if client.has_collection(COLLECTION_NAME):
        client.drop_collection(COLLECTION_NAME)
    
    schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=True)
    schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
    schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=DIMENSION)
    schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="source", datatype=DataType.VARCHAR, max_length=100)
    schema.add_field(field_name="page", datatype=DataType.INT32)
    schema.add_field(field_name="type", datatype=DataType.VARCHAR, max_length=50)
    
    index_params = client.prepare_index_params()
    index_params.add_index(field_name="vector", index_type="IVF_FLAT", metric_type="IP", params={"nlist": 128})
    client.create_collection(collection_name=COLLECTION_NAME, schema=schema, index_params=index_params)
    
    # 插入数据
    print('  插入向量数据...')
    data = []
    for i, (chunk, vec) in enumerate(zip(all_chunks, all_vectors)):
        data.append({
            'vector': vec.tolist() if hasattr(vec, 'tolist') else vec,
            'text': chunk['text'],
            'source': chunk['source'],
            'page': chunk['page'],
            'type': 'text',
        })
    
    for i in range(0, len(data), 100):
        batch = data[i:i+100]
        client.insert(collection_name=COLLECTION_NAME, data=batch)
    
    client.flush(COLLECTION_NAME)
    client.load_collection(COLLECTION_NAME)
    count_res = client.query(collection_name=COLLECTION_NAME, output_fields=["count(*)"], limit=1)
    count = count_res[0]['count(*)'] if count_res else 0
    print(f'  [索引构建完成] {len(all_chunks)} 块, Milvus 记录数: {count}')
    
    # 保存全量文本用于关键词检索（含元数据）
    index_data = {
        'chunks': [{'text': c['text'], 'source': c['source'], 'page': c['page']} for c in all_chunks],
        'count': len(all_chunks)
    }
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    print(f'  [完成] 索引文件: {MILVUS_PATH}')
    print('[构建完成]')

if __name__ == '__main__':
    build_index()
