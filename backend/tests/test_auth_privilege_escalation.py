"""越权防护测试：管理员认证边界验证

验证管理后台的认证机制能正确拒绝以下越权行为：
1. 无 Token 访问管理接口
2. 伪造 Token（错误密钥签名）
3. 过期 Token 重放
4. is_admin 标志篡改（Token 有效但非管理员）

测试设计（生产级标准）：
- 每个攻击向量独立用例（测试隔离）
- 覆盖边界：空字符串、格式错误的 Token
- 参考：OWASP Authentication Testing Guide
"""
import asyncio
import base64
import hashlib
import hmac
import json
import time
import unittest

from fastapi import HTTPException

from apps.admin.dependencies import (
    _require_admin_payload,
    admin_required,
    create_token,
    verify_token,
)
from core.settings import settings


class AuthPrivilegeEscalationTests(unittest.TestCase):
    """越权防护：每个攻击向量独立用例"""

    def _run(self, coro):
        asyncio.run(coro)

    def _setup(self):
        """保存并设置测试密钥"""
        original = dict(settings.user_config)
        settings.jwt_secret = "test-secret-for-auth-escalation"
        return original

    def _teardown(self, original):
        settings.user_config = original

    # ---------- 攻击向量 1：无 Token ----------

    def test_no_token_rejected(self):
        """无 Authorization 头 → 401"""
        original = self._setup()
        try:
            with self.assertRaises(HTTPException) as ctx:
                _require_admin_payload(None)
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            self._teardown(original)

    def test_empty_bearer_token_rejected(self):
        """Authorization: Bearer（空 token）→ 401"""
        original = self._setup()
        try:
            with self.assertRaises(HTTPException) as ctx:
                _require_admin_payload("Bearer ")
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            self._teardown(original)

    def test_malformed_authorization_header_rejected(self):
        """格式错误的 Authorization 头（非 Bearer 前缀）→ 401"""
        original = self._setup()
        try:
            for bad_header in ["", "Basic abc123", "Token xyz", "Bearer"]:
                with self.subTest(header=bad_header):
                    with self.assertRaises(HTTPException) as ctx:
                        _require_admin_payload(bad_header)
                    self.assertEqual(ctx.exception.status_code, 401)
        finally:
            self._teardown(original)

    # ---------- 攻击向量 2：伪造 Token ----------

    def test_forged_token_wrong_secret_rejected(self):
        """用错误密钥签名的 Token → 401（签名校验失败）"""
        original = self._setup()
        try:
            # Arrange: 用另一个密钥伪造 Token
            fake_secret = b"attacker-secret-key"
            header = base64.b64encode(
                json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
            ).decode()
            payload = base64.b64encode(
                json.dumps({"is_admin": True, "exp": int(time.time()) + 3600}).encode()
            ).decode()
            fake_sig = hmac.new(fake_secret, f"{header}.{payload}".encode(), "sha256").digest()
            fake_token = f"{header}.{payload}.{base64.b64encode(fake_sig).decode()}"

            # Act & Assert
            with self.assertRaises(HTTPException) as ctx:
                _require_admin_payload(f"Bearer {fake_token}")
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            self._teardown(original)

    def test_tampered_payload_rejected(self):
        """篡改 Token payload（修改内容但不重签名）→ 401"""
        original = self._setup()
        try:
            # Arrange: 先创建合法 Token，再篡改 payload
            legit_token = create_token({"is_admin": True}, expires_in=3600)
            parts = legit_token.split(".")
            # 篡改 payload：把 is_admin 改成 True（假设原来是 False 的 Token）
            tampered_payload = base64.b64encode(
                json.dumps({"is_admin": True, "role": "superadmin", "exp": int(time.time()) + 99999}).encode()
            ).decode()
            tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

            # Act & Assert: 签名不匹配，应被拒绝
            with self.assertRaises(HTTPException) as ctx:
                _require_admin_payload(f"Bearer {tampered_token}")
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            self._teardown(original)

    def test_garbage_token_rejected(self):
        """完全无效的垃圾字符串作为 Token → 401"""
        original = self._setup()
        try:
            for garbage in ["abc.def.ghi", "not-a-jwt", "a.b", "...", "x" * 200]:
                with self.subTest(token=garbage[:20]):
                    with self.assertRaises(HTTPException) as ctx:
                        _require_admin_payload(f"Bearer {garbage}")
                    self.assertEqual(ctx.exception.status_code, 401)
        finally:
            self._teardown(original)

    # ---------- 攻击向量 3：过期 Token 重放 ----------

    def test_expired_token_rejected(self):
        """已过期的 Token → 401（防止重放攻击）"""
        original = self._setup()
        try:
            # Arrange: 创建一个已过期的 Token（expires_in=-10 表示 10 秒前过期）
            expired_token = create_token({"is_admin": True}, expires_in=-10)

            # Act & Assert
            with self.assertRaises(HTTPException) as ctx:
                _require_admin_payload(f"Bearer {expired_token}")
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            self._teardown(original)

    def test_token_just_expired_at_boundary(self):
        """边界：Token 恰好在当前秒过期（exp == time.time()）→ 401"""
        original = self._setup()
        try:
            # Arrange: 手工构造一个 exp 恰好等于当前时间的 Token
            now = int(time.time())
            header = base64.b64encode(
                json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
            ).decode()
            payload = base64.b64encode(
                json.dumps({"is_admin": True, "exp": now}).encode()
            ).decode()
            secret = settings.jwt_secret.encode()
            sig = hmac.new(secret, f"{header}.{payload}".encode(), "sha256").digest()
            boundary_token = f"{header}.{payload}.{base64.b64encode(sig).decode()}"

            # Act & Assert: exp < time.time() 在 exp==now 时取决于精度
            # 由于 time.time() 有微秒精度，exp=int 必然 < time.time()
            with self.assertRaises(HTTPException) as ctx:
                _require_admin_payload(f"Bearer {boundary_token}")
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            self._teardown(original)

    # ---------- 攻击向量 4：is_admin 标志篡改 ----------

    def test_non_admin_token_rejected(self):
        """Token 签名有效但 is_admin=False → 401（权限不足）"""
        original = self._setup()
        try:
            # Arrange: 用正确密钥创建 Token，但 is_admin=False
            non_admin_token = create_token({"is_admin": False, "user": "guest"}, expires_in=3600)

            # Act & Assert
            with self.assertRaises(HTTPException) as ctx:
                _require_admin_payload(f"Bearer {non_admin_token}")
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            self._teardown(original)

    def test_missing_is_admin_field_rejected(self):
        """Token 有效但缺少 is_admin 字段 → 401"""
        original = self._setup()
        try:
            # Arrange: 创建不含 is_admin 的 Token
            no_role_token = create_token({"user": "someone"}, expires_in=3600)

            # Act & Assert
            with self.assertRaises(HTTPException) as ctx:
                _require_admin_payload(f"Bearer {no_role_token}")
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            self._teardown(original)

    # ---------- 正向验证：合法 Token 通过 ----------

    def test_valid_admin_token_accepted(self):
        """合法管理员 Token → 正常通过（确保校验不误伤）"""
        original = self._setup()
        try:
            # Arrange
            valid_token = create_token({"is_admin": True}, expires_in=3600)

            # Act
            payload = _require_admin_payload(f"Bearer {valid_token}")

            # Assert
            self.assertTrue(payload["is_admin"])
        finally:
            self._teardown(original)


if __name__ == "__main__":
    unittest.main()
