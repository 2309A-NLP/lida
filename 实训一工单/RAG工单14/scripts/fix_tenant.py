import pymysql

conn = pymysql.connect(
    host='mysql', port=3306, user='root',
    password='infini_rag_flow', database='rag_flow'
)
cursor = conn.cursor()

# 检查tenant
cursor.execute("SELECT id, llm_id, embd_id FROM tenant")
for row in cursor.fetchall():
    print(f"  {row}")

# 更新所有tenant
cursor.execute("UPDATE tenant SET llm_id='mimo-v2.5-pro@XiaoMi'")
print(f"更新: {cursor.rowcount} 行")
conn.commit()

cursor.execute("SELECT id, llm_id, embd_id FROM tenant")
for row in cursor.fetchall():
    print(f"  {row}")

conn.close()
