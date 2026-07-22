# @Time    : 2026/7/19
# @File    : webhook.py
# @Desc    : Webhook 事件分发与发送，异步重试 + SSRF 防护
import asyncio
import datetime
import ipaddress
import json
from typing import Optional
from urllib.parse import urlparse

import aiohttp

from core.logger import logger
from core.settings import settings


# 配置常量
_MAX_WEBHOOKS = 10
_SEND_TIMEOUT = 10  # 秒
_MAX_RETRIES = 3
_RETRY_BACKOFF = [1, 2, 4]  # 指数退避秒数
_LOG_RETENTION_DAYS = 30

# 内网网段（SSRF防护）
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_webhook_enabled() -> bool:
    """检查 Webhook 功能是否启用"""
    return bool(getattr(settings, "enableWebhook", 0))


def validate_webhook_url(url: str) -> Optional[str]:
    """校验 Webhook URL 安全性，返回错误信息或 None（通过）

    Args:
        url: 待校验的URL

    Returns:
        错误描述字符串，通过则返回 None
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return "URL 格式无效"

    if parsed.scheme not in ("http", "https"):
        return "仅允许 http/https 协议"

    hostname = parsed.hostname
    if not hostname:
        return "URL 缺少主机名"

    # 检查是否为内网地址
    try:
        addr = ipaddress.ip_address(hostname)
        for network in _BLOCKED_NETWORKS:
            if addr in network:
                return "禁止使用内网地址"
    except ValueError:
        # 非IP地址（域名），检查常见内网域名
        lower_host = hostname.lower()
        if lower_host in ("localhost", "localhost.localdomain"):
            return "禁止使用内网地址"
        if lower_host.endswith(".local") or lower_host.endswith(".internal"):
            return "禁止使用内网地址"

    return None


async def emit_webhook(event_type: str, data: dict) -> None:
    """触发 Webhook 事件（异步，不阻塞主流程）

    Args:
        event_type: 事件类型 (file.uploaded / file.retrieved / file.expired)
        data: 事件数据
    """
    if not _is_webhook_enabled():
        return

    asyncio.create_task(_dispatch_event(event_type, data))


async def _dispatch_event(event_type: str, data: dict) -> None:
    """分发事件到所有匹配的 Webhook 配置"""
    try:
        from apps.base.models import WebhookConfig

        configs = await WebhookConfig.filter(enabled=True).all()
        if not configs:
            return

        now = datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=8))
        )
        payload = {
            "event": event_type,
            "timestamp": now.isoformat(),
            "data": data,
        }

        for config in configs:
            events = config.events if isinstance(config.events, list) else []
            if event_type in events:
                asyncio.create_task(
                    _send_with_retry(config, event_type, payload)
                )
    except Exception as e:
        logger.warning(f"Webhook 事件分发失败: {e}")


async def _send_with_retry(config, event_type: str, payload: dict) -> None:
    """带重试的 Webhook 发送"""
    from apps.base.models import WebhookLog

    last_status = None
    last_body = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            headers = {"Content-Type": "application/json"}
            if config.headers and isinstance(config.headers, dict):
                headers.update(config.headers)

            timeout = aiohttp.ClientTimeout(total=_SEND_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    config.url,
                    data=json.dumps(payload, ensure_ascii=False, default=str),
                    headers=headers,
                ) as resp:
                    last_status = resp.status
                    last_body = (await resp.text())[:2000]

                    if 200 <= resp.status < 300:
                        # 成功
                        await WebhookLog.create(
                            webhook_id=config.id,
                            event_type=event_type,
                            payload=payload,
                            response_status=last_status,
                            response_body=last_body,
                            success=True,
                            attempt=attempt,
                        )
                        return
        except asyncio.TimeoutError:
            last_status = None
            last_body = f"Timeout after {_SEND_TIMEOUT}s"
        except Exception as e:
            last_status = None
            last_body = str(e)[:2000]

        # 退避等待（最后一次不等待）
        if attempt < _MAX_RETRIES:
            await asyncio.sleep(_RETRY_BACKOFF[attempt - 1])

    # 全部重试失败，记录日志
    try:
        await WebhookLog.create(
            webhook_id=config.id,
            event_type=event_type,
            payload=payload,
            response_status=last_status,
            response_body=last_body,
            success=False,
            attempt=_MAX_RETRIES,
        )
    except Exception as e:
        logger.warning(f"Webhook 日志写入失败: {e}")
