import pymysql
import uuid
import time

conn = pymysql.connect(
    host='mysql',
    port=3306,
    user='root',
    password='infini_rag_flow',
    database='rag_flow'
)
cursor = conn.cursor()

# 检查api_token表
cursor.execute("SHOW TABLES LIKE 'api_token'")
print(f"api_token表: {cursor.fetchone()}")

# 检查是否有api_token表
cursor.execute("SHOW TABLES")
tables = [t[0] for t in cursor.fetchall()]
print(f"所有表: {tables}")

# 如果有api_token表，检查结构
if 'api_token' in tables:
    cursor.execute("DESCRIBE api_token")
    print("\n=== api_token 表结构 ===")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")
    
    # 创建API token
    tenant_id = '9e195e94654311f19aef6926720e38a2'
    token = str(uuid.uuid4()).replace('-', '')
    
    cursor.execute("""
        INSERT INTO api_token (create_time, create_date, update_time, update_date, 
            tenant_id, token, name, status)
        VALUES (NOW(), NOW(), NOW(), NOW(), %s, %s, 'default', '1')
    """, (tenant_id, token))
    conn.commit()
    print(f"\n创建API token: {token}")

conn.close()
