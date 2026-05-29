# Docker 部署指南

本文档介绍如何使用 Docker 容器化部署 RAG 多角色智能聊天机器人系统。

## 前置条件

| 软件 | 版本要求 |
|------|---------|
| Docker Engine | 24.0+ |
| Docker Compose | 2.0+ |

验证安装：

```bash
docker --version
docker compose version
```

## 方式一：单容器部署（Dockerfile）

适用于单实例快速部署和测试。

### 1. 构建镜像

```bash
cd RAG_多角色智能聊天机器人项目
docker build -t rag-chatbot:latest .
```

构建参数说明：

- `-t rag-chatbot:latest`：指定镜像名称和标签
- `.`：指定构建上下文为当前目录

### 2. 准备 .env 文件

确保项目根目录下存在正确的 `.env` 文件，Docker 运行时会读取该文件。

### 3. 运行容器

```bash
docker run -d \
  --name rag-chatbot \
  -p 8080:8080 \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  rag-chatbot:latest
```

参数说明：

| 参数 | 说明 |
|------|------|
| `-d` | 后台运行 |
| `--name` | 容器名称 |
| `-p 8080:8080` | 宿主机端口:容器端口映射 |
| `--env-file` | 加载环境变量文件 |
| `-v` | 挂载日志目录到宿主机 |
| `--restart unless-stopped` | 自动重启策略 |

### 4. 验证容器

```bash
# 查看容器状态
docker ps

# 查看容器日志
docker logs -f rag-chatbot

# 查看健康状态
docker inspect rag-chatbot --format='{{json .State.Health}}'
```

### 5. 访问应用

打开浏览器访问：http://localhost:8080

### 6. 管理容器

```bash
# 停止容器
docker stop rag-chatbot

# 启动容器
docker start rag-chatbot

# 重启容器
docker restart rag-chatbot

# 删除容器
docker rm -f rag-chatbot
```

## 方式二：多服务编排部署（Docker Compose）

适用于生产环境，包含 Nginx 负载均衡、Redis、Milvus 等完整服务栈。

### 1. 检查配置文件

确认项目根目录下存在以下文件：

- `docker-compose.yml` - 服务编排文件
- `Dockerfile` - 后端构建文件
- `nginx.conf` - Nginx 配置
- `.env` - 环境变量

### 2. 修改环境变量

编辑 `.env` 文件，确保 Docker 网络内的服务地址配置正确：

```ini
# Docker 内使用服务名访问
MILVUS_HOST=milvus
REDIS_HOST=redis
MYSQL_HOST=host.docker.internal  # 或外部 MySQL 地址
```

### 3. 启动所有服务

```bash
# 启动所有服务
docker compose up -d

# 仅启动特定服务
docker compose up -d backend1 backend2 backend3
```

### 4. 查看服务状态

```bash
# 查看所有服务状态
docker compose ps

# 输出示例
NAME                IMAGE               STATUS                   PORTS
rag_nginx           nginx:alpine        Up                       0.0.0.0:8080->80/tcp
rag_backend1        rag-chatbot:latest  Up (healthy)             0.0.0.0:8081->8080/tcp
rag_backend2        rag-chatbot:latest  Up (healthy)             0.0.0.0:8082->8080/tcp
rag_backend3        rag-chatbot:latest  Up (healthy)             0.0.0.0:8083->8080/tcp
rag_redis           redis:alpine        Up (healthy)             0.0.0.0:6379->6379/tcp
rag_milvus          milvusdb/milvus     Up                       0.0.0.0:19530->19530/tcp
rag_etcd            quay.io/coreos/etcd Up                       2379/tcp
rag_minio           minio/minio         Up                       0.0.0.0:9001-9002->9000-9001/tcp
```

### 5. 访问应用

通过 Nginx 统一入口访问：http://localhost:8080

### 6. 查看日志

```bash
# 查看所有服务日志
docker compose logs -f

# 查看特定服务日志
docker compose logs -f backend1
docker compose logs -f nginx
docker compose logs -f redis
```

### 7. 扩展实例数

Docker Compose 支持便捷的横向扩展：

```bash
# 扩展到 5 个后端实例
docker compose up -d --scale backend1=5
```

注意：扩展实例前需确保 `docker-compose.yml` 中的端口映射不冲突。

### 8. 停止所有服务

```bash
# 停止但不删除容器
docker compose stop

# 停止并删除容器和网络
docker compose down

# 停止并删除容器、网络和卷（会丢失数据）
docker compose down -v
```

## 镜像构建优化

### 使用 .dockerignore

在项目根目录创建 `.dockerignore` 文件（如已有则补充）：

```
venv/
.git/
.idea/
__pycache__/
*.pyc
.env
logs/*
!logs/.gitkeep
```

### 多阶段构建（进阶）

如需优化镜像大小，可修改 Dockerfile 使用多阶段构建：

```dockerfile
# 构建阶段
FROM python:3.10-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 运行阶段
FROM python:3.10-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY . .
CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8080"]
```

## 数据持久化

### 重要数据卷挂载

| 数据 | 容器路径 | 建议挂载路径 |
|------|---------|-------------|
| 应用日志 | /app/logs | ./logs |
| Redis 数据 | /data | redis_data (Docker 卷) |
| Milvus 数据 | /var/lib/milvus | milvus_data (Docker 卷) |
| MinIO 数据 | /minio_data | minio_data (Docker 卷) |

### 备份与恢复

```bash
# 备份 Redis
docker exec rag_redis redis-cli SAVE
cp /var/lib/docker/volumes/rag-redis-data/_data/dump.rdb ./backup/

# 恢复 Redis
docker cp ./backup/dump.rdb rag_redis:/data/dump.rdb
docker restart rag_redis
```

## 容器健康检查

Docker Compose 已配置健康检查。查看健康状态：

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

健康状态说明：
- `healthy`：服务运行正常
- `unhealthy`：服务异常，自动重启
- `starting`：服务启动中

## 故障排查

```bash
# 查看完整日志
docker compose logs --tail=200 -f

# 进入容器内部排查
docker exec -it rag_backend1 /bin/bash

# 查看容器资源使用
docker stats

# 检查网络连通性
docker exec rag_backend1 ping redis
docker exec rag_backend1 curl http://localhost:8080/health
```
