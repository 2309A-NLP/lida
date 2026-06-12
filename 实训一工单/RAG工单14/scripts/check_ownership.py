import pymysql

conn = pymysql.connect(
    host='mysql',
    port=3306,
    user='root',
    password='infini_rag_flow',
    database='rag_flow'
)
cursor = conn.cursor()

# 检查dataset的tenant_id
cursor.execute("SELECT id, name, tenant_id FROM knowledgebase")
print("=== knowledgebase ===")
for row in cursor.fetchall():
    print(f"  {row}")

# 检查api_token的tenant_id
cursor.execute("SELECT tenant_id, token FROM api_token")
print("\n=== api_token ===")
for row in cursor.fetchall():
    print(f"  {row}")

# 检查user_tenant
cursor.execute("SELECT user_id, tenant_id, role FROM user_tenant")
print("\n=== user_tenant ===")
for row in cursor.fetchall():
    print(f"  {row}")

conn.close()
