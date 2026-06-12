# RAG工单14 - 任务一技术总结文档

## 一、RAGFlow 项目概述

### 1.1 系统架构

RAGFlow 的系统架构包含两个核心组件：

| 组件 | 功能 | 技术栈 |
|------|------|--------|
| API Server | 提供外部接口和平台基本功能 | FastAPI + Python |
| Task Executor | 负责文件解析和切片处理 | Celery + Redis |

### 1.2 核心流程

```
用户上传文档 → API Server 接收 → Redis Stream 消息队列 → Task Executor 处理 → 解析/分块/向量化 → 存储
```

---

## 二、DeepDoc 模块技术分析

### 2.1 解析器架构

DeepDoc 内置了以下文件解析器：

| 解析器 | 支持格式 | 位置 |
|--------|----------|------|
| PDF Parser | PDF | `deepdoc/parser/pdf_parser.py` |
| Docx Parser | Word | `deepdoc/parser/docx_parser.py` |
| Excel Parser | Excel | `deepdoc/parser/excel_parser.py` |
| PPT Parser | PowerPoint | `deepdoc/parser/ppt_parser.py` |
| Markdown Parser | Markdown | `deepdoc/parser/markdown_parser.py` |
| JSON Parser | JSON | `deepdoc/parser/json_parser.py` |
| HTML Parser | HTML | `deepdoc/parser/html_parser.py` |

### 2.2 PDF 解析技术

#### 2.2.1 解析流程

```python
def __call__(self, fnm, need_image=True, zoomin=3):
    # 1. 提取PDF大纲
    self.outlines = extract_pdf_outlines(fnm)
    
    # 2. 页面转图片（用于OCR）
    self.__images__(fnm, zoomin)
    
    # 3. 版面分析（识别文本/表格/图片区域）
    self._layouts_rec(zoomin)
    
    # 4. 表格结构识别
    self._table_transformer_job(zoomin)
    
    # 5. 文本合并
    self._text_merge()
    
    # 6. 跨页拼接
    self._concat_downward()
    
    # 7. 提取表格和图片
    tbls = self._extract_table_figure(need_image, zoomin)
```

#### 2.2.2 版面分析模型

- **LayoutRecognizer**: 使用 ONNX 或 Ascend 模型
- 识别类型：text、table、figure、title、header/footer
- 使用 KMeans 聚类检测多栏布局

---

## 三、分块策略分析

### 3.1 paper_id 对应的分块策略

| paper_id | 分块方式 | 适用场景 | 触发条件 |
|----------|----------|----------|----------|
| `paper` | 按论文章节分块 | 学术论文 | 识别到论文结构 |
| `table` | 表格专用分块 | 表格数据 | 识别到表格区域 |
| `one` | 整文档作为一个chunk | 小文档 | 文档长度较短 |
| `knowledge_graph` | 知识图谱分块 | 知识图谱 | 启用GraphRAG |
| `naive` (默认) | 按token数分块 | 通用文档 | 默认策略 |

### 3.2 分块参数

```json
{
    "chunk_token_num": 128,
    "delimiter": "\n!?。；！？",
    "overlapped_percent": 0,
    "layout_recognize": "DeepDOC",
    "table_context_size": 0,
    "image_context_size": 0
}
```

### 3.3 分块算法 (naive_merge)

```python
def naive_merge(sections, chunk_token_num, delimiter, overlapped_percent):
    chunks = []
    current_chunk = ""
    
    for section in sections:
        text = section[0]
        tokens = num_tokens_from_string(text)
        
        if current_tokens + tokens > chunk_token_num:
            chunks.append(current_chunk)
            # 计算重叠
            if overlapped_percent > 0:
                overlap_len = int(len(current_chunk) * overlapped_percent / 100)
                current_chunk = current_chunk[-overlap_len:]
            else:
                current_chunk = ""
        
        current_chunk += "\n" + text
    
    return chunks
```

---

## 四、任务处理流程 (do_handle_task)

### 4.1 主要逻辑

`do_handle_task` 是 RAGFlow 的核心任务处理函数，负责：

1. **文档解析**
   - 根据文件类型选择解析器
   - 提取文本、表格、图片
   
2. **分块处理**
   - 根据 paper_id 选择分块策略
   - 应用分块参数（chunk_token_num、delimiter等）
   
3. **向量化**
   - 使用 Embedding 模型将文本块转为向量
   - 存储到向量数据库
   
4. **索引构建**
   - 构建全文索引（Elasticsearch/Infinity）
   - 构建向量索引

### 4.2 技术实现

```python
def do_handle_task(task_id, doc_id, kb_id):
    # 1. 获取文档信息
    doc = get_document(doc_id)
    
    # 2. 解析文档
    parser = get_parser(doc.parser_id)
    sections, tables = parser(doc.location)
    
    # 3. 分块
    chunks = chunk(sections, doc.parser_config)
    
    # 4. 向量化
    embeddings = embed(chunks)
    
    # 5. 存储
    store_to_elasticsearch(chunks)
    store_to_vector_db(embeddings)
```

### 4.3 Redis Stream 消息队列

任务通过 Redis Stream 进行异步处理：

```
Producer (API Server) → Redis Stream → Consumer (Task Executor)
```

- 消息格式：任务ID、文档ID、知识库ID
- 支持多消费者并行处理
- 支持任务重试和死信队列

---

## 五、总结

### 5.1 关键发现

1. DeepDoc 使用深度学习进行版面分析，识别精度高
2. 分块策略灵活，支持多种 paper_id
3. 任务处理流程清晰，支持异步处理

### 5.2 针对工单14的优化建议

1. **解析模式**：使用 DeepDOC（扫描型PDF必须用OCR）
2. **分块参数**：增大 chunk_token_num 到 512
3. **检索参数**：降低 similarity_threshold 到 0.1
4. **Rerank**：启用外部 Rerank 模型

---

*文档生成时间：2026-06-11*
*基于 RAGFlow v0.25.6 代码分析*
