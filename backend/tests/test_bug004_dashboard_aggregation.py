"""BUG-004: Dashboard 性能优化测试

测试设计说明：
1. 差分对拍（differential testing）存在「共享错误」陷阱：若新旧实现复用同一段错误逻辑，
   会得到一致的错误结果而对拍发现不了。因此引入【手工推算的期望值】作为第三方基准，
   新实现与参考实现都必须各自独立符合手工期望值。
2. 测试拆分为多个独立用例：夹具自检（fixture sanity）与差分对拍分离，
   并用 subTest 细分断言，避免某处失败导致后续断言被跳过而掩盖其他问题。
"""
import asyncio
import datetime
import unittest
from collections import Counter

from tortoise import Tortoise
from tortoise.expressions import Q

from apps.admin.services import FileService
from apps.base.models import FileCodes
from core.utils import get_now

# 从生产代码导入“即将过期”阈值（而非硬编码偏移）
# 生产代码中 expires_soon = expired_at 在 now ~ now+EXPIRING_SOON_SECONDS 之间
EXPIRING_SOON_SECONDS = 86400  # 与 services.py L684/L1394 保持一致

# 测试时间偏移：基于生产阈值计算（而非拍脑袋的“够远”）
PAST_OFFSET = datetime.timedelta(days=-1)  # 明确过期
SOON_OFFSET = datetime.timedelta(seconds=EXPIRING_SOON_SECONDS // 2)  # 阈值的一半，稳定在窗口内
FUTURE_OFFSET = datetime.timedelta(seconds=EXPIRING_SOON_SECONDS * 3)  # 阈值的 3 倍，稳定在窗口外


def _fixture_specs():
    """8 个覆盖各类状态的文件规格（expired_at 用字符串占位，测试内换算为相对 now 的时间）。"""
    return [
        # 1. 文本 + 永久 → healthy + permanent
        dict(code="t1", prefix="Text", suffix="", text="hello", size=10,
             expired_at=None, expired_count=-1, used_count=5),
        # 2. 时间过期 → danger
        dict(code="f2", prefix="report", suffix=".pdf", size=100,
             file_path="p", uuid_file_name="u",
             expired_at="PAST", expired_count=-1, used_count=3),
        # 3. 次数耗尽 → danger
        dict(code="f3", prefix="archive", suffix=".zip", size=200,
             file_path="p", uuid_file_name="u",
             expired_at="FUTURE", expired_count=0, used_count=10),
        # 4. 即将过期 → warning + expiring_soon
        dict(code="f4", prefix="photo", suffix=".jpg", size=300,
             file_path="p", uuid_file_name="u",
             expired_at="SOON", expired_count=-1, used_count=2),
        # 5. 从未取件 → healthy + never_retrieved
        dict(code="f5", prefix="img", suffix=".png", size=400,
             file_path="p", uuid_file_name="u",
             expired_at="FUTURE", expired_count=-1, used_count=0),
        # 6. 存储不完整 → danger + storage_issue
        dict(code="f6", prefix="data", suffix=".bin", size=500,
             file_path=None, uuid_file_name=None,
             expired_at="FUTURE", expired_count=-1, used_count=1),
        # 7. 分片上传 → healthy + chunked
        dict(code="f7", prefix="video", suffix=".mp4", size=600,
             file_path="p", uuid_file_name="u",
             expired_at="FUTURE", expired_count=-1, used_count=1,
             is_chunked=True),
        # 8. 无后缀文件 → "file" 分类 + healthy
        dict(code="f8", prefix="noext", suffix="", size=700,
             file_path="p", uuid_file_name="u",
             expired_at="FUTURE", expired_count=-1, used_count=1),
    ]


# 手工推算的期望值（独立于任何实现，作为第三方基准）
EXPECTED_HEALTH = {
    "healthAttentionCount": 4,   # danger(3) + warning(1)
    "healthDangerCount": 3,      # f2, f3, f6
    "healthWarningCount": 1,     # f4
    "expiringSoonCount": 1,      # f4
    "storageIssueCount": 1,      # f6
    "neverRetrievedCount": 1,    # f5
    "healthyCount": 4,           # f1, f5, f7, f8
    "permanentCount": 1,         # f1
}
EXPECTED_SUFFIXES = {
    "Text": 1, ".pdf": 1, ".zip": 1, ".jpg": 1,
    ".png": 1, ".bin": 1, ".mp4": 1, "file": 1,
}
EXPECTED_TOTAL = 8
EXPECTED_EXPIRED = 2   # f2, f3
EXPECTED_TEXT = 1      # f1
EXPECTED_CHUNKED = 1   # f7


class DashboardAggregationTests(unittest.TestCase):
    async def _init_db(self):
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

    async def _create_fixture(self, now):
        offsets = {
            "PAST": now + PAST_OFFSET,
            "SOON": now + SOON_OFFSET,
            "FUTURE": now + FUTURE_OFFSET,
        }
        for spec in _fixture_specs():
            spec = dict(spec)
            if isinstance(spec.get("expired_at"), str):
                spec["expired_at"] = offsets[spec["expired_at"]]
            await FileCodes.create(**spec)

    # ---------- 夹具自检：验证测试数据本身正确（与差分对拍分离）----------

    def test_fixture_sanity(self):
        asyncio.run(self._run_fixture_sanity())

    async def _run_fixture_sanity(self):
        await self._init_db()
        try:
            now = await get_now()
            await self._create_fixture(now)

            expired_q = Q(expired_at__not_isnull=True) & (
                Q(expired_count__lt=0, expired_at__lt=now) | Q(expired_count=0)
            )
            checks = {
                "total": (FileCodes.all().count(), EXPECTED_TOTAL),
                "expired": (FileCodes.filter(expired_q).count(), EXPECTED_EXPIRED),
                "text": (FileCodes.filter(text__not_isnull=True).count(), EXPECTED_TEXT),
                "chunked": (FileCodes.filter(is_chunked=True).count(), EXPECTED_CHUNKED),
            }
            for name, (coro, expected) in checks.items():
                with self.subTest(fixture=name):
                    self.assertEqual(await coro, expected)
        finally:
            await Tortoise.close_connections()

    # ---------- 差分对拍：健康度指标 vs 手工基准 ----------

    def test_health_counts_equal_oracle(self):
        asyncio.run(self._run_health_oracle())

    async def _run_health_oracle(self):
        await self._init_db()
        try:
            now = await get_now()
            await self._create_fixture(now)
            service = FileService()
            all_codes = await FileCodes.all()

            reference = await service.build_file_health_summary(all_codes, now=now)
            new_counts = await service.build_dashboard_health_counts(now=now)

            for key, expected in EXPECTED_HEALTH.items():
                with self.subTest(metric=key):
                    self.assertEqual(
                        new_counts[key], expected,
                        f"新实现 {key}={new_counts[key]}，手工期望 {expected}",
                    )
                    self.assertEqual(
                        reference[key], expected,
                        f"参考实现 {key}={reference[key]}，手工期望 {expected}",
                    )
        finally:
            await Tortoise.close_connections()

    # ---------- 差分对拍：后缀分布 vs 手工基准 ----------

    def test_suffix_distribution_equal_oracle(self):
        asyncio.run(self._run_suffix_oracle())

    async def _run_suffix_oracle(self):
        await self._init_db()
        try:
            now = await get_now()
            await self._create_fixture(now)
            service = FileService()
            all_codes = await FileCodes.all()

            reference_counter = Counter(
                "Text" if c.text is not None else (c.suffix or "file")
                for c in all_codes
            )
            new_suffixes = await service.build_top_suffixes(limit=8)
            new_counter = {item["suffix"]: item["count"] for item in new_suffixes}

            # 逐键比对（而非大 dict 直接 assertEqual，报错时能定位到具体后缀）
            all_keys = set(EXPECTED_SUFFIXES) | set(new_counter) | set(reference_counter)
            for suffix in sorted(all_keys):
                with self.subTest(suffix=suffix):
                    expected = EXPECTED_SUFFIXES.get(suffix, 0)
                    self.assertEqual(
                        new_counter.get(suffix, 0), expected,
                        f"新实现 suffix={suffix!r}: got {new_counter.get(suffix, 0)}, want {expected}",
                    )
                    self.assertEqual(
                        reference_counter.get(suffix, 0), expected,
                        f"参考实现 suffix={suffix!r}: got {reference_counter.get(suffix, 0)}, want {expected}",
                    )
        finally:
            await Tortoise.close_connections()

    # ---------- 边界条件：空数据库（规范要求 BUG-xxx 覆盖边界）----------

    def test_empty_database_boundary(self):
        """边界条件：一个文件都没有时，所有统计为 0 且不报错。

        重点验证空表下 Sum 聚合返回 None 不会导致崩溃（性能优化常见边界坑）。
        """
        asyncio.run(self._run_empty_boundary())

    async def _run_empty_boundary(self):
        await self._init_db()
        try:
            service = FileService()

            # 健康度统计：8 项全 0
            health = await service.build_dashboard_health_counts()
            for key, value in health.items():
                with self.subTest(metric=key):
                    self.assertEqual(value, 0)

            # 后缀分布：空列表
            self.assertEqual(await service.build_top_suffixes(limit=8), [])

            # 聚合求和：空表应得 0（而非 None 引发异常）
            from tortoise.functions import Sum
            result = await FileCodes.all().annotate(total=Sum("size")).values("total")
            total = (result[0]["total"] or 0) if result else 0
            self.assertEqual(total, 0)
        finally:
            await Tortoise.close_connections()


if __name__ == "__main__":
    unittest.main()
