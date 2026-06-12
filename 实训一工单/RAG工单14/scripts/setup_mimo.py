import pymysql

conn = pymysql.connect(
    host='mysql', port=3306, user='root',
    password='infini_rag_flow', database='rag_flow'
)
cursor = conn.cursor()

tenant_id = '9e195e94654311f19aef6926720e38a2'
mimo_key = 'tp-cxit9r7gak3n335w1vewzxjadh7f8d34ahecucld7514moj9'

# 1. 更新DeepSeek -> Mimo
cursor.execute("""
    UPDATE tenant_llm SET llm_factory='XiaoMi', llm_name='mimo-v2.5-pro',
    api_key=%s, api_base='https://token-plan-cn.xiaomimimo.com/v1'
    WHERE llm_factory='DeepSeek' AND model_type='chat'
""", (mimo_key,))
print(f"更新LLM: {cursor.rowcount} 行")

# 2. 更新tenant默认模型
cursor.execute("""
    UPDATE tenant SET llm_id='mimo-v2.5-pro@XiaoMi'
    WHERE id=%s
""", (tenant_id,))
print(f"更新tenant: {cursor.rowcount} 行")

conn.commit()

# 验证
cursor.execute("SELECT llm_factory, model_type, llm_name, api_base FROM tenant_llm")
for row in cursor.fetchall():
    print(f"  {row}")

cursor.execute("SELECT llm_id, embd_id FROM tenant WHERE id=%s", (tenant_id,))
print(f"  tenant: {cursor.fetchone()}")

conn.close()
print("\n完成!")
