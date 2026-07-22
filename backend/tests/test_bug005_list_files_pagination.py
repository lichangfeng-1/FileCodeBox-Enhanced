"""BUG-005: list_files 过滤分页下推数据库测试

验证重构后的文件列表：
- 快速路径（无 health/dedup）：DB 层过滤+排序+分页，结果正确
- 慢速路径（有 health/dedup）：基础 DB 过滤 + Python 复杂筛选，结果正确
- 摘要统计：始终反映全库数据（不受筛选影响）
- 边界条件：空数据库返回空列表+全零统计

测试设计：每个场景独立用例，AAA 模式，subTest 细分断言。
"""
import asyncio
import datetime
import unittest

from tortoise import Tortoise

from apps.admin.services import FileService
from apps.base.models import FileCodes
from core.utils import get_now

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


async def _create_file(code, size=100, text=None, prefix="文件", expired_count=-1, expired_at=None, file_hash=None, is_chunked=False):
    """测试夹具：创建文件记录"""
    now = await get_now()
    return await FileCodes.create(
        code=code,
        prefix=prefix,
        size=size,
        text=text,
        used_count=0,
        expired_count=expired_count,
        expired_at=expired_at,
        file_hash=file_hash,
        is_chunked=is_chunked,
        created_at=now,
    )


class ListFilesFastPathTests(unittest.TestCase):
    """快速路径：无 health/dedup 筛选"""

    def _run(self, coro):
        asyncio.run(coro)

    async def _init_db(self):
        await Tortoise.init(config=DB_CONFIG)
        await Tortoise.generate_schemas()

    def test_basic_pagination(self):
        """基本分页：10 个文件，每页 3 个，第 2 页返回 3 个"""
        self._run(self._basic_pagination())

    async def _basic_pagination(self):
        await self._init_db()
        try:
            # Arrange: 创建 10 个文件
            for i in range(10):
                await _create_file(f"CODE{i:02d}", size=(i + 1) * 100)

            service = FileService()
            # Act: 第 2 页，每页 3 个
            items, total, summary = await service.list_files(page=2, size=3)

            # Assert
            self.assertEqual(total, 10)
            self.assertEqual(len(items), 3)
            self.assertEqual(summary["totalFiles"], 10)
        finally:
            await Tortoise.close_connections()

    def test_keyword_filter(self):
        """关键词筛选：只返回匹配的文件"""
        self._run(self._keyword_filter())

    async def _keyword_filter(self):
        await self._init_db()
        try:
            # Arrange
            await _create_file("ABC123", prefix="报告文件")
            await _create_file("XYZ789", prefix="照片")
            await _create_file("DEF456", prefix="报告v2")

            service = FileService()
            # Act: 搜索 "报告"
            items, total, _ = await service.list_files(page=1, size=10, keyword="报告")

            # Assert
            self.assertEqual(total, 2)
            codes = {item["code"] for item in items}
            self.assertIn("ABC123", codes)
            self.assertIn("DEF456", codes)
        finally:
            await Tortoise.close_connections()

    def test_file_type_filter(self):
        """文件类型筛选：text vs file"""
        self._run(self._file_type_filter())

    async def _file_type_filter(self):
        await self._init_db()
        try:
            # Arrange
            await _create_file("TEXT01", text="hello world")
            await _create_file("FILE01", text=None)
            await _create_file("FILE02", text=None)

            service = FileService()
            # Act
            text_items, text_total, _ = await service.list_files(page=1, size=10, file_type="text")
            file_items, file_total, _ = await service.list_files(page=1, size=10, file_type="file")

            # Assert
            self.assertEqual(text_total, 1)
            self.assertEqual(file_total, 2)
        finally:
            await Tortoise.close_connections()

    def test_sort_by_size_desc(self):
        """排序：按大小降序"""
        self._run(self._sort_by_size_desc())

    async def _sort_by_size_desc(self):
        await self._init_db()
        try:
            # Arrange
            await _create_file("SMALL", size=100)
            await _create_file("LARGE", size=9999)
            await _create_file("MEDIUM", size=500)

            service = FileService()
            # Act
            items, _, _ = await service.list_files(page=1, size=10, sort_by="size", sort_order="desc")

            # Assert: 最大的在前
            self.assertEqual(items[0]["code"], "LARGE")
            self.assertEqual(items[2]["code"], "SMALL")
        finally:
            await Tortoise.close_connections()

    def test_summary_unaffected_by_filter(self):
        """摘要统计始终反映全库（不受筛选影响）"""
        self._run(self._summary_unaffected_by_filter())

    async def _summary_unaffected_by_filter(self):
        await self._init_db()
        try:
            # Arrange: 3 个文件（1 text + 2 file）
            await _create_file("T1", text="hi", size=10)
            await _create_file("F1", size=200)
            await _create_file("F2", size=300)

            service = FileService()
            # Act: 筛选 text，但摘要应反映全部 3 个文件
            _, _, summary = await service.list_files(page=1, size=10, file_type="text")

            # Assert
            self.assertEqual(summary["totalFiles"], 3)
            self.assertEqual(summary["textCount"], 1)
            self.assertEqual(summary["fileCount"], 2)
            self.assertEqual(summary["storageUsed"], 510)
        finally:
            await Tortoise.close_connections()


class ListFilesSlowPathTests(unittest.TestCase):
    """慢速路径：有 health/dedup 筛选"""

    def _run(self, coro):
        asyncio.run(coro)

    async def _init_db(self):
        await Tortoise.init(config=DB_CONFIG)
        await Tortoise.generate_schemas()

    def test_dedup_filter(self):
        """秒传筛选：只返回有重复 hash 的文件"""
        self._run(self._dedup_filter())

    async def _dedup_filter(self):
        await self._init_db()
        try:
            # Arrange: 2 个文件共享 hash（秒传），1 个独立
            await _create_file("DUP1", file_hash="abc123", size=100)
            await _create_file("DUP2", file_hash="abc123", size=100)
            await _create_file("UNIQUE", file_hash="xyz789", size=200)

            service = FileService()
            # Act: 筛选 dedup
            items, total, _ = await service.list_files(page=1, size=10, dedup="dedup")

            # Assert: 只有 DUP1 和 DUP2
            self.assertEqual(total, 2)
            codes = {item["code"] for item in items}
            self.assertEqual(codes, {"DUP1", "DUP2"})
        finally:
            await Tortoise.close_connections()

    def test_health_danger_filter(self):
        """健康度筛选：danger（过期文件）"""
        self._run(self._health_danger_filter())

    async def _health_danger_filter(self):
        await self._init_db()
        try:
            now = await get_now()
            past = now - datetime.timedelta(days=1)
            # Arrange: 1 个已过期（danger），1 个正常（文本文件，无存储问题）
            await _create_file("EXPIRED", expired_at=past, expired_count=5)
            await _create_file("ACTIVE", expired_at=None, expired_count=-1, text="正常文本")

            service = FileService()
            # Act
            items, total, _ = await service.list_files(page=1, size=10, health="danger")

            # Assert
            self.assertEqual(total, 1)
            self.assertEqual(items[0]["code"], "EXPIRED")
        finally:
            await Tortoise.close_connections()


class ListFilesBoundaryTests(unittest.TestCase):
    """边界条件"""

    def _run(self, coro):
        asyncio.run(coro)

    async def _init_db(self):
        await Tortoise.init(config=DB_CONFIG)
        await Tortoise.generate_schemas()

    def test_empty_database(self):
        """边界：空数据库返回空列表+全零统计"""
        self._run(self._empty_database())

    async def _empty_database(self):
        await self._init_db()
        try:
            service = FileService()
            items, total, summary = await service.list_files(page=1, size=10)

            self.assertEqual(items, [])
            self.assertEqual(total, 0)
            self.assertEqual(summary["totalFiles"], 0)
            self.assertEqual(summary["storageUsed"], 0)
            self.assertEqual(summary["textCount"], 0)
        finally:
            await Tortoise.close_connections()

    def test_page_beyond_total(self):
        """边界：请求超出总页数的页码 → 返回空列表"""
        self._run(self._page_beyond_total())

    async def _page_beyond_total(self):
        await self._init_db()
        try:
            # Arrange: 只有 2 个文件
            await _create_file("A1")
            await _create_file("A2")

            service = FileService()
            # Act: 请求第 100 页
            items, total, _ = await service.list_files(page=100, size=10)

            # Assert
            self.assertEqual(total, 2)
            self.assertEqual(items, [])
        finally:
            await Tortoise.close_connections()


if __name__ == "__main__":
    unittest.main()
