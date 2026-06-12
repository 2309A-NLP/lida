import pymysql

conn = pymysql.connect(
    host='mysql', port=3306, user='root',
    password='infini_rag_flow', database='rag_flow'
)
cursor = conn.cursor()

# 检查当前配置
cursor.execute("SELECT llm_factory, llm_name, api_key, api_base FROM tenant_llm WHERE model_type='chat'")
row = cursor.fetchone()
print(f"当前LLM配置:")
print(f"  factory: {row[0]}")
print(f"  model: {row[1]}")
print(f"  api_key: {row[2][:15]}...")
print(f"  api_base: {row[3]}")

# 尝试改用DeepSeek作为factory（因为Mimo兼容OpenAI接口，但LiteLLM可能需要特定的factory）
# 或者检查是否有其他问题

# 检查llm_factories表中OpenAI的配置
cursor.execute("SELECT * FROM llm_factories WHERE name='OpenAI'")
row = cursor.fetchone()
print(f"\nOpenAI factory配置: {row}")

conn.close()
