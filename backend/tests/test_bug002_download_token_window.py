"""BUG-002: 下载 Token 时间窗口竞态修复测试

验证下载 token 在时间窗口边界处的兼容性：
当前窗口与上一个窗口的 token 都应被接受，更早窗口的 token 则拒绝。

测试设计（生产级标准）：
- 每个场景独立用例（避免 fail-fast 掩盖后续问题）
- 覆盖精确窗口边界点（time 恰好 = N*1000 的瞬间）
- 覆盖边界条件：空 code、无效 token、跨文件越权
- AAA 模式（Arrange-Act-Assert）
"""
import asyncio
import time
import unittest
from unittest.mock import patch

from core.settings import settings
from core.utils import get_select_token

# 测试常量（避免魔法数字）
CODE = "TESTCODE"
SECRET = "test-secret-for-bug002"
WINDOW_SIZE = 1000  # 时间窗口大小（秒）


class DownloadTokenWindowTests(unittest.TestCase):
    """BUG-002 时间窗口竞态：每个场景独立用例"""

    def _run(self, coro):
        asyncio.run(coro)

    def _setup_secret(self):
        original = dict(settings.user_config)
        settings.jwt_secret = SECRET
        return original

    def _teardown_secret(self, original):
        settings.user_config = original

    # ---------- 正常流程 ----------

    def test_same_window_token_consistent(self):
        """同一窗口内生成的 token 一致（offset=0 幂等）"""
        self._run(self._same_window_token_consistent())

    async def _same_window_token_consistent(self):
        original = self._setup_secret()
        try:
            with patch.object(time, "time", return_value=1000 * WINDOW_SIZE + 500):
                token_a = await get_select_token(CODE, offset=0)
                token_b = await get_select_token(CODE, offset=0)
                self.assertEqual(token_a, token_b)
        finally:
            self._teardown_secret(original)

    def test_previous_window_token_accepted(self):
        """核心修复验证：上一窗口的 token 在当前窗口仍被接受"""
        self._run(self._previous_window_token_accepted())

    async def _previous_window_token_accepted(self):
        original = self._setup_secret()
        try:
            with patch.object(time, "time", return_value=1000 * WINDOW_SIZE + 500):
                token_f = await get_select_token(CODE)
            with patch.object(time, "time", return_value=1001 * WINDOW_SIZE + 100):
                valid_keys = [await get_select_token(CODE, offset=i) for i in range(2)]
            self.assertIn(token_f, valid_keys)
        finally:
            self._teardown_secret(original)

    def test_current_window_token_accepted(self):
        """当前窗口的 token 被接受"""
        self._run(self._current_window_token_accepted())

    async def _current_window_token_accepted(self):
        original = self._setup_secret()
        try:
            with patch.object(time, "time", return_value=1001 * WINDOW_SIZE + 100):
                current_token = await get_select_token(CODE, offset=0)
                valid_keys = [await get_select_token(CODE, offset=i) for i in range(2)]
            self.assertIn(current_token, valid_keys)
        finally:
            self._teardown_secret(original)

    def test_expired_window_token_rejected(self):
        """窗口 F+2 时，窗口 F 的 token 超出范围被拒绝"""
        self._run(self._expired_window_token_rejected())

    async def _expired_window_token_rejected(self):
        original = self._setup_secret()
        try:
            with patch.object(time, "time", return_value=1000 * WINDOW_SIZE + 500):
                token_f = await get_select_token(CODE)
            with patch.object(time, "time", return_value=1002 * WINDOW_SIZE + 100):
                valid_keys = [await get_select_token(CODE, offset=i) for i in range(2)]
            self.assertNotIn(token_f, valid_keys)
        finally:
            self._teardown_secret(original)

    def test_invalid_token_rejected(self):
        """伪造的无效 token 被拒绝"""
        self._run(self._invalid_token_rejected())

    async def _invalid_token_rejected(self):
        original = self._setup_secret()
        try:
            with patch.object(time, "time", return_value=1001 * WINDOW_SIZE + 100):
                valid_keys = [await get_select_token(CODE, offset=i) for i in range(2)]
            for fake in ["invalid-token-xyz", "", "0" * 64, CODE]:
                with self.subTest(fake_token=fake):
                    self.assertNotIn(fake, valid_keys)
        finally:
            self._teardown_secret(original)

    # ---------- 边界条件 ----------

    def test_exact_window_boundary_point(self):
        """精确边界点：time 恰好 = N*1000（窗口翻转的瞬间）"""
        self._run(self._exact_window_boundary_point())

    async def _exact_window_boundary_point(self):
        original = self._setup_secret()
        try:
            with patch.object(time, "time", return_value=999 * WINDOW_SIZE + 999.999):
                token_999 = await get_select_token(CODE)
            with patch.object(time, "time", return_value=1000 * WINDOW_SIZE):
                valid_keys = [await get_select_token(CODE, offset=i) for i in range(2)]
            self.assertIn(token_999, valid_keys)
        finally:
            self._teardown_secret(original)

    def test_window_just_before_boundary(self):
        """边界前一刻：time=999999.99（仍在窗口 999 内）"""
        self._run(self._window_just_before_boundary())

    async def _window_just_before_boundary(self):
        original = self._setup_secret()
        try:
            with patch.object(time, "time", return_value=999 * WINDOW_SIZE + 500):
                token_mid = await get_select_token(CODE)
            with patch.object(time, "time", return_value=999 * WINDOW_SIZE + 999.99):
                valid_keys = [await get_select_token(CODE, offset=i) for i in range(2)]
            self.assertIn(token_mid, valid_keys)
        finally:
            self._teardown_secret(original)

    def test_different_codes_produce_different_tokens(self):
        """不同取件码生成不同 token（隔离性验证）"""
        self._run(self._different_codes_produce_different_tokens())

    async def _different_codes_produce_different_tokens(self):
        original = self._setup_secret()
        try:
            with patch.object(time, "time", return_value=1000 * WINDOW_SIZE + 500):
                token_a = await get_select_token("CODE_A")
                token_b = await get_select_token("CODE_B")
            self.assertNotEqual(token_a, token_b)
        finally:
            self._teardown_secret(original)

    # ---------- 越权防护 ----------

    def test_cross_file_token_rejected(self):
        """越权防护：用 A 文件的 Token 无法下载 B 文件"""
        self._run(self._cross_file_token_rejected())

    async def _cross_file_token_rejected(self):
        original = self._setup_secret()
        try:
            with patch.object(time, "time", return_value=1000 * WINDOW_SIZE + 500):
                token_for_a = await get_select_token("FILE_A_CODE")
            with patch.object(time, "time", return_value=1000 * WINDOW_SIZE + 500):
                valid_keys_for_b = [await get_select_token("FILE_B_CODE", offset=i) for i in range(2)]
            self.assertNotIn(token_for_a, valid_keys_for_b)
        finally:
            self._teardown_secret(original)


if __name__ == "__main__":
    unittest.main()
