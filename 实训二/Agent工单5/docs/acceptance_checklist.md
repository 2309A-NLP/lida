# 验收标准检查清单

## 工单编号

`人工智能NLP-Agent数字人项目-招股书数据问答智能体任务`

## 需求文档要求对照

根据需求文档 `requirements.pdf`，本项目需要完成以下交付内容：

---

## ✅ 验收项目清单

### 1. 产出物要求

#### 1.1 基于 question.json 的问题生成回复

- [x] **问题文件处理**
  - 文件位置：`dataset_raw/question.json`
  - 格式：每行一个JSON对象
  - 字段：`id`, `question`
  - 数量：1000题

- [x] **答案生成**
  - 输出文件：`outputs/answers.jsonl`
  - 格式：JSONL（每行一个JSON对象）
  - 必需字段：`id`, `question`, `answer`
  - 补全字段：`answer`（根据问题生成）

- [x] **答案质量**
  - 招股书类问题：能从文本中检索并生成答案
  - 数据库类问题：识别并说明需要数据库支持
  - 提供置信度和证据支持

**验收方法**：
```bash
# 查看输出文件
cat outputs/answers.jsonl | head -5

# 统计处理数量
wc -l outputs/answers.jsonl
# 预期：1000

# 验证格式
python -c "import json; [json.loads(line) for line in open('outputs/answers.jsonl')]"
```

#### 1.2 功能实现代码

- [x] **核心模块**
  - [x] `prospectus_qa/data_access.py` - 数据下载
  - [x] `prospectus_qa/indexing.py` - 索引构建
  - [x] `prospectus_qa/retrieval.py` - 检索模块
  - [x] `prospectus_qa/answering.py` - 问答逻辑
  - [x] `prospectus_qa/api.py` - Web API
  - [x] `prospectus_qa/models.py` - 数据模型
  - [x] `prospectus_qa/config.py` - 配置管理
  - [x] `prospectus_qa/qa_pipeline.py` - 问答流程

- [x] **执行脚本**
  - [x] `scripts/download_knowledge_base.py` - 数据下载脚本
  - [x] `scripts/build_index.py` - 索引构建脚本
  - [x] `scripts/answer_questions.py` - 批量问答脚本
  - [x] `scripts/run_web.py` - Web服务启动脚本

- [x] **Web界面**
  - [x] `web/index.html` - 完整的Web工作台界面
  - [x] 支持示例问题快速测试
  - [x] 显示答案、证据、路由、置信度
  - [x] 响应式设计，美观易用

- [x] **一键启动脚本**
  - [x] `start.bat` - Windows启动脚本
  - [x] `start.sh` - Linux/Mac启动脚本

**验收方法**：
```bash
# 检查文件完整性
ls -la prospectus_qa/*.py scripts/*.py web/*.html

# 启动Web服务测试
python scripts/run_web.py
# 访问 http://127.0.0.1:8001

# 或使用一键启动
./start.bat  # Windows
./start.sh   # Linux/Mac
```

#### 1.3 实现步骤与过程问题记录文档

- [x] **文档位置**：`docs/process_record.md`

- [x] **文档内容**
  - [x] 需求理解
  - [x] 数据源确认
  - [x] 发现的问题及解决方案
  - [x] 实现方案说明
  - [x] 当前交付物清单
  - [x] 后续可增强项

- [x] **补充文档**
  - [x] `docs/demo_guide.md` - 演示说明文档
  - [x] `docs/user_guide.md` - 使用说明文档
  - [x] `README.md` - 项目总览

**验收方法**：
```bash
# 查看文档
cat docs/process_record.md
cat docs/demo_guide.md
cat docs/user_guide.md
cat README.md
```

---

### 2. 功能要求

#### 2.1 招股书数据处理

- [x] **数据来源**
  - 来源：ModelScope数据集 `bs_challenge_financial_14b_dataset`
  - 招股书PDF源文件：80份（527MB）
  - 招股书TXT文件：80份（44MB）
  - 存储位置：`dataset_raw/pdf_txt_file/*.txt`

- [x] **自动下载**
  - 脚本：`scripts/download_knowledge_base.py`
  - 支持断点续传和重试
  - 自动验证文件完整性

**验收方法**：
```bash
# 下载数据
python scripts/download_knowledge_base.py

# 验证文件数量
ls dataset_raw/pdf_txt_file/*.txt | wc -l
# 预期：80

# 验证文件大小
du -sh dataset_raw/pdf_txt_file
# 预期：约44MB
```

#### 2.2 RAG功能实现

- [x] **使用主流解决方案**
  - 检索算法：BM25 + TF-IDF混合检索
  - 中文分词：Jieba
  - 文本处理：清洗、分块、索引
  - 索引切片数：24,844个

- [x] **检索流程**
  1. 问题分词
  2. BM25检索候选
  3. TF-IDF重排序
  4. 返回Top-K结果（默认5个）

- [x] **答案生成**
  - 基于检索证据抽取答案
  - 提供置信度评分
  - 返回证据来源

**验收方法**：
```bash
# 构建索引
python scripts/build_index.py

# 验证索引文件
ls outputs/index/
# 预期：chunks.jsonl

# 测试检索
python -c "
from prospectus_qa.indexing import load_chunks
from prospectus_qa.retrieval import HybridRetriever
chunks = load_chunks()
retriever = HybridRetriever(chunks)
results = retriever.search('沃森生物研发部门', top_k=3)
for r in results:
    print(f'Score: {r[\"score\"]:.3f}, Source: {r[\"source_file\"]}')
    print(r['text'][:100])
"
```

#### 2.3 问题路由识别

- [x] **路由类型**
  - `prospectus_rag`: 招股书问题（正常回答）
  - `unsupported_mixed_dataset_question`: 数据库类问题（说明原因）

- [x] **识别逻辑**
  - 基于问题关键词和模式识别
  - 对基金、股票、行业统计等问题进行路由
  - 提供清晰的说明信息

**验收方法**：
```bash
# 测试招股书问题
curl -X POST http://127.0.0.1:8001/answer \
  -H "Content-Type: application/json" \
  -d '{"question":"云南沃森生物技术股份有限公司负责产品研发的是什么部门？"}'
# 预期 route: "prospectus_rag"

# 测试数据库问题
curl -X POST http://127.0.0.1:8001/answer \
  -H "Content-Type: application/json" \
  -d '{"question":"请帮我计算，在20210105，中信行业分类划分的一级行业为综合金融行业中，涨跌幅最大股票的股票代码是？"}'
# 预期 route: "unsupported_mixed_dataset_question"
```

---

### 3. 技术要求

#### 3.1 代码注释包含工单编号

- [x] **要求**：所有代码文件头部注释需包含工单编号

- [x] **格式**：
```python
"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""
```

- [ ] **待检查文件**（需逐个添加）：
  - [ ] `prospectus_qa/answering.py`
  - [ ] `prospectus_qa/config.py`
  - [ ] `prospectus_qa/data_access.py`
  - [ ] `prospectus_qa/indexing.py`
  - [ ] `prospectus_qa/models.py`
  - [ ] `prospectus_qa/retrieval.py`
  - [ ] `prospectus_qa/text_utils.py`
  - [ ] `prospectus_qa/qa_pipeline.py`
  - [ ] `prospectus_qa/financial_answering.py`
  - [ ] `prospectus_qa/financial_routing.py`
  - [ ] `prospectus_qa/financial_schema.py`
  - [ ] `scripts/download_knowledge_base.py`
  - [ ] `scripts/build_index.py`
  - [ ] `scripts/answer_questions.py`
  - [ ] 其他脚本文件

**验收方法**：
```bash
# 检查所有Python文件是否包含工单编号
grep -r "人工智能NLP-Agent数字人项目-招股书数据问答智能体任务" prospectus_qa/ scripts/ --include="*.py"

# 列出缺少工单编号的文件
for file in prospectus_qa/*.py scripts/*.py; do
  if ! grep -q "人工智能NLP-Agent数字人项目-招股书数据问答智能体任务" "$file"; then
    echo "缺少工单编号: $file"
  fi
done
```

#### 3.2 使用主流RAG方案

- [x] **检索技术**
  - BM25算法（rank-bm25库）
  - TF-IDF向量化（scikit-learn）
  - 混合检索策略

- [x] **文本处理**
  - Jieba中文分词
  - 文本清洗（去除特殊字符、空白）
  - 智能分块（考虑段落边界）

- [x] **索引存储**
  - JSONL格式（便于增量更新）
  - 包含元数据（来源文件、位置）

**验收方法**：
```bash
# 检查依赖包
pip list | grep -E "rank-bm25|scikit-learn|jieba"

# 查看索引文件
head outputs/index/chunks.jsonl
```

---

### 4. 提交格式要求

#### 4.1 JSONL格式

- [x] **格式规范**
  - 每行一个完整JSON对象
  - 不修改id信息（用于结果匹配）
  - 包含必需字段：`id`, `question`, `answer`

- [x] **输出文件**
  - `outputs/answers.jsonl` - 提交版本
  - `outputs/answers_with_evidence.jsonl` - 详细版本

**验收方法**：
```bash
# 验证JSONL格式
python -c "
import json
with open('outputs/answers.jsonl') as f:
    for i, line in enumerate(f, 1):
        try:
            obj = json.loads(line)
            assert 'id' in obj and 'question' in obj and 'answer' in obj
        except Exception as e:
            print(f'第{i}行格式错误: {e}')
            break
print('格式验证通过')
"

# 验证ID顺序
python -c "
import json
with open('outputs/answers.jsonl') as f:
    ids = [json.loads(line)['id'] for line in f]
    print(f'ID范围: {min(ids)} - {max(ids)}')
    print(f'ID数量: {len(ids)}')
    print(f'ID连续: {ids == list(range(len(ids)))}')
"
```

---

## 快速验收流程

### 步骤1：环境检查（2分钟）

```bash
# 检查Python版本
python --version
# 要求：3.8+

# 检查依赖
pip list | grep -E "fastapi|uvicorn|pandas|scikit-learn|jieba"
```

### 步骤2：数据准备（5分钟）

```bash
# 下载知识库
python scripts/download_knowledge_base.py

# 验证数据
ls dataset_raw/pdf_txt_file/*.txt | wc -l
# 预期：80

# 构建索引
python scripts/build_index.py

# 验证索引
ls outputs/index/chunks.jsonl
```

### 步骤3：Web界面演示（3分钟）

```bash
# 启动服务
python scripts/run_web.py
# 或使用：./start.bat (Windows) / ./start.sh (Linux)

# 浏览器访问
# http://127.0.0.1:8001

# 测试示例问题
# 点击"研发部门"示例
# 查看答案、证据、置信度
```

### 步骤4：批量处理验证（2分钟）

```bash
# 运行批量问答（测试10题）
python scripts/answer_questions.py --limit 10

# 查看结果
head outputs/answers.jsonl

# 运行全量（可选，需要约5-10分钟）
python scripts/answer_questions.py
```

### 步骤5：文档检查（2分钟）

```bash
# 查看文档完整性
ls docs/
# 预期：process_record.md, demo_guide.md, user_guide.md

# 查看README
cat README.md
```

### 步骤6：代码注释检查（需补充）

```bash
# 检查工单编号
grep -r "人工智能NLP-Agent数字人项目-招股书数据问答智能体任务" prospectus_qa/ scripts/ --include="*.py"
```

---

## 验收通过标准

- ✅ 所有核心功能模块代码完整
- ✅ Web界面可正常访问和使用
- ✅ 批量问答脚本可生成1000题答案
- ✅ 输出文件格式符合JSONL规范
- ✅ 文档完整（实现步骤、演示说明、使用说明）
- ⏳ 所有代码文件包含工单编号注释（需补充）
- ✅ 使用主流RAG方案实现

---

## 待办事项

### 高优先级

1. **补充工单编号注释**（约10分钟）
   - 为所有Python文件添加头部注释
   - 格式：`"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""`

### 可选增强

1. **截图/视频**（如需要）
   - Web界面截图
   - 批量处理截图
   - 演示视频

2. **性能优化**
   - 增加缓存机制
   - 并发请求处理
   - 索引优化

3. **功能扩展**
   - 接入向量检索模型
   - 支持数据库类问题（需要数据库文件）
   - 增加reranker模块

---

## 验收通过后交付清单

1. ✅ 完整的源代码（`prospectus_qa/`, `scripts/`, `web/`）
2. ✅ 问答结果文件（`outputs/answers.jsonl`）
3. ✅ 实现文档（`docs/process_record.md`）
4. ✅ 演示说明（`docs/demo_guide.md`）
5. ✅ 使用说明（`docs/user_guide.md`）
6. ✅ 项目说明（`README.md`）
7. ✅ 一键启动脚本（`start.bat`, `start.sh`）
8. ✅ 依赖清单（`requirements.txt`）
9. ⏳ 工单编号注释（需补充到所有代码文件）

---

## 总结

当前项目已完成：
- ✅ 核心功能开发（100%）
- ✅ Web界面（100%）
- ✅ 文档编写（100%）
- ⏳ 代码注释规范（90%，需补充工单编号）

预计补充工作：10-15分钟（添加工单编号注释）

完成后即可通过验收！
