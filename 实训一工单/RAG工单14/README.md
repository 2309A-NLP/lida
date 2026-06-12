# RAG工单14 - 修复低质量工业PDF的解析与信息丢失

## 项目概述

针对IMDR数据集中低分辨率、格式复杂的图片型PDF，修复RAGFlow解析流水线中导致图文信息丢失、关联错误的缺陷。

## 目录结构

```
RAG工单14/
├── README.md                    # 项目说明
├── documents/                   # 1700个PDF文件（IMDR数据集）
├── questions.jsonl              # 6个测试问题
├── deepdoc_analysis.md          # DeepDoc技术分析文档
├── optimization_plan.md         # 调优方案
├── pdf_pages/                   # CN100342976C.pdf的页面截图
├── scripts/                     # 自动化脚本
│   ├── deploy_ragflow.sh        # RAGFlow部署脚本
│   ├── build_knowledge_base.py  # 知识库构建脚本
│   ├── test_questions.py        # 问题测试脚本
│   └── optimize.py              # 调优自动化脚本
├── results/                     # 测试结果
│   ├── round1_default/          # 第一轮：默认配置
│   ├── round2_params/           # 第二轮：参数调优
│   ├── round3_rerank/           # 第三轮：Rerank优化
│   └── round4_deep/             # 第四轮：深度优化
└── docs/                        # 文档输出
    ├── task1_technical_summary.md  # 任务一技术总结
    └── task2_test_report.md        # 任务二测试报告
```

## 任务要求

### 任务一：部署RAGFlow
1. 部署运行RAGFlow项目
2. 梳理DeepDoc模块技术实现：
   - paper_id为paper/table/one/knowledge_graph时的分块策略
   - do_handle_task函数的主要逻辑
   - DeepDoc内置的文件解析器

### 任务二：构建知识库并测试
1. 上传CN100342976C.pdf到知识库
2. 测试6个问题，达到100%准确率
3. 调整解析方法、分块策略、向量相似度权重、ReRank模型

## 验收标准

1. **文档验收**：技术总结文档清晰准确
2. **功能验收**：问答准确率达到100%
3. **性能验收**：响应时间不超过3秒

## 快速开始

```bash
# 1. 部署RAGFlow
bash scripts/deploy_ragflow.sh

# 2. 构建知识库
python scripts/build_knowledge_base.py

# 3. 测试问题
python scripts/test_questions.py

# 4. 运行调优
python scripts/optimize.py
```

## 工时预估

2人日

## 产出物

1. 任务一技术总结文档
2. 任务二测试结果、原因分析及优化方案
3. 演示视频
4. 修改后的代码
