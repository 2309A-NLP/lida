# 记账本Agent

**工单编号**: 人工智能NLP-Agent数字人项目-记账本任务  
**版本**: V1.0  
**日期**: 2025-01-14

---

## 1. 项目简介

家庭记账本智能体，通过对话方式实现记账、查询、删除等功能。

### 1.1 核心功能

- **记账**: 记录家庭成员的消费支出与财政收入
- **查询**: 按时间、成员、项目查询账目
- **汇总**: 按月、按成员统计消费情况
- **删除**: 删除错误记录

### 1.2 支持的成员

- 爸爸
- 妈妈
- 女儿

---

## 2. 快速开始

### 2.1 安装依赖

```bash
cd /mnt/d/Agent工单/Agent工单1
pip install -r requirements.txt
```

### 2.2 启动服务

```bash
python scripts/api.py
```

### 2.3 访问界面

浏览器访问: http://localhost:5000

---

## 3. 使用指南

### 3.1 记账

```
今天女儿买了双登山鞋499元
7月5日妈妈收到报销1000元
今天爸爸买书花了50元
```

### 3.2 查询

```
看下这个月家里花钱明细
这个月女儿花了多少钱？
我哪天买的三体
```

### 3.3 删除

```
删除女儿报旅游团的费用
```

---

## 4. API接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web界面 |
| `/api/chat` | POST | 对话API |
| `/api/records` | GET | 获取记录 |
| `/api/summary` | GET | 获取汇总 |
| `/api/health` | GET | 健康检查 |

### 4.1 对话API示例

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "今天女儿买了双登山鞋499元"}'
```

响应：
```json
{"reply": "已记录：2025-01-14，女儿，购物，登山鞋，支出499.0元"}
```

---

## 5. 目录结构

```
Agent工单1/
├── scripts/
│   ├── database.py      # 数据库模块
│   ├── agent.py         # Agent核心功能
│   └── api.py           # API接口
├── tests/
│   └── test_agent.py    # 测试脚本
├── docs/
│   ├── design_doc.md    # 设计文档
│   └── implementation_steps.md  # 实现步骤
├── data/
│   └── money_notes.db   # SQLite数据库
├── requirements.txt     # 依赖列表
└── README.md            # 项目说明
```

---

## 6. 测试

### 6.1 运行测试

```bash
python tests/test_agent.py
```

### 6.2 测试用例

| 测试 | 输入 | 期望输出 |
|------|------|----------|
| 1 | 今天女儿买了双登山鞋499元 | 已记录 |
| 2 | 7月5日妈妈收到报销1000元 | 已记录 |
| 3 | 看下这个月家里花钱明细 | 消费明细 |
| 4 | 这个月女儿花了多少钱？ | 女儿消费明细 |
| 5 | 删除女儿报旅游团的费用 | 已删除 |

---

**文档生成时间**: 2025-01-14  
**编写人**: Agent Developer
