# @Time    : 2026/7/19
# @File    : audit.py
# @Desc    : 审计日志服务，异步写入不阻塞主业务流程
import asyncio
import time
from typing import Optional

from fastapi import Request

from core.ip_location import get_ip_location
from core.logger import logger
from core.settings import settings
from core.ua_parser import parse_user_agent


# 写入保护：连续失败计数与熔断
_consecutive_failures = 0
_circuit_break_until = 0.0  # 熔断截止时间戳
_MAX_CONSECUTIVE_FAILURES = 10
_CIRCUIT_BREAK_SECONDS = 60  # 熔断后等待60秒再重试


def _is_audit_enabled() -> bool:
    """检查审计功能是否启用"""
    return bool(getattr(settings, "enableAudit", 1))


def _is_circuit_open() -> bool:
    """检查熔断器是否开启（连续失败过多时暂停写入）"""
    global _consecutive_failures, _circuit_break_until
    if _consecutive_failures < _MAX_CONSECUTIVE_FAILURES:
        return False
    if time.time() < _circuit_break_until:
        return True
    # 熔断时间已过，允许重试
    _consecutive_failures = 0
    return False


async def record_audit(
    event_type: str,
    ip: str,
    request: Optional[Request] = None,
    file_id: Optional[int] = None,
    file_code: Optional[str] = None,
    file_name: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    """异步记录审计日志（不阻塞主流程）

    Args:
        event_type: 事件类型 (upload/download/retrieve/expire/delete/admin_login)
        ip: 客户端IP
        request: FastAPI Request 对象（用于提取UA）
        file_id: 关联文件ID
        file_code: 关联文件取件码
        file_name: 文件名
        detail: 扩展信息
    """
    if not _is_audit_enabled():
        return

    if _is_circuit_open():
        return

    asyncio.create_task(
        _write_audit(event_type, ip, request, file_id, file_code, file_name, detail)
    )


async def _write_audit(
    event_type: str,
    ip: str,
    request: Optional[Request],
    file_id: Optional[int],
    file_code: Optional[str],
    file_name: Optional[str],
    detail: Optional[dict],
) -> None:
    """实际写入审计日志（后台任务，带熔断保护）"""
    global _consecutive_failures, _circuit_break_until
    try:
        from apps.base.models import AuditLog

        # 解析 UA
        ua_str = None
        browser = None
        browser_version = None
        os_name = None
        os_version = None
        device_type = None

        if request:
            ua_str = request.headers.get("user-agent")
            # 截断超长UA，防止存储滥用
            if ua_str and len(ua_str) > 512:
                ua_str = ua_str[:512]
            ua_result = parse_user_agent(ua_str)
            browser = ua_result.browser
            browser_version = ua_result.browser_version
            os_name = ua_result.os
            os_version = ua_result.os_version
            device_type = ua_result.device_type

        # 查询 IP 归属地
        ip_location = get_ip_location(ip)

        await AuditLog.create(
            event_type=event_type,
            file_id=file_id,
            file_code=file_code,
            file_name=file_name[:512] if file_name else None,
            ip=ip or "unknown",
            ip_location=ip_location,
            user_agent=ua_str,
            browser=browser,
            browser_version=browser_version,
            os=os_name,
            os_version=os_version,
            device_type=device_type,
            detail=detail,
        )
        # 写入成功，重置失败计数
        _consecutive_failures = 0
    except Exception as e:
        _consecutive_failures += 1
        if _consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
            _circuit_break_until = time.time() + _CIRCUIT_BREAK_SECONDS
            logger.warning(
                f"审计日志连续失败{_consecutive_failures}次，"
                f"熔断{_CIRCUIT_BREAK_SECONDS}秒: {e}"
            )
        else:
            logger.warning(f"审计日志写入失败: {e}")
