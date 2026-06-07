"""
RAG工单6 v3 - 全模型向量索引构建工具
为 bge_small_zh / bge_m3 / m3e 三个模型分别构建索引
"""
import os, sys, json, time

BASE_DIR = '/mnt/d/RAG工单/RAG工单6'
INDEX_PATH = os.path.join(BASE_DIR, 'index_data_v6.json')
MILVUS_PATH = os.path.join(BASE_DIR, 'milvus_v6.db')

os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')

from pymilvus import MilvusClient, DataType

# 模型定义
EMBEDDING_MODELS = [
    {'id': 'bge_small_zh', 'dim': 512, 'load_fn': 'fastembed', 'path': None},
    {'id': 'bge_m3',       'dim': 1024, 'load_fn': 'sentence_transformers', 'path': '/mnt/d/BGE-M3'},
    {'id': 'm3e',          'dim': 768, 'load_fn': 'sentence_transformers', 'path': '/mnt/d/M3E-base/NLP专高2日周月考附件 m3e-base/m3e-base'},
]
MODEL_COLLECTIONS = {
    'bge_small_zh': 'docs_v6_bge',
    'bge_m3': 'docs_v6_bgem3',
    'm3e': 'docs_v6_m3e',
}


def load_chunks():
    if not os.path.exists(INDEX_PATH):
        print(f'[错误] index_data_v6.json 不存在: {INDEX_PATH}')
        print('请先用原版 build_index_v6.py 进行PDF分块')
        sys.exit(1)
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    print(f'[加载] {len(chunks)} 个文本块')
    return chunks


def get_encoder(model_info):
    """根据模型类型加载对应的编码器"""
    mid = model_info['id']
    print(f'[模型] 加载 {mid} ({model_info["dim"]}维)...')
    t0 = time.time()

    if model_info['load_fn'] == 'fastembed':
        os.environ.setdefault('HF_HUB_OFFLINE', '1')
        os.environ.setdefault('HUGGINGFACE_HUB_CACHE', os.path.expanduser('~/.cache/fastembed'))
        from fastembed import TextEmbedding
        model = TextEmbedding(
            model_name="BAAI/bge-small-zh-v1.5", max_length=512,
            cache_dir=os.path.expanduser('~/.cache/fastembed')
        )

        def encode(texts):
            all_vecs = []
            batch_size = 32
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                for vec in model.embed(batch):
                    all_vecs.append(list(vec))
                print(f'  [{mid}] 已编码 {min(i + batch_size, len(texts))}/{len(texts)}', end='\r')
            print()
            return all_vecs

    else:
        from sentence_transformers import SentenceTransformer
        print(f'  加载本地模型 {model_info["path"]}')
        model = SentenceTransformer(model_info['path'], device='cpu')
        if mid == 'bge_m3':
            model.max_seq_length = 8192

        def encode(texts):
            batch_size = 8  # smaller batches for ST models
            all_vecs = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                vecs = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
                all_vecs.extend(vecs.tolist())
                print(f'  [{mid}] 已编码 {min(i + batch_size, len(texts))}/{len(texts)}', end='\r')
            print()
            return all_vecs

    print(f'  [加载完成] {time.time() - t0:.1f}s')
    return encode


def ensure_collection(client, collection_name, dim):
    if client.has_collection(collection_name):
        client.drop_collection(collection_name)
        print(f'  [删除旧集合] {collection_name}')

    schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=True)
    schema.add_field(field_name="chunk_id", datatype=DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field(field_name="pdf", datatype=DataType.VARCHAR, max_length=200)
    schema.add_field(field_name="page", datatype=DataType.INT64)
    schema.add_field(field_name="section", datatype=DataType.VARCHAR, max_length=200)
    index_params = client.prepare_index_params()
    index_params.add_index(field_name="vector", index_type="IVF_FLAT", metric_type="IP", params={"nlist": 128})
    client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)
    print(f'  [创建集合] {collection_name} (dim={dim})')


def build_index(model_id: str):
    print(f'\n{"=" * 60}')
    print(f'  构建 {model_id} 索引')
    print(f'{"=" * 60}')

    model_info = next((m for m in EMBEDDING_MODELS if m['id'] == model_id), None)
    if not model_info:
        print(f'[错误] 未知模型: {model_id}')
        return False

    collection_name = MODEL_COLLECTIONS[model_id]
    chunks = load_chunks()

    client = MilvusClient(MILVUS_PATH)
    ensure_collection(client, collection_name, model_info['dim'])

    encode_fn = get_encoder(model_info)

    texts = [c['text'] for c in chunks]
    print(f'[编码] 计算 {len(texts)} 个文本的向量...')
    t0 = time.time()
    vectors = encode_fn(texts)
    encode_time = time.time() - t0
    print(f'[编码完成] {encode_time:.1f}s (avg {encode_time/len(vectors):.3f}s/块)')

    # 批量插入
    batch_size = 50
    total = len(chunks)
    for i in range(0, total, batch_size):
        batch_data = []
        for j in range(i, min(i + batch_size, total)):
            batch_data.append({
                'text': chunks[j]['text'],
                'vector': vectors[j],
                'pdf': chunks[j].get('pdf', ''),
                'page': chunks[j].get('page', 0),
                'section': chunks[j].get('section', ''),
            })
        client.insert(collection_name=collection_name, data=batch_data)
        print(f'  [插入] {min(i + batch_size, total)}/{total}', end='\r')
    print()

    client.flush(collection_name)
    print(f'  [刷新完成] {collection_name}')

    # 验证
    stats = client.query(collection_name=collection_name, output_fields=['chunk_id'], limit=10000)
    print(f'  [验证] {len(stats)} 个向量已存入 {collection_name}')
    client.load_collection(collection_name)
    print(f'  [已加载] {collection_name} 可查询')

    return True


if __name__ == '__main__':
    if len(sys.argv) > 1:
        model_ids = sys.argv[1:]
    else:
        model_ids = ['bge_small_zh', 'bge_m3', 'm3e']

    for mid in model_ids:
        if mid not in MODEL_COLLECTIONS:
            print(f'[跳过] 未知模型: {mid}')
            continue
        build_index(mid)
        print()

    print('=' * 60)
    print('  全部索引构建完成')
    print('=' * 60)
