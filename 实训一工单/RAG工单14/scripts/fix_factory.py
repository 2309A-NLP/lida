import pymysql

conn = pymysql.connect(
    host='mysql', port=3306, user='root',
    password='infini_rag_flow', database='rag_flow'
)
cursor = conn.cursor()

mimo_key = 'tp-cxit9r7gak3n335w1vewzxjadh7f8d34ahecucld7514moj9'

# 改用OpenAI工厂名（Mimo兼容OpenAI接口）
cursor.execute("""
    UPDATE tenant_llm SET llm_factory='OpenAI', llm_name='mimo-v2.5-pro',
    api_key=%s, api_base='https://token-plan-cn.xiaomimimo.com/v1'
    WHERE model_type='chat'
""", (mimo_key,))
print(f"更新LLM: {cursor.rowcount} 行")

# 更新tenant
cursor.execute("UPDATE tenant SET llm_id='mimo-v2.5-pro@OpenAI'")
print(f"更新tenant: {cursor.rowcount} 行")

conn.commit()

# 验证
cursor.execute("SELECT llm_factory, model_type, llm_name, api_base FROM tenant_llm")
for row in cursor.fetchall():
    print(f"  {row}")

cursor.execute("SELECT llm_id, embd_id FROM tenant WHERE id='9e195e94654311f19aef6926720e38a2'")
print(f"  tenant: {cursor.fetchone()}")

conn.close()
print("\n完成!")
