import shutil, os

db_path = "/mnt/d/RAG工单7/milvus_v6.db"
if os.path.isdir(db_path):
    shutil.rmtree(db_path)
    print(f"Removed directory {db_path}")
elif os.path.exists(db_path):
    os.remove(db_path)
else:
    print("Already removed")
