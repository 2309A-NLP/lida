import pymysql

conn = pymysql.connect(
    host='mysql', port=3306, user='root',
    password='infini_rag_flow', database='rag_flow'
)
cursor = conn.cursor()

# 检查tenant_llm
cursor.execute("SELECT llm_factory, model_type, llm_name, api_base FROM tenant_llm")
print("=== tenant_llm ===")
for row in cursor.fetchall():
    print(f"  {row}")

# 检查llm_factories表
cursor.execute("SELECT * FROM llm_factories LIMIT 20")
print("\n=== llm_factories ===")
for row in cursor.fetchall():
    print(f"  {row}")

conn.close()
