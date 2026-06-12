import pymysql

conn = pymysql.connect(
    host='mysql', port=3306, user='root',
    password='infini_rag_flow', database='rag_flow'
)
cursor = conn.cursor()

# 改用 mimo-v2.5（不带pro，可能不返回reasoning_content）
cursor.execute("""
    UPDATE tenant_llm SET llm_name='mimo-v2.5'
    WHERE model_type='chat'
""")
print(f"更新模型: {cursor.rowcount} 行")

cursor.execute("""
    UPDATE dialog SET llm_id='mimo-v2.5@OpenAI'
""")
print(f"更新dialog: {cursor.rowcount} 行")

cursor.execute("""
    UPDATE tenant SET llm_id='mimo-v2.5@OpenAI'
""")
print(f"更新tenant: {cursor.rowcount} 行")

conn.commit()
conn.close()
print("完成!")
