from tortoise import connections

from core.db_config import get_db_type


async def migrate():
    conn = connections.get("default")
    db_type = get_db_type()

    if db_type == "mysql":
        # MySQL 不支持 CREATE INDEX IF NOT EXISTS，需先查询
        result = await conn.execute_query(
            "SELECT COUNT(1) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() "
            "AND table_name = 'filecodes' AND index_name = 'idx_filecodes_file_hash'"
        )
        if not result[1] or result[1][0][0] == 0:
            await conn.execute_script(
                "CREATE INDEX idx_filecodes_file_hash ON filecodes (file_hash)"
            )
    else:
        # SQLite / PostgreSQL 支持 IF NOT EXISTS
        await conn.execute_script(
            """
            CREATE INDEX IF NOT EXISTS idx_filecodes_file_hash
                ON filecodes (file_hash);
            """
        )
