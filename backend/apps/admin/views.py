# @Time    : 2023/8/14 14:38
# @Author  : Lan
# @File    : views.py
# @Software: PyCharm
import datetime
from collections import Counter
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from apps.admin.services import FileService, ConfigService, LocalFileService
from apps.admin.dependencies import (
    admin_required,
    get_admin_session,
    get_file_service,
    get_config_service,
    get_local_file_service,
)
from apps.admin.schemas import (
    IDData,
    IDsData,
    BatchUpdateFileData,
    BatchFilePolicyActionData,
    FilePolicyActionData,
    FileMetadataData,
    FileViewPresetData,
    FileViewPresetDeleteData,
    ShareItem,
    DeleteItem,
    LoginData,
    UpdateFileData,
)
from core.response import APIResponse
from apps.base.models import FileCodes, KeyValue
from core.audit import record_audit
from apps.admin.dependencies import (
    create_token,
    get_admin_session_expire_seconds,
    verify_token,
)
from core.settings import settings
from core.utils import get_now, verify_password

admin_api = APIRouter(
    prefix="/admin", tags=["管理"], dependencies=[Depends(admin_required)]
)


def _pick_query_text(*values: Optional[str]) -> Optional[str]:
    for value in values:
        normalized_value = str(value or "").strip()
        if normalized_value:
            return normalized_value
    return None


@admin_api.post("/login")
async def login(data: LoginData, request: Request = None):
    # SEC-005: 登录防暴力破解——先检查 IP 是否已被锁定
    from apps.base.dependencies import get_client_ip
    from apps.base.utils import ip_limit

    client_ip = get_client_ip(request) if request else "unknown"
    if not ip_limit["login"].check_ip(client_ip):
        raise HTTPException(status_code=429, detail="登录失败次数过多，请15分钟后重试")

    if not verify_password(data.password, settings.admin_token):
        ip_limit["login"].add_ip(client_ip)  # 记录失败
        raise HTTPException(status_code=401, detail="密码错误")

    # 登录成功，清除该 IP 的失败计数
    ip_limit["login"].ips.pop(client_ip, None)

    expires_in = get_admin_session_expire_seconds()
    token = create_token({"is_admin": True}, expires_in=expires_in)
    # 审计记录
    if request:
        await record_audit(event_type="admin_login", ip=client_ip, request=request)
    return APIResponse(
        detail={
            "id": "admin",
            "username": "admin",
            "token": token,
            "token_type": "Bearer",
            "expires_at": verify_token(token)["exp"],
            "expires_in": expires_in,
        }
    )


@admin_api.get("/verify")
async def verify_admin(session: dict = Depends(get_admin_session)):
    return APIResponse(detail=session)


@admin_api.post("/logout")
async def logout_admin():
    return APIResponse(detail={"ok": True})


async def build_dashboard_recent_file(file_code: FileCodes) -> dict:
    is_expired = await file_code.is_expired()
    return {
        "id": file_code.id,
        "code": file_code.code,
        "name": file_code.prefix + file_code.suffix,
        "suffix": file_code.suffix,
        "size": file_code.size,
        "text": file_code.text is not None,
        "expiredAt": file_code.expired_at,
        "expiredCount": file_code.expired_count,
        "usedCount": file_code.used_count,
        "createdAt": file_code.created_at,
        "isExpired": is_expired,
    }


@admin_api.get("/dashboard")
async def dashboard(file_service: FileService = Depends(get_file_service)):
    from tortoise.expressions import Q
    from tortoise.functions import Sum

    now = await get_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - datetime.timedelta(days=1)

    # BUG-004: 基础统计改用数据库聚合，避免 FileCodes.all() 全量加载到内存
    async def _sum(queryset, field: str) -> int:
        result = await queryset.annotate(total=Sum(field)).values("total")
        return (result[0]["total"] or 0) if result else 0

    total_files = await FileCodes.all().count()
    all_size = await _sum(FileCodes.all(), "size")
    used_count = await _sum(FileCodes.all(), "used_count")
    text_count = await FileCodes.filter(text__not_isnull=True).count()
    chunked_count = await FileCodes.filter(is_chunked=True).count()

    today_qs = FileCodes.filter(created_at__gte=today_start)
    today_count = await today_qs.count()
    today_size = await _sum(today_qs, "size")

    yesterday_qs = FileCodes.filter(
        created_at__gte=yesterday_start, created_at__lt=today_start
    )
    yesterday_count = await yesterday_qs.count()
    yesterday_size = await _sum(yesterday_qs, "size")

    # 过期数：精确翻译 FileCodes.is_expired 逻辑
    expired_q = Q(expired_at__not_isnull=True) & (
        Q(expired_count__lt=0, expired_at__lt=now) | Q(expired_count=0)
    )
    expired_count = await FileCodes.filter(expired_q).count()

    # 健康度汇总与后缀分布：数据库聚合
    health_summary = await file_service.build_dashboard_health_counts(now=now)
    top_suffixes = await file_service.build_top_suffixes(limit=8)

    # 最近文件：数据库排序 + 限制条数，避免全量排序
    recent_file_codes = await FileCodes.all().order_by("-created_at").limit(8)

    sys_start = await KeyValue.filter(key="sys_start").first()
    recent_activities = await file_service.list_admin_activities(limit=8)
    return APIResponse(
        detail={
            "totalFiles": total_files,
            "storageUsed": str(all_size),
            "sysUptime": sys_start.value if sys_start else None,
            "yesterdayCount": yesterday_count,
            "yesterdaySize": str(yesterday_size),
            "todayCount": today_count,
            "todaySize": str(today_size),
            "activeCount": total_files - expired_count,
            "expiredCount": expired_count,
            "textCount": text_count,
            "fileCount": total_files - text_count,
            "chunkedCount": chunked_count,
            "usedCount": used_count,
            "storageBackend": settings.file_storage,
            "uploadSizeLimit": settings.uploadSize,
            "openUpload": settings.openUpload,
            "enableChunk": settings.enableChunk,
            "maxSaveSeconds": settings.max_save_seconds,
            **health_summary,
            "healthSummary": health_summary,
            "topSuffixes": top_suffixes,
            "recentFiles": [
                await build_dashboard_recent_file(file_code)
                for file_code in recent_file_codes
            ],
            "recentActivities": recent_activities["activities"],
            "recent_activities": recent_activities["activities"],
        }
    )


@admin_api.get("/activities")
async def admin_activities(
    limit: int = 20,
    action: Optional[str] = None,
    targetType: Optional[str] = None,
    target_type: Optional[str] = None,
    keyword: Optional[str] = None,
    file_service: FileService = Depends(get_file_service),
):
    result = await file_service.list_admin_activities(
        limit=limit,
        action=action,
        target_type=_pick_query_text(targetType, target_type),
        keyword=keyword,
    )
    return APIResponse(detail=result)


@admin_api.delete("/file/delete")
async def file_delete(
    data: IDData,
    file_service: FileService = Depends(get_file_service),
):
    await file_service.delete_file(data.id)
    return APIResponse()


async def batch_delete_files(
    data: IDsData,
    file_service: FileService,
):
    if not data.ids:
        raise HTTPException(status_code=400, detail="请选择要删除的文件")
    result = await file_service.delete_files(data.ids)
    return APIResponse(detail=result)


@admin_api.delete("/file/batch-delete")
async def file_batch_delete(
    data: IDsData,
    file_service: FileService = Depends(get_file_service),
):
    return await batch_delete_files(data, file_service)


@admin_api.post("/file/batch-delete")
async def file_batch_delete_post(
    data: IDsData,
    file_service: FileService = Depends(get_file_service),
):
    return await batch_delete_files(data, file_service)


async def batch_update_files(
    data: BatchUpdateFileData,
    file_service: FileService,
):
    if not data.ids:
        raise HTTPException(status_code=400, detail="请选择要更新的文件")

    update_data = {}
    fields_set = data.model_fields_set
    should_clear_expired_at = bool(data.clearExpiredAt or data.clear_expired_at)

    if should_clear_expired_at:
        update_data["expired_at"] = None
        update_data["expired_count"] = -1
    elif "expired_at" in fields_set and data.expired_at != "":
        update_data["expired_at"] = data.expired_at

    if (
        not should_clear_expired_at
        and "expired_count" in fields_set
        and data.expired_count is not None
    ):
        update_data["expired_count"] = data.expired_count

    if not update_data:
        raise HTTPException(status_code=400, detail="请选择要更新的字段")

    result = await file_service.update_files(data.ids, update_data)
    return APIResponse(detail=result)


@admin_api.patch("/file/batch-update")
async def file_batch_update(
    data: BatchUpdateFileData,
    file_service: FileService = Depends(get_file_service),
):
    return await batch_update_files(data, file_service)


@admin_api.post("/file/batch-update")
async def file_batch_update_post(
    data: BatchUpdateFileData,
    file_service: FileService = Depends(get_file_service),
):
    return await batch_update_files(data, file_service)


async def apply_file_policy_action(
    data: FilePolicyActionData,
    file_service: FileService,
):
    download_limit = data.downloadLimit
    if download_limit is None:
        download_limit = data.download_limit

    detail = await file_service.apply_file_policy_action(
        file_id=data.id,
        action=data.action,
        download_limit=download_limit,
    )
    return APIResponse(detail=detail)


@admin_api.patch("/file/policy-action")
async def file_policy_action(
    data: FilePolicyActionData,
    file_service: FileService = Depends(get_file_service),
):
    return await apply_file_policy_action(data, file_service)


@admin_api.post("/file/policy-action")
async def file_policy_action_post(
    data: FilePolicyActionData,
    file_service: FileService = Depends(get_file_service),
):
    return await apply_file_policy_action(data, file_service)


async def apply_batch_file_policy_action(
    data: BatchFilePolicyActionData,
    file_service: FileService,
):
    if not data.ids:
        raise HTTPException(status_code=400, detail="请选择要更新的文件")

    download_limit = data.downloadLimit
    if download_limit is None:
        download_limit = data.download_limit

    result = await file_service.apply_files_policy_action(
        file_ids=data.ids,
        action=data.action,
        download_limit=download_limit,
    )
    return APIResponse(detail=result)


@admin_api.patch("/file/batch-policy-action")
async def file_batch_policy_action(
    data: BatchFilePolicyActionData,
    file_service: FileService = Depends(get_file_service),
):
    return await apply_batch_file_policy_action(data, file_service)


@admin_api.post("/file/batch-policy-action")
async def file_batch_policy_action_post(
    data: BatchFilePolicyActionData,
    file_service: FileService = Depends(get_file_service),
):
    return await apply_batch_file_policy_action(data, file_service)


@admin_api.get("/file/list")
async def file_list(
    page: int = 1,
    size: int = 10,
    keyword: str = "",
    status: str = "",
    type: str = "",
    health: str = "",
    dedup: str = "",
    sortBy: str = "created_at",
    sortOrder: str = "desc",
    file_service: FileService = Depends(get_file_service),
):
    page = max(page, 1)
    size = min(max(size, 1), 100)
    files, total, summary = await file_service.list_files(
        page,
        size,
        keyword,
        status=status,
        file_type=type,
        health=health,
        dedup=dedup,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return APIResponse(
        detail={
            "page": page,
            "size": size,
            "data": files,
            "total": total,
            "summary": summary,
        }
    )


@admin_api.get("/file/detail")
async def file_detail(
    id: int,
    file_service: FileService = Depends(get_file_service),
):
    detail = await file_service.get_file_detail(id)
    return APIResponse(detail=detail)


@admin_api.post("/file/detail")
async def file_detail_post(
    data: IDData,
    file_service: FileService = Depends(get_file_service),
):
    detail = await file_service.get_file_detail(data.id)
    return APIResponse(detail=detail)


async def update_file_metadata(
    data: FileMetadataData,
    file_service: FileService,
):
    fields_set = data.model_fields_set
    update_note = "note" in fields_set
    update_tags = "tags" in fields_set
    if not update_note and not update_tags:
        raise HTTPException(status_code=400, detail="请选择要更新的元数据")

    detail = await file_service.update_file_metadata(
        file_id=data.id,
        note=data.note,
        tags=data.tags,
        update_note=update_note,
        update_tags=update_tags,
    )
    return APIResponse(detail=detail)


@admin_api.patch("/file/metadata")
async def file_metadata(
    data: FileMetadataData,
    file_service: FileService = Depends(get_file_service),
):
    return await update_file_metadata(data, file_service)


@admin_api.post("/file/metadata")
async def file_metadata_post(
    data: FileMetadataData,
    file_service: FileService = Depends(get_file_service),
):
    return await update_file_metadata(data, file_service)


@admin_api.get("/file/view-presets")
async def file_view_presets(
    file_service: FileService = Depends(get_file_service),
):
    result = await file_service.list_file_view_presets()
    return APIResponse(detail=result)


async def save_file_view_preset(
    data: FileViewPresetData,
    file_service: FileService,
):
    filters = data.filters if data.filters is not None else data.params
    preset = await file_service.save_file_view_preset(
        preset_id=data.id,
        name=data.name,
        filters=filters or {},
    )
    return APIResponse(detail=preset)


@admin_api.post("/file/view-presets")
async def file_view_presets_save(
    data: FileViewPresetData,
    file_service: FileService = Depends(get_file_service),
):
    return await save_file_view_preset(data, file_service)


@admin_api.patch("/file/view-presets")
async def file_view_presets_patch(
    data: FileViewPresetData,
    file_service: FileService = Depends(get_file_service),
):
    return await save_file_view_preset(data, file_service)


async def delete_file_view_preset(
    data: FileViewPresetDeleteData,
    file_service: FileService,
):
    result = await file_service.delete_file_view_preset(data.id)
    return APIResponse(detail=result)


@admin_api.delete("/file/view-presets")
async def file_view_presets_delete(
    data: FileViewPresetDeleteData,
    file_service: FileService = Depends(get_file_service),
):
    return await delete_file_view_preset(data, file_service)


@admin_api.post("/file/view-presets/delete")
async def file_view_presets_delete_post(
    data: FileViewPresetDeleteData,
    file_service: FileService = Depends(get_file_service),
):
    return await delete_file_view_preset(data, file_service)


@admin_api.get("/config/get")
async def get_config(
    config_service: ConfigService = Depends(get_config_service),
):
    return APIResponse(detail=config_service.get_config())


@admin_api.patch("/config/update")
async def update_config(
    data: dict,
    config_service: ConfigService = Depends(get_config_service),
    file_service: FileService = Depends(get_file_service),
):
    data.pop("themesChoices", None)
    await config_service.update_config(data)
    await file_service.record_admin_activity(
        action="config.update",
        target_type="config",
        target_name="system",
        count=1,
        meta={"fields": sorted(data.keys())},
    )
    return APIResponse()


@admin_api.get("/file/download")
async def file_download(
    id: int,
    file_service: FileService = Depends(get_file_service),
):
    file_content = await file_service.download_file(id)
    return file_content


@admin_api.get("/file/preview")
async def file_preview(
    id: int,
    maxChars: int = 4000,
    file_service: FileService = Depends(get_file_service),
):
    preview = await file_service.preview_file(id, maxChars)
    return APIResponse(detail=preview)


@admin_api.get("/local/lists")
async def get_local_lists(
    local_file_service: LocalFileService = Depends(get_local_file_service),
):
    files = await local_file_service.list_files()
    return APIResponse(detail=files)


@admin_api.delete("/local/delete")
async def delete_local_file(
    item: DeleteItem,
    local_file_service: LocalFileService = Depends(get_local_file_service),
    file_service: FileService = Depends(get_file_service),
):
    result = await local_file_service.delete_file(item.filename)
    await file_service.record_admin_activity(
        action="local_file.delete",
        target_type="local_file",
        target_name=item.filename,
        count=1,
        meta={"success": bool(result)},
    )
    return APIResponse(detail=result)


@admin_api.post("/local/share")
async def share_local_file(
    item: ShareItem,
    file_service: FileService = Depends(get_file_service),
):
    share_info = await file_service.share_local_file(item)
    await file_service.record_admin_activity(
        action="local_file.share",
        target_type="file",
        target_id=share_info.get("id") if isinstance(share_info, dict) else None,
        target_name=item.filename,
        count=1,
        meta={
            "expireValue": item.expire_value,
            "expireStyle": item.expire_style,
        },
    )
    return APIResponse(detail=share_info)


@admin_api.patch("/file/update")
async def update_file(
    data: UpdateFileData,
    file_service: FileService = Depends(get_file_service),
):
    file_code = await FileCodes.filter(id=data.id).first()
    if not file_code:
        raise HTTPException(status_code=404, detail="文件不存在")
    target_name = file_service._build_file_activity_name(file_code)
    update_data = {}

    if data.code is not None and data.code != file_code.code:
        # 判断code是否存在
        if await FileCodes.filter(code=data.code).first():
            raise HTTPException(status_code=400, detail="code已存在")
        update_data["code"] = data.code
    if data.prefix is not None and data.prefix != file_code.prefix:
        update_data["prefix"] = data.prefix
    if data.suffix is not None and data.suffix != file_code.suffix:
        update_data["suffix"] = data.suffix
    if (
        data.expired_at is not None
        and data.expired_at != ""
        and data.expired_at != file_code.expired_at
    ):
        update_data["expired_at"] = data.expired_at
    if data.expired_count is not None and data.expired_count != file_code.expired_count:
        update_data["expired_count"] = data.expired_count

    await file_code.update_from_dict(update_data).save()
    if update_data:
        await file_service.record_admin_activity(
            action="file.update",
            target_type="file",
            target_id=data.id,
            target_name=target_name,
            count=1,
            meta={"fields": sorted(update_data.keys())},
        )
    return APIResponse(detail="更新成功")


# ============ 审计日志 API ============


@admin_api.get("/audit/logs")
async def audit_logs(
    page: int = 1,
    size: int = 20,
    event_type: str = "",
    file_id: Optional[int] = None,
    ip: str = "",
    keyword: str = "",
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    """审计日志列表，支持多维度筛选"""
    from apps.base.models import AuditLog
    from tortoise.expressions import Q

    page = max(page, 1)
    size = min(max(size, 1), 100)

    filters = Q()
    if event_type:
        filters &= Q(event_type=event_type)
    if file_id is not None:
        filters &= Q(file_id=file_id)
    if ip:
        filters &= Q(ip__startswith=ip)
    if keyword:
        filters &= Q(file_name__icontains=keyword)
    if start_time:
        filters &= Q(created_at__gte=start_time)
    if end_time:
        filters &= Q(created_at__lte=end_time)

    # 排序字段白名单
    allowed_sort = {"created_at", "event_type", "ip", "file_name"}
    if sort_by not in allowed_sort:
        sort_by = "created_at"
    order_field = f"-{sort_by}" if sort_order == "desc" else sort_by

    total = await AuditLog.filter(filters).count()
    logs = await AuditLog.filter(filters).order_by(order_field).offset((page - 1) * size).limit(size)

    return APIResponse(
        detail={
            "page": page,
            "size": size,
            "total": total,
            "data": [
                {
                    "id": log.id,
                    "event_type": log.event_type,
                    "file_id": log.file_id,
                    "file_code": log.file_code,
                    "file_name": log.file_name,
                    "ip": log.ip,
                    "ip_location": log.ip_location,
                    "browser": log.browser,
                    "browser_version": log.browser_version,
                    "os": log.os,
                    "os_version": log.os_version,
                    "device_type": log.device_type,
                    "detail": log.detail,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ],
        }
    )


@admin_api.get("/audit/file/{target_file_id}/timeline")
async def audit_file_timeline(target_file_id: int):
    """单文件完整生命周期时间线"""
    from apps.base.models import AuditLog

    logs = await AuditLog.filter(file_id=target_file_id).order_by("created_at")
    return APIResponse(
        detail={
            "file_id": target_file_id,
            "events": [
                {
                    "event_type": log.event_type,
                    "ip": log.ip,
                    "ip_location": log.ip_location,
                    "device_type": log.device_type,
                    "browser": log.browser,
                    "os": log.os,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ],
        }
    )


@admin_api.get("/audit/export")
async def audit_export_csv(
    event_type: str = "",
    file_id: Optional[int] = None,
    ip: str = "",
    keyword: str = "",
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 5000,
):
    """导出审计日志为 CSV 文件"""
    import csv
    import io
    from fastapi.responses import StreamingResponse
    from apps.base.models import AuditLog
    from tortoise.expressions import Q

    limit = min(max(limit, 1), 50000)

    filters = Q()
    if event_type:
        filters &= Q(event_type=event_type)
    if file_id is not None:
        filters &= Q(file_id=file_id)
    if ip:
        filters &= Q(ip__startswith=ip)
    if keyword:
        filters &= Q(file_name__icontains=keyword)
    if start_time:
        filters &= Q(created_at__gte=start_time)
    if end_time:
        filters &= Q(created_at__lte=end_time)

    logs = await AuditLog.filter(filters).order_by("-created_at").limit(limit)

    def _csv_safe(value) -> str:
        """防止 CSV 注入：对以 = + - @ 开头的内容添加前缀"""
        s = str(value) if value is not None else ""
        if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{s}"
        return s

    # 生成 CSV
    output = io.StringIO()
    # BOM 头，确保 Excel 正确识别 UTF-8
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([
        "ID", "事件类型", "文件ID", "取件码", "文件名",
        "IP", "IP归属地", "浏览器", "浏览器版本",
        "操作系统", "系统版本", "设备类型", "时间",
    ])
    for log in logs:
        writer.writerow([
            log.id,
            _csv_safe(log.event_type),
            log.file_id or "",
            _csv_safe(log.file_code),
            _csv_safe(log.file_name),
            _csv_safe(log.ip),
            _csv_safe(log.ip_location),
            _csv_safe(log.browser),
            _csv_safe(log.browser_version),
            _csv_safe(log.os),
            _csv_safe(log.os_version),
            _csv_safe(log.device_type),
            log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="audit_logs.csv"'
        },
    )


# ============ Webhook 管理 API ============


@admin_api.get("/webhook/list")
async def webhook_list():
    """获取所有 Webhook 配置"""
    from apps.base.models import WebhookConfig

    configs = await WebhookConfig.all().order_by("-created_at")
    return APIResponse(detail=[
        {
            "id": c.id,
            "name": c.name,
            "url": c.url,
            "events": c.events,
            "headers": c.headers,
            "enabled": c.enabled,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in configs
    ])


@admin_api.post("/webhook/create")
async def webhook_create(data: dict):
    """创建 Webhook 配置"""
    from apps.base.models import WebhookConfig
    from core.webhook import validate_webhook_url, _MAX_WEBHOOKS

    # 数量限制
    count = await WebhookConfig.all().count()
    if count >= _MAX_WEBHOOKS:
        raise HTTPException(status_code=400, detail=f"最多支持 {_MAX_WEBHOOKS} 个 Webhook 配置")

    name = str(data.get("name", "")).strip()
    url = str(data.get("url", "")).strip()
    events = data.get("events", [])
    headers = data.get("headers")

    if not name:
        raise HTTPException(status_code=400, detail="名称不能为空")
    if not url:
        raise HTTPException(status_code=400, detail="URL 不能为空")

    # SSRF 安全校验
    error = validate_webhook_url(url)
    if error:
        raise HTTPException(status_code=400, detail=error)

    if not isinstance(events, list) or not events:
        raise HTTPException(status_code=400, detail="至少选择一个事件类型")

    config = await WebhookConfig.create(
        name=name[:128],
        url=url[:1024],
        events=events,
        headers=headers if isinstance(headers, dict) else None,
        enabled=bool(data.get("enabled", True)),
    )
    return APIResponse(detail={"id": config.id, "name": config.name})


@admin_api.patch("/webhook/update")
async def webhook_update(data: dict):
    """更新 Webhook 配置"""
    from apps.base.models import WebhookConfig
    from core.webhook import validate_webhook_url

    config_id = data.get("id")
    if not config_id:
        raise HTTPException(status_code=400, detail="缺少 id")

    config = await WebhookConfig.filter(id=config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Webhook 不存在")

    if "url" in data and data["url"]:
        error = validate_webhook_url(str(data["url"]))
        if error:
            raise HTTPException(status_code=400, detail=error)
        config.url = str(data["url"])[:1024]
    if "name" in data and data["name"]:
        config.name = str(data["name"]).strip()[:128]
    if "events" in data:
        if not isinstance(data["events"], list) or not data["events"]:
            raise HTTPException(status_code=400, detail="至少选择一个事件类型")
        config.events = data["events"]
    if "headers" in data:
        config.headers = data["headers"] if isinstance(data["headers"], dict) else None
    if "enabled" in data:
        config.enabled = bool(data["enabled"])

    await config.save()
    return APIResponse(detail={"id": config.id, "name": config.name})


@admin_api.delete("/webhook/delete")
async def webhook_delete(data: dict):
    """删除 Webhook 配置"""
    from apps.base.models import WebhookConfig, WebhookLog

    config_id = data.get("id")
    if not config_id:
        raise HTTPException(status_code=400, detail="缺少 id")

    deleted = await WebhookConfig.filter(id=config_id).delete()
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook 不存在")

    # 清理关联日志
    await WebhookLog.filter(webhook_id=config_id).delete()
    return APIResponse(detail={"ok": True})


@admin_api.post("/webhook/test")
async def webhook_test(data: dict):
    """发送测试事件"""
    from apps.base.models import WebhookConfig
    from core.webhook import _send_with_retry

    config_id = data.get("id")
    if not config_id:
        raise HTTPException(status_code=400, detail="缺少 id")

    config = await WebhookConfig.filter(id=config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Webhook 不存在")

    import datetime as dt
    payload = {
        "event": "webhook.test",
        "timestamp": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
        "data": {"message": "这是一条测试事件", "webhook_name": config.name},
    }
    await _send_with_retry(config, "webhook.test", payload)
    return APIResponse(detail={"ok": True, "message": "测试事件已发送"})


@admin_api.get("/webhook/logs")
async def webhook_logs(
    webhook_id: Optional[int] = None,
    page: int = 1,
    size: int = 20,
):
    """查看 Webhook 发送历史"""
    from apps.base.models import WebhookLog
    from tortoise.expressions import Q

    page = max(page, 1)
    size = min(max(size, 1), 100)

    filters = Q()
    if webhook_id is not None:
        filters &= Q(webhook_id=webhook_id)

    total = await WebhookLog.filter(filters).count()
    logs = await WebhookLog.filter(filters).order_by("-created_at").offset((page - 1) * size).limit(size)

    return APIResponse(detail={
        "page": page,
        "size": size,
        "total": total,
        "data": [
            {
                "id": log.id,
                "webhook_id": log.webhook_id,
                "event_type": log.event_type,
                "response_status": log.response_status,
                "response_body": (log.response_body or "")[:500],
                "success": log.success,
                "attempt": log.attempt,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    })


# ============ 信任代理配置 API ============


@admin_api.get("/proxy/list")
async def proxy_list(request: Request):
    """获取当前信任代理列表"""
    from apps.base.dependencies import get_client_ip

    proxies = getattr(settings, "trustedProxies", [])
    if isinstance(proxies, str):
        proxies = [p.strip() for p in proxies.split(",") if p.strip()]

    return APIResponse(detail={
        "trusted_proxies": proxies,
        "current_ip": get_client_ip(request),
    })


@admin_api.put("/proxy/update")
async def proxy_update(data: dict, request: Request):
    """更新信任代理列表"""
    import ipaddress as _ipaddress
    from apps.base.dependencies import get_client_ip
    from core.config import refresh_settings
    from apps.base.models import KeyValue

    proxies = data.get("trusted_proxies", [])
    if not isinstance(proxies, list):
        raise HTTPException(status_code=400, detail="trusted_proxies 必须为列表")

    if len(proxies) > 50:
        raise HTTPException(status_code=400, detail="最多支持 50 个信任代理")

    # 校验每一项是否为合法 IP 或 CIDR
    validated = []
    for item in proxies:
        item = str(item).strip()
        if not item:
            continue
        try:
            if "/" in item:
                network = _ipaddress.ip_network(item, strict=False)
                # 安全拦截：禁止信任所有地址（等效于关闭IP审计）
                if network.prefixlen == 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"禁止使用 {item}：信任所有地址会导致IP审计失效"
                    )
            else:
                _ipaddress.ip_address(item)
            validated.append(item)
        except HTTPException:
            raise
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"无效的 IP/CIDR 格式: {item}"
            )

    # 写入配置
    config_record = await KeyValue.filter(key="settings").first()
    if config_record and config_record.value:
        config_record.value["trustedProxies"] = validated
        await config_record.save()
    await refresh_settings(force=True)  # REL-001: 配置变更后强制刷新

    # 审计记录
    client_ip = get_client_ip(request)
    await record_audit(
        event_type="config_update", ip=client_ip, request=request,
        detail={"action": "proxy.update", "proxies": validated},
    )

    return APIResponse(detail={
        "trusted_proxies": validated,
        "current_ip": client_ip,
    })
