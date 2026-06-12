import pymysql
import os

# 读取DeepSeek key
deepseek_key = ""
with open(os.path.expanduser('~/.hermes/.env')) as f:
    for line in f:
        if line.startswith('DEEPSEEK_API_KEY='):
            deepseek_key = line.strip().split('=', 1)[1]
            break

print(f"DeepSeek key: {deepseek_key[:15]}...")

conn = pymysql.connect(
    host='mysql',
    port=3306,
    user='root',
    password='infini_rag_flow',
    database='rag_flow'
)
cursor = conn.cursor()

# 更新DeepSeek API key
cursor.execute("""
    UPDATE tenant_llm SET api_key=%s 
    WHERE llm_factory='DeepSeek' AND model_type='chat'
""", (deepseek_key,))
print(f"更新DeepSeek key: {cursor.rowcount} 行")

conn.commit()

# 验证
cursor.execute("SELECT llm_factory, model_type, llm_name, api_key FROM tenant_llm")
for row in cursor.fetchall():
    print(f"  {row[0]} {row[1]}: {row[2]} key={row[3][:15]}...")

conn.close()
