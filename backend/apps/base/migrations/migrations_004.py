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
        # MySQL 不支持 IF NOT EXISTS，用存储过程包装
        await conn.execute_script("""
            ALTER TABLE uploadchunk ADD COLUMN save_path VARCHAR(512) NULL;
        """)
    else:
        await conn.execute_script("""
            ALTER TABLE uploadchunk ADD COLUMN save_path VARCHAR(512) NULL;
        """)


async def migrate():
    await add_save_path_to_uploadchunk()
