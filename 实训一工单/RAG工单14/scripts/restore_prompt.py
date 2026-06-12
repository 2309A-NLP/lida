import pymysql, json

conn = pymysql.connect(
    host='mysql', port=3306, user='root',
    password='infini_rag_flow', database='rag_flow'
)
cursor = conn.cursor()

# 恢复prompt_config
prompt_config = {
    "empty_response": "Sorry! No relevant content was found in the knowledge base!",
    "parameters": [{"key": "knowledge", "optional": False}],
    "prologue": "Hi! I'm your assistant. What can I do for you?",
    "quote": True,
    "refine_multiturn": True,
    "system": "You are an intelligent assistant. Please summarize the content of the dataset to answer the question. Please list the data in the dataset and answer in detail. When all dataset content is irrelevant to the question, your answer must include the sentence \"The answer you are looking for is not found in the dataset!\" Answers need to consider chat history.\n      Here is the knowledge base:\n      {knowledge}\n      The above is the knowledge base.",
    "tts": False
}

cursor.execute("""
    UPDATE dialog SET prompt_type='simple', prompt_config=%s
    WHERE id='4672a448658911f19aef6926720e38a2'
""", (json.dumps(prompt_config),))
print(f"恢复prompt: {cursor.rowcount} 行")

# 也更新similarity_threshold
cursor.execute("""
    UPDATE dialog SET similarity_threshold=0.01
    WHERE id='4672a448658911f19aef6926720e38a2'
""")
print(f"更新threshold: {cursor.rowcount} 行")

conn.commit()
conn.close()
print("完成!")
