import pymysql

conn = pymysql.connect(
    host='mysql',
    port=3306,
    user='root',
    password='infini_rag_flow',
    database='rag_flow'
)
cursor = conn.cursor()

# 获取用户的access_token
cursor.execute("SELECT id, email, access_token FROM user WHERE email='admin@ragflow.io'")
row = cursor.fetchone()
if row:
    print(f"user_id: {row[0]}")
    print(f"email: {row[1]}")
    print(f"access_token: {row[2]}")
    
    # 如果没有token，生成一个
    if not row[2]:
        import uuid
        token = str(uuid.uuid4()).replace('-', '')
        cursor.execute("UPDATE user SET access_token=%s WHERE id=%s", (token, row[0]))
        conn.commit()
        print(f"新token: {token}")

conn.close()
