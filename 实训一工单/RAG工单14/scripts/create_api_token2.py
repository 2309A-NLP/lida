import pymysql
import uuid

conn = pymysql.connect(
    host='mysql',
    port=3306,
    user='root',
    password='infini_rag_flow',
    database='rag_flow'
)
cursor = conn.cursor()

# 检查api_token表结构
cursor.execute("DESCRIBE api_token")
print("=== api_token 表结构 ===")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

# 创建API token
tenant_id = '9e195e94654311f19aef6926720e38a2'
token = str(uuid.uuid4()).replace('-', '')

cursor.execute("""
    INSERT INTO api_token (create_time, create_date, update_time, update_date, 
        tenant_id, token)
    VALUES (NOW(), NOW(), NOW(), NOW(), %s, %s)
""", (tenant_id, token))
conn.commit()
print(f"\n创建API token: {token}")

# 验证
cursor.execute("SELECT tenant_id, token FROM api_token")
for row in cursor.fetchall():
    print(f"  {row}")

conn.close()
