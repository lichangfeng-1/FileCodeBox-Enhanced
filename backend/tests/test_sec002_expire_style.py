"""SEC-002: share_text expire_style 白名单校验测试

验证文本分享接口拒绝管理员未启用的过期方式（与 share_file 行为一致），
防止用户绕过管理员配置的过期策略限制。

测试设计：
- 每个场景独立用例（避免 fail-fast 掩盖后续问题）
- 覆盖边界条件：空白名单、空字符串 expire_style
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from tortoise import Tortoise

from apps.base import views
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


class ShareTextExpireStyleValidationTests(unittest.TestCase):
    """SEC-002 白名单校验：每个场景独立用例"""

    def _run(self, coro):
        asyncio.run(coro)

    async def _init_db(self):
        await Tortoise.init(config=DB_CONFIG)
        await Tortoise.generate_schemas()

    # ---------- 正常流程 ----------

    def test_disabled_style_rejected(self):
        """管理员未启用的过期方式（forever）→ 400"""
        self._run(self._disabled_style_rejected())

    async def _disabled_style_rejected(self):
        original = dict(settings.user_config)
        settings.expireStyle = ["day", "hour"]
        await self._init_db()
        try:
            with self.assertRaises(HTTPException) as ctx:
                await views.share_text(
                    request=None, text="hello", expire_value=1,
                    expire_style="forever", ip="127.0.0.1",
                )
            self.assertEqual(ctx.exception.status_code, 400)
        finally:
            settings.user_config = original
            await Tortoise.close_connections()

    def test_forged_style_rejected(self):
        """伪造的非法过期方式 → 400"""
        self._run(self._forged_style_rejected())

    async def _forged_style_rejected(self):
        original = dict(settings.user_config)
        settings.expireStyle = ["day", "hour"]
        await self._init_db()
        try:
            with self.assertRaises(HTTPException) as ctx:
                await views.share_text(
                    request=None, text="hello", expire_value=1,
                    expire_style="hacked_style", ip="127.0.0.1",
                )
            self.assertEqual(ctx.exception.status_code, 400)
        finally:
            settings.user_config = original
            await Tortoise.close_connections()

    def test_allowed_style_passes(self):
        """已启用的过期方式（day）→ 正常通过"""
        self._run(self._allowed_style_passes())

    async def _allowed_style_passes(self):
        original = dict(settings.user_config)
        settings.expireStyle = ["day", "hour"]
        await self._init_db()
        try:
            with patch.object(views, "record_audit", new=AsyncMock()), \
                 patch.object(views, "emit_webhook", new=AsyncMock()):
                resp = await views.share_text(
                    request=None, text="hello", expire_value=1,
                    expire_style="day", ip="127.0.0.1",
                )
            self.assertEqual(resp.code, 200)
            self.assertIn("code", resp.detail)
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
        await self._init_db()
        try:
            for style in ["day", "hour", "forever", "count"]:
                with self.subTest(style=style):
                    with self.assertRaises(HTTPException) as ctx:
                        await views.share_text(
                            request=None, text="x", expire_value=1,
                            expire_style=style, ip="127.0.0.1",
                        )
                    self.assertEqual(ctx.exception.status_code, 400)
        finally:
            settings.user_config = original
            await Tortoise.close_connections()

    def test_empty_string_style_rejected(self):
        """边界：expire_style 为空字符串 → 拒绝"""
        self._run(self._empty_string_style_rejected())

    async def _empty_string_style_rejected(self):
        original = dict(settings.user_config)
        settings.expireStyle = ["day", "hour"]
        await self._init_db()
        try:
            with self.assertRaises(HTTPException) as ctx:
                await views.share_text(
                    request=None, text="x", expire_value=1,
                    expire_style="", ip="127.0.0.1",
                )
            self.assertEqual(ctx.exception.status_code, 400)
        finally:
            settings.user_config = original
            await Tortoise.close_connections()


if __name__ == "__main__":
    unittest.main()
