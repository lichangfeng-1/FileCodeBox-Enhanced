"""迁移脚本幂等性测试

验证所有迁移脚本在两种场景下都能正常执行：
1. 新装场景：空数据库，迁移从头顺序执行
2. 升级场景：表/字段已由旧版 generate_schemas=True 创建，迁移重跑不崩溃

这是 v2.1.1 反思后补充的测试——之前 183 个测试全部绕过迁移逻辑。
"""
import asyncio
import unittest

from tortoise import Tortoise
from tortoise import connections

from core.db_config import get_db_type

# 内存 SQLite 配置（不注册模型，纯手工建表模拟真实迁移环境）
RAW_DB_CONFIG = {
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


class TestMigrationFreshInstall(unittest.TestCase):
    """新装场景：空数据库，迁移顺序执行"""

    def _run(self, coro):
        asyncio.run(coro)

    async def _init_raw_db(self):
        """初始化空数据库（不 generate_schemas，模拟全新安装）"""
        await Tortoise.init(config=RAW_DB_CONFIG)
        # 只创建 migrates 记录表（模拟 database.py 的 init_db 行为）
        conn = connections.get("default")
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS migrates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_file VARCHAR(255) NOT NULL UNIQUE,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def test_all_migrations_fresh_install(self):
        """新装：12 个迁移顺序执行无报错"""
        self._run(self._fresh_install())

    async def _fresh_install(self):
        await self._init_raw_db()
        try:
            # 按顺序导入并执行所有迁移
            migration_modules = []
            for i in range(1, 13):
                module_name = f"apps.base.migrations.migrations_{i:03d}"
                import importlib
                mod = importlib.import_module(module_name)
                migration_modules.append((module_name, mod))

            for name, mod in migration_modules:
                self.assertTrue(
                    hasattr(mod, "migrate"),
                    f"{name} 缺少 migrate() 函数",
                )
                # 执行迁移——新装场景不应抛异常
                await mod.migrate()

            # 验证关键表已创建
            conn = connections.get("default")
            result = await conn.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = {row[0] for row in result[1]}
            expected_tables = {
                "filecodes", "keyvalue", "uploadchunk",
                "presignuploadsession", "storagereservation",
                "auditlog", "webhookconfig", "webhooklog",
            }
            missing = expected_tables - tables
            self.assertEqual(missing, set(), f"缺少表: {missing}")
        finally:
            await Tortoise.close_connections()


class TestMigrationIdempotent(unittest.TestCase):
    """升级场景：表/字段已存在，迁移重跑不崩溃"""

    def _run(self, coro):
        asyncio.run(coro)

    async def _init_with_schemas(self):
        """初始化数据库并用 generate_schemas 创建所有表（模拟旧版已运行）"""
        await Tortoise.init(config=RAW_DB_CONFIG)
        await Tortoise.generate_schemas()
        # 创建 migrates 记录表
        conn = connections.get("default")
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS migrates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_file VARCHAR(255) NOT NULL UNIQUE,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def test_all_migrations_idempotent(self):
        """升级：表和字段已存在，迁移重跑不报错"""
        self._run(self._idempotent_run())

    async def _idempotent_run(self):
        await self._init_with_schemas()
        try:
            import importlib
            for i in range(1, 13):
                module_name = f"apps.base.migrations.migrations_{i:03d}"
                mod = importlib.import_module(module_name)
                # 升级场景：所有表/字段已存在，不应抛异常
                try:
                    await mod.migrate()
                except Exception as e:
                    self.fail(
                        f"{module_name} 在升级场景下抛出异常: {e}"
                    )
        finally:
            await Tortoise.close_connections()

    def test_migration_002_double_run(self):
        """迁移 002 连续执行两次不报错（幂等核心验证）"""
        self._run(self._double_run_002())

    async def _double_run_002(self):
        await self._init_with_schemas()
        try:
            import importlib
            mod = importlib.import_module("apps.base.migrations.migrations_002")
            # 第一次执行
            await mod.migrate()
            # 第二次执行（幂等验证）
            try:
                await mod.migrate()
            except Exception as e:
                self.fail(f"migrations_002 第二次执行失败（非幂等）: {e}")
        finally:
            await Tortoise.close_connections()

    def test_migration_004_double_run(self):
        """迁移 004 连续执行两次不报错（幂等核心验证）"""
        self._run(self._double_run_004())

    async def _double_run_004(self):
        await self._init_with_schemas()
        try:
            import importlib
            mod = importlib.import_module("apps.base.migrations.migrations_004")
            await mod.migrate()
            try:
                await mod.migrate()
            except Exception as e:
                self.fail(f"migrations_004 第二次执行失败（非幂等）: {e}")
        finally:
            await Tortoise.close_connections()


if __name__ == "__main__":
    unittest.main()
