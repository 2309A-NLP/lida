# RAGFlow DeepDoc 技术分析文档

## 一、DeepDoc 模块概述

DeepDoc 是 RAGFlow 的核心文档解析模块，负责将 PDF、Word、Excel 等格式的文档转换为结构化的文本块（chunks），用于后续的向量化和检索。

### 1.1 核心组件

| 组件 | 功能 | 位置 |
|------|------|------|
| RAGFlowPdfParser | PDF 解析器核心类 | deepdoc/parser/pdf_parser.py |
| LayoutRecognizer | 版面分析模型（识别文本、表格、图片等区域） | deepdoc/vision/ |
| TableStructureRecognizer | 表格结构识别 | deepdoc/vision/ |
| OCR | 光学字符识别 | deepdoc/vision/ |
| XGBoost Model | 上下文合并决策模型 | rag/res/deepdoc/ |

### 1.2 支持的解析模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| DeepDOC | 默认模式，使用深度学习进行版面识别+OCR | 大多数 PDF 文档 |
| PlainText | 简单文本提取（pypdf） | 纯文本 PDF |
| TCADP | 腾讯云解析器 | 需要腾讯云 API |
| Docling | Docling 解析器 | 第三方解析 |
| MinerU | MinerU 解析器 | 第三方解析 |
| PaddleOCR | PaddleOCR 解析器 | 第三方解析 |
| OpenDataLoader | OpenDataLoader 解析器 | 第三方解析 |

---

## 二、PDF 解析流程详解

### 2.1 整体流程

```python
def __call__(self, fnm, need_image=True, zoomin=3, return_html=False, auto_rotate_tables=None):
    # 1. 提取 PDF 大纲（目录结构）
    self.outlines = extract_pdf_outlines(fnm)
    
    # 2. 将 PDF 页面转为图片（用于 OCR 和版面分析）
    self.__images__(fnm, zoomin)
    
    # 3. 版面分析：识别文本块、表格、图片等区域
    self._layouts_rec(zoomin)
    
    # 4. 表格结构识别
    self._table_transformer_job(zoomin, auto_rotate=auto_rotate_tables)
    
    # 5. 文本合并：将相邻的文本块合并
    self._text_merge()
    
    # 6. 向下拼接：处理跨页文本
    self._concat_downward()
    
    # 7. 过滤无效页面
    self._filter_forpages()
    
    # 8. 提取表格和图片
    tbls = self._extract_table_figure(need_image, zoomin, return_html, False)
    
    return self.__filterout_scraps(deepcopy(self.boxes), zoomin), tbls
```

### 2.2 详细步骤说明

#### 步骤1：PDF 大纲提取
- 使用 `extract_pdf_outlines()` 提取 PDF 的目录结构
- 大纲信息会附加到第一个 chunk 的元数据中

#### 步骤2：页面转图片
- 使用 `__images__()` 将 PDF 页面转为图片
- 默认放大倍数 `zoomin=3`（提高 OCR 精度）
- 如果放大后没有检测到文本块，会自动提高放大倍数（最大9倍）

#### 步骤3：版面分析
- 使用 `LayoutRecognizer`（ONNX 或 Ascend 模型）识别页面中的：
  - 文本块（text）
  - 表格（table）
  - 图片（figure）
  - 标题（title）
  - 页眉页脚（header/footer）
- 使用 KMeans 聚类算法自动检测多栏布局

#### 步骤4：表格结构识别
- 使用 `TableStructureRecognizer` 识别表格内部结构
- 支持自动旋转校正（`TABLE_AUTO_ROTATE` 环境变量）

#### 步骤5：文本合并
- 使用 `_text_merge()` 合并相邻的文本块
- 合并策略：
  - 同一栏（column）内的相邻文本块
  - 相同版面类型（layout_type）的文本块
  - 使用 XGBoost 模型判断是否应该合并（考虑上下文关系）

#### 步骤6：向下拼接
- 使用 `_concat_downward()` 处理跨页的文本块
- 将被页面分割的段落重新连接

#### 步骤7：表格和图片提取
- 使用 `_extract_table_figure()` 提取表格和图片
- 表格：转换为 HTML 或纯文本格式
- 图片：裁剪并保存为图片对象

---

## 三、分块策略详解

### 3.1 核心参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `chunk_token_num` | 128 | 每个 chunk 的最大 token 数 |
| `delimiter` | `\n!?。；！？` | 文本切分的分隔符 |
| `overlapped_percent` | 0 | 相邻 chunk 的重叠百分比 |
| `layout_recognize` | DeepDOC | 解析模式选择 |
| `table_context_size` | 0 | 表格上下文大小 |
| `image_context_size` | 0 | 图片上下文大小 |
| `children_delimiter` | 空 | 子分块分隔符 |
| `analyze_hyperlink` | true | 是否分析超链接 |

### 3.2 分块流程（naive 模式）

```python
def chunk(filename, binary=None, from_page=0, to_page=MAXIMUM_PAGE_NUMBER, 
          lang="Chinese", callback=None, **kwargs):
    # 1. 根据文件类型选择解析器
    parser_config = kwargs.get("parser_config", {...})
    
    # 2. 解析文档，获取 sections（文本段落）和 tables（表格）
    sections, tables, pdf_parser = parser(
        filename=filename,
        binary=binary,
        from_page=from_page,
        to_page=to_page,
        lang=lang,
        callback=callback,
        layout_recognizer=layout_recognizer,
        **kwargs,
    )
    
    # 3. 分块合并
    overlapped_percent = normalize_overlapped_percent(parser_config.get("overlapped_percent", 0))
    chunks = naive_merge(sections, int(parser_config.get("chunk_token_num", 128)), 
                        parser_config.get("delimiter", "\n!?。；！？"), overlapped_percent)
    
    # 4. 词汇化处理
    res = tokenize_chunks(chunks, doc, is_english, pdf_parser, 
                         child_delimiters_pattern=child_deli)
    
    return res
```

### 3.3 naive_merge 分块算法

```python
def naive_merge(sections, chunk_token_num, delimiter, overlapped_percent):
    """
    分块逻辑：
    1. 按分隔符切分文本为段落
    2. 合并相邻段落直到达到 chunk_token_num 限制
    3. 支持重叠（overlapped_percent）
    """
    chunks = []
    current_chunk = ""
    current_tokens = 0
    
    for section in sections:
        text = section[0]
        tokens = num_tokens_from_string(text)
        
        # 如果当前 chunk + 新段落超过限制，保存当前 chunk
        if current_tokens + tokens > chunk_token_num and current_chunk:
            chunks.append(current_chunk)
            
            # 计算重叠部分
            if overlapped_percent > 0:
                overlap_len = int(len(current_chunk) * overlapped_percent / 100)
                current_chunk = current_chunk[-overlap_len:] if overlap_len > 0 else ""
            else:
                current_chunk = ""
            
            current_tokens = num_tokens_from_string(current_chunk)
        
        # 追加新段落
        if current_chunk:
            current_chunk += "\n" + text
        else:
            current_chunk = text
        current_tokens += tokens
    
    # 保存最后一个 chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks
```

### 3.4 不同解析器的分块差异

| 解析器 | 分块方式 | 特点 |
|--------|----------|------|
| DeepDOC | 按版面区域分块 | 识别文本、表格、图片区域，分别处理 |
| PlainText | 按页面分块 | 简单提取文本，不做版面分析 |
| Paper | 按论文章节分块 | 识别论文结构（摘要、方法、结果等） |
| Book | 按章节分块 | 识别书籍的章节结构 |
| Table | 表格专用分块 | 保持表格结构，按行分块 |

---

## 四、向量检索和 Rerank 机制

### 4.1 检索流程

```python
async def retrieval(self, question, embd_mdl, tenant_ids, kb_ids, 
                    page, page_size, similarity_threshold=0.2,
                    vector_similarity_weight=0.3, top=1024, 
                    doc_ids=None, aggs=True, rerank_mdl=None,
                    highlight=False, rank_feature=None, trace_id=None):
    """
    检索流程：
    1. 构建检索请求
    2. 执行混合检索（向量 + 全文）
    3. Rerank 重排序
    4. 过滤和分页
    """
    
    # 1. 构建检索请求
    req = {
        "kb_ids": kb_ids,
        "doc_ids": doc_ids,
        "page": page,
        "size": page_size,
        "question": question,
        "vector": True,
        "topk": top,
        "similarity": similarity_threshold,
        "available_int": 1,
    }
    
    # 2. 执行混合检索
    sres = await self.search(req, idx_names, kb_ids, embd_mdl, highlight,
                            rank_feature=rank_feature)
    
    # 3. Rerank 重排序
    if rerank_mdl and sres.total > 0:
        # 使用外部 Rerank 模型
        sim, tsim, vsim = self.rerank_by_model(
            rerank_mdl, sres, question,
            term_similarity_weight, vector_similarity_weight,
            rank_feature=rank_feature,
        )
    else:
        # 内置 Rerank：融合向量相似度和全文相似度
        sim, tsim, vsim = self.rerank(
            sres, question,
            term_similarity_weight, vector_similarity_weight,
            rank_feature=rank_feature,
        )
    
    # 4. 过滤和分页
    sorted_idx = np.argsort(sim_np * -1, kind='stable')
    valid_idx = [int(i) for i in sorted_idx if sim_np[i] >= similarity_threshold]
    
    return ranks
```

### 4.2 混合检索策略

RAGFlow 支持三种检索模式：

1. **向量检索（Vector Search）**
   - 使用 embedding 模型将查询和文档转为向量
   - 计算余弦相似度
   - 适用于语义相似的查询

2. **全文检索（Full-Text Search）**
   - 使用 Elasticsearch/Infinity 进行关键词匹配
   - 基于 BM25 算法
   - 适用于精确关键词查询

3. **混合检索（Hybrid Search）**
   - 融合向量检索和全文检索的结果
   - 通过 `vector_similarity_weight` 参数调整权重
   - 默认权重：向量 0.3，全文 0.7

### 4.3 Rerank 机制

#### 内置 Rerank

```python
def rerank(self, sres, question, term_similarity_weight, vector_similarity_weight, 
           rank_feature=None):
    """
    内置 Rerank 算法：
    1. 计算全文相似度（token_similarity）
    2. 计算向量相似度（rerank_mdl.similarity）
    3. 融合得分 = tkweight * tksim + vtweight * vtsim + rank_fea
    """
    tksim = self.qryr.token_similarity(keywords, ins_tw)
    vtsim, _ = rerank_mdl.similarity(query, docs)
    rank_fea = self._rank_feature_scores(rank_feature, sres)
    
    return tkweight * np.array(tksim) + vtweight * vtsim + rank_fea, tksim, vtsim
```

#### 外部 Rerank 模型

- 支持配置外部 Rerank 模型（如 BGE-Reranker、Cohere Rerank 等）
- 在检索配置中设置 `rerank_model` 参数
- 外部 Rerank 模型会重新计算查询和文档的相关性得分

### 4.4 关键配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `similarity_threshold` | 0.2 | 相似度阈值，低于此值的结果被过滤 |
| `vector_similarity_weight` | 0.3 | 向量相似度权重 |
| `term_similarity_weight` | 0.7 | 全文相似度权重（自动计算：1 - vector_similarity_weight） |
| `top` | 1024 | 检索的候选文档数量 |
| `page_size` | 30 | 每页返回的结果数量 |

---

## 五、知识库配置参数详解

### 5.1 知识库创建参数

```python
{
    "name": "知识库名称",
    "avatar": "头像",
    "description": "描述",
    "permission": "me",  # 权限：me 或 team
    "chunk_method": "naive",  # 分块方法
    "parser_config": {
        "chunk_token_num": 128,  # 最大 token 数
        "delimiter": "\n!?。；！？",  # 分隔符
        "overlapped_percent": 0,  # 重叠百分比
        "layout_recognize": "DeepDOC",  # 解析模式
        "html4excel": false,  # Excel 是否转 HTML
        "table_context_size": 0,  # 表格上下文大小
        "image_context_size": 0,  # 图片上下文大小
        "analyze_hyperlink": true,  # 是否分析超链接
        "auto_keywords": false,  # 自动生成关键词
        "auto_questions": false,  # 自动生成问题
    }
}
```

### 5.2 文档上传参数

```python
{
    "doc_id": "文档ID",
    "kb_id": "知识库ID",
    "parser_id": "naive",  # 解析器类型
    "parser_config": {
        # 同知识库配置，可覆盖
    },
    "from_page": 0,  # 起始页
    "to_page": 100,  # 结束页
    "language": "Chinese",  # 语言
}
```

---

## 六、针对 RAG 工单14 的优化建议

### 6.1 针对 CN100342976C.pdf（专利文档）的优化

1. **解析模式选择**
   - 推荐使用 `DeepDOC` 模式
   - 专利文档通常包含复杂的表格和图片，DeepDOC 能够更好地识别

2. **分块参数调优**
   - `chunk_token_num`：建议设为 256-512（专利文档段落较长）
   - `delimiter`：可添加 `\n\n`（段落分隔符）
   - `overlapped_percent`：建议设为 10-20%（保持上下文连贯）

3. **检索参数调优**
   - `vector_similarity_weight`：建议设为 0.5（平衡语义和关键词）
   - `similarity_threshold`：建议设为 0.1-0.15（放宽阈值，避免漏检）
   - `top`：建议设为 512-1024（增加候选数量）

4. **Rerank 配置**
   - 建议配置外部 Rerank 模型（如 BGE-Reranker）
   - 或调整内置 Rerank 权重

### 6.2 针对图文混合问题的优化

1. **图片处理**
   - 启用 `image_context_size`，为图片添加上下文
   - 使用 Vision LLM 对图片进行描述（如果配置了）

2. **表格处理**
   - 启用 `table_context_size`，为表格添加上下文
   - 表格会自动转换为 HTML 格式保存

3. **OCR 优化**
   - 确保 OCR 模型正确加载
   - 对于扫描件，可提高 `zoomin` 参数

### 6.3 针对6个测试问题的优化策略

| 问题 | 优化策略 |
|------|----------|
| 发明人 | 关键词检索优先，设置 `vector_similarity_weight=0.3` |
| 特征描述 | 语义检索优先，设置 `vector_similarity_weight=0.7` |
| 部件位置 | 需要图文结合，启用图片上下文 |
| X1X2X3含义 | 需要上下文理解，增大 `chunk_token_num` |
| 气流方向 | 需要流程理解，增大 `chunk_token_num` 和重叠 |
| h1h2计算 | 需要公式识别，确保 OCR 正确提取公式 |

---

## 七、代码修改建议

如果需要修改 DeepDoc 代码以优化特定功能，以下是可以修改的关键位置：

1. **修改分块逻辑**
   - 文件：`rag/app/naive.py`
   - 函数：`naive_merge()`（第 1082-1143 行）

2. **修改检索逻辑**
   - 文件：`rag/nlp/search.py`
   - 函数：`retrieval()`（第 573-771 行）

3. **修改 Rerank 逻辑**
   - 文件：`rag/nlp/search.py`
   - 函数：`rerank()`（第 520-540 行）

4. **修改 PDF 解析逻辑**
   - 文件：`deepdoc/parser/pdf_parser.py`
   - 函数：`__call__()`（第 1673-1698 行）

---

## 八、总结

RAGFlow 的 DeepDoc 模块是一个功能强大的文档解析系统，通过深度学习进行版面分析和 OCR，能够处理复杂的 PDF 文档。分块策略灵活，支持多种参数调优。检索系统支持向量检索、全文检索和混合检索，并通过 Rerank 机制提高检索质量。

针对 RAG 工单14 的需求，建议：
1. 使用 DeepDOC 模式解析专利文档
2. 调整分块参数（增大 chunk_token_num 和重叠比例）
3. 调整检索权重（根据问题类型动态调整）
4. 配置外部 Rerank 模型（如果可用）
5. 启用图片和表格上下文

通过以上优化，有望达到 100% 的答案准确率。

---

*文档生成时间：2026-06-10*
*基于 RAGFlow v0.25.6 代码分析*
