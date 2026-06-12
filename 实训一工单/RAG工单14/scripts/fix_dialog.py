import pymysql

conn = pymysql.connect(
    host='mysql', port=3306, user='root',
    password='infini_rag_flow', database='rag_flow'
)
cursor = conn.cursor()

# 检查dialog表
cursor.execute("SELECT id, name, llm_id FROM dialog")
print("=== dialog ===")
for row in cursor.fetchall():
    print(f"  {row}")

# 更新dialog的llm_id
cursor.execute("UPDATE dialog SET llm_id='mimo-v2.5-pro@OpenAI' WHERE llm_id LIKE '%DeepSeek%'")
print(f"\n更新dialog: {cursor.rowcount} 行")

conn.commit()

cursor.execute("SELECT id, name, llm_id FROM dialog")
print("\n=== 更新后 ===")
for row in cursor.fetchall():
    print(f"  {row}")

conn.close()
