"""测试公共基础设施（所有测试文件共享）

避免每个测试文件重复定义 DB_CONFIG、初始化逻辑、通用夹具。
用法：from tests.helpers import DB_CONFIG, init_test_db, create_test_file
"""
import asyncio
from tortoise import Tortoise

from apps.base.models import FileCodes
from core.utils import get_now

# 统一的内存数据库配置（所有测试共用）
DB_CONFIG = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.sqlite",
            "credentials": {"file_path": ":memory:"},
        }
    },
    "apps": {
        "models": {
            "models": ["apps.base.models"],
            "default_connection": "default",
        }
    },
    "use_tz": False,
    "timezone": "Asia/Shanghai",
}


async def init_test_db():
    """初始化内存数据库 + 生成表结构"""
    await Tortoise.init(config=DB_CONFIG)
    await Tortoise.generate_schemas()


async def close_test_db():
    """关闭数据库连接"""
    await Tortoise.close_connections()


async def create_test_file(
    code: str,
    size: int = 100,
    text: str = None,
    prefix: str = "文件",
    expired_count: int = -1,
    expired_at=None,
    file_hash: str = None,
    is_chunked: bool = False,
    used_count: int = 0,
):
    """通用测试夹具：创建文件记录"""
    now = await get_now()
    return await FileCodes.create(
        code=code,
        prefix=prefix,
        size=size,
        text=text,
        used_count=used_count,
        expired_count=expired_count,
        expired_at=expired_at,
        file_hash=file_hash,
        is_chunked=is_chunked,
        created_at=now,
    )


def run_async(coro):
    """同步测试方法中运行异步代码的快捷方式"""
    return asyncio.run(coro)
