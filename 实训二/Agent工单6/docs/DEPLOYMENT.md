# 智能体任务工单系统 - 部署指南

## 环境要求

- Python 3.9 或更高版本
- pip (Python包管理器)
- 至少 2GB 内存
- 磁盘空间 500MB+

## 安装步骤

### 1. 克隆或下载项目

```bash
cd d:\Agent工单\Agent工单6
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv

# Windows激活虚拟环境
venv\Scripts\activate

# Linux/Mac激活虚拟环境
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

复制 `.env.example` 为 `.env` 并填入配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入必要的配置：
- `OPENAI_API_KEY`: OpenAI API密钥（可选）
- `ANTHROPIC_API_KEY`: Anthropic API密钥（可选）
- `SECRET_KEY`: 系统密钥（必须修改）

### 5. 初始化数据库

数据库会在首次启动时自动初始化，无需手动操作。

### 6. 启动服务

```bash
python main.py
```

### 7. 访问系统

打开浏览器访问：
- 系统首页: http://localhost:8000
- API文档: http://localhost:8000/docs
- 交互式文档: http://localhost:8000/redoc

## 生产环境部署

### 使用Gunicorn（Linux）

```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend.api:app --bind 0.0.0.0:8000
```

### 使用Docker

创建 `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["python", "main.py"]
```

构建并运行：

```bash
docker build -t workorder-system .
docker run -p 8000:8000 workorder-system
```

## 配置说明

主要配置文件：`config/config.yaml`

- **服务器配置**: host, port, debug
- **数据库配置**: 支持SQLite和PostgreSQL
- **AI配置**: OpenAI和Anthropic API设置
- **NLP配置**: 语言模型和分析阈值
- **Agent配置**: 并发任务数和超时设置

## 故障排查

### 端口被占用

修改 `.env` 文件中的 `PORT` 变量为其他端口。

### 数据库连接失败

检查 `config/config.yaml` 中的数据库配置，确保路径正确且有写入权限。

### AI服务不可用

系统可以在没有AI服务的情况下运行，但功能会受限。确保API密钥配置正确。

## 性能优化

1. 使用PostgreSQL替代SQLite以获得更好的并发性能
2. 配置Redis用于缓存
3. 使用反向代理（Nginx/Apache）
4. 启用CDN加速静态资源

## 安全建议

1. 修改默认的 `SECRET_KEY`
2. 使用HTTPS协议
3. 定期备份数据库
4. 限制API访问频率
5. 启用日志审计

## 联系支持

如有问题，请查看项目README或联系技术支持。
