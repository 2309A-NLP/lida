# ⚖️ 法小助 - 法律数字人咨询系统

## 项目说明
基于 Linly-Talker 数字人框架 + RAG 法律知识检索的法律咨询系统。

## 已收录法律（9部）
- 中华人民共和国民法典
- 中华人民共和国刑法
- 中华人民共和国劳动法
- 中华人民共和国劳动合同法
- 中华人民共和国消费者权益保护法
- 中华人民共和国公司法
- 中华人民共和国道路交通安全法
- 中华人民共和国社会保险法
- 中华人民共和国治安管理处罚法

## 启动方式

### 轻量版（纯文本，无需GPU）
```bash
cd D:\数字机器人\Linly-Talker
python legal_app.py
# 访问 http://localhost:7860
```

### 完整版（含数字人形象，需GPU）
```bash
cd D:\数字机器人\Linly-Talker
python webui.py
```

## 配置API Key（建议）
如果配置了 OpenAI API Key，回答会更准确：
```bash
set OPENAI_API_KEY=your_key_here
python legal_app.py
```

## 法律知识库维护
知识库文件在 `legal_kb/` 目录，可自行添加法律文本（.txt格式，需包含"第X条"格式）。

## 免责声明
本系统提供的法律信息仅供参考，不构成正式法律意见。如涉及重大法律事务，请咨询专业律师或拨打 12348 法律服务热线。