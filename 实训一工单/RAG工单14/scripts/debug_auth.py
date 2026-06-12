import pymysql

conn = pymysql.connect(
    host='mysql',
    port=3306,
    user='root',
    password='infini_rag_flow',
    database='rag_flow'
)
cursor = conn.cursor()

# 检查用户
cursor.execute("SELECT id, email, status FROM user")
print("=== users ===")
for row in cursor.fetchall():
    print(f"  {row}")

# 检查api_token
cursor.execute("SELECT tenant_id, token FROM api_token")
print("\n=== api_token ===")
for row in cursor.fetchall():
    print(f"  {row}")

# 检查knowledgebase
cursor.execute("SELECT id, name, tenant_id, status FROM knowledgebase")
print("\n=== knowledgebase ===")
for row in cursor.fetchall():
    print(f"  {row}")

conn.close()
