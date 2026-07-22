"""
migrations_010: 修复 PostgreSQL 时间字段类型
将所有 TIMESTAMP（无时区）列转换为 TIMESTAMPTZ（带时区），
以配合 Tortoise ORM use_tz=True 配置。

背景：
  use_tz=True 时，Tortoise 生成 timezone-aware datetime (UTC)，
  若 PostgreSQL 列为 TIMESTAMP（无时区），asyncpg 编码时会抛出
  "can't subtract offset-naive and offset-aware datetimes" 错误。

影响表/字段：
  - filecodes.created_at
  - presignuploadsession.expires_at
  - webhookconfig.updated_at
  - webhooklog.created_at

注：USING created_at AT TIME ZONE 'UTC' 确保已有数据按 UTC 解释后转换，
    不会丢失或偏移已有时间数据。
"""

from tortoise import connections

from core.db_config import get_db_type


async def migrate():
    db_type = get_db_type()

    # 仅 PostgreSQL 需要修复（MySQL/SQLite 无 TIMESTAMP vs TIMESTAMPTZ 区分）
    if db_type != "postgres":
        return

    conn = connections.get("default")

    # 逐列转换：TIMESTAMP → TIMESTAMPTZ
    # USING ... AT TIME ZONE 'UTC' 表示将原 naive 时间视为 UTC 后转为带时区
    await conn.execute_script("""
        ALTER TABLE filecodes
            ALTER COLUMN created_at TYPE TIMESTAMPTZ
            USING created_at AT TIME ZONE 'UTC';

        ALTER TABLE presignuploadsession
            ALTER COLUMN expires_at TYPE TIMESTAMPTZ
            USING expires_at AT TIME ZONE 'UTC';

        ALTER TABLE webhookconfig
            ALTER COLUMN updated_at TYPE TIMESTAMPTZ
            USING updated_at AT TIME ZONE 'UTC';

        ALTER TABLE webhooklog
            ALTER COLUMN created_at TYPE TIMESTAMPTZ
            USING created_at AT TIME ZONE 'UTC';
    """)
