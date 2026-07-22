import asyncio
import datetime
import unittest
from unittest.mock import patch

from tortoise import Tortoise

from apps.base.models import FileCodes
from apps.base import views
from apps.base.schemas import DedupCheckModel
from core.settings import settings
from core.utils import get_now


VALID_HASH = "a" * 64  # 合法 SHA256 格式


class FakeDedupStorage:
    """秒传测试用假存储：file_exists 始终返回 True"""

    async def file_exists(self, save_path: str) -> bool:
        return True


class FakeDedupStorageMissing:
    """文件不存在的假存储"""

    async def file_exists(self, save_path: str) -> bool:
        return False


class DedupCheckTests(unittest.TestCase):
    def test_dedup_disabled_returns_not_existed(self):
        asyncio.run(self._test_disabled())

    def test_dedup_hit_creates_new_record(self):
        asyncio.run(self._test_hit())

    def test_dedup_expired_file_returns_not_existed(self):
        asyncio.run(self._test_expired())

    def test_dedup_text_share_not_matched(self):
        """带备注的文件也参与秒传（hash+size 匹配即可）"""
        asyncio.run(self._test_text_excluded())

    def test_dedup_file_size_exceeds_limit(self):
        asyncio.run(self._test_size_limit())

    def test_dedup_storage_file_missing(self):
        asyncio.run(self._test_storage_missing())

    def test_dedup_invalid_hash_format(self):
        asyncio.run(self._test_invalid_hash())

    def test_dedup_size_mismatch(self):
        asyncio.run(self._test_size_mismatch())

    async def _setup_db(self):
        await Tortoise.init(
            config={
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
        )
        await Tortoise.generate_schemas()

    async def _teardown_db(self):
        await Tortoise.close_connections()

    async def _test_disabled(self):
        original = dict(settings.user_config)
        settings.enableDedup = 0
        try:
            data = DedupCheckModel(
                file_hash=VALID_HASH, file_size=1024, file_name="test.txt"
            )
            result = await views.dedup_check(request=None, data=data, ip="127.0.0.1")
            self.assertFalse(result.detail["existed"])
        finally:
            settings.user_config = original

    async def _test_hit(self):
        await self._setup_db()
        original = dict(settings.user_config)
        settings.enableDedup = 1
        settings.file_storage = "local"
        try:
            now = await get_now()
            await FileCodes.create(
                code="OLD01",
                prefix="report",
                suffix=".pdf",
                file_hash="b" * 64,
                file_path="share/data/2026/07/19/abc",
                uuid_file_name="report.pdf",
                size=2048,
                expired_count=-1,
                expired_at=now + datetime.timedelta(days=1),
            )
            data = DedupCheckModel(
                file_hash="b" * 64, file_size=2048, file_name="report.pdf",
                expire_value=1, expire_style="day",
            )
            with patch.dict(views.storages, {"local": FakeDedupStorage}):
                result = await views.dedup_check(request=None, data=data, ip="127.0.0.1")

            self.assertTrue(result.detail["existed"])
            # 安全核心：返回的是新码，不是原始码
            self.assertNotEqual(result.detail["code"], "OLD01")
            self.assertEqual(result.detail["name"], "report.pdf")
            self.assertEqual(result.detail["size"], 2048)
            # 验证新记录已创建
            new_record = await FileCodes.filter(code=result.detail["code"]).first()
            self.assertIsNotNone(new_record)
            self.assertEqual(new_record.file_path, "share/data/2026/07/19/abc")
        finally:
            settings.user_config = original
            await self._teardown_db()

    async def _test_expired(self):
        await self._setup_db()
        original = dict(settings.user_config)
        settings.enableDedup = 1
        settings.file_storage = "local"
        try:
            now = await get_now()
            await FileCodes.create(
                code="OLD02",
                prefix="old",
                suffix=".zip",
                file_hash="c" * 64,
                file_path="share/data/2026/07/18/def",
                uuid_file_name="old.zip",
                size=4096,
                expired_count=-1,
                expired_at=now - datetime.timedelta(seconds=1),
            )
            data = DedupCheckModel(
                file_hash="c" * 64, file_size=4096, file_name="old.zip"
            )
            with patch.dict(views.storages, {"local": FakeDedupStorage}):
                result = await views.dedup_check(request=None, data=data, ip="127.0.0.1")

            self.assertFalse(result.detail["existed"])
        finally:
            settings.user_config = original
            await self._teardown_db()

    async def _test_text_excluded(self):
        await self._setup_db()
        original = dict(settings.user_config)
        settings.enableDedup = 1
        settings.file_storage = "local"
        try:
            now = await get_now()
            await FileCodes.create(
                code="OLD03",
                prefix="Text",
                suffix="",
                text="some text content",
                file_hash="d" * 64,
                size=17,
                expired_count=-1,
                expired_at=now + datetime.timedelta(days=1),
            )
            data = DedupCheckModel(
                file_hash="d" * 64, file_size=17, file_name="notes.txt"
            )
            with patch.dict(views.storages, {"local": FakeDedupStorage}):
                result = await views.dedup_check(request=None, data=data, ip="127.0.0.1")

            self.assertTrue(result.detail["existed"])
        finally:
            settings.user_config = original
            await self._teardown_db()

    async def _test_size_limit(self):
        original = dict(settings.user_config)
        settings.enableDedup = 1
        settings.uploadSize = 1024
        try:
            data = DedupCheckModel(
                file_hash="e" * 64, file_size=2048, file_name="big.bin"
            )
            with self.assertRaises(Exception) as ctx:
                await views.dedup_check(request=None, data=data, ip="127.0.0.1")
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            settings.user_config = original

    async def _test_storage_missing(self):
        await self._setup_db()
        original = dict(settings.user_config)
        settings.enableDedup = 1
        settings.file_storage = "local"
        try:
            now = await get_now()
            await FileCodes.create(
                code="OLD04",
                prefix="gone",
                suffix=".dat",
                file_hash="f" * 64,
                file_path="share/data/2026/07/17/ghi",
                uuid_file_name="gone.dat",
                size=512,
                expired_count=-1,
                expired_at=now + datetime.timedelta(days=1),
            )
            data = DedupCheckModel(
                file_hash="f" * 64, file_size=512, file_name="gone.dat"
            )
            with patch.dict(views.storages, {"local": FakeDedupStorageMissing}):
                result = await views.dedup_check(request=None, data=data, ip="127.0.0.1")

            self.assertFalse(result.detail["existed"])
        finally:
            settings.user_config = original
            await self._teardown_db()

    async def _test_invalid_hash(self):
        """非法 hash 格式应返回 existed=False"""
        original = dict(settings.user_config)
        settings.enableDedup = 1
        try:
            # 太短
            data = DedupCheckModel(
                file_hash="abc123", file_size=100, file_name="x.txt"
            )
            result = await views.dedup_check(request=None, data=data, ip="127.0.0.1")
            self.assertFalse(result.detail["existed"])
            # 含非法字符
            data2 = DedupCheckModel(
                file_hash="g" * 64, file_size=100, file_name="x.txt"
            )
            result2 = await views.dedup_check(request=None, data=data2, ip="127.0.0.1")
            self.assertFalse(result2.detail["existed"])
        finally:
            settings.user_config = original

    async def _test_size_mismatch(self):
        """hash匹配但size不匹配应返回 existed=False"""
        await self._setup_db()
        original = dict(settings.user_config)
        settings.enableDedup = 1
        settings.file_storage = "local"
        try:
            now = await get_now()
            await FileCodes.create(
                code="OLD05",
                prefix="file",
                suffix=".bin",
                file_hash="a" * 64,
                file_path="share/data/2026/07/19/xyz",
                uuid_file_name="file.bin",
                size=9999,  # 实际大小
                expired_count=-1,
                expired_at=now + datetime.timedelta(days=1),
            )
            # 请求中声明不同大小
            data = DedupCheckModel(
                file_hash="a" * 64, file_size=1111, file_name="file.bin"
            )
            with patch.dict(views.storages, {"local": FakeDedupStorage}):
                result = await views.dedup_check(request=None, data=data, ip="127.0.0.1")

            self.assertFalse(result.detail["existed"])
        finally:
            settings.user_config = original
            await self._teardown_db()


if __name__ == "__main__":
    unittest.main()
