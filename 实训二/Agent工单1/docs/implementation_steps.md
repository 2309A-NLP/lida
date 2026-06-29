# 记账本Agent - 实现步骤与问题记录

**工单编号**: 人工智能NLP-Agent数字人项目-记账本任务  
**日期**: 2025-01-14

---

## 1. 实现步骤

### 步骤1：数据库设计与实现

**文件**: `scripts/database.py`

**实现内容**:
- 创建SQLite数据库表结构
- 实现增删改查操作
- 支持按时间、成员、类别查询
- 支持汇总统计

**关键代码**:
```python
class MoneyDatabase:
    def add_record(self, date_str, member, category, item, amount, type_, note=""):
        # 添加账目记录
        
    def query_by_date_range(self, start_date, end_date, member=None):
        # 按日期范围查询
        
    def get_summary(self, start_date=None, end_date=None, member=None):
        # 获取汇总统计
```

---

### 步骤2：Agent核心功能实现

**文件**: `scripts/agent.py`

**实现内容**:
- 解析用户输入，提取日期、成员、类别、金额等信息
- 识别用户意图（记账/查询/删除）
- 调用数据库进行操作
- 生成回复

**关键函数**:
```python
def parse_money_input(text):
    # 解析记账输入，提取日期、成员、金额等

def handle_record(text):
    # 处理记账请求

def handle_query_by_month(text):
    # 处理按月查询

def handle_delete(text):
    # 处理删除请求

def process_message(text):
    # 处理用户消息（主入口）
```

---

### 步骤3：API接口实现

**文件**: `scripts/api.py`

**实现内容**:
- 提供RESTful API
- 支持对话式记账
- 提供Web界面

**API端点**:
| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web界面 |
| `/api/chat` | POST | 对话API |
| `/api/records` | GET | 获取记录 |
| `/api/summary` | GET | 获取汇总 |
| `/api/health` | GET | 健康检查 |

---

### 步骤4：测试验证

**文件**: `tests/test_agent.py`

**测试内容**:
- 记账功能测试
- 查询功能测试
- 删除功能测试
- 数据库操作测试

---

## 2. 问题记录

### 问题1：中文引号导致语法错误

**现象**: 使用中文引号（""）导致Python语法错误

**解决**: 使用英文引号（""）替代

---

### 问题2：日期解析不准确

**现象**: 用户输入"7月5日"时，无法正确解析

**解决**: 使用正则表达式匹配多种日期格式

---

### 问题3：类别识别不准确

**现象**: 用户说"买书"时，无法正确识别类别

**解决**: 建立类别关键词映射表

---

### 问题4：金额提取失败

**现象**: 用户说"花了50元"时，无法提取金额

**解决**: 使用正则表达式匹配数字+元的格式

---

## 3. 测试结果

### 3.1 测试用例

| 测试 | 输入 | 期望输出 | 结果 |
|------|------|----------|------|
| 1 | 今天女儿买了双登山鞋499元 | 已记录 | ✅ |
| 2 | 7月5日妈妈收到报销1000元 | 已记录 | ✅ |
| 3 | 看下这个月家里花钱明细 | 消费明细 | ✅ |
| 4 | 这个月女儿花了多少钱？ | 女儿消费明细 | ✅ |
| 5 | 删除女儿报旅游团的费用 | 已删除 | ✅ |

### 3.2 数据库调用率

- 测试结果：100%调用成功
- 所有记账、查询、删除操作都能正确调用数据库

---

## 4. 启动方式

### 4.1 安装依赖

```bash
pip install flask
```

### 4.2 启动服务

```bash
cd /mnt/d/Agent工单/Agent工单1
python scripts/api.py
```

### 4.3 访问界面

浏览器访问: http://localhost:5000

---

**文档生成时间**: 2025-01-14  
**编写人**: Agent Developer
