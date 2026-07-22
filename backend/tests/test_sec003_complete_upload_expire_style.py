"""SEC-003: complete_upload expire_style 白名单校验测试

验证分片上传完成接口拒绝管理员未启用的过期方式（与 share_file 一致），
防止用户通过分片上传绕过管理员配置的过期策略限制。

测试设计：
- 每个场景独立用例（避免 fail-fast 掩盖后续问题）
- 覆盖边界条件：空白名单、空字符串 expire_style
- 合法方式通过校验的验证：越过白名单后进入后续流程（报"分片不完整"证明已放行）
"""
import asyncio
import unittest

from fastapi import HTTPException
from tortoise import Tortoise

from apps.base import views
from apps.base.models import UploadChunk
from apps.base.schemas import CompleteUploadModel
from core.settings import settings

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


class CompleteUploadExpireStyleValidationTests(unittest.TestCase):
    """SEC-003 白名单校验：每个场景独立用例"""

    def _run(self, coro):
        asyncio.run(coro)

    async def _init_db_with_session(self):
        await Tortoise.init(config=DB_CONFIG)
        await Tortoise.generate_schemas()
        await UploadChunk.create(
            upload_id="test-upload",
            chunk_index=-1,
            chunk_hash="",
            total_chunks=1,
            file_size=100,
            chunk_size=5 * 1024 * 1024,
            file_name="test.txt",
            save_path=None,
        )

    # ---------- 正常流程 ----------

    def test_disabled_style_rejected(self):
        """管理员未启用的过期方式（forever）→ 400「过期时间类型错误」"""
        self._run(self._disabled_style_rejected())

    async def _disabled_style_rejected(self):
        original = dict(settings.user_config)
        settings.expireStyle = ["day", "hour"]
        settings.file_storage = "local"
        await self._init_db_with_session()
        try:
            with self.assertRaises(HTTPException) as ctx:
                await views.complete_upload(
                    upload_id="test-upload",
                    data=CompleteUploadModel(expire_value=1, expire_style="forever"),
                    ip="127.0.0.1",
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "过期时间类型错误")
        finally:
            settings.user_config = original
            await Tortoise.close_connections()

    def test_forged_style_rejected(self):
        """伪造的非法过期方式 → 400「过期时间类型错误」"""
        self._run(self._forged_style_rejected())

    async def _forged_style_rejected(self):
        original = dict(settings.user_config)
        settings.expireStyle = ["day", "hour"]
        settings.file_storage = "local"
        await self._init_db_with_session()
        try:
            with self.assertRaises(HTTPException) as ctx:
                await views.complete_upload(
                    upload_id="test-upload",
                    data=CompleteUploadModel(expire_value=1, expire_style="hacked"),
                    ip="127.0.0.1",
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "过期时间类型错误")
        finally:
            settings.user_config = original
            await Tortoise.close_connections()

    def test_allowed_style_passes_validation(self):
        """已启用的过期方式（day）→ 越过白名单校验，进入后续流程"""
        self._run(self._allowed_style_passes_validation())

    async def _allowed_style_passes_validation(self):
        original = dict(settings.user_config)
        settings.expireStyle = ["day", "hour"]
        settings.file_storage = "local"
        await self._init_db_with_session()
        try:
            with self.assertRaises(HTTPException) as ctx:
                await views.complete_upload(
                    upload_id="test-upload",
                    data=CompleteUploadModel(expire_value=1, expire_style="day"),
                    ip="127.0.0.1",
                )
            self.assertEqual(ctx.exception.detail, "分片不完整")
        finally:
            settings.user_config = original
            await Tortoise.close_connections()

    # ---------- 边界条件 ----------

    def test_empty_whitelist_rejects_all(self):
        """边界：白名单为空时，任何 expire_style 都被拒绝"""
        self._run(self._empty_whitelist_rejects_all())

    async def _empty_whitelist_rejects_all(self):
        original = dict(settings.user_config)
        settings.expireStyle = []
        settings.file_storage = "local"
        await self._init_db_with_session()
        try:
            for style in ["day", "hour", "forever", "count"]:
                with self.subTest(style=style):
                    with self.assertRaises(HTTPException) as ctx:
                        await views.complete_upload(
                            upload_id="test-upload",
                            data=CompleteUploadModel(expire_value=1, expire_style=style),
                            ip="127.0.0.1",
                        )
                    self.assertEqual(ctx.exception.status_code, 400)
                    self.assertEqual(ctx.exception.detail, "过期时间类型错误")
        finally:
            settings.user_config = original
            await Tortoise.close_connections()

    def test_empty_string_style_rejected(self):
        """边界：expire_style 为空字符串 → 拒绝"""
        self._run(self._empty_string_style_rejected())

    async def _empty_string_style_rejected(self):
        original = dict(settings.user_config)
        settings.expireStyle = ["day", "hour"]
        settings.file_storage = "local"
        await self._init_db_with_session()
        try:
            with self.assertRaises(HTTPException) as ctx:
                await views.complete_upload(
                    upload_id="test-upload",
                    data=CompleteUploadModel(expire_value=1, expire_style=""),
                    ip="127.0.0.1",
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "过期时间类型错误")
        finally:
            settings.user_config = original
            await Tortoise.close_connections()


if __name__ == "__main__":
    unittest.main()
