import pymysql
import time

conn = pymysql.connect(
    host='mysql',
    port=3306,
    user='root',
    password='infini_rag_flow',
    database='rag_flow'
)
cursor = conn.cursor()

tenant_id = '9e195e94654311f1a9e5a38200189c7a'
kb_id = '4320936a657311f19aef6926720e38a2'
now = int(time.time() * 1000)

# 1. 添加DeepSeek LLM
print("[1] 添加DeepSeek LLM...")
cursor.execute("""
    INSERT INTO tenant_llm (create_time, create_date, update_time, update_date, 
        tenant_id, llm_factory, model_type, llm_name, api_key, api_base, max_tokens, used_tokens, status)
    VALUES (NOW(), NOW(), NOW(), NOW(), %s, 'DeepSeek', 'chat', 'deepseek-chat', %s, 'https://api.deepseek.com/v1', 8192, 0, '1')
""", (tenant_id, 'sk-ef1031a'))
print(f"  影响行数: {cursor.rowcount}")

# 2. 添加LocalAI Embedding
print("[2] 添加LocalAI Embedding...")
cursor.execute("""
    INSERT INTO tenant_llm (create_time, create_date, update_time, update_date, 
        tenant_id, llm_factory, model_type, llm_name, api_key, api_base, max_tokens, used_tokens, status)
    VALUES (NOW(), NOW(), NOW(), NOW(), %s, 'LocalAI', 'embedding', 'bge-m3', 'not-needed', 'http://host.docker.internal:11434/v1', 8192, 0, '1')
""", (tenant_id,))
print(f"  影响行数: {cursor.rowcount}")

# 3. 更新tenant默认模型
print("[3] 更新tenant默认模型...")
cursor.execute("""
    UPDATE tenant SET llm_id='deepseek-chat@DeepSeek', embd_id='bge-m3@LocalAI' 
    WHERE id=%s
""", (tenant_id,))
print(f"  影响行数: {cursor.rowcount}")

# 4. 更新knowledgebase的embedding模型
print("[4] 更新knowledgebase的embedding模型...")
cursor.execute("""
    UPDATE knowledgebase SET embd_id='bge-m3@LocalAI' 
    WHERE id=%s
""", (kb_id,))
print(f"  影响行数: {cursor.rowcount}")

conn.commit()

# 验证
print("\n=== 验证 ===")
cursor.execute("SELECT tenant_id, llm_factory, model_type, llm_name, api_base FROM tenant_llm")
for row in cursor.fetchall():
    print(f"  {row}")

cursor.execute("SELECT id, llm_id, embd_id FROM tenant WHERE id=%s", (tenant_id,))
for row in cursor.fetchall():
    print(f"  tenant: {row}")

cursor.execute("SELECT id, name, embd_id FROM knowledgebase WHERE id=%s", (kb_id,))
for row in cursor.fetchall():
    print(f"  kb: {row}")

conn.close()
print("\n完成!")
