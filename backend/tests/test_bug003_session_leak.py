"""BUG-003: StreamingResponse 会话泄漏修复测试

验证两点：
1. BackgroundTask 兜底机制：即使流式响应体未被完全消费（模拟客户端中断），
   会话也会被关闭，避免连接泄漏。
2. 修复已落地：storage.py 的 S3/OneDrive/WebDAV 三处下载均挂载了 background 关闭任务。
"""
import asyncio
import unittest
from pathlib import Path

from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse


class FakeSession:
    """模拟 aiohttp.ClientSession，记录 close 调用"""

    def __init__(self):
        self.closed = False
        self.close_calls = 0

    async def close(self):
        self.closed = True
        self.close_calls += 1


class SessionCleanupMechanismTests(unittest.TestCase):
    def test_background_closes_session_on_full_consumption(self):
        """正常消费完毕：background 任务关闭会话"""
        asyncio.run(self._full_consumption())

    async def _full_consumption(self):
        session = FakeSession()

        async def gen():
            for _ in range(3):
                yield b"chunk"

        resp = StreamingResponse(gen(), background=BackgroundTask(session.close))
        async for _ in resp.body_iterator:
            pass
        await resp.background()
        self.assertTrue(session.closed)

    def test_background_closes_session_on_abandon(self):
        """客户端中途断开（未消费完）：background 任务仍兜底关闭会话"""
        asyncio.run(self._abandon())

    async def _abandon(self):
        session = FakeSession()

        async def gen():
            for _ in range(100):
                yield b"chunk"

        resp = StreamingResponse(gen(), background=BackgroundTask(session.close))
        iterator = resp.body_iterator.__aiter__()
        await iterator.__anext__()  # 只消费一部分，模拟客户端中途断开
        # 不再继续消费，直接执行 background（模拟 Starlette 响应结束后的兜底关闭）
        await resp.background()
        self.assertTrue(session.closed)


class StorageFixAppliedTests(unittest.TestCase):
    def test_all_three_backends_attach_background_close(self):
        """S3/OneDrive/WebDAV 三处下载响应均挂载 background=BackgroundTask(session.close)"""
        storage_source = (
            Path(__file__).resolve().parent.parent / "core" / "storage.py"
        ).read_text(encoding="utf-8")
        count = storage_source.count("background=BackgroundTask(session.close)")
        self.assertEqual(count, 3, f"预期 3 处下载挂载 background 关闭任务，实际 {count} 处")

    def test_background_task_imported(self):
        """storage 模块已引入 BackgroundTask"""
        from core import storage

        self.assertTrue(hasattr(storage, "BackgroundTask"))


if __name__ == "__main__":
    unittest.main()
