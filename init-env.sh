#!/bin/bash
# ============================================================
# FileCodeBox 环境初始化脚本
# 功能：如果 .env 不存在，自动从 .env.example 生成并填入随机密钥
# 用法：bash init-env.sh（在 docker compose up 之前执行）
# ============================================================

ENV_FILE=".env"
EXAMPLE_FILE=".env.example"

if [ -f "$ENV_FILE" ]; then
    echo "[OK] .env 已存在，跳过生成"
    exit 0
fi

if [ ! -f "$EXAMPLE_FILE" ]; then
    echo "[ERROR] 找不到 .env.example 模板文件！"
    exit 1
fi

echo "[INFO] .env 不存在，正在从 .env.example 自动生成..."

# 生成随机密钥
DB_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))" 2>/dev/null || openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
JWT_SEC=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))" 2>/dev/null || openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 64)
ADMIN_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))" 2>/dev/null || openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 22)

# 从模板生成 .env，替换占位符
sed -e "s|your_random_db_password_here|${DB_PASS}|g" \
    -e "s|your_random_jwt_secret_here_at_least_32_chars|${JWT_SEC}|g" \
    -e "s|your_admin_password_here|${ADMIN_PASS}|g" \
    "$EXAMPLE_FILE" > "$ENV_FILE"

echo "[OK] .env 已生成！"
echo ""
echo "  数据库密码: ${DB_PASS}"
echo "  JWT 密钥:   ${JWT_SEC:0:16}..."
echo "  管理员密码: ${ADMIN_PASS}"
echo ""
echo "[提示] 请牢记管理员密码，首次登录时使用。"
echo "[提示] 如需修改，编辑 .env 后重新 docker compose up -d"
