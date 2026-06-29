# 记账本Agent - 软件设计文档

**工单编号**: 人工智能NLP-Agent数字人项目-记账本任务  
**版本**: V1.0  
**日期**: 2025-01-14

---

## 1. 功能概述

### 1.1 核心功能

| 功能 | 说明 |
|------|------|
| 记账 | 记录家庭成员的消费支出与财政收入 |
| 查询 | 按时间、成员、项目查询账目 |
| 汇总 | 按月、按成员统计消费情况 |
| 删除 | 删除错误记录 |

### 1.2 支持的成员

- 爸爸
- 妈妈
- 女儿

---

## 2. 流程图

```
用户输入
    ↓
意图识别
    ↓
┌─────────────────────────────────────┐
│  记账?  │  查询?  │  删除?  │  其他  │
└─────────────────────────────────────┘
    ↓        ↓        ↓        ↓
 解析信息  解析条件  解析条件  开场白
    ↓        ↓        ↓        ↓
 存入数据库 查询数据库 查询数据库 返回帮助
    ↓        ↓        ↓
 返回确认  返回结果  返回确认
```

---

## 3. 数据库设计

### 3.1 表结构

```sql
CREATE TABLE money_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,           -- 日期（YYYY-MM-DD）
    member TEXT NOT NULL,         -- 成员（爸爸/妈妈/女儿）
    category TEXT NOT NULL,       -- 类别（买书/吃饭/交通等）
    item TEXT NOT NULL,           -- 具体项目
    amount REAL NOT NULL,         -- 金额
    type TEXT NOT NULL,           -- 类型（收入/支出）
    note TEXT DEFAULT '',         -- 备注
    created_at TEXT,              -- 创建时间
    updated_at TEXT               -- 更新时间
);
```

### 3.2 索引

```sql
CREATE INDEX idx_date ON money_notes(date);
CREATE INDEX idx_member ON money_notes(member);
CREATE INDEX idx_category ON money_notes(category);
CREATE INDEX idx_type ON money_notes(type);
```

---

## 4. 输入格式

### 4.1 记账格式

```
x年x月x日，谁做什事收入/支出多少钱
```

**示例**：
- 今天女儿买了双登山鞋499元
- 7月5日妈妈收到报销1000元
- 今天爸爸买书花了50元

### 4.2 查询格式

```
看下这个月家里花钱明细
这个月女儿花了多少钱？
我哪天买的三体
```

### 4.3 删除格式

```
删除女儿报旅游团的费用
```

---

## 5. 类别映射

| 类别 | 关键词 |
|------|--------|
| 买书 | 书、书籍、教材、小说 |
| 吃饭 | 饭、餐、午餐、晚餐、早餐、外卖 |
| 交通 | 打车、地铁、公交、高铁、飞机 |
| 购物 | 衣服、鞋、包、化妆品、日用品 |
| 娱乐 | 电影、游戏、旅游、KTV |
| 教育 | 学费、培训、课程 |
| 医疗 | 看病、药、体检 |
| 工资 | 工资、薪水、奖金 |
| 报销 | 报销 |

---

## 6. 技术栈

| 组件 | 技术选型 |
|------|----------|
| 后端框架 | Flask |
| 数据库 | SQLite |
| 前端 | HTML + CSS + JavaScript |
| API | RESTful |

---

## 7. 目录结构

```
Agent工单1/
├── scripts/
│   ├── database.py      # 数据库模块
│   ├── agent.py         # Agent核心功能
│   └── api.py           # API接口
├── tests/
│   └── test_agent.py    # 测试脚本
├── docs/
│   └── design_doc.md    # 设计文档
├── data/
│   └── money_notes.db   # SQLite数据库
└── templates/
    └── index.html       # 前端页面
```

---

**文档生成时间**: 2025-01-14  
**编写人**: Agent Developer
