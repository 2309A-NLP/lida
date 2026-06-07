#!python3
"""
RAG工单3 - 知识库索引构建
支持双PDF文档，改进的分块策略
"""
import os, sys, json, re, time, uuid
import fitz
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

BASE_DIR = '/mnt/d/RAG工单3'
PDFS = [
    os.path.join(BASE_DIR, '招股说明书1-无水印.pdf'),
    os.path.join(BASE_DIR, '招股说明书2-无水印.pdf'),
]
DB_PATH = os.path.join(BASE_DIR, 'chromadb_data')
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
MIN_CHUNK_LEN = 30

def chunk_text_improved(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """改进分块：按段落感知分块"""
    # 按章节标题分块
    sections = re.split(r'(第[一二三四五六七八九十]+[章节部篇]|(?<=\n)[一二三四五六七八九十]+[、．.][^\n]{2,50}\n)', text)
    
    chunks = []
    buffer = ''
    for piece in sections:
        if not piece or len(piece.strip()) < 10:
            continue
        buffer += piece
        while len(buffer) >= size:
            chunk = buffer[:size]
            # 在合理位置切断（句号、换行）
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
    
    # 如果没有合理分块，回退到滑动窗口
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
    print('RAG工单3 - 知识库索引构建')
    print('=' * 60)
    
    # 1) 读取并分块所有PDF
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
    
    # 2) 写入索引
    client = PersistentClient(path=DB_PATH)
    
    # 删除旧集合
    try:
        client.delete_collection('rag')
        print('已删除旧集合')
    except:
        pass
    
    ef = ONNXMiniLM_L6_V2()
    col = client.create_collection(name='rag', embedding_function=ef)
    
    batch_size = 50
    texts = [c['text'] for c in all_chunks]
    ids = [str(uuid.uuid4()) for _ in all_chunks]
    metadatas = [{'source': c['source'], 'chunk_id': c['chunk_id']} for c in all_chunks]
    
    for i in range(0, len(texts), batch_size):
        end = min(i + batch_size, len(texts))
        col.add(
            ids=ids[i:end],
            documents=texts[i:end],
            metadatas=metadatas[i:end]
        )
        print(f'  索引进度: {end}/{len(texts)} ({100*end//len(texts)}%)')
    
    # 3) 保存全量文本供关键词检索
    index_data = {
        'chunks': [{'source': c['source'], 'chunk_id': c['chunk_id'], 'text': c['text']} for c in all_chunks],
        'total': len(all_chunks),
        'pdfs': PDFS
    }
    index_path = os.path.join(BASE_DIR, 'index_data.json')
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False)
    print(f'\n索引数据已保存: {index_path}')
    print(f'集合中记录数: {col.count()}')
    print('\n构建完成!')

if __name__ == '__main__':
    build_index()
