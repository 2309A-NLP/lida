# 基金数据问答智能体

本项目按照 PDF《人工智能NLP-Agent数字人项目-04-基金数据问答任务工单V1.1-20250206》要求实现，目标是基于基金 SQLite 数据库与招股书解析文本构建一个问答智能体，覆盖 `NL2SQL`、招股书文本检索、`question.json` 批量答题、数据表关系图和实现文档等交付内容。

## 项目内容

- 结构化问答链路：针对基金/股票/债券/行业等问题走 `NL2SQL` 路由
- 非结构化问答链路：针对招股说明书类问题走 `pdf_txt_file` 检索路由
- 批量答题脚本：读取 `question.json`，输出补全 `answer` 字段的 `jsonl`
- 数据表关系图脚本：从 SQLite 自动抽取 schema 并生成文档和图
- FastAPI 服务：提供 `/ask` 接口用于单题问答
- 实现记录文档：记录步骤、问题与当前阻塞

## 目录结构

```text
src/fund_qa/
  api.py
  config.py
  models.py
  data/
  retrieval/
  service/
scripts/
docs/
outputs/
dataset_partial/
```

## 数据准备

当前工作区已准备：

- `dataset_partial/question.json`
- `dataset_partial/pdf_txt_file/*.txt`
- `dataset_partial/sqlite_db.csv`
- `dataset_partial/dataset/financial_fund_data.db`

如果数据库不在默认位置，可通过环境变量指定：

```powershell
$env:FUND_QA_SQLITE_DB="D:\your_path\博金杯比赛数据.db"
```

## 安装与运行

```powershell
python -m pip install -e .
python scripts\analyze_questions.py
python scripts\generate_schema_docs.py
python scripts\batch_answer.py
python scripts\validate_delivery.py
python scripts\smoke_test.py
uvicorn fund_qa.api:app --host 0.0.0.0 --port 8000
```

## 推荐验收流程

```powershell
python scripts\generate_schema_docs.py
python scripts\batch_answer.py
python scripts\validate_delivery.py
python scripts\smoke_test.py
uvicorn fund_qa.api:app --host 127.0.0.1 --port 8000
```

说明：

- `validate_delivery.py`：检查 PDF 对应的硬性指标是否齐全，包括 `10` 张表、`80` 份招股书 `txt`、`1000` 条答案和必需交付文件
- `smoke_test.py`：抽取真实题目 `id=0/1/2/11` 做本地冒烟验证
- `batch_answer.py`：支持断点续跑，避免中断时覆盖坏 `outputs/answers.jsonl`

## 接口示例

```powershell
curl -X POST http://127.0.0.1:8000/ask ^
  -H "Content-Type: application/json" ^
  -d "{\"question\": \"股票002244在20191220日期中的收盘价是多少?（小数点保留3位）\"}"
```

## 当前实现说明

- 招股书问答：已经可以基于 80 份 `txt` 文本进行 TF-IDF 检索
- 结构化问答：已经接入真实 SQLite 基金库，并支持多类高频题型的可执行 SQL
- 批量答题：已经基于 `question.json` 生成 `outputs/answers.jsonl`
- 数据表关系图：已经基于真实 10 张表生成文档和图片
- 项目验收：已经补充自动验收脚本与冒烟测试脚本，便于按 PDF 要求复查

## 交付物对应关系

- 基金 DB 数据表关系图：`docs/db_schema.md`、`outputs/db_relationship_graph.png`
- 问题回复结果：`outputs/answers.jsonl`
- 功能实现代码：`src/`、`scripts/`
- 实现步骤与问题记录：`docs/implementation_notes.md`
