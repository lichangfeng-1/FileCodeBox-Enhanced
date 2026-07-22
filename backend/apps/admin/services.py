import hashlib
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from core.response import APIResponse
from core.storage import FileStorageInterface, storages
from core.settings import (
    ADMIN_SESSION_EXPIRE_MAX,
    ADMIN_SESSION_EXPIRE_MIN,
    settings,
)
from core.config import refresh_settings
from core.security import INTERNAL_CONFIG_KEYS, generate_jwt_secret
from apps.base.models import FileCodes, KeyValue
from apps.base.utils import get_expire_info, get_file_path_name
from apps.base.quota import release_storage, reserve_storage
from fastapi import HTTPException
from core.settings import data_root
from core.utils import get_now, hash_password, is_password_hashed


class FileService:
    FILE_METADATA_KEY_PREFIX = "admin_file_metadata:"
    FILE_VIEW_PRESETS_KEY = "admin_file_view_presets"
    ADMIN_ACTIVITY_KEY = "admin_activity_events"
    MAX_METADATA_NOTE_LENGTH = 2000
    MAX_METADATA_TAGS = 12
    MAX_METADATA_TAG_LENGTH = 24
    MAX_VIEW_PRESETS = 24
    MAX_VIEW_PRESET_NAME_LENGTH = 32
    MAX_VIEW_PRESET_KEYWORD_LENGTH = 80
    MAX_ADMIN_ACTIVITIES = 80
    MAX_ADMIN_ACTIVITY_TEXT_LENGTH = 120

    POLICY_ACTIONS = {
        "extend_24h",
        "extend_7d",
        "make_permanent",
        "reset_download_limit",
    }

    SORT_FIELDS = {
        "created_at",
        "createdat",
        "expired_at",
        "expiredat",
        "name",
        "size",
        "used_count",
        "usedcount",
        "code",
    }
    VIEW_PRESET_STATUS_VALUES = {"all", "active", "expired"}
    VIEW_PRESET_TYPE_VALUES = {"all", "file", "text", "chunked"}
    VIEW_PRESET_HEALTH_VALUES = {
        "all",
        "attention",
        "danger",
        "warning",
        "healthy",
        "expired",
        "expiring_soon",
        "storage_issue",
        "never_retrieved",
        "permanent",
    }
    VIEW_PRESET_SORT_FIELDS = {
        "created_at",
        "expired_at",
        "name",
        "size",
        "used_count",
        "code",
    }

    def __init__(self):
        self._file_storage: Optional[FileStorageInterface] = None

    @property
    def file_storage(self) -> FileStorageInterface:
        if self._file_storage is None:
            self._file_storage = storages[settings.file_storage]()
        return self._file_storage

    def _file_metadata_key(self, file_id: int) -> str:
        return f"{self.FILE_METADATA_KEY_PREFIX}{file_id}"

    async def _delete_file_code(self, file_code: FileCodes):
        if file_code.text is None:
            await self.file_storage.delete_file(file_code)
        await KeyValue.filter(key=self._file_metadata_key(file_code.id)).delete()
        await file_code.delete()

    async def delete_file(self, file_id: int):
        file_code = await FileCodes.get(id=file_id)
        target_name = self._build_file_activity_name(file_code)
        await self._delete_file_code(file_code)
        await self.record_admin_activity(
            action="file.delete",
            target_type="file",
            target_id=file_id,
            target_name=target_name,
            count=1,
        )

    async def delete_files(self, file_ids: list[int]):
        unique_ids = list(dict.fromkeys(file_ids))
        deleted = []
        failed = []
        missing = []

        for file_id in unique_ids:
            file_code = await FileCodes.filter(id=file_id).first()
            if not file_code:
                missing.append(file_id)
                continue

            try:
                await self._delete_file_code(file_code)
                deleted.append(file_id)
            except Exception as exc:
                failed.append({"id": file_id, "reason": str(exc)})

        if deleted:
            await self.record_admin_activity(
                action="files.batch_delete",
                target_type="file",
                count=len(deleted),
                meta={
                    "requestedCount": len(file_ids),
                    "uniqueCount": len(unique_ids),
                    "deleted": deleted,
                    "missing": missing,
                    "failedCount": len(failed),
                },
            )

        return {
            "requestedCount": len(file_ids),
            "requested_count": len(file_ids),
            "uniqueCount": len(unique_ids),
            "unique_count": len(unique_ids),
            "deletedCount": len(deleted),
            "deleted_count": len(deleted),
            "missingCount": len(missing),
            "missing_count": len(missing),
            "failedCount": len(failed),
            "failed_count": len(failed),
            "deleted": deleted,
            "missing": missing,
            "failed": failed,
        }

    async def update_files(self, file_ids: list[int], update_data: dict[str, Any]):
        unique_ids = list(dict.fromkeys(file_ids))
        updated = []
        failed = []
        missing = []

        for file_id in unique_ids:
            file_code = await FileCodes.filter(id=file_id).first()
            if not file_code:
                missing.append(file_id)
                continue

            try:
                await file_code.update_from_dict(update_data).save()
                updated.append(file_id)
            except Exception as exc:
                failed.append({"id": file_id, "reason": str(exc)})

        if updated:
            await self.record_admin_activity(
                action="files.batch_update",
                target_type="file",
                count=len(updated),
                meta={
                    "fields": sorted(update_data.keys()),
                    "requestedCount": len(file_ids),
                    "uniqueCount": len(unique_ids),
                    "updated": updated,
                    "missing": missing,
                    "failedCount": len(failed),
                },
            )

        return {
            "requestedCount": len(file_ids),
            "requested_count": len(file_ids),
            "uniqueCount": len(unique_ids),
            "unique_count": len(unique_ids),
            "updatedCount": len(updated),
            "updated_count": len(updated),
            "missingCount": len(missing),
            "missing_count": len(missing),
            "failedCount": len(failed),
            "failed_count": len(failed),
            "updated": updated,
            "missing": missing,
            "failed": failed,
        }

    async def apply_file_policy_action(
        self,
        file_id: int,
        action: str,
        download_limit: Optional[int] = None,
    ) -> dict[str, Any]:
        file_code = await FileCodes.filter(id=file_id).first()
        if not file_code:
            raise HTTPException(status_code=404, detail="文件不存在")

        action = action.strip().lower()
        now = await get_now()
        update_data = self._build_policy_action_update(
            file_code=file_code,
            action=action,
            now=now,
            download_limit=download_limit,
        )

        await file_code.update_from_dict(update_data).save()
        await self.record_admin_activity(
            action="file.policy_action",
            target_type="file",
            target_id=file_id,
            target_name=self._build_file_activity_name(file_code),
            count=1,
            meta={"policyAction": action},
        )
        return await self.get_file_detail(file_id)

    async def get_file_metadata(self, file_id: int) -> dict[str, Any]:
        record = await KeyValue.filter(key=self._file_metadata_key(file_id)).first()
        return self._normalize_file_metadata(record.value if record else None)

    async def update_file_metadata(
        self,
        file_id: int,
        note: Optional[str],
        tags: Optional[list[str]],
        update_note: bool,
        update_tags: bool,
    ) -> dict[str, Any]:
        file_code = await FileCodes.filter(id=file_id).first()
        if not file_code:
            raise HTTPException(status_code=404, detail="文件不存在")

        current_metadata = await self.get_file_metadata(file_id)
        next_metadata = dict(current_metadata)
        if update_note:
            next_metadata["note"] = self._normalize_metadata_note(note)
        if update_tags:
            next_metadata["tags"] = self._normalize_metadata_tags(tags)

        now = await get_now()
        updated_at = now.isoformat()
        next_metadata["updatedAt"] = updated_at
        next_metadata["updated_at"] = updated_at
        await KeyValue.update_or_create(
            key=self._file_metadata_key(file_id),
            defaults={"value": next_metadata},
        )
        await self.record_admin_activity(
            action="file.metadata_update",
            target_type="file",
            target_id=file_id,
            target_name=self._build_file_activity_name(file_code),
            count=1,
            meta={
                "updateNote": update_note,
                "updateTags": update_tags,
                "tagCount": len(next_metadata["tags"]),
            },
        )
        return await self.get_file_detail(file_id)

    async def list_file_view_presets(self) -> dict[str, Any]:
        presets = await self._get_file_view_presets()
        return {
            "presets": presets,
            "items": presets,
            "total": len(presets),
        }

    async def save_file_view_preset(
        self,
        preset_id: Optional[str],
        name: str,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        presets = await self._get_file_view_presets()
        normalized_name = self._normalize_file_view_preset_name(name)
        normalized_filters = self._normalize_file_view_preset_filters(filters)
        now = await get_now()
        updated_at = now.isoformat()

        target_index = next(
            (index for index, preset in enumerate(presets) if preset["id"] == preset_id),
            -1,
        )
        is_update = target_index >= 0
        if is_update:
            preset = presets[target_index]
            next_preset = {
                **preset,
                "name": normalized_name,
                "filters": normalized_filters,
                "params": normalized_filters,
                "updatedAt": updated_at,
                "updated_at": updated_at,
            }
            presets[target_index] = next_preset
        else:
            if len(presets) >= self.MAX_VIEW_PRESETS:
                raise HTTPException(status_code=400, detail="视图预设数量已达上限")
            next_preset = {
                "id": preset_id or self._build_file_view_preset_id(normalized_name, now),
                "name": normalized_name,
                "filters": normalized_filters,
                "params": normalized_filters,
                "createdAt": updated_at,
                "created_at": updated_at,
                "updatedAt": updated_at,
                "updated_at": updated_at,
            }
            presets.append(next_preset)

        await self._save_file_view_presets(presets)
        await self.record_admin_activity(
            action="file.view_preset_update" if is_update else "file.view_preset_create",
            target_type="view_preset",
            target_id=next_preset["id"],
            target_name=next_preset["name"],
            count=1,
            meta={"filters": normalized_filters},
        )
        return next_preset

    async def delete_file_view_preset(self, preset_id: str) -> dict[str, Any]:
        preset_id = str(preset_id).strip()
        if not preset_id:
            raise HTTPException(status_code=400, detail="请选择要删除的视图预设")

        presets = await self._get_file_view_presets()
        deleted_preset = next(
            (preset for preset in presets if preset["id"] == preset_id),
            None,
        )
        next_presets = [preset for preset in presets if preset["id"] != preset_id]
        if len(next_presets) == len(presets):
            raise HTTPException(status_code=404, detail="视图预设不存在")

        await self._save_file_view_presets(next_presets)
        await self.record_admin_activity(
            action="file.view_preset_delete",
            target_type="view_preset",
            target_id=preset_id,
            target_name=(deleted_preset or {}).get("name", ""),
            count=1,
        )
        return {
            "deleted": preset_id,
            "deletedPresetId": preset_id,
            "deleted_preset_id": preset_id,
            "total": len(next_presets),
        }

    async def apply_files_policy_action(
        self,
        file_ids: list[int],
        action: str,
        download_limit: Optional[int] = None,
    ) -> dict[str, Any]:
        unique_ids = list(dict.fromkeys(file_ids))
        updated = []
        failed = []
        missing = []
        action = action.strip().lower()

        if action not in self.POLICY_ACTIONS:
            raise HTTPException(status_code=400, detail="不支持的策略动作")

        if action == "reset_download_limit":
            next_limit = download_limit if download_limit is not None else 5
            if next_limit < 1:
                raise HTTPException(status_code=400, detail="取件次数必须大于 0")

        now = await get_now()
        for file_id in unique_ids:
            file_code = await FileCodes.filter(id=file_id).first()
            if not file_code:
                missing.append(file_id)
                continue

            try:
                update_data = self._build_policy_action_update(
                    file_code=file_code,
                    action=action,
                    now=now,
                    download_limit=download_limit,
                )
                await file_code.update_from_dict(update_data).save()
                updated.append(file_id)
            except Exception as exc:
                failed.append({"id": file_id, "reason": str(exc)})

        if updated:
            await self.record_admin_activity(
                action="files.batch_policy_action",
                target_type="file",
                count=len(updated),
                meta={
                    "policyAction": action,
                    "requestedCount": len(file_ids),
                    "uniqueCount": len(unique_ids),
                    "updated": updated,
                    "missing": missing,
                    "failedCount": len(failed),
                },
            )

        return {
            "requestedCount": len(file_ids),
            "requested_count": len(file_ids),
            "uniqueCount": len(unique_ids),
            "unique_count": len(unique_ids),
            "updatedCount": len(updated),
            "updated_count": len(updated),
            "missingCount": len(missing),
            "missing_count": len(missing),
            "failedCount": len(failed),
            "failed_count": len(failed),
            "action": action,
            "updated": updated,
            "missing": missing,
            "failed": failed,
        }

    async def list_files(
        self,
        page: int,
        size: int,
        keyword: str = "",
        status: str = "",
        file_type: str = "",
        health: str = "",
        dedup: str = "",
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ):
        """BUG-005: 过滤分页下推数据库，避免全量加载到内存。

        快速路径（无 health/dedup 筛选）：全部在 DB 层完成，只加载一页数据。
        慢速路径（有 health/dedup）：DB 做基础过滤减少数据集，Python 做复杂筛选。
        摘要统计始终走 DB 聚合（不依赖列表查询）。
        """
        page = max(page, 1)
        size = min(max(size, 1), 100)
        keyword = keyword.strip().lower()
        status = status.strip().lower()
        file_type = file_type.strip().lower()
        health = health.strip().lower()
        dedup = dedup.strip().lower()
        sort_by = self._normalize_sort_by(sort_by)
        reverse = sort_order.strip().lower() != "asc"

        now = await get_now()

        # 1. 摘要统计：始终走 DB 聚合（与列表筛选无关）
        summary = await self._build_list_summary(now)

        # 2. 判断是否需要 Python 层复杂筛选
        needs_complex_filter = (
            (health and health != "all") or (dedup and dedup != "all")
        )

        if not needs_complex_filter:
            # === 快速路径：全部下推 DB ===
            query = FileCodes.all()
            query = self._apply_list_db_filters(query, keyword, status, file_type, now)
            total = await query.count()
            # DB 排序 + 分页
            sort_prefix = "-" if reverse else ""
            db_sort = self._map_sort_field(sort_by)
            offset = (page - 1) * size
            files = await query.order_by(f"{sort_prefix}{db_sort}").offset(offset).limit(size)
            # 构建页面条目
            items = [await self._build_admin_file_item(fc, now=now) for fc in files]
            # 秒传标记：只对当前页的文件查询 hash 计数
            await self._mark_dedup_for_page(items, files)
            return items, total, summary
        else:
            # === 慢速路径：DB 基础过滤 + Python 复杂筛选 ===
            query = FileCodes.all()
            query = self._apply_list_db_filters(query, keyword, status, file_type, now)
            filtered_files = await query.all()

            # 秒传分组：统计相同 file_hash+size 的出现次数
            hash_count: dict = {}
            for fc in filtered_files:
                if fc.file_hash:
                    key = (fc.file_hash, fc.size)
                    hash_count[key] = hash_count.get(key, 0) + 1

            enriched_files = []
            for file_code in filtered_files:
                item = await self._build_admin_file_item(file_code, now=now)
                if file_code.file_hash:
                    item["isDedup"] = hash_count.get((file_code.file_hash, file_code.size), 0) > 1
                else:
                    item["isDedup"] = False
                # 只应用 health/dedup 筛选（keyword/status/file_type 已在 DB 层处理）
                if not self._match_admin_file(item, "", "", "", health, dedup):
                    continue
                enriched_files.append(item)

            enriched_files.sort(
                key=lambda item: self._get_sort_value(item, sort_by),
                reverse=reverse,
            )
            offset = (page - 1) * size
            return enriched_files[offset : offset + size], len(enriched_files), summary

    def _apply_list_db_filters(self, query, keyword: str, status: str, file_type: str, now):
        """将基础筛选条件下推到数据库层（BUG-005）"""
        from tortoise.expressions import Q

        if keyword:
            query = query.filter(
                Q(code__icontains=keyword) | Q(prefix__icontains=keyword) | Q(text__icontains=keyword)
            )
        if status == "active":
            query = query.filter(
                Q(expired_at__isnull=True) | Q(expired_at__gt=now, expired_count__lt=0)
            ).exclude(expired_count=0)
        elif status == "expired":
            query = query.filter(
                Q(expired_count=0) | Q(expired_at__not_isnull=True, expired_at__lt=now)
            )
        if file_type == "text":
            query = query.filter(text__not_isnull=True)
        elif file_type == "file":
            query = query.filter(text__isnull=True)
        elif file_type == "chunked":
            query = query.filter(is_chunked=True)
        return query

    def _map_sort_field(self, sort_by: str) -> str:
        """将排序字段映射到数据库列名（BUG-005）"""
        mapping = {
            "created_at": "created_at",
            "createdat": "created_at",
            "expired_at": "expired_at",
            "expiredat": "expired_at",
            "name": "prefix",
            "size": "size",
            "used_count": "used_count",
            "usedcount": "used_count",
            "code": "code",
        }
        return mapping.get(sort_by, "created_at")

    async def _build_list_summary(self, now) -> dict:
        """用 DB 聚合查询构建文件列表摘要统计（BUG-005，复用 BUG-004 模式）"""
        from tortoise.functions import Sum

        async def _sum(field: str) -> int:
            result = await FileCodes.all().annotate(total=Sum(field)).values("total")
            return (result[0]["total"] or 0) if result else 0

        total_files = await FileCodes.all().count()
        text_count = await FileCodes.filter(text__not_isnull=True).count()
        chunked_count = await FileCodes.filter(is_chunked=True).count()
        storage_used = await _sum("size")
        used_count = await _sum("used_count")

        # 健康度统计复用 BUG-004 的方法
        health_counts = await self.build_dashboard_health_counts(now)

        return {
            "totalFiles": total_files,
            "activeCount": total_files - health_counts.get("expiredCount", 0),
            "expiredCount": health_counts.get("expiredCount", 0),
            "textCount": text_count,
            "fileCount": total_files - text_count,
            "chunkedCount": chunked_count,
            **self._empty_health_summary(),
            **{k: v for k, v in health_counts.items() if k in self._empty_health_summary()},
            "storageUsed": storage_used,
            "usedCount": used_count,
        }

    async def _mark_dedup_for_page(self, items: list[dict], files: list) -> None:
        """只对当前页的文件标记秒传状态（BUG-005，避免全量 hash_count）"""
        # 收集当前页有 hash 的文件的 (hash, size) 对
        hash_pairs = set()
        for fc in files:
            if fc.file_hash:
                hash_pairs.add((fc.file_hash, fc.size))

        if not hash_pairs:
            for item in items:
                item["isDedup"] = False
            return

        # 一次性查询这些 hash+size 组合在全库中的出现次数
        from tortoise.functions import Count
        from tortoise.expressions import Q

        hash_count: dict = {}
        for file_hash, file_size in hash_pairs:
            count = await FileCodes.filter(file_hash=file_hash, size=file_size).count()
            hash_count[(file_hash, file_size)] = count

        # 标记
        for i, fc in enumerate(files):
            if fc.file_hash:
                items[i]["isDedup"] = hash_count.get((fc.file_hash, fc.size), 0) > 1
            else:
                items[i]["isDedup"] = False

    def _empty_health_summary(self) -> dict[str, int]:
        return {
            "healthAttentionCount": 0,
            "healthDangerCount": 0,
            "healthWarningCount": 0,
            "expiringSoonCount": 0,
            "storageIssueCount": 0,
            "neverRetrievedCount": 0,
            "healthyCount": 0,
            "permanentCount": 0,
        }

    def _accumulate_health_summary(self, summary: dict[str, Any], item: dict[str, Any]) -> None:
        status_insights = item.get("statusInsights") or {}
        reasons = status_insights.get("reasons") or []
        severity = status_insights.get("severity")
        state = status_insights.get("state")

        if severity in {"danger", "warning"}:
            summary["healthAttentionCount"] += 1
        if severity == "danger":
            summary["healthDangerCount"] += 1
        if severity == "warning":
            summary["healthWarningCount"] += 1
        if severity == "success":
            summary["healthyCount"] += 1
        if state == "permanent":
            summary["permanentCount"] += 1
        if "expires_soon" in reasons:
            summary["expiringSoonCount"] += 1
        if "storage_metadata_incomplete" in reasons:
            summary["storageIssueCount"] += 1
        if "never_retrieved" in reasons:
            summary["neverRetrievedCount"] += 1

    async def build_file_health_summary(
        self, file_codes: list[FileCodes], now: Optional[datetime] = None
    ) -> dict[str, int]:
        if now is None:
            now = await get_now()
        summary = self._empty_health_summary()
        for file_code in file_codes:
            item = await self._build_admin_file_item(file_code, now=now)
            self._accumulate_health_summary(summary, item)
        return summary

    async def build_dashboard_health_counts(
        self, now: Optional[datetime] = None
    ) -> dict[str, int]:
        """用数据库聚合查询计算仪表盘健康度统计（BUG-004 性能优化）。

        统计口径与 build_file_health_summary 保持一致，但避免将全部文件记录
        加载进内存逐个处理，文件量大时显著降低内存与 CPU 开销。
        """
        from tortoise.expressions import Q

        if now is None:
            now = await get_now()
        now_plus_day = now + timedelta(seconds=86400)

        # is_expired（与 FileCodes.is_expired 逻辑一致）
        expired_q = Q(expired_at__not_isnull=True) & (
            Q(expired_count__lt=0, expired_at__lt=now) | Q(expired_count=0)
        )
        # 下载次数耗尽（expired_count == 0）
        limit_exhausted_q = Q(expired_count=0)
        # 无法下载：非文本且无文件路径与 UUID（兼容空字符串）
        no_path_q = Q(file_path__isnull=True) | Q(file_path="")
        no_uuid_q = Q(uuid_file_name__isnull=True) | Q(uuid_file_name="")
        not_can_download_q = Q(text__isnull=True) & no_path_q & no_uuid_q
        # danger：已过期 / 次数耗尽 / 无法下载
        danger_q = expired_q | limit_exhausted_q | not_can_download_q
        # expires_soon：未来 24 小时内过期
        expires_soon_q = Q(expired_at__gt=now) & Q(expired_at__lte=now_plus_day)
        # warning：即将过期且未达 danger
        warning_q = expires_soon_q & ~danger_q
        # is_permanent：无过期时间且次数不限
        is_permanent_q = Q(expired_at__isnull=True) & Q(expired_count__lt=0)
        # permanent 状态：永久且非 danger。
        # 注意：永久文件 expired_at 为 NULL，不可能 expires_soon（需 expired_at 非空），
        # 故必非 warning；此处不叠加 ~warning_q，避免 NULL 三值逻辑导致漏计。
        permanent_q = is_permanent_q & ~danger_q
        # never_retrieved：从未被取件
        never_retrieved_q = Q(used_count=0)

        total = await FileCodes.all().count()
        danger_count = await FileCodes.filter(danger_q).count()
        warning_count = await FileCodes.filter(warning_q).count()

        return {
            "healthAttentionCount": danger_count + warning_count,
            "healthDangerCount": danger_count,
            "healthWarningCount": warning_count,
            "expiringSoonCount": await FileCodes.filter(expires_soon_q).count(),
            "storageIssueCount": await FileCodes.filter(not_can_download_q).count(),
            "neverRetrievedCount": await FileCodes.filter(never_retrieved_q).count(),
            "healthyCount": total - danger_count - warning_count,
            "permanentCount": await FileCodes.filter(permanent_q).count(),
        }

    async def build_top_suffixes(self, limit: int = 8) -> list[dict[str, Any]]:
        """用数据库分组统计文件后缀分布（BUG-004 性能优化）。

        口径与原有 Counter 一致：文本分享计为 "Text"，无后缀文件计为 "file"。
        """
        from tortoise.expressions import Q
        from tortoise.functions import Count

        counter: dict[str, int] = {}
        text_count = await FileCodes.filter(text__not_isnull=True).count()
        if text_count:
            counter["Text"] = text_count

        non_text = FileCodes.filter(text__isnull=True)
        empty_suffix_q = Q(suffix="") | Q(suffix__isnull=True)
        no_suffix_count = await non_text.filter(empty_suffix_q).count()
        if no_suffix_count:
            counter["file"] = no_suffix_count

        rows = (
            await non_text.exclude(empty_suffix_q)
            .annotate(cnt=Count("id"))
            .group_by("suffix")
            .values("suffix", "cnt")
        )
        for row in rows:
            counter[row["suffix"]] = row["cnt"]

        top = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
        return [{"suffix": suffix, "count": count} for suffix, count in top]

    async def _build_admin_file_item(
        self, file_code: FileCodes, now: Optional[datetime] = None
    ) -> dict[str, Any]:
        if now is None:
            now = await get_now()
        is_text = file_code.text is not None
        is_expired = await file_code.is_expired()
        name = f"{file_code.prefix}{file_code.suffix}"
        has_download_limit = file_code.expired_count >= 0
        is_permanent = file_code.expired_at is None and file_code.expired_count < 0
        can_download = is_text or bool(file_code.file_path or file_code.uuid_file_name)
        remaining_downloads = (
            max(file_code.expired_count, 0) if file_code.expired_count >= 0 else None
        )
        data = {
            "id": file_code.id,
            "code": file_code.code,
            "prefix": file_code.prefix,
            "suffix": file_code.suffix,
            "uuid_file_name": file_code.uuid_file_name,
            "file_path": file_code.file_path,
            "size": file_code.size or 0,
            "text": file_code.text,
            "expired_at": file_code.expired_at,
            "expired_count": file_code.expired_count,
            "used_count": file_code.used_count,
            "created_at": file_code.created_at,
            "file_hash": file_code.file_hash,
            "is_chunked": file_code.is_chunked,
            "upload_id": file_code.upload_id,
        }
        data.update(
            {
                "name": name,
                "type": "text" if is_text else "file",
                "status": "expired" if is_expired else "active",
                "isText": is_text,
                "is_text": is_text,
                "isExpired": is_expired,
                "is_expired": is_expired,
                "isChunked": file_code.is_chunked,
                "is_chunked": file_code.is_chunked,
                "remainingDownloads": remaining_downloads,
                "remaining_downloads": remaining_downloads,
                "usedCount": file_code.used_count,
                "used_count": file_code.used_count,
                "createdAt": file_code.created_at,
                "created_at": file_code.created_at,
                "expiredAt": file_code.expired_at,
                "expired_at": file_code.expired_at,
                "fileHash": file_code.file_hash,
                "file_hash": file_code.file_hash,
            }
        )
        status_insights = self._build_file_status_insights(
            file_code=file_code,
            detail=data,
            now=now,
            has_download_limit=has_download_limit,
            is_permanent=is_permanent,
            can_download=can_download,
        )
        data.update(
            {
                "statusInsights": status_insights,
                "status_insights": status_insights,
            }
        )
        return data

    async def get_file_detail(self, file_id: int):
        file_code = await FileCodes.filter(id=file_id).first()
        if not file_code:
            raise HTTPException(status_code=404, detail="文件不存在")

        now = await get_now()
        detail = await self._build_admin_file_item(file_code, now=now)
        is_text = file_code.text is not None
        has_download_limit = file_code.expired_count >= 0
        is_permanent = file_code.expired_at is None and file_code.expired_count < 0
        text_length = len(file_code.text) if file_code.text else 0
        can_download = is_text or bool(file_code.file_path or file_code.uuid_file_name)
        status_insights = self._build_file_status_insights(
            file_code=file_code,
            detail=detail,
            now=now,
            has_download_limit=has_download_limit,
            is_permanent=is_permanent,
            can_download=can_download,
        )
        timeline = self._build_file_timeline(
            file_code=file_code,
            detail=detail,
            now=now,
            has_download_limit=has_download_limit,
            is_permanent=is_permanent,
            is_text=is_text,
        )

        detail.update(
            {
                "filename": detail["name"],
                "displayName": detail["name"],
                "display_name": detail["name"],
                "isPermanent": is_permanent,
                "is_permanent": is_permanent,
                "hasDownloadLimit": has_download_limit,
                "has_download_limit": has_download_limit,
                "hasExpirationTime": file_code.expired_at is not None,
                "has_expiration_time": file_code.expired_at is not None,
                "textLength": text_length,
                "text_length": text_length,
                "canPreviewText": is_text,
                "can_preview_text": is_text,
                "canDownload": can_download,
                "can_download": can_download,
                "storageBackend": settings.file_storage,
                "storage_backend": settings.file_storage,
                "filePath": file_code.file_path,
                "file_path": file_code.file_path,
                "uuidFileName": file_code.uuid_file_name,
                "uuid_file_name": file_code.uuid_file_name,
                "uploadId": file_code.upload_id,
                "upload_id": file_code.upload_id,
                "policy": {
                    "expiredAt": file_code.expired_at,
                    "expired_at": file_code.expired_at,
                    "expiredCount": file_code.expired_count,
                    "expired_count": file_code.expired_count,
                    "remainingDownloads": detail["remainingDownloads"],
                    "remaining_downloads": detail["remaining_downloads"],
                    "isExpired": detail["isExpired"],
                    "is_expired": detail["is_expired"],
                    "isPermanent": is_permanent,
                    "is_permanent": is_permanent,
                },
                "storage": {
                    "backend": settings.file_storage,
                    "filePath": file_code.file_path,
                    "file_path": file_code.file_path,
                    "uuidFileName": file_code.uuid_file_name,
                    "uuid_file_name": file_code.uuid_file_name,
                    "fileHash": file_code.file_hash,
                    "file_hash": file_code.file_hash,
                    "isChunked": file_code.is_chunked,
                    "is_chunked": file_code.is_chunked,
                    "uploadId": file_code.upload_id,
                    "upload_id": file_code.upload_id,
                },
                "statusInsights": status_insights,
                "status_insights": status_insights,
                "timeline": timeline,
            }
        )
        metadata = await self.get_file_metadata(file_id)
        detail.update(
            {
                "metadata": metadata,
                "meta": metadata,
                "note": metadata["note"],
                "tags": metadata["tags"],
                "metadataUpdatedAt": metadata["updatedAt"],
                "metadata_updated_at": metadata["updated_at"],
            }
        )
        # 审计日志：该文件的上传/下载/取件记录
        try:
            from apps.base.models import AuditLog

            audit_logs = await AuditLog.filter(file_id=file_id).order_by("-created_at").limit(50)
            audit_data = [
                {
                    "id": log.id,
                    "event_type": log.event_type,
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
                for log in audit_logs
            ]
            detail.update(
                {
                    "auditLogs": audit_data,
                    "audit_logs": audit_data,
                    "downloadCount": sum(1 for log in audit_data if log["event_type"] == "download"),
                    "download_count": sum(1 for log in audit_data if log["event_type"] == "download"),
                }
            )
        except Exception:
            detail.update({"auditLogs": [], "audit_logs": [], "downloadCount": 0, "download_count": 0})
        return detail

    def _normalize_metadata_note(self, note: Optional[str]) -> str:
        if note is None:
            return ""
        return str(note).strip()[: self.MAX_METADATA_NOTE_LENGTH]

    def _normalize_metadata_tags(self, tags: Any) -> list[str]:
        if not tags:
            return []
        if isinstance(tags, str):
            tags = [tags]
        elif not isinstance(tags, list):
            return []

        normalized_tags = []
        seen_tags = set()
        for raw_tag in tags:
            tag = str(raw_tag).strip()
            if not tag:
                continue
            tag = tag[: self.MAX_METADATA_TAG_LENGTH]
            dedupe_key = tag.lower()
            if dedupe_key in seen_tags:
                continue
            seen_tags.add(dedupe_key)
            normalized_tags.append(tag)
            if len(normalized_tags) >= self.MAX_METADATA_TAGS:
                break
        return normalized_tags

    def _normalize_file_metadata(self, metadata: Any) -> dict[str, Any]:
        if not isinstance(metadata, dict):
            metadata = {}

        updated_at = metadata.get("updatedAt") or metadata.get("updated_at")
        return {
            "note": self._normalize_metadata_note(metadata.get("note")),
            "tags": self._normalize_metadata_tags(metadata.get("tags")),
            "updatedAt": updated_at,
            "updated_at": updated_at,
        }

    async def list_admin_activities(
        self,
        limit: int = 8,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> dict[str, Any]:
        try:
            normalized_limit = int(limit or 8)
        except (TypeError, ValueError):
            normalized_limit = 8
        limit = min(max(normalized_limit, 1), self.MAX_ADMIN_ACTIVITIES)
        activities = await self._get_admin_activities()
        normalized_action = self._normalize_admin_activity_text(action).lower()
        normalized_target_type = self._normalize_admin_activity_text(target_type).lower()
        normalized_keyword = self._normalize_admin_activity_text(keyword).lower()
        filtered_activities = self._filter_admin_activities(
            activities,
            action=normalized_action,
            target_type=normalized_target_type,
            keyword=normalized_keyword,
        )
        visible_activities = filtered_activities[:limit]
        action_options = self._build_admin_activity_options(activities, "action")
        target_type_options = self._build_admin_activity_options(activities, "targetType")
        return {
            "activities": visible_activities,
            "items": visible_activities,
            "total": len(filtered_activities),
            "storedTotal": len(activities),
            "stored_total": len(activities),
            "limit": limit,
            "filters": {
                "action": normalized_action,
                "targetType": normalized_target_type,
                "target_type": normalized_target_type,
                "keyword": normalized_keyword,
            },
            "actionOptions": action_options,
            "action_options": action_options,
            "targetTypeOptions": target_type_options,
            "target_type_options": target_type_options,
        }

    async def record_admin_activity(
        self,
        action: str,
        target_type: str,
        target_id: Optional[Any] = None,
        target_name: str = "",
        count: int = 1,
        meta: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        try:
            now = await get_now()
            created_at = now.isoformat()
            activity = self._normalize_admin_activity(
                {
                    "id": self._build_admin_activity_id(
                        action=action,
                        target_type=target_type,
                        target_id=target_id,
                        target_name=target_name,
                        timestamp=now,
                    ),
                    "action": action,
                    "targetType": target_type,
                    "target_type": target_type,
                    "targetId": target_id,
                    "target_id": target_id,
                    "targetName": target_name,
                    "target_name": target_name,
                    "count": count,
                    "meta": meta or {},
                    "createdAt": created_at,
                    "created_at": created_at,
                }
            )
            if not activity:
                return None

            activities = await self._get_admin_activities()
            next_activities = [
                activity,
                *[item for item in activities if item["id"] != activity["id"]],
            ][: self.MAX_ADMIN_ACTIVITIES]
            await self._save_admin_activities(next_activities)
            return activity
        except Exception:
            return None

    async def _get_admin_activities(self) -> list[dict[str, Any]]:
        record = await KeyValue.filter(key=self.ADMIN_ACTIVITY_KEY).first()
        raw_activities = record.value if record else []
        if isinstance(raw_activities, dict):
            raw_activities = (
                raw_activities.get("activities") or raw_activities.get("items") or []
            )
        if not isinstance(raw_activities, list):
            return []

        activities = []
        seen_ids = set()
        for raw_activity in raw_activities:
            activity = self._normalize_admin_activity(raw_activity)
            if not activity or activity["id"] in seen_ids:
                continue
            seen_ids.add(activity["id"])
            activities.append(activity)
            if len(activities) >= self.MAX_ADMIN_ACTIVITIES:
                break

        activities.sort(key=lambda item: item.get("createdAt") or "", reverse=True)
        return activities

    async def _save_admin_activities(self, activities: list[dict[str, Any]]) -> None:
        await KeyValue.update_or_create(
            key=self.ADMIN_ACTIVITY_KEY,
            defaults={"value": {"activities": activities}},
        )

    def _normalize_admin_activity(self, activity: Any) -> Optional[dict[str, Any]]:
        if not isinstance(activity, dict):
            return None

        action = self._normalize_admin_activity_text(activity.get("action"))
        target_type = self._normalize_admin_activity_text(
            activity.get("targetType") or activity.get("target_type") or "system"
        )
        if not action:
            return None

        target_name = self._normalize_admin_activity_text(
            activity.get("targetName") or activity.get("target_name")
        )
        created_at = activity.get("createdAt") or activity.get("created_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        created_at = str(created_at or "")
        if not created_at:
            return None

        target_id = activity.get("targetId")
        if target_id is None:
            target_id = activity.get("target_id")

        count = activity.get("count", 1)
        try:
            count = max(int(count), 1)
        except (TypeError, ValueError):
            count = 1

        meta = activity.get("meta")
        if not isinstance(meta, dict):
            meta = {}

        activity_id = self._normalize_admin_activity_text(activity.get("id"))
        if not activity_id:
            activity_id = self._build_admin_activity_id(
                action=action,
                target_type=target_type,
                target_id=target_id,
                target_name=target_name,
                timestamp=None,
                seed=created_at,
            )

        return {
            "id": activity_id,
            "action": action,
            "targetType": target_type,
            "target_type": target_type,
            "targetId": target_id,
            "target_id": target_id,
            "targetName": target_name,
            "target_name": target_name,
            "count": count,
            "meta": meta,
            "createdAt": created_at,
            "created_at": created_at,
        }

    def _normalize_admin_activity_text(self, value: Any) -> str:
        return str(value or "").strip()[: self.MAX_ADMIN_ACTIVITY_TEXT_LENGTH]

    def _filter_admin_activities(
        self,
        activities: list[dict[str, Any]],
        action: str,
        target_type: str,
        keyword: str,
    ) -> list[dict[str, Any]]:
        filtered_activities = []
        for activity in activities:
            if action and str(activity.get("action") or "").lower() != action:
                continue
            if target_type and str(activity.get("targetType") or "").lower() != target_type:
                continue
            if keyword and not self._activity_matches_keyword(activity, keyword):
                continue
            filtered_activities.append(activity)
        return filtered_activities

    def _activity_matches_keyword(self, activity: dict[str, Any], keyword: str) -> bool:
        searchable_values = [
            activity.get("action"),
            activity.get("targetType"),
            activity.get("target_type"),
            activity.get("targetId"),
            activity.get("target_id"),
            activity.get("targetName"),
            activity.get("target_name"),
        ]
        meta = activity.get("meta")
        if isinstance(meta, dict):
            searchable_values.extend(meta.values())

        return any(keyword in str(value or "").lower() for value in searchable_values)

    def _build_admin_activity_options(
        self,
        activities: list[dict[str, Any]],
        field: str,
    ) -> list[dict[str, Any]]:
        counters: dict[str, dict[str, Any]] = {}
        for activity in activities:
            raw_value = self._normalize_admin_activity_text(activity.get(field))
            if not raw_value:
                continue
            value = raw_value.lower()
            if value not in counters:
                counters[value] = {"label": raw_value, "count": 0}
            counters[value]["count"] += 1

        return [
            {
                "value": value,
                "label": option["label"],
                "count": option["count"],
            }
            for value, option in sorted(
                counters.items(),
                key=lambda item: (-item[1]["count"], item[0]),
            )
        ]

    def _build_admin_activity_id(
        self,
        action: str,
        target_type: str,
        target_id: Optional[Any],
        target_name: str,
        timestamp: Optional[datetime],
        seed: Optional[str] = None,
    ) -> str:
        timestamp_seed = (
            str(int(timestamp.timestamp() * 1000)) if timestamp else str(seed or "activity")
        )
        digest = hashlib.sha1(
            f"{timestamp_seed}:{action}:{target_type}:{target_id}:{target_name}".encode("utf-8")
        ).hexdigest()[:10]
        return f"act_{timestamp_seed}_{digest}"

    def _build_file_activity_name(self, file_code: FileCodes) -> str:
        return (file_code.prefix + file_code.suffix) or file_code.code

    async def _get_file_view_presets(self) -> list[dict[str, Any]]:
        record = await KeyValue.filter(key=self.FILE_VIEW_PRESETS_KEY).first()
        raw_presets = record.value if record else []
        if isinstance(raw_presets, dict):
            raw_presets = raw_presets.get("presets") or raw_presets.get("items") or []
        if not isinstance(raw_presets, list):
            return []

        presets = []
        seen_ids = set()
        for raw_preset in raw_presets:
            try:
                preset = self._normalize_file_view_preset(raw_preset)
            except HTTPException:
                continue
            if not preset or preset["id"] in seen_ids:
                continue
            seen_ids.add(preset["id"])
            presets.append(preset)
            if len(presets) >= self.MAX_VIEW_PRESETS:
                break
        return presets

    async def _save_file_view_presets(self, presets: list[dict[str, Any]]) -> None:
        await KeyValue.update_or_create(
            key=self.FILE_VIEW_PRESETS_KEY,
            defaults={"value": {"presets": presets}},
        )

    def _normalize_file_view_preset(self, preset: Any) -> Optional[dict[str, Any]]:
        if not isinstance(preset, dict):
            return None

        preset_id = str(preset.get("id") or "").strip()
        raw_name = str(preset.get("name") or "").strip()
        if not raw_name:
            return None
        name = self._normalize_file_view_preset_name(raw_name)
        if not preset_id:
            preset_id = self._build_file_view_preset_id(name)

        filters = preset.get("filters") or preset.get("params") or {}
        normalized_filters = self._normalize_file_view_preset_filters(filters)
        created_at = preset.get("createdAt") or preset.get("created_at")
        updated_at = preset.get("updatedAt") or preset.get("updated_at")

        return {
            "id": preset_id,
            "name": name,
            "filters": normalized_filters,
            "params": normalized_filters,
            "createdAt": created_at,
            "created_at": created_at,
            "updatedAt": updated_at,
            "updated_at": updated_at,
        }

    def _normalize_file_view_preset_name(self, name: Any) -> str:
        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise HTTPException(status_code=400, detail="请输入视图名称")
        return normalized_name[: self.MAX_VIEW_PRESET_NAME_LENGTH]

    def _normalize_file_view_preset_filters(self, filters: Any) -> dict[str, Any]:
        if not isinstance(filters, dict):
            filters = {}

        sort_by = str(filters.get("sortBy") or filters.get("sort_by") or "created_at")
        sort_by = sort_by.replace("-", "_").strip().lower()
        if sort_by not in self.VIEW_PRESET_SORT_FIELDS:
            sort_by = "created_at"

        sort_order = str(filters.get("sortOrder") or filters.get("sort_order") or "desc")
        sort_order = sort_order.strip().lower()
        if sort_order not in {"asc", "desc"}:
            sort_order = "desc"

        size = filters.get("size", 10)
        try:
            size = int(size)
        except (TypeError, ValueError):
            size = 10

        return {
            "keyword": str(filters.get("keyword") or "").strip()[
                : self.MAX_VIEW_PRESET_KEYWORD_LENGTH
            ],
            "status": self._normalize_file_view_preset_choice(
                filters.get("status"), self.VIEW_PRESET_STATUS_VALUES
            ),
            "type": self._normalize_file_view_preset_choice(
                filters.get("type"), self.VIEW_PRESET_TYPE_VALUES
            ),
            "health": self._normalize_file_view_preset_choice(
                filters.get("health"), self.VIEW_PRESET_HEALTH_VALUES
            ),
            "sortBy": sort_by,
            "sortOrder": sort_order,
            "size": min(max(size, 1), 100),
        }

    def _normalize_file_view_preset_choice(self, value: Any, allowed_values: set[str]) -> str:
        normalized_value = str(value or "all").strip().lower()
        if normalized_value not in allowed_values:
            return "all"
        return normalized_value

    def _build_file_view_preset_id(
        self, name: str, timestamp: Optional[datetime] = None
    ) -> str:
        seed = int(timestamp.timestamp() * 1000) if timestamp else "saved"
        digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
        return f"view_{seed}_{digest}"

    def _build_file_status_insights(
        self,
        file_code: FileCodes,
        detail: dict[str, Any],
        now: datetime,
        has_download_limit: bool,
        is_permanent: bool,
        can_download: bool,
    ) -> dict[str, Any]:
        remaining_downloads = detail["remainingDownloads"]
        seconds_until_expiration = self._seconds_between(now, file_code.expired_at)
        age_seconds = self._seconds_between(file_code.created_at, now)
        reasons = []

        if detail["isExpired"]:
            reasons.append("expired")
        if has_download_limit and remaining_downloads == 0:
            reasons.append("download_limit_exhausted")
        if seconds_until_expiration is not None and 0 < seconds_until_expiration <= 86400:
            reasons.append("expires_soon")
        if file_code.used_count == 0:
            reasons.append("never_retrieved")
        if not can_download:
            reasons.append("storage_metadata_incomplete")
        if file_code.is_chunked:
            reasons.append("chunked_upload")

        severity = "success"
        state = "available"
        next_action = "monitor"
        if detail["isExpired"] or (has_download_limit and remaining_downloads == 0):
            severity = "danger"
            state = "expired"
            next_action = "extend_or_delete"
        elif not can_download:
            severity = "danger"
            state = "storage_incomplete"
            next_action = "inspect_storage"
        elif "expires_soon" in reasons:
            severity = "warning"
            state = "expiring_soon"
            next_action = "extend_expiration"
        elif is_permanent:
            state = "permanent"
            next_action = "monitor"

        return {
            "severity": severity,
            "state": state,
            "nextAction": next_action,
            "next_action": next_action,
            "reasons": reasons,
            "metrics": {
                "ageSeconds": max(age_seconds or 0, 0),
                "age_seconds": max(age_seconds or 0, 0),
                "secondsUntilExpiration": seconds_until_expiration,
                "seconds_until_expiration": seconds_until_expiration,
                "remainingDownloads": remaining_downloads,
                "remaining_downloads": remaining_downloads,
                "usedCount": file_code.used_count,
                "used_count": file_code.used_count,
            },
        }

    def _build_file_timeline(
        self,
        file_code: FileCodes,
        detail: dict[str, Any],
        now: datetime,
        has_download_limit: bool,
        is_permanent: bool,
        is_text: bool,
    ) -> list[dict[str, Any]]:
        remaining_downloads = detail["remainingDownloads"]
        seconds_until_expiration = self._seconds_between(now, file_code.expired_at)
        timeline = [
            {
                "key": "created",
                "status": "done",
                "severity": "success",
                "timestamp": file_code.created_at,
            },
            {
                "key": "content_ready",
                "status": "done",
                "severity": "success",
                "timestamp": file_code.created_at,
                "detail": "text" if is_text else "file",
            },
        ]

        if file_code.upload_id:
            timeline.append(
                {
                    "key": "upload_session",
                    "status": "done",
                    "severity": "info",
                    "timestamp": file_code.created_at,
                    "detail": file_code.upload_id,
                }
            )

        if is_permanent:
            timeline.append(
                {
                    "key": "expiration_policy",
                    "status": "unlimited",
                    "severity": "success",
                    "timestamp": None,
                }
            )
        elif file_code.expired_at is not None:
            expired = seconds_until_expiration is not None and seconds_until_expiration <= 0
            timeline.append(
                {
                    "key": "expiration_policy",
                    "status": "expired" if expired else "pending",
                    "severity": "danger" if expired else "warning",
                    "timestamp": file_code.expired_at,
                    "value": seconds_until_expiration,
                }
            )

        if has_download_limit:
            exhausted = remaining_downloads == 0
            timeline.append(
                {
                    "key": "download_limit",
                    "status": "exhausted" if exhausted else "active",
                    "severity": "danger" if exhausted else "info",
                    "timestamp": None,
                    "value": remaining_downloads,
                }
            )
        else:
            timeline.append(
                {
                    "key": "download_limit",
                    "status": "unlimited",
                    "severity": "success",
                    "timestamp": None,
                    "value": None,
                }
            )

        timeline.append(
            {
                "key": "retrieved",
                "status": "done" if file_code.used_count > 0 else "pending",
                "severity": "success" if file_code.used_count > 0 else "neutral",
                "timestamp": None,
                "value": file_code.used_count,
            }
        )
        return timeline

    def _seconds_between(
        self, start: Optional[datetime], end: Optional[datetime]
    ) -> Optional[int]:
        if start is None or end is None:
            return None
        if start.tzinfo is None and end.tzinfo is not None:
            end = end.replace(tzinfo=None)
        elif start.tzinfo is not None and end.tzinfo is None:
            start = start.replace(tzinfo=None)
        return int((end - start).total_seconds())

    def _build_policy_action_update(
        self,
        file_code: FileCodes,
        action: str,
        now: datetime,
        download_limit: Optional[int],
    ) -> dict[str, Any]:
        if action == "extend_24h":
            return {"expired_at": self._extended_expiration(file_code.expired_at, now, hours=24)}
        if action == "extend_7d":
            return {"expired_at": self._extended_expiration(file_code.expired_at, now, days=7)}
        if action == "make_permanent":
            return {"expired_at": None, "expired_count": -1}
        if action == "reset_download_limit":
            next_limit = download_limit if download_limit is not None else 5
            if next_limit < 1:
                raise HTTPException(status_code=400, detail="取件次数必须大于 0")
            return {"expired_count": next_limit}

        raise HTTPException(status_code=400, detail="不支持的策略动作")

    def _extended_expiration(
        self,
        expired_at: Optional[datetime],
        now: datetime,
        **duration: int,
    ) -> datetime:
        base_time = now
        if expired_at is not None:
            comparable_expired_at = self._align_datetime(expired_at, now)
            if comparable_expired_at > now:
                base_time = comparable_expired_at
        return base_time + timedelta(**duration)

    def _align_datetime(self, value: datetime, reference: datetime) -> datetime:
        if value.tzinfo is None and reference.tzinfo is not None:
            return value.replace(tzinfo=reference.tzinfo)
        if value.tzinfo is not None and reference.tzinfo is None:
            return value.replace(tzinfo=None)
        return value

    def _match_admin_file(
        self,
        item: dict[str, Any],
        keyword: str,
        status: str,
        file_type: str,
        health: str,
        dedup: str = "",
    ) -> bool:
        if status == "active" and item["isExpired"]:
            return False
        if status == "expired" and not item["isExpired"]:
            return False
        if file_type == "text" and not item["isText"]:
            return False
        if file_type == "file" and item["isText"]:
            return False
        if file_type == "chunked" and not item["isChunked"]:
            return False
        if dedup == "dedup" and not item.get("isDedup"):
            return False
        if dedup == "unique" and item.get("isDedup"):
            return False
        if not self._match_admin_file_health(item, health):
            return False
        if not keyword:
            return True

        search_values = [
            item.get("code"),
            item.get("name"),
            item.get("prefix"),
            item.get("suffix"),
            item.get("fileHash"),
            item.get("text"),
        ]
        return any(keyword in str(value).lower() for value in search_values if value)

    def _match_admin_file_health(self, item: dict[str, Any], health: str) -> bool:
        if not health or health == "all":
            return True

        status_insights = item.get("statusInsights") or {}
        severity = status_insights.get("severity")
        state = status_insights.get("state")
        reasons = set(status_insights.get("reasons") or [])

        if health == "attention":
            return severity in {"danger", "warning"}
        if health == "danger":
            return severity == "danger"
        if health == "warning":
            return severity == "warning"
        if health == "expired":
            return state == "expired" or item.get("isExpired") is True
        if health == "expiring_soon":
            return "expires_soon" in reasons
        if health == "storage_issue":
            return state == "storage_incomplete" or "storage_metadata_incomplete" in reasons
        if health == "never_retrieved":
            return "never_retrieved" in reasons
        if health == "healthy":
            return severity == "success"
        if health == "permanent":
            return state == "permanent"

        return True

    def _normalize_sort_by(self, sort_by: str) -> str:
        normalized = sort_by.replace("-", "_").strip().lower()
        if normalized not in self.SORT_FIELDS:
            return "created_at"
        return normalized

    def _get_sort_value(self, item: dict[str, Any], sort_by: str):
        def date_value(value: Any) -> float:
            if value is None:
                return 0
            if isinstance(value, datetime):
                return value.timestamp()
            return 0

        sort_map = {
            "created_at": date_value(item.get("createdAt")),
            "createdat": date_value(item.get("createdAt")),
            "expired_at": date_value(item.get("expiredAt")),
            "expiredat": date_value(item.get("expiredAt")),
            "name": item.get("name") or "",
            "size": item.get("size") or 0,
            "used_count": item.get("usedCount") or 0,
            "usedcount": item.get("usedCount") or 0,
            "code": item.get("code") or "",
        }
        return sort_map.get(sort_by)

    async def download_file(self, file_id: int):
        file_code = await FileCodes.filter(id=file_id).first()
        if not file_code:
            raise HTTPException(status_code=404, detail="文件不存在")
        if file_code.text:
            return APIResponse(detail=file_code.text)
        else:
            return await self.file_storage.get_file_response(file_code)

    async def preview_file(self, file_id: int, max_chars: int = 4000):
        max_chars = min(max(max_chars, 1), 20000)
        file_code = await FileCodes.filter(id=file_id).first()
        if not file_code:
            raise HTTPException(status_code=404, detail="文件不存在")
        if file_code.text is None:
            raise HTTPException(status_code=400, detail="仅文本分享支持预览")

        content = file_code.text
        preview = content[:max_chars]
        return {
            "id": file_code.id,
            "code": file_code.code,
            "name": f"{file_code.prefix}{file_code.suffix}",
            "type": "text",
            "content": preview,
            "length": len(content),
            "previewLength": len(preview),
            "preview_length": len(preview),
            "truncated": len(content) > max_chars,
            "maxChars": max_chars,
            "max_chars": max_chars,
            "createdAt": file_code.created_at,
            "created_at": file_code.created_at,
            "expiredAt": file_code.expired_at,
            "expired_at": file_code.expired_at,
        }

    async def share_local_file(self, item):
        local_file = LocalFileClass(item.filename)
        if not await local_file.exists():
            raise HTTPException(status_code=404, detail="文件不存在")

        reservation_token = f"local:{uuid.uuid4().hex}"
        await reserve_storage(reservation_token, local_file.size, ttl_seconds=3600)
        try:
            text = await local_file.read()
            expired_at, expired_count, used_count, code = await get_expire_info(
                item.expire_value, item.expire_style
            )
            path, suffix, prefix, uuid_file_name, save_path = await get_file_path_name(
                item
            )
            await self.file_storage.save_file(text, save_path)
            try:
                await FileCodes.create(
                    code=code,
                    prefix=prefix,
                    suffix=suffix,
                    uuid_file_name=uuid_file_name,
                    file_path=path,
                    size=local_file.size,
                    expired_at=expired_at,
                    expired_count=expired_count,
                    used_count=used_count,
                )
            except Exception:
                await self.file_storage.delete_file(
                    FileCodes(file_path=path, uuid_file_name=uuid_file_name)
                )
                raise
        finally:
            await release_storage(reservation_token)

        return {
            "code": code,
            "name": local_file.file,
        }


class ConfigService:
    INT_FIELDS = {
        "adminSessionExpire",
        "enableChunk",
        "errorCount",
        "errorMinute",
        "max_save_seconds",
        "onedrive_proxy",
        "openUpload",
        "port",
        "s3_proxy",
        "serverPort",
        "serverWorkers",
        "showAdminAddr",
        "storageLimit",
        "uploadCount",
        "uploadMinute",
        "uploadSize",
        "webdav_proxy",
    }
    FLOAT_FIELDS = {"opacity"}

    def get_config(self):
        config = dict(settings.items())
        config["admin_token"] = ""
        for key in INTERNAL_CONFIG_KEYS:
            config.pop(key, None)
        return config

    async def update_config(self, data: dict):
        current_config = dict(settings.items())
        next_config = dict(current_config)
        update_data = {
            key: value
            for key, value in data.items()
            if key in settings.default_config and key not in INTERNAL_CONFIG_KEYS
        }

        admin_token = update_data.get("admin_token")
        admin_password_changed = False
        if admin_token is None or admin_token == "":
            update_data.pop("admin_token", None)
        elif not is_password_hashed(admin_token):
            update_data["admin_token"] = hash_password(admin_token)
            admin_password_changed = True
        else:
            admin_password_changed = True

        for key, value in update_data.items():
            if value == "" and key in self.INT_FIELDS | self.FLOAT_FIELDS:
                continue

            try:
                if key in self.INT_FIELDS:
                    next_config[key] = int(value)
                elif key in self.FLOAT_FIELDS:
                    next_config[key] = float(value)
                else:
                    next_config[key] = value
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{key} 配置值格式错误")

        try:
            session_expire = int(next_config.get("adminSessionExpire"))
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="adminSessionExpire 配置值格式错误",
            )
        if (
            not ADMIN_SESSION_EXPIRE_MIN <= session_expire <= ADMIN_SESSION_EXPIRE_MAX
            or session_expire % ADMIN_SESSION_EXPIRE_MIN != 0
        ):
            raise HTTPException(
                status_code=400,
                detail="adminSessionExpire 必须是 1 到 365 个整天",
            )
        next_config["adminSessionExpire"] = session_expire

        if int(next_config.get("storageLimit", 0)) < 0:
            raise HTTPException(
                status_code=400,
                detail="storageLimit 不能小于 0",
            )

        if admin_password_changed:
            next_config["jwt_secret"] = generate_jwt_secret()

        await KeyValue.update_or_create(key="settings", defaults={"value": next_config})
        await refresh_settings(force=True)  # REL-001: 配置变更后强制刷新，不等 TTL


class LocalFileService:
    async def list_files(self):
        files = []
        if not os.path.exists(data_root / "local"):
            os.makedirs(data_root / "local")
        for file in os.listdir(data_root / "local"):
            local_file = LocalFileClass(file)
            files.append({
                "file": local_file.file,
                "ctime": local_file.ctime,
                "size": local_file.size,
            })
        return files

    async def delete_file(self, filename: str):
        file = LocalFileClass(filename)
        if await file.exists():
            await file.delete()
            return "删除成功"
        raise HTTPException(status_code=404, detail="文件不存在")


class LocalFileClass:
    def __init__(self, file):
        self.file = file
        # SEC-001: 路径边界校验，防止路径穿越攻击（如 ../../xxx）
        # 规范化（resolve）后的路径必须仍在 local 目录内；
        # resolve() 会展开符号链接，因此也能防住"目录内软链接指向外部"的逃逸。
        base_dir = (data_root / "local").resolve()
        resolved_path = (base_dir / file).resolve()
        if not resolved_path.is_relative_to(base_dir):
            raise HTTPException(status_code=400, detail="非法文件路径")
        self.path = resolved_path
        if os.path.exists(self.path):
            self.ctime = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(os.path.getctime(self.path))
            )
            self.size = os.path.getsize(self.path)
        else:
            self.ctime = None
            self.size = None

    async def read(self):
        return open(self.path, "rb")

    async def write(self, data):
        with open(self.path, "w") as f:
            f.write(data)

    async def delete(self):
        os.remove(self.path)

    async def exists(self):
        return os.path.exists(self.path)
