#!/bin/sh
# ============================================================
# FileCodeBox 容器入口脚本
# 解决 Docker 卷挂载后权限丢失问题：
#   构建时 chown 会被 volume mount 覆盖，
#   因此需要在运行时（以 root 身份）修正数据目录权限，
#   然后降权到 fcb 用户执行主进程。
# ============================================================

# 确保数据目录及子目录存在且权限正确
mkdir -p /app/data/share
chown -R fcb:fcb /app/data

# 降权执行主命令（SEC-007: 最小权限原则）
# setpriv 是 Debian 自带的 util-linux 工具，无需额外安装
exec setpriv --reuid=fcb --regid=fcb --init-groups "$@"
