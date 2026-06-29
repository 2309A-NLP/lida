# 招股书 PDF 数据问答智能体

本项目按照需求文档 `requirements.pdf` 实现招股书 PDF 数据问答任务，提供以下交付内容：

- 自动拉取知识库数据集
- 基于招股书文本构建本地知识库
- 使用 RAG 完成单题和批量问答
- 输出符合验收要求的 `jsonl` 结果文件
- 提供 CLI 与 HTTP API 两种使用方式
- 提供实现步骤与问题记录文档

## 工单编号

`人工智能NLP-Agent数字人项目-招股书数据问答智能体任务`

## 当前实现范围

需求 PDF 聚焦“招股书数据问答”。ModelScope 数据集中同时存在招股书文本和基金/股票数据库题目，但数据库大文件当前通过公开 SDK 直链返回 `404`。因此本项目：

- 完整实现招股书 RAG 主链路
- 自动拉取并使用 80 份招股书文本知识库
- 对非招股书题目进行题型识别与提示
- 预留数据库题扩展接口，便于后续补齐混合题库能力

## 目录结构

```text
prospectus_qa/
  api.py
  answering.py
  config.py
  data_access.py
  indexing.py
  models.py
  retrieval.py
  text_utils.py
scripts/
  answer_questions.py
  build_index.py
  download_knowledge_base.py
docs/
  process_record.md
dataset_raw/
outputs/
```

## 快速开始

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 拉取知识库

```bash
python scripts/download_knowledge_base.py
```

3. 构建索引

```bash
python scripts/build_index.py
```

4. 运行样例问答

```bash
python scripts/answer_questions.py --limit 10
```

5. 启动 API

```bash
uvicorn prospectus_qa.api:app --host 0.0.0.0 --port 8000
```

## 输出文件

- 问答结果：`outputs/answers.jsonl`
- 检索证据：`outputs/answers_with_evidence.jsonl`
- 索引文件：`outputs/index/`

## 当前验证情况

- 已成功拉取 80 份招股书文本
- 已成功构建 24,844 个检索切片
- 已验证样例中的沃森生物类问题可命中正确公司并输出答案
- 已验证对基金、股票、行业统计类问题会进行显式路由说明
- 已完成 1000 题全量结果导出

## 已知边界

- 个别表格强依赖题目仍可能命中到包含表格占位符的文本片段，需要后续增加表格解析逻辑进一步提升精度
- 数据集中的数据库大文件目前无法通过公开接口下载，因此基金/股票/行业统计题尚未做数值计算型解答

## API 示例

```bash
curl -X POST http://127.0.0.1:8000/answer ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"云南沃森生物技术股份有限公司负责产品研发的是什么部门？\"}"
```

## 说明

- 项目默认仅对“招股书类问题”给出正式答案。
- 若题目明显属于基金、股票或数据库统计问题，系统会返回 `route=unsupported_mixed_dataset_question`，并在证据中说明原因。
