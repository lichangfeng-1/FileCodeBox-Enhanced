"""SEC-005: 管理员登录防暴力破解测试

验证登录限流机制：
- 正常登录不受影响
- 连续失败 5 次后第 6 次返回 429（锁定）
- 锁定时间窗口过后恢复
- 成功登录清除失败计数

测试设计：每个场景独立用例，AAA 模式。
"""
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from apps.base.dependencies import IPRateLimit


class LoginRateLimitTests(unittest.TestCase):
    """SEC-005 登录防暴力破解：每个场景独立用例"""

    def _make_limiter(self):
        """创建与生产一致的限流器（5次/15分钟）"""
        return IPRateLimit(count=5, minutes=15)

    def test_normal_login_not_affected(self):
        """正常用户（失败 1-2 次）不受限流影响"""
        limiter = self._make_limiter()
        ip = "192.168.1.100"

        # 失败 2 次
        limiter.add_ip(ip)
        limiter.add_ip(ip)

        # 仍可继续尝试（check_ip 返回 True = 未锁定）
        self.assertTrue(limiter.check_ip(ip))

    def test_lockout_after_5_failures(self):
        """连续失败 5 次后被锁定（check_ip 返回 False）"""
        limiter = self._make_limiter()
        ip = "10.0.0.1"

        # 失败 5 次
        for _ in range(5):
            limiter.add_ip(ip)

        # 第 6 次应被锁定
        self.assertFalse(limiter.check_ip(ip))

    def test_lockout_expires_after_window(self):
        """锁定时间窗口（15分钟）过后恢复"""
        limiter = self._make_limiter()
        ip = "10.0.0.2"

        # 失败 5 次
        for _ in range(5):
            limiter.add_ip(ip)

        # 确认已锁定
        self.assertFalse(limiter.check_ip(ip))

        # 模拟 15 分钟后（手动修改时间戳）
        limiter.ips[ip]["time"] = datetime.now() - timedelta(minutes=16)

        # 锁定应已解除
        self.assertTrue(limiter.check_ip(ip))

    def test_successful_login_clears_count(self):
        """成功登录清除失败计数（模拟 ips.pop）"""
        limiter = self._make_limiter()
        ip = "10.0.0.3"

        # 失败 4 次（差 1 次就锁定）
        for _ in range(4):
            limiter.add_ip(ip)

        # 模拟登录成功：清除记录
        limiter.ips.pop(ip, None)

        # 之后再有 5 次机会
        for _ in range(5):
            limiter.add_ip(ip)
        self.assertFalse(limiter.check_ip(ip))  # 5 次后才锁定

    def test_different_ips_independent(self):
        """不同 IP 互不影响"""
        limiter = self._make_limiter()

        # IP-A 被锁定
        for _ in range(5):
            limiter.add_ip("1.1.1.1")
        self.assertFalse(limiter.check_ip("1.1.1.1"))

        # IP-B 不受影响
        self.assertTrue(limiter.check_ip("2.2.2.2"))

    def test_boundary_exactly_at_count(self):
        """边界：恰好达到阈值（count=5）时锁定"""
        limiter = self._make_limiter()
        ip = "10.0.0.4"

        # 4 次 → 未锁定
        for _ in range(4):
            limiter.add_ip(ip)
        self.assertTrue(limiter.check_ip(ip))

        # 第 5 次 → 锁定
        limiter.add_ip(ip)
        self.assertFalse(limiter.check_ip(ip))


if __name__ == "__main__":
    unittest.main()
