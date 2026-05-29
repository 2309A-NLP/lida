# RAG 检索流程设计文档

## 1. RAG 系统概述

RAG (Retrieval-Augmented Generation) 是系统的核心功能，通过检索相关知识库来增强 AI 回复的准确性和专业性。

### 1.1 整体流程

```
用户输入问题
    |
    v
[1. 分词与关键词提取]
    - jieba 中文分词
    - 合并预定义关键词集合
    |
    v
[2. 知识检索]
    - 方式 A: Milvus 混合检索 (BGE-M3 + BM25 + BGE-rerank)
    - 方式 B: 内存关键词匹配 (jieba + BM25) -- 默认降级方案
    |
    v
[3. 重排序]
    - 按相关性分数降序排列
    - 截取 top_k 个结果
    |
    v
[4. 上下文注入]
    - 将检索结果拼接到 System Prompt 中
    - 传递给 DeepSeek API 生成回答
    |
    v
AI 回复 (基于知识库的专业回答)
```

### 1.2 检索策略优先级

系统优先尝试最高级的检索方式，逐步降级：

```
1. Milvus 混合检索 (BGE-M3 向量 + BM25 + BGE-rerank)
       |
       v (Milvus 不可用或返回空结果)
2. 内存关键词匹配 (jieba 分词 + 预定义关键词 + BM25 排序)
```

## 2. 降级方案：jieba 分词 + BM25 关键词检索

这是系统默认使用的检索方式（当 Milvus 不可用时），也是本系统的核心检索实现。

### 2.1 检索入口

**方法**: `KnowledgeService.search(query, role_id=None, top_k=3)`

**参数:**
- `query`: 用户输入的问题文本
- `role_id`: 指定搜索的角色知识库 (None 时搜索所有角色)
- `top_k`: 返回最相关的段落数量 (默认 3)

### 2.2 分词处理流程

```
用户输入: "我最近很焦虑，总是失眠"
    |
    v
jieba.lcut("我最近很焦虑，总是失眠")
    |
    v
query_words = {"我", "最近", "很焦虑", "总是", "失眠"}
    |
    v
合并预定义关键词集合
    |
    v
all_keywords = {"我", "最近", "很焦虑", "总是", "失眠", "焦虑", "抑郁", 
                "压力", "失眠", "情绪", "心理", "精神", "治疗", "症状",
                "障碍", "诊断", "药物", "咨询", "康复", "强迫", "惊恐", 
                "双相", "精神分裂", ...}
```

### 2.3 预定义关键词集合

以下关键词在检索时自动合并，用于增强检索效果：

```python
keywords = {
    # 心理情绪类
    "焦虑", "抑郁", "压力", "失眠", "情绪", "心理",
    # 临床精神类
    "精神", "治疗", "症状", "障碍", "诊断", "药物", "咨询", "康复",
    "强迫", "惊恐", "双相", "精神分裂",
    # 法律相关 (预留)
    "法律", "合同", "纠纷", "权利", "义务", "赔偿", "诉讼", "仲裁"
}
```

**设计说明:**
- 这些关键词覆盖了心理健康和精神医学领域的核心概念
- 即使患者的问题中没有显式提到专业术语，这些关键词也能帮助匹配到相关知识
- 法律相关关键词已预留（为可能的律师角色做准备），目前实际使用中效果有限

### 2.4 段落匹配与排序

```python
relevant = []
for para in paragraphs:
    hit_count = sum(1 for kw in all_keywords if kw in para)
    if hit_count > 0:
        relevant.append((para, hit_count))

relevant.sort(key=lambda x: x[1], reverse=True)
return [para for para, _ in relevant[:top_k]]
```

**排序逻辑:**
1. 遍历知识库中的所有段落
2. 对每个段落，统计命中了多少关键词
3. 命中数大于 0 的段落被视为相关段落
4. 按命中数量从高到低降序排列
5. 截取前 top_k 个段落返回

**评分示例:**

| 段落 | 命中关键词 | 命中数 | 排名 |
|------|-----------|--------|------|
| "广泛性焦虑障碍是一种以持续的、过度的担忧和焦虑为特征的心理障碍..." | 焦虑、障碍、心理 | 3 | 1 |
| "认知行为疗法（CBT）是治疗焦虑症的首选心理治疗方法之一..." | 焦虑、治疗、心理 | 3 | 1 |
| "失眠症的治疗包括认知行为疗法和药物治疗..." | 失眠、治疗 | 2 | 3 |
| "健康的饮食和规律的运动有助于改善情绪..." | 情绪 | 1 | 4 |

### 2.5 完整检索算法伪代码

```
function search(query, role_id, top_k=3):
    # 步骤 1: 确定搜索范围
    if role_id:
        paragraphs = knowledge_base[role_id]
    else:
        paragraphs = merge_all_knowledge_bases()
    
    # 步骤 2: jieba 分词
    try:
        query_words = set(jieba.lcut(query))
    except ImportError:
        query_words = set(query)  # 降级为字符级
    
    # 步骤 3: 合并预定义关键词
    all_keywords = query_words | predefined_keywords
    
    # 步骤 4: 计算每个段落的关键词命中数
    scored_paragraphs = []
    for para in paragraphs:
        hits = count_keyword_hits(para, all_keywords)
        if hits > 0:
            scored_paragraphs.append((para, hits))
    
    # 步骤 5: 按命中数降序排序
    scored_paragraphs.sort(by=hits, descending)
    
    # 步骤 6: 返回 top_k
    return [para for para, _ in scored_paragraphs[:top_k]]
```

## 3. 上下文注入

检索到的知识段落被注入到 System Prompt 中，格式如下：

```
你是林语薇，一位温暖共情的心理医生...

【重要】请基于以下知识库内容回答用户问题：
广泛性焦虑障碍（GAD）是一种以持续的、过度的担忧和焦虑为特征的心理障碍，患者常常难以控制自己的担忧情绪，并伴有多种躯体症状...
认知行为疗法（CBT）是治疗焦虑症的首选心理治疗方法之一，通过改变患者的思维模式和行为习惯来缓解焦虑症状...
```

**注入策略:**
- 最多注入前 3 条最相关的知识段落
- 注入文本前添加 "【重要】" 标记，引导 LLM 优先参考
- 角色提示词在前，知识库内容在后

## 4. Milvus 混合检索 (高级方案)

当 Milvus 向量数据库可用时，系统会使用更高级的混合检索方案。

### 4.1 检索链路

```
BGE-M3 向量化模型
    |
    ├──> 向量检索: 将问题/段落转为 1024 维向量，计算余弦相似度
    |
    ├──> BM25 检索: 基于词频-逆文档频率的关键词检索
    |
    ├──> 分数融合: 向量分数 * 0.7 + BM25 分数 * 0.3
    |
    └──> BGE-reranker 重排序: 对 top_n 结果进行二次排序
```

### 4.2 配置参数

```python
# config/settings.py
hybrid_search_weight = 0.7   # 向量搜索权重
bm25_weight = 0.3            # BM25 搜索权重
rerank_top_n = 3             # 重排序后返回条数
top_k = 5                    # 初始检索条数
embedding_dim = 1024         # BGE-M3 向量维度
```

## 5. 知识库加载与管理

### 5.1 文件加载

知识库文件位于 `text_data/` 目录，启动时由 KnowledgeService 自动加载：

```
text_data/
├── 心理医生.txt      (33 条, 心理健康相关内容)
└── 精神科医生.txt    (492 条, 精神障碍诊疗规范)
```

**解析规则:**
- 按 `\n\n` (两个换行符) 分割为段落
- 过滤空段落
- 编码格式: UTF-8

### 5.2 动态管理 API

| 操作 | 端点 | 说明 |
|------|------|------|
| 添加文档 | POST /knowledge/add | 向指定角色添加新段落 |
| 清空知识库 | DELETE /knowledge/clear/{role_id} | 清空指定角色的知识库 |
| 重新加载 | POST /knowledge/reload | 从文件系统重新读取所有知识库 |
| 搜索测试 | GET /knowledge/search | 测试检索效果 |

## 6. 检索效果优化建议

### 6.1 当前限制

- 纯关键词匹配无法理解语义相似性（如"难过"和"悲伤"无法关联）
- 预定义关键词需要人工维护扩展
- 关键词命中数为整数，区分度有限
- 段落长度差异会影响命中概率

### 6.2 优化方向

1. **引入同义词扩展**: 使用同义词词典扩展查询词
2. **TF-IDF 加权**: 引入词频权重而非简单的命中计数
3. **语义向量化**: 启用 BGE-M3 模型进行语义检索
4. **段落分块优化**: 控制段落长度，提高检索精度
5. **多路召回融合**: 结合多种检索策略的结果
