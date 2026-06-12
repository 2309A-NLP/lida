import pymysql

conn = pymysql.connect(
    host='mysql',
    port=3306,
    user='root',
    password='infini_rag_flow',
    database='rag_flow'
)
cursor = conn.cursor()

# 1. 检查tenant_llm表结构
cursor.execute("DESCRIBE tenant_llm")
print("=== tenant_llm 表结构 ===")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

# 2. 检查现有数据
cursor.execute("SELECT * FROM tenant_llm LIMIT 5")
print("\n=== tenant_llm 数据 ===")
for row in cursor.fetchall():
    print(f"  {row}")

# 3. 检查tenant表
cursor.execute("SELECT id, name, llm_id, embd_id FROM tenant LIMIT 5")
print("\n=== tenant 数据 ===")
for row in cursor.fetchall():
    print(f"  {row}")

# 4. 检查knowledgebase表
cursor.execute("SELECT id, name, parser_id, embd_id FROM knowledgebase LIMIT 5")
print("\n=== knowledgebase 数据 ===")
for row in cursor.fetchall():
    print(f"  {row}")

conn.close()
