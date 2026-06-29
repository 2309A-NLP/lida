# 使用说明文档

## 工单编号

`人工智能NLP-Agent数字人项目-招股书数据问答智能体任务`

## 项目简介

本项目是一个基于RAG（检索增强生成）技术的招股书PDF数据问答智能体，能够自动从80份招股说明书中检索相关信息并回答用户问题。

**核心功能**：
- 招股书文本知识库自动构建
- 基于BM25和TF-IDF的混合检索
- 支持Web界面、API接口和CLI批量处理
- 自动路由识别问题类型
- 提供答案、证据、置信度等完整信息

## 快速开始

### 方式一：一键启动（推荐）

**Windows系统**：
```bash
start.bat
```

**Linux/Mac系统**：
```bash
chmod +x start.sh
./start.sh
```

脚本会自动完成：
1. 检查Python环境
2. 安装依赖包（如需要）
3. 下载知识库数据（如需要）
4. 构建索引（如需要）
5. 启动Web服务

启动成功后访问：http://127.0.0.1:8001

### 方式二：手动步骤

#### 1. 环境要求

- Python 3.8 或更高版本
- 建议使用虚拟环境

#### 2. 安装依赖

```bash
pip install -r requirements.txt
```

依赖包说明：
- `fastapi`, `uvicorn`: Web框架和服务器
- `pandas`, `numpy`: 数据处理
- `scikit-learn`: 特征提取
- `rank-bm25`: BM25检索算法
- `jieba`: 中文分词
- `orjson`: 高性能JSON处理
- `modelscope`: 数据集下载

#### 3. 下载知识库

```bash
python scripts/download_knowledge_base.py
```

下载内容：
- `question.json`: 1000道测试题目
- `pdf_txt_file/*.txt`: 80份招股书文本
- `financial_data.db`: 金融数据库（可选）
- 相关元数据文件

数据将保存到 `dataset_raw/` 目录。

#### 4. 构建索引

```bash
python scripts/build_index.py
```

构建过程：
- 读取80份招股书文本
- 文本清洗和分块（每块约500字符）
- 生成约24,844个检索切片
- 保存索引到 `outputs/index/`

预计耗时：1-2分钟

#### 5. 启动服务

```bash
python scripts/run_web.py
```

服务信息：
- 地址：http://127.0.0.1:8001
- 首次启动会预热模型（2-3秒）
- 后续查询响应时间：100-300ms

## 使用方式

### 1. Web界面使用

访问 http://127.0.0.1:8001

#### 界面说明

**品牌区**：
- 项目名称和简介
- 三大核心能力展示（RAG、SQL、FAST）

**示例问题区**：
- 提供4个预设问题
- 点击即可快速测试

**问答区**：
- 输入框：输入问题或点击示例
- 提交按钮：发送问题
- 清空按钮：清空所有内容
- 进度条：显示处理状态

**结果区**：
- 答案：AI生成的回答
- 证据：前两条检索证据
- 元信息：路由类型、置信度、耗时

#### 操作流程

1. 打开Web界面
2. 点击示例问题或输入自定义问题
3. 点击"提交问题"
4. 查看答案、证据和元信息

#### 示例问题

```
湖南长远锂科股份有限公司变更设立时作为发起人的法人有哪些？
云南沃森生物技术股份有限公司负责产品研发的是什么部门？
中国铁路通信信号股份有限公司的主要经营模式是怎样的？
广州中海达卫星导航技术股份有限公司本次募集资金主要投资哪些项目？
```

### 2. API接口使用

#### 2.1 健康检查

```bash
curl http://127.0.0.1:8001/health
```

响应：
```json
{"status": "ok"}
```

#### 2.2 获取知识库信息

```bash
curl http://127.0.0.1:8001/meta
```

响应：
```json
{
  "prospectus_texts": "dataset_raw/pdf_txt_file/*.txt",
  "prospectus_text_count": 80,
  "financial_db": "dataset_raw/financial_data.db",
  "dataset_source": "ModelScope bs_challenge_financial_14b_dataset"
}
```

#### 2.3 问答接口

**请求**：

```bash
curl -X POST http://127.0.0.1:8001/answer \
  -H "Content-Type: application/json" \
  -d '{"question":"云南沃森生物技术股份有限公司负责产品研发的是什么部门？"}'
```

**Windows PowerShell**：
```powershell
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8001/answer" `
  -ContentType "application/json" `
  -Body '{"question":"云南沃森生物技术股份有限公司负责产品研发的是什么部门？"}'
```

**响应格式**：
```json
{
  "id": -1,
  "question": "云南沃森生物技术股份有限公司负责产品研发的是什么部门？",
  "answer": "技术中心",
  "route": "prospectus_rag",
  "confidence": 0.85,
  "elapsed_ms": 123.45,
  "evidence": [
    {
      "source_file": "xxx.txt",
      "text_preview": "...技术中心负责产品研发...",
      "score": 0.85
    }
  ]
}
```

**字段说明**：
- `id`: 问题ID（自定义或-1）
- `question`: 原始问题
- `answer`: 生成的答案
- `route`: 路由类型
  - `prospectus_rag`: 招股书问题（正常回答）
  - `unsupported_mixed_dataset_question`: 数据库类问题（说明原因）
- `confidence`: 置信度（0-1）
- `elapsed_ms`: 处理耗时（毫秒）
- `evidence`: 检索证据列表
  - `source_file`: 来源文件
  - `text_preview`: 文本摘要
  - `score`: 相关性分数

### 3. CLI批量处理

#### 3.1 批量问答

```bash
python scripts/answer_questions.py
```

**参数说明**：
- `--limit N`: 只处理前N道题（默认全部1000题）
- 无参数：处理全部题目

**示例**：

```bash
# 处理前10题（快速测试）
python scripts/answer_questions.py --limit 10

# 处理全部1000题
python scripts/answer_questions.py
```

**输出文件**：
- `outputs/answers.jsonl`: 简化版（仅id、question、answer）
- `outputs/answers_with_evidence.jsonl`: 完整版（包含证据）

#### 3.2 查看结果

```bash
# 查看前5条结果
head -5 outputs/answers.jsonl

# 统计处理数量
wc -l outputs/answers.jsonl

# Windows查看
type outputs\answers.jsonl | more
```

**结果格式（简化版）**：
```jsonl
{"id": 0, "question": "...", "answer": "..."}
{"id": 1, "question": "...", "answer": "..."}
```

**结果格式（完整版）**：
```jsonl
{"id": 0, "question": "...", "answer": "...", "route": "...", "confidence": 0.85, "evidence": [...]}
```

## 高级功能

### 1. 自定义配置

编辑 `prospectus_qa/config.py`：

```python
# 索引目录
INDEX_DIR = Path("outputs/index")

# 检索参数
TOP_K = 5  # 检索前K个结果

# 分块参数
CHUNK_SIZE = 500  # 每块字符数
CHUNK_OVERLAP = 50  # 块之间重叠字符数
```

### 2. 分析工具

#### 2.1 问题类型分析

```bash
python scripts/analyze_question_patterns.py
```

分析1000道题目的类型分布。

#### 2.2 数据库诊断

```bash
python scripts/diagnose_questions.py
```

诊断哪些问题需要数据库支持。

#### 2.3 金融数据覆盖分析

```bash
python scripts/scan_financial_coverage.py
```

扫描金融数据库的覆盖范围。

### 3. 开发调试

#### 启动开发模式

```bash
uvicorn prospectus_qa.api:app --reload --port 8001
```

代码修改后自动重载。

#### 查看日志

```bash
tail -f outputs/runweb_stdout.log
tail -f outputs/runweb_stderr.log
```

## 项目结构

```
.
├── prospectus_qa/           # 核心代码模块
│   ├── api.py              # FastAPI接口
│   ├── answering.py        # 问答逻辑
│   ├── retrieval.py        # 检索模块
│   ├── indexing.py         # 索引构建
│   ├── data_access.py      # 数据下载
│   ├── config.py           # 配置文件
│   └── models.py           # 数据模型
├── scripts/                 # 执行脚本
│   ├── download_knowledge_base.py
│   ├── build_index.py
│   ├── answer_questions.py
│   └── run_web.py
├── web/                     # Web前端
│   └── index.html
├── docs/                    # 文档
│   ├── process_record.md   # 实现步骤记录
│   ├── demo_guide.md       # 演示说明
│   └── user_guide.md       # 使用说明（本文件）
├── dataset_raw/             # 原始数据集
│   ├── question.json       # 测试题目
│   ├── pdf_txt_file/       # 招股书文本
│   └── financial_data.db   # 金融数据库
├── outputs/                 # 输出文件
│   ├── index/              # 索引文件
│   ├── answers.jsonl       # 问答结果
│   └── answers_with_evidence.jsonl
├── requirements.txt         # 依赖包列表
├── README.md               # 项目说明
├── start.bat               # Windows启动脚本
└── start.sh                # Linux/Mac启动脚本
```

## 常见问题

### Q1: 安装依赖时报错？

**解决方法**：
```bash
# 升级pip
pip install --upgrade pip

# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q2: 下载数据集失败？

**原因**：网络问题或ModelScope访问受限

**解决方法**：
1. 检查网络连接
2. 多次重试（脚本会自动重试）
3. 手动下载数据集并放到 `dataset_raw/` 目录

### Q3: 构建索引时内存不足？

**解决方法**：
- 关闭其他程序释放内存
- 增加系统虚拟内存
- 项目默认配置需要约2GB内存

### Q4: Web服务启动失败？

**检查项**：
1. 端口8001是否被占用
2. 是否已安装所有依赖
3. 是否已构建索引

**查看日志**：
```bash
cat outputs/web_stderr.log
```

### Q5: 为什么有些问题返回"不支持"？

**原因**：数据集混合了两类问题
- 招股书类：可以从文本中检索回答
- 数据库类：需要SQL查询股票/基金数据

**当前实现**：
- 完整支持招股书类问题
- 对数据库类问题进行路由识别并说明

### Q6: 如何提高答案质量？

**方法**：
1. 增加检索数量（修改 `TOP_K`）
2. 调整分块大小（修改 `CHUNK_SIZE`）
3. 增加重叠区域（修改 `CHUNK_OVERLAP`）
4. 接入向量检索模型（需要额外开发）

### Q7: 能否处理PDF文件而不是TXT？

**当前状态**：项目使用数据集提供的预处理TXT文件

**扩展方法**：
1. 安装PDF解析库（如pypdf2、pdfplumber）
2. 在 `indexing.py` 中添加PDF解析逻辑
3. 修改数据加载流程

### Q8: 如何部署到生产环境？

**建议配置**：
```bash
# 使用Gunicorn + Uvicorn workers
gunicorn prospectus_qa.api:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001

# 或使用Docker部署
```

**注意事项**：
- 配置HTTPS证书
- 设置访问限流
- 增加日志监控
- 使用反向代理（Nginx）

## 性能指标

| 指标 | 数值 |
|------|------|
| 知识库大小 | 80份招股书（44MB） |
| 索引切片数 | 24,844个 |
| 题库数量 | 1000题 |
| 首次查询耗时 | 2-3秒（含模型预热） |
| 后续查询耗时 | 100-300ms |
| 内存占用 | 约1.5-2GB |
| 并发能力 | 支持多用户同时访问 |

## 技术栈

- **后端框架**：FastAPI
- **Web服务器**：Uvicorn
- **检索算法**：BM25 + TF-IDF混合检索
- **中文分词**：Jieba
- **数据处理**：Pandas, NumPy
- **前端**：原生HTML + JavaScript
- **数据格式**：JSONL

## 参考资料

- 需求文档：`requirements.pdf`
- 实现步骤：`docs/process_record.md`
- 演示说明：`docs/demo_guide.md`
- 数据集来源：[天池比赛](https://tianchi.aliyun.com/competition/entrance/532172/information)

## 联系方式

如有问题，请查看：
1. `docs/process_record.md` - 实现过程中遇到的问题及解决方案
2. `docs/demo_guide.md` - 演示和验收说明

## 版本历史

- **v1.0.0** (2025-01-14)
  - 初始版本
  - 完整实现招股书RAG主链路
  - 提供Web、API、CLI三种使用方式
  - 支持1000题批量处理
