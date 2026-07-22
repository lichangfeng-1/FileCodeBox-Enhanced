# @Time    : 2023/8/15 22:00
# @Author  : Lan
# @File    : tasks.py
# @Software: PyCharm
import asyncio
import datetime
import logging
import os

from tortoise.expressions import Q

from apps.base.models import (
    AuditLog,
    FileCodes,
    PresignUploadSession,
    StorageReservation,
    UploadChunk,
    WebhookLog,
)
from apps.base.utils import ip_limit, get_chunk_file_path_name
from core.config import refresh_settings
from core.settings import settings, data_root
from core.storage import FileStorageInterface, storages
from core.utils import get_now


async def delete_expire_files():
    while True:
        try:
            await refresh_settings()
            # REL-004: 循环前取一次时间，全程复用
            now = await get_now()
            file_storage: FileStorageInterface = storages[settings.file_storage]()
            # 遍历 share目录下的所有文件夹，删除空的文件夹，并判断父目录是否为空，如果为空也删除
            if settings.file_storage == "local":
                for root, dirs, files in os.walk(f"{data_root}/share/data"):
                    if not dirs and not files:
                        os.rmdir(root)
            await ip_limit["error"].remove_expired_ip()
            await ip_limit["metadata"].remove_expired_ip()
            await ip_limit["upload"].remove_expired_ip()
            await ip_limit["login"].remove_expired_ip()
            await StorageReservation.filter(expires_at__lte=now).delete()
            # 清理过期审计日志（时间 + 总量双重限制）
            retention_days = int(getattr(settings, "auditRetentionDays", 90))
            if retention_days > 0:
                audit_cutoff = now - datetime.timedelta(days=retention_days)
                await AuditLog.filter(created_at__lt=audit_cutoff).delete()
            max_records = int(getattr(settings, "auditMaxRecords", 100000))
            if max_records > 0:
                total_count = await AuditLog.all().count()
                if total_count > max_records:
                    # 删除最旧的超出部分
                    overflow = total_count - max_records
                    oldest_ids = await AuditLog.all().order_by("created_at").limit(overflow).values_list("id", flat=True)
                    if oldest_ids:
                        await AuditLog.filter(id__in=list(oldest_ids)).delete()
                        logging.info(f"审计日志总量超限，已清理{len(oldest_ids)}条最旧记录")
            # 清理过期 Webhook 日志（30天）
            webhook_cutoff = now - datetime.timedelta(days=30)
            await WebhookLog.filter(created_at__lt=webhook_cutoff).delete()
            expire_data = await FileCodes.filter(
                Q(expired_at__lt=now) | Q(expired_count=0)
            ).all()
            for exp in expire_data:
                try:
                    # 秒传保护：检查是否有其他未过期记录共享同一物理文件
                    # 只有当没有其他记录引用该文件时，才删除物理文件
                    shared_count = await FileCodes.filter(
                        file_hash=exp.file_hash,
                        size=exp.size,
                    ).exclude(id=exp.id).exclude(
                        Q(expired_at__lt=now) | Q(expired_count=0)
                    ).count()
                    if shared_count == 0:
                        await file_storage.delete_file(exp)
                    else:
                        logging.info(
                            f"文件被{shared_count}个其他记录共享，仅删除记录不删物理文件 code={exp.code}"
                        )
                except Exception as e:
                    logging.error(f"删除过期文件失败 code={exp.code}: {e}")
                try:
                    # 触发 file.expired Webhook
                    from core.webhook import emit_webhook
                    await emit_webhook("file.expired", {
                        "code": exp.code,
                        "name": f"{exp.prefix}{exp.suffix}",
                        "size": exp.size,
                    })
                    await exp.delete()
                except Exception as e:
                    logging.error(f"删除记录失败 code={exp.code}: {e}")
        except Exception as e:
            logging.error(e)
        finally:
            await asyncio.sleep(600)


async def clean_incomplete_uploads():
    while True:
        try:
            await refresh_settings()
            file_storage: FileStorageInterface = storages[settings.file_storage]()
            expire_hours = getattr(settings, "chunk_expire_hours", 24)
            now = await get_now()
            expire_time = now - datetime.timedelta(hours=expire_hours)
            expired_sessions = await UploadChunk.filter(
                chunk_index=-1, created_at__lt=expire_time
            ).all()

            for session in expired_sessions:
                try:
                    save_path = session.save_path
                    if not save_path:
                        _, _, _, _, save_path = await get_chunk_file_path_name(
                            session.file_name, session.upload_id
                        )
                    await file_storage.clean_chunks(session.upload_id, save_path)
                except Exception as e:
                    logging.error(
                        f"清理分片文件失败 upload_id={session.upload_id}: {e}"
                    )

                try:
                    await UploadChunk.filter(upload_id=session.upload_id).delete()
                    await StorageReservation.filter(
                        token=f"chunk:{session.upload_id}"
                    ).delete()
                    logging.info(f"已清理过期上传会话 upload_id={session.upload_id}")
                except Exception as e:
                    logging.error(
                        f"删除分片记录失败 upload_id={session.upload_id}: {e}"
                    )

        except Exception as e:
            logging.error(f"清理未完成上传任务异常: {e}")
        finally:
            await asyncio.sleep(3600)


async def clean_expired_presign_sessions():
    while True:
        try:
            await refresh_settings()
            storage: FileStorageInterface = storages[settings.file_storage]()
            now = await get_now()
            expired_sessions = await PresignUploadSession.filter(
                expires_at__lt=now
            ).all()
            for session in expired_sessions:
                if session.mode == "direct":
                    try:
                        if await storage.file_exists(session.save_path):
                            await storage.delete_file(
                                FileCodes(
                                    file_path=os.path.dirname(session.save_path),
                                    uuid_file_name=os.path.basename(session.save_path),
                                )
                            )
                    except Exception as e:
                        logging.error(
                            "清理过期直传文件失败 "
                            f"upload_id={session.upload_id}: {e}"
                        )
                await StorageReservation.filter(
                    token=f"presign:{session.upload_id}"
                ).delete()
                await session.delete()
        except Exception as e:
            logging.error(f"清理过期预签名会话异常: {e}")
        finally:
            await asyncio.sleep(900)
