import pymysql

conn = pymysql.connect(
    host='mysql',
    port=3306,
    user='root',
    password='infini_rag_flow',
    database='rag_flow'
)
cursor = conn.cursor()

# 检查api_token表
cursor.execute("SELECT tenant_id, token, dialog_id, source, beta FROM api_token")
print("=== api_token ===")
for row in cursor.fetchall():
    print(f"  tenant_id: {row[0]}")
    print(f"  token: {row[1]}")
    print(f"  dialog_id: {row[2]}")
    print(f"  source: {row[3]}")
    print(f"  beta: {row[4]}")
    print()

conn.close()
