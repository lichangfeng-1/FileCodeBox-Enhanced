# @Time    : 2026/7/19
# @File    : db_config.py
# @Desc    : 多数据库配置解析，支持 PostgreSQL / MySQL / SQLite
import os
from urllib.parse import urlparse, unquote

from core.logger import logger
from core.settings import data_root, settings


# 环境变量名
ENV_DATABASE_URL = "DATABASE_URL"
ENV_DB_TYPE = "DB_TYPE"
ENV_DB_HOST = "DB_HOST"
ENV_DB_PORT = "DB_PORT"
ENV_DB_NAME = "DB_NAME"
ENV_DB_USER = "DB_USER"
ENV_DB_PASS = "DB_PASS"

# 默认 SQLite 文件路径
_SQLITE_FILE = os.path.join(data_root, "filecodebox.db")

# 支持的数据库类型
DB_TYPE_POSTGRES = "postgres"
DB_TYPE_MYSQL = "mysql"
DB_TYPE_SQLITE = "sqlite"

# Tortoise ORM 引擎映射
_ENGINE_MAP = {
    DB_TYPE_POSTGRES: "tortoise.backends.asyncpg",
    DB_TYPE_MYSQL: "tortoise.backends.mysql",
    DB_TYPE_SQLITE: "tortoise.backends.sqlite",
}

# 默认端口
_DEFAULT_PORTS = {
    DB_TYPE_POSTGRES: 5432,
    DB_TYPE_MYSQL: 3306,
}


def _resolve_db_type() -> str:
    """确定数据库类型，优先级：环境变量 > settings 配置"""
    env_type = os.environ.get(ENV_DB_TYPE, "").strip().lower()
    # 兼容 postgresql 和 postgres 两种写法
    if env_type == "postgresql":
        env_type = "postgres"
    if env_type in _ENGINE_MAP:
        return env_type
    config_type = str(getattr(settings, "db_type", DB_TYPE_SQLITE)).strip().lower()
    if config_type == "postgresql":
        config_type = "postgres"
    if config_type in _ENGINE_MAP:
        return config_type
    return DB_TYPE_SQLITE


def _parse_database_url(url: str) -> dict:
    """解析 DATABASE_URL 为配置字典

    支持格式:
        postgres://user:pass@host:port/dbname
        mysql://user:pass@host:port/dbname
        sqlite:///path/to/db.sqlite3
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    # 规范化 scheme
    if scheme in ("postgres", "postgresql"):
        db_type = DB_TYPE_POSTGRES
    elif scheme == "mysql":
        db_type = DB_TYPE_MYSQL
    elif scheme == "sqlite":
        db_type = DB_TYPE_SQLITE
    else:
        logger.warning(f"不支持的数据库协议: {scheme}，回退到 SQLite")
        db_type = DB_TYPE_SQLITE

    if db_type == DB_TYPE_SQLITE:
        # sqlite:///path/to/db 或 sqlite:////absolute/path
        path = parsed.path
        if path.startswith("//"):
            path = path[1:]  # 去掉多余的 /
        if not path or path == "/":
            path = _SQLITE_FILE
        return {"db_type": db_type, "file_path": path}

    return {
        "db_type": db_type,
        "host": parsed.hostname or "localhost",
        "port": parsed.port or _DEFAULT_PORTS.get(db_type, 5432),
        "database": (parsed.path or "/").lstrip("/"),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
    }


def _get_connection_config() -> dict:
    """构建 Tortoise ORM 连接配置"""
    # 优先级：DATABASE_URL 环境变量 > 分项环境变量 > settings 配置
    database_url = os.environ.get(ENV_DATABASE_URL, "").strip()
    if not database_url:
        database_url = str(getattr(settings, "db_url", "") or "").strip()

    if database_url:
        params = _parse_database_url(database_url)
    else:
        db_type = _resolve_db_type()
        if db_type == DB_TYPE_SQLITE:
            params = {"db_type": db_type, "file_path": _SQLITE_FILE}
        else:
            params = {
                "db_type": db_type,
                "host": os.environ.get(ENV_DB_HOST, "") or str(getattr(settings, "db_host", "localhost")),
                "port": int(os.environ.get(ENV_DB_PORT, "") or getattr(settings, "db_port", _DEFAULT_PORTS.get(db_type, 5432))),
                "database": os.environ.get(ENV_DB_NAME, "") or str(getattr(settings, "db_name", "filecodebox")),
                "user": os.environ.get(ENV_DB_USER, "") or str(getattr(settings, "db_user", "")),
                "password": os.environ.get(ENV_DB_PASS, "") or str(getattr(settings, "db_pass", "")),
            }

    db_type = params["db_type"]
    engine = _ENGINE_MAP[db_type]

    if db_type == DB_TYPE_SQLITE:
        credentials = {
            "file_path": params.get("file_path", _SQLITE_FILE),
            "journal_mode": "WAL",
            "busy_timeout": 10000,
            "foreign_keys": "ON",
        }
    else:
        pool_size = int(getattr(settings, "db_pool_size", 10))
        credentials = {
            "host": params["host"],
            "port": params["port"],
            "user": params["user"],
            "password": params["password"],
            "database": params["database"],
            "minsize": 1,
            "maxsize": pool_size,
        }

    return {
        "engine": engine,
        "credentials": credentials,
    }


def get_db_type() -> str:
    """获取当前数据库类型（供迁移脚本使用）"""
    database_url = os.environ.get(ENV_DATABASE_URL, "").strip()
    if not database_url:
        database_url = str(getattr(settings, "db_url", "") or "").strip()
    if database_url:
        return _parse_database_url(database_url)["db_type"]
    return _resolve_db_type()


def build_tortoise_config() -> dict:
    """构建完整的 Tortoise ORM 配置"""
    return {
        "connections": {
            "default": _get_connection_config(),
        },
        "apps": {
            "models": {
                "models": ["apps.base.models"],
                "default_connection": "default",
            }
        },
        "use_tz": True,
        "timezone": "Asia/Shanghai",
    }
