# ============================================================
# FileCodeBox 后端 - 纯 Python API 镜像
# 前后端分离架构：后端只提供 REST API，不再内嵌前端静态文件
# ============================================================

FROM python:3.12-slim-bookworm

LABEL maintainer="FileCodeBox"

# 设置工作目录
WORKDIR /app

# 镜像源配置（国内用户构建时传 --build-arg APT_MIRROR=mirrors.aliyun.com PIP_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple）
ARG APT_MIRROR=""
ARG PIP_MIRROR=""

# 安装系统依赖（curl 用于健康检查）
RUN if [ -n "$APT_MIRROR" ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 先复制依赖文件（利用 Docker 层缓存）
COPY requirements.txt .
RUN if [ -n "$PIP_MIRROR" ]; then \
      pip install --no-cache-dir -i "$PIP_MIRROR" --trusted-host "$(echo $PIP_MIRROR | sed 's|https\?://||;s|/.*||')" -r requirements.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

# 复制后端源码
COPY . .

# 确保 ip2region.xdb 存在（如果被 .dockerignore 意外排除，从网络下载保底）
RUN if [ ! -f /app/core/ip2region.xdb ]; then \
      echo "Downloading ip2region.xdb..." && \
      curl -L -o /app/core/ip2region.xdb "https://gitee.com/lionsoul/ip2region/raw/master/data/ip2region.xdb"; \
    fi

# 创建数据目录
RUN mkdir -p /app/data/share

# SEC-007: 创建非 root 用户运行应用（最小权限原则）
RUN groupadd -r fcb && useradd -r -g fcb -d /app -s /sbin/nologin fcb && \
    chown -R fcb:fcb /app/data

# 入口脚本：解决 volume 挂载后权限丢失问题（以 root 修正权限后降权运行）
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# 暴露 API 端口
EXPOSE 12345

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:12345/api/v1/config || exit 1

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "12345"]
