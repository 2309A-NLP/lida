# Nginx 配置指南

本文档介绍 Nginx 反向代理和负载均衡配置，适用于 RAG 多角色智能聊天机器人系统的生产环境部署。

## 前置条件

安装 Nginx：

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install nginx

# CentOS / RHEL
sudo yum install nginx

# macOS
brew install nginx

# Windows
# 下载: https://nginx.org/en/download.html
```

验证安装：

```bash
nginx -v
```

## 配置文件说明

项目根目录下已提供 `nginx.conf` 文件，主要功能包括：

1. **负载均衡**：将请求分发到多个后端实例
2. **反向代理**：隐藏后端服务细节
3. **静态文件缓存**：加速静态资源访问
4. **限流**：防止恶意请求
5. **WebSocket 支持**：支持实时通信

## 快速部署

### 步骤 1：复制配置文件

```bash
# Linux
sudo cp nginx.conf /etc/nginx/nginx.conf

# 或放入 sites-available（推荐）
sudo cp nginx.conf /etc/nginx/sites-available/rag-chatbot
sudo ln -s /etc/nginx/sites-available/rag-chatbot /etc/nginx/sites-enabled/
```

### 步骤 2：修改 upstream 配置

根据实际部署情况，编辑 `upstream` 块中的后端服务器地址：

```nginx
upstream rag_backend {
    # 本地部署时使用
    server 127.0.0.1:8080 weight=5;

    # Docker Compose 部署时使用容器名
    # server backend1:8080 weight=5;
    # server backend2:8080 weight=5;
    # server backend3:8080 weight=5;

    # 多机部署时使用实际 IP
    # server 192.168.1.10:8080 weight=3;
    # server 192.168.1.11:8080 weight=3;

    keepalive 32;
}
```

### 步骤 3：修改 server_name

将 `server_name` 修改为实际域名或 IP：

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 改为实际域名
    # 或使用 IP
    # server_name 192.168.1.100;
}
```

### 步骤 4：测试配置并重载

```bash
# 测试配置语法
sudo nginx -t

# 重载配置
sudo nginx -s reload
```

## 负载均衡策略

`nginx.conf` 中预设了三种负载均衡策略：

### 1. 轮询（默认）

请求依次分发到后端服务器，带权重设置：

```nginx
upstream rag_backend {
    server 127.0.0.1:8080 weight=5;
    server 127.0.0.1:8081 weight=3;
    server 127.0.0.1:8082 weight=2;
}
```

### 2. 最少连接数

将请求分发到当前连接数最少的服务器：

```nginx
upstream rag_backend {
    least_conn;
    server 127.0.0.1:8080;
    server 127.0.0.1:8081;
    server 127.0.0.1:8082;
}
```

### 3. IP 哈希

同一 IP 的请求始终转发到同一台服务器（适用于需要会话保持的场景）：

```nginx
upstream rag_backend {
    ip_hash;
    server 127.0.0.1:8080;
    server 127.0.0.1:8081;
    server 127.0.0.1:8082;
}
```

## SSL/TLS 配置

### 使用 Let's Encrypt 免费证书

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书并自动配置
sudo certbot --nginx -d your-domain.com

# 自动续期（Certbot 默认添加定时任务）
sudo certbot renew --dry-run
```

### 手动配置 SSL

编辑 nginx.conf，取消 HTTPS server 块的注释并修改：

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL 证书路径
    ssl_certificate     /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # SSL 协议和加密套件
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # SSL 会话缓存
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;

    # HSTS（强制 HTTPS）
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # 代理后端
    location / {
        proxy_pass http://rag_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# HTTP 重定向到 HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### SSL 性能优化建议

```nginx
ssl_session_cache shared:SSL:50m;
ssl_session_timeout 1d;
ssl_session_tickets off;

# 使用更快的加密套件
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
```

## 限流配置

当前配置包含两层限流：

### 请求频率限制

```nginx
# 定义限流区域：每秒 100 个请求
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;

# 应用限流
limit_req zone=api_limit burst=200 nodelay;
```

### 连接数限制

```nginx
# 定义连接数限制区域
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

# 单 IP 最大连接数 10
limit_conn conn_limit 10;
```

推荐限流配置参考（根据实际情况调整）：

| 场景 | 速率 | 突发 | 说明 |
|------|------|------|------|
| 个人使用 | 50 r/s | 100 | 宽松限制 |
| 小团队 | 100 r/s | 200 | 默认配置 |
| 公网生产 | 30 r/s | 50 | 严格限制 |
| API 接口 | 10 r/s | 20 | 更严格 |

## 超时配置

```nginx
# 代理超时
proxy_connect_timeout 30s;    # 连接后端超时
proxy_send_timeout    60s;    # 发送数据超时
proxy_read_timeout    60s;    # 读取数据超时

# WebSocket 超时（长连接）
proxy_read_timeout 86400;     # 24小时
```

## 日志配置

```nginx
# 访问日志
log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                '$status $body_bytes_sent "$http_referer" '
                '"$http_user_agent" "$http_x_forwarded_for" '
                'rt=$request_time uct="$upstream_connect_time" '
                'uht="$upstream_header_time" urt="$upstream_response_time"';

access_log /var/log/nginx/rag-access.log main;
error_log  /var/log/nginx/rag-error.log warn;
```

日志字段说明：

| 字段 | 说明 |
|------|------|
| $request_time | 总请求处理时间 |
| $upstream_connect_time | 后端连接时间 |
| $upstream_header_time | 后端响应首字节时间 |
| $upstream_response_time | 后端完整响应时间 |

## 安全配置

### 隐藏 Nginx 版本号

```nginx
server_tokens off;
```

### 限制请求方法

```nginx
if ($request_method !~ ^(GET|POST|HEAD)$) {
    return 405;
}
```

### 防止点击劫持

```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
```

## 与 Docker Compose 配合使用

在 Docker Compose 环境中，Nginx 作为单独服务运行，配置已预设在 `docker-compose.yml` 中：

```yaml
nginx:
  image: nginx:alpine
  container_name: rag_nginx
  ports:
    - "8080:80"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf:ro
  depends_on:
    - backend1
    - backend2
    - backend3
```

Docker 环境中 upstream 应使用服务名：

```nginx
upstream rag_backend {
    server backend1:8080 weight=5;
    server backend2:8080 weight=5;
    server backend3:8080 weight=5;
    keepalive 32;
}
```

## 验证配置

访问以下端点确认配置生效：

```bash
# 健康检查
curl http://localhost:8080/health

# 查看响应头
curl -I http://localhost:8080/

# 查看 Nginx 状态（如已启用状态模块）
curl http://localhost:8080/nginx_status
```

## 常用管理命令

```bash
# 测试配置
sudo nginx -t

# 重载配置（不中断服务）
sudo nginx -s reload

# 重启
sudo systemctl restart nginx

# 查看状态
sudo systemctl status nginx

# 查看日志
tail -f /var/log/nginx/rag-access.log
tail -f /var/log/nginx/rag-error.log
```
