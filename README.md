<div align="center">

# FileCodeBox 前后端分离版

### 文件快递柜 - 匿名口令分享文本和文件

像拿快递一样取文件，无需注册，输入口令即可获取

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.x-4FC08D?style=flat-square&logo=vue.js&logoColor=white)](https://vuejs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docs.docker.com/compose/)

基于 [FileCodeBox v2.5.0](https://github.com/vastsa/FileCodeBox) 二次开发

</div>

---

## 项目简介

FileCodeBox 是一个轻量级的文件分享工具，基于 **FastAPI + Vue3** 开发。用户可以通过简单的方式匿名分享文本和文件，接收者只需输入提取码即可获取内容——就像从快递柜取出快递一样简单。

### 应用场景

| 场景 | 描述 |
|------|------|
| 📁 **临时文件分享** | 快速分享文件，无需注册登录 |
| 📝 **代码片段分享** | 分享代码、配置文件等文本内容 |
| 🕶️ **匿名文件传输** | 保护隐私的点对点传输 |
| 🔄 **跨设备传输** | 在不同设备间快速同步文件 |
| 💾 **临时存储** | 支持自定义过期时间的云存储 |
| 🌐 **私有服务** | 搭建企业或个人专属分享服务 |

---

## 功能特性

### 核心功能

| 功能 | 说明 |
|------|------|
| 文件分享 | 上传文件生成 5 位取件码，收件人输入码即可下载 |
| 文本分享 | 纯文本内容分享，支持 Markdown 预览 |
| 文件备注 | 上传文件时可附带文本说明（智能判断：纯文本/纯文件/文件+备注） |
| 多文件上传 | 一次选择多个文件批量分享，自动打包为 ZIP |
| 过期策略 | 支持按天数/小时/分钟/次数/永久多种过期方式 |
| 秒传去重 | 基于 SHA256 哈希检测，相同文件瞬间完成上传 |
| 分片上传 | 大文件自动切片上传，支持断点续传 |

### 管理后台

| 功能 | 说明 |
|------|------|
| 仪表盘 | 文件统计、存储空间、健康状态一览 |
| 文件管理 | 搜索/筛选/编辑/删除/批量操作 |
| 审计日志 | 记录每次操作的 IP、归属地、浏览器、设备、时间 |
| Webhook | 文件被取走/过期时触发 HTTP 回调通知（3次重试+SSRF防护） |
| 系统设置 | 上传限制/过期策略/存储配置/安全开关/ICP备案号 |
| 信任代理 | 配置反向代理 IP，确保审计记录真实 IP |

### 安全特性

- JWT 令牌认证 + 密码 SHA256 加盐哈希
- **登录防暴力破解**（可配置失败次数/锁定时长，底线保护）
- **文件类型深度校验**（magic bytes 检测，防扩展名伪造绕过）
- **Docker 容器非 root 运行**（最小权限原则）
- SSRF 防护（Webhook 禁止内网地址）
- CSV 导出防注入 + 条数上限
- 审计写入熔断器保护（连续失败自动暂停）
- Nginx 安全响应头（X-Frame-Options / CSP / nosniff）
- 禁止搜索引擎索引开关（robots meta + robots.txt）
- IP 上传频率限制 + 提取码错误次数限制
- 路径穿越防护 + CORS 安全配置 + 多数据库 SQL 兼容

### 技术亮点

- 毛玻璃（Glassmorphism）UI 风格 + 暗色模式
- 前后端分离架构（Nginx + FastAPI + PostgreSQL）
- 多数据库支持（PostgreSQL / MySQL / SQLite）
- Docker Compose 一键部署，.env 环境变量驱动
- ip2region 离线 IP 归属地（无需网络请求）
- 结构化日志 + 请求追踪
- 响应式设计，支持移动端

---

## 架构

```
docker compose
├── fcb-frontend (Nginx)     → Vue 3 静态文件 + API 反向代理
├── fcb-backend  (FastAPI)   → 纯 REST API（端口 12345）
└── fcb-postgres (PG 16)     → 数据库
```

---

## 快速开始

### 一键部署（推荐）

```bash
# 自动生成 .env（含随机密钥）+ 构建 + 启动
bash init-env.sh && docker compose up --build -d
```

部署完成后：
- 前端：`http://你的IP:40157`
- 管理后台：`http://你的IP:40157/#/login`
- 管理员密码在 `init-env.sh` 输出中显示

### 常用命令

```bash
docker compose logs -f     # 查看日志
docker compose down        # 停止服务
docker compose down -v     # 完全清理（含数据库，慎用）
```

### 自定义配置

编辑 `.env` 文件后重新 `docker compose up -d`，可配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `FRONTEND_PORT` | 前端访问端口 | 40157 |
| `DB_TYPE` | 数据库类型（postgresql/mysql/sqlite） | postgresql |
| `DB_PASSWORD` | 数据库密码 | 无（必填） |
| `JWT_SECRET` | JWT 签名密钥 | 无（必填） |
| `ADMIN_PASSWORD` | 管理员密码（首次初始化用） | 空（手动初始化） |
| `DATA_DIR` | 宿主机数据持久化目录 | Docker 卷 `fcb-data` |
| `PG_DATA_DIR` | PostgreSQL 数据目录 | Docker 卷 `fcb-pg-data` |
| `FCB_DATA_DIR` | 容器内数据目录（需与 volumes 挂载点一致） | /app/data |

> 💡 **数据持久化说明**：
> - 默认使用 Docker 命名卷（`fcb-data`），数据由 Docker 管理
> - 生产环境推荐设置 `DATA_DIR=/你的路径/data`，方便备份和迁移
> - `FCB_DATA_DIR` 一般无需修改，仅当你自定义了容器内挂载点时才需同步调整

详见 `.env.example` 中的注释说明。

### 源码部署（免 Docker）

适合不想装 Docker 的用户（学生、轻量 VPS、开发调试）。

**环境要求**：Python 3.12+ 、Node 22+（仅构建时需要）

```bash
# 1. 后端
cd backend
pip install -r requirements.txt

# 2. 前端构建（生成纯静态文件，构建完不再需要 Node）
cd ../frontend
npm install && npm run build-only
# 构建产物在 frontend/dist/ 目录

# 3. 启动（使用 SQLite，零配置）
cd ../backend
export DB_TYPE=sqlite          # Linux/Mac
set DB_TYPE=sqlite             # Windows
uvicorn main:app --host 0.0.0.0 --port 12345
```

**访问方式**：
- 后端 API：`http://你的IP:12345`
- 前端页面：用任意静态服务器托管 `frontend/dist/`（如 Nginx、Caddy、`python -m http.server`）
- 管理后台：`http://你的IP:12345/admin`

> 💡 提示：使用 SQLite 时数据库文件自动创建在 `backend/data/` 目录，无需安装任何数据库服务。
> 如需 PostgreSQL/MySQL，设置 `DB_TYPE`、`DB_HOST` 等环境变量即可（见 `.env.example`）。

---

## 系统初始化

### 方式一：自动初始化（推荐）

`.env` 中配置了 `ADMIN_PASSWORD` 时，系统首次启动自动完成初始化。

### 方式二：手动初始化

`ADMIN_PASSWORD` 为空时，浏览器打开站点会显示初始化页面，设置管理员密码（至少 8 位）即可。

### 管理员登录

访问 `http://你的IP:40157/#/login`，输入管理员密码登录。

> **忘记密码？** `docker compose down -v && docker compose up --build -d`（数据会丢失）

---

## 使用指南

### 命令行使用（curl）

**上传文件**

```bash
# 基础上传（默认 1 天有效期）
curl -X POST "http://localhost:40157/share/file/" \
  -F "file=@/path/to/file.txt"

# 上传文件 + 备注
curl -X POST "http://localhost:40157/share/file/" \
  -F "file=@/path/to/file.txt" \
  -F "text=这是文件备注说明"

# 指定 1 小时有效期
curl -X POST "http://localhost:40157/share/file/" \
  -F "file=@/path/to/file.txt" \
  -F "expire_value=1" \
  -F "expire_style=hour"

# 指定下载 10 次后过期
curl -X POST "http://localhost:40157/share/file/" \
  -F "file=@/path/to/file.txt" \
  -F "expire_value=10" \
  -F "expire_style=count"
```

**分享文本**

```bash
curl -X POST "http://localhost:40157/share/text/" \
  -F "text=要分享的文本内容"
```

**下载文件**

```bash
curl -L "http://localhost:40157/share/select/?code=取件码" -o filename
```

**有效期参数**

| `expire_style` | 说明 |
|----------------|------|
| `day` | 天数 |
| `hour` | 小时 |
| `minute` | 分钟 |
| `count` | 下载次数 |
| `forever` | 永久有效 |

---

## 反向代理

支持 Nginx / Lucky666 等反向代理。配置要点：必须传递真实客户端 IP 头，否则审计系统记录的将是代理服务器 IP。

### 基础配置（标准 Nginx）

```nginx
location / {
    proxy_pass http://127.0.0.1:40157;
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 0;          # 不限制上传大小
    proxy_request_buffering off;     # 流式上传
    proxy_read_timeout 600s;
}
```

> 💡 **Lucky666 用户注意**：`client_max_body_size`、`proxy_request_buffering`、`proxy_read_timeout` 不能写在自定义配置里，需在 Lucky 主配置界面设置（请求体大小=0、超时=600s）。自定义配置只写下方的 `proxy_set_header` 等指令。

### Lucky666 完整自定义配置

以下为 Lucky666 反向代理的完整配置（在 Lucky 后台「自定义配置」中粘贴）：

> ⚠️ **Lucky666 自定义配置语法限制**（官方文档）：
>
> **支持的指令**（每行末尾必须有 `;`）：
> - `proxy_set_header Header Value;` — 设置发送到后端的请求头（Value 为空字符串时删除该头）
> - `proxy_hide_header Header;` — 删除后端响应返回给浏览器的指定响应头
> - `add_header Header Value [always];` — 给响应追加 header（加 `always` 后所有状态码生效）
> - `proxy_redirect From To;` — 替换响应中的 Location/Refresh 重定向地址
> - `location /path/ { 指令; }` — 按路径分组应用指令（支持前缀/`=`精确/`~`正则/`~*`忽略大小写/`!~`取反）
> - `path /api/* 指令;` — Lucky 简写语法（支持 `*` 通配、`regexp:` 正则、`!!!` 取反）
>
> **不支持**：`client_max_body_size`、`proxy_request_buffering`、`proxy_read_timeout`、`proxy_pass` 等
> （这些需在 Lucky 主配置界面设置）
>
> **常用变量**：`$host`、`$http_host`、`$scheme`、`$request`、`$request_method`、`$request_uri`、`$uri`、`$args`、`$query_string`、`$remote_addr`、`$remote_port`、`$server_port`、`$http_upgrade`、`$connection_upgrade`、`$proxy_add_x_forwarded_for`、`$http_请求头名`
>
> **注意**：文件服务只执行响应头相关指令（`add_header`、`proxy_hide_header`）；`proxy_set_header`、`proxy_redirect` 仅用于反向代理场景。

```nginx
# ============================================================
# FileCodeBox + Lucky666 反向代理自定义配置
# 适用版本：FileCodeBox 二开版（含审计/Webhook/秒传）
# ============================================================

# ===== 1. 真实客户端信息传递（审计系统核心依赖） =====
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host $http_host;
proxy_set_header X-Forwarded-Port $server_port;
proxy_set_header Host $http_host;

# ===== 2. 大文件上传/下载：流式转发 + 断点续传 =====
proxy_set_header X-Content-Length $http_content_length;
proxy_set_header Range $http_range;
proxy_set_header If-Range $http_if_range;
proxy_set_header Content-Range $http_content_range;

# ===== 3. WebSocket 升级支持 =====
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection $connection_upgrade;

# ===== 4. 重定向修正 =====
proxy_redirect http://127.0.0.1:12345/ /;

# ===== 5. 安全：隐藏后端技术栈信息 =====
proxy_hide_header X-Powered-By;
proxy_hide_header Server;
proxy_hide_header X-Internal-Path;

# ===== 6. 安全：响应头加固 =====
add_header X-Frame-Options SAMEORIGIN always;
add_header X-Content-Type-Options nosniff always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy strict-origin-when-cross-origin always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

# ===== 7. 分片上传/预签名路径：禁缓存 =====
location /chunk/ {
    add_header Cache-Control "no-store" always;
}

location /presign/ {
    add_header Cache-Control "no-store" always;
}

# ===== 8. 管理后台：禁缓存（防敏感数据残留） =====
location /admin/ {
    add_header Cache-Control "no-store, no-cache, must-revalidate" always;
    add_header Pragma "no-cache" always;
}

# ===== 9. 文件下载：隐藏内部头 =====
location /share/download {
    proxy_hide_header X-Internal-Path;
}

# ===== 10. 静态资源：允许浏览器缓存 =====
location /assets/ {
    add_header Cache-Control "public, max-age=86400" always;
}

# ===== 11. 健康检查端点 =====
location = /health {
    add_header Cache-Control "no-store" always;
}
```

> **重要：** 配置反代后，系统默认信任所有私有网段（`172.16.0.0/12`、`10.0.0.0/8`、`192.168.0.0/16`）的代理头。如果你的代理服务器是公网 IP，需在管理后台「系统设置 → 信任代理」中添加对应 IP。

---

## 技术栈

| 类别 | 技术 |
|------|------|
| **后端框架** | FastAPI + Uvicorn |
| **数据库** | PostgreSQL 16 / MySQL / SQLite（Tortoise ORM） |
| **前端框架** | Vue 3 + Tailwind CSS + Vite |
| **容器化** | Docker + Docker Compose + Nginx |
| **对象存储** | 本地 / S3 协议 / WebDAV |
| **运行环境** | Python 3.12+ / Node.js 22+ |

---

## 目录结构

```
├── .env.example         # 配置模板（复制为 .env 使用）
├── .gitignore
├── docker-compose.yml   # 容器编排
├── init-env.sh          # 自动生成 .env + 随机密钥
├── README.md
├── backend/             # FastAPI 后端
│   ├── Dockerfile
│   ├── main.py
│   ├── apps/            # 应用模块（admin/base）
│   ├── core/            # 核心模块（配置/审计/存储/安全）
│   └── requirements.txt
└── frontend/            # Vue 3 前端
    ├── Dockerfile       # Node 构建 + Nginx 运行
    ├── nginx.conf       # 反代配置
    ├── src/             # 源码
    └── package.json
```

---

## 常见问题

<details>
<summary><b>如何修改上传大小限制？</b></summary>

在管理后台 → 系统设置中修改 `uploadSize`。如使用反向代理，还需调整 `client_max_body_size`。
</details>

<details>
<summary><b>如何备份数据？</b></summary>

备份 `.env` 中 `DATA_DIR` 和 `PG_DATA_DIR` 指定的目录即可（包含上传文件和数据库）。
</details>

<details>
<summary><b>如何修改管理员密码？</b></summary>

登录管理后台 → 系统设置 → 修改管理员密码。
</details>

<details>
<summary><b>如何切换为 SQLite（零配置）？</b></summary>

在 `.env` 中设置 `DB_TYPE=sqlite`，注释掉 PostgreSQL 相关配置，然后 `docker compose up -d`。
</details>

---

## 免责声明

本项目开源仅供学习交流使用，不得用于任何违法用途，否则后果自负，与作者无关。使用本项目时请保留项目地址和版权信息。

---

<div align="center">

基于 [FileCodeBox](https://github.com/vastsa/FileCodeBox) by [vastsa](https://github.com/vastsa) 二次开发

</div>
