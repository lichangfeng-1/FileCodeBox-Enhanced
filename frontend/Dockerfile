# ============================================================
# FileCodeBox 前端 - Node 构建 + Nginx 运行
# 多阶段构建：编译 Vue 项目后由 Nginx 提供静态文件 + API 反代
# ============================================================

# ---------- Stage 1: 构建 ----------
FROM node:22-alpine AS builder

# npm 镜像配置（国内用户构建时传 --build-arg NPM_REGISTRY=https://registry.npmmirror.com）
ARG NPM_REGISTRY=""

# 安装 pnpm，可选切换 npm 镜像
RUN corepack enable && corepack prepare pnpm@9 --activate && \
    if [ -n "$NPM_REGISTRY" ]; then pnpm config set registry "$NPM_REGISTRY"; fi

WORKDIR /build

# 先复制依赖描述文件（利用 Docker 层缓存）
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# 复制源码并构建
COPY . .
RUN pnpm run build-only

# ---------- Stage 2: 运行 ----------
FROM nginx:alpine

# 删除默认配置
RUN rm /etc/nginx/conf.d/default.conf

# 复制自定义 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 从构建阶段复制编译产物
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -q --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
