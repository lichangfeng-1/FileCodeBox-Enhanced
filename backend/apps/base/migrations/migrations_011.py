from tortoise import connections

from core.db_config import get_db_type


async def migrate():
    conn = connections.get("default")
    db_type = get_db_type()

    if db_type == "postgres":
        await conn.execute_script("""
            ALTER TABLE presignuploadsession
                ADD COLUMN IF NOT EXISTS text TEXT;
        """)
    elif db_type == "mysql":
        # MySQL 不支持 IF NOT EXISTS，用存储过程包装
        result = await conn.execute_query(
            "SELECT COUNT(1) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() "
            "AND table_name = 'presignuploadsession' AND column_name = 'text'"
        )
        if not result[1] or result[1][0][0] == 0:
            await conn.execute_script(
                "ALTER TABLE presignuploadsession ADD COLUMN text TEXT NULL"
            )
    else:
        # SQLite: 尝试添加列，已存在则忽略
        try:
            await conn.execute_script(
                "ALTER TABLE presignuploadsession ADD COLUMN text TEXT"
            )
        except Exception:
            pass
