from tortoise import connections

from core.db_config import get_db_type


async def add_save_path_to_uploadchunk():
    conn = connections.get("default")
    db_type = get_db_type()

    if db_type == "postgres":
        await conn.execute_script("""
            ALTER TABLE uploadchunk ADD COLUMN IF NOT EXISTS save_path VARCHAR(512) NULL;
        """)
    elif db_type == "mysql":
        # MySQL 不支持 IF NOT EXISTS，先检测列是否存在
        result = await conn.execute_query(
            "SELECT COUNT(1) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() "
            "AND table_name = 'uploadchunk' AND column_name = 'save_path'"
        )
        if not result[1] or result[1][0][0] == 0:
            await conn.execute_script("""
                ALTER TABLE uploadchunk ADD COLUMN save_path VARCHAR(512) NULL;
            """)
    else:
        # SQLite 不支持 IF NOT EXISTS，用 try/except 保护（从旧版升级时列可能已存在）
        try:
            await conn.execute_script("""
                ALTER TABLE uploadchunk ADD COLUMN save_path VARCHAR(512) NULL;
            """)
        except Exception:
            pass


async def migrate():
    await add_save_path_to_uploadchunk()
