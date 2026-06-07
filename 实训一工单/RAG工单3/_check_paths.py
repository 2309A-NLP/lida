import os
print('BASE_DIR exists:', os.path.isdir('/mnt/d/RAG工单/RAG工单3'))
print('PDF1:', os.path.isfile('/mnt/d/RAG工单/RAG工单3/招股说明书1-无水印.pdf'))
print('PDF2:', os.path.isfile('/mnt/d/RAG工单/RAG工单3/招股说明书2-无水印.pdf'))
print('chromadb:', os.path.isdir('/mnt/d/RAG工单/RAG工单3/chromadb_data'))
print('templates:', os.path.isfile('/mnt/d/RAG工单/RAG工单3/templates/index.html'))
print('app.py:', os.path.isfile('/mnt/d/RAG工单/RAG工单3/app.py'))
