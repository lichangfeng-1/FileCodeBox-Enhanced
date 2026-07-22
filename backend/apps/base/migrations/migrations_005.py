from tortoise import connections

from core.db_config import get_db_type


def _need_upgrade(columns: list[tuple]) -> bool:
    for column in columns:
        # PRAGMA table_info 返回 (cid, name, type, notnull, dflt_value, pk)
        if column[1] == "size":
            column_type = (column[2] or "").upper()
            return "BIGINT" not in column_type
    return False


async def migrate():
    conn = connections.get("default")
    db_type = get_db_type()

    if db_type == "postgres":
        # PostgreSQL: 直接修改列类型
        await conn.execute_script("""
            ALTER TABLE filecodes ALTER COLUMN size TYPE BIGINT;
        """)
    elif db_type == "mysql":
        # MySQL: MODIFY COLUMN
        await conn.execute_script("""
            ALTER TABLE filecodes MODIFY COLUMN size BIGINT DEFAULT 0 NOT NULL;
        """)
    else:
        # SQLite: PRAGMA 检测 + 表重建
        result = await conn.execute_query("PRAGMA table_info(filecodes)")
        columns = result[1] if result and len(result) > 1 else []

        if not columns or not _need_upgrade(columns):
            return

        await conn.execute_script("""
            BEGIN;
            CREATE TABLE IF NOT EXISTS filecodes_new (
                id             INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                code           VARCHAR(255) NOT NULL UNIQUE,
                prefix         VARCHAR(255) DEFAULT '' NOT NULL,
                suffix         VARCHAR(255) DEFAULT '' NOT NULL,
                uuid_file_name VARCHAR(255),
                file_path      VARCHAR(255),
                size           BIGINT DEFAULT 0 NOT NULL,
                text           TEXT,
                expired_at     TIMESTAMP,
                expired_count  INT DEFAULT 0 NOT NULL,
                used_count     INT DEFAULT 0 NOT NULL,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                file_hash      VARCHAR(128),
                is_chunked     BOOL DEFAULT False NOT NULL,
                upload_id      VARCHAR(128)
            );

            INSERT INTO filecodes_new (id, code, prefix, suffix, uuid_file_name, file_path, size, text,
                                       expired_at, expired_count, used_count, created_at, file_hash,
                                       is_chunked, upload_id)
            SELECT id, code, prefix, suffix, uuid_file_name, file_path, size, text,
                   expired_at, expired_count, used_count, created_at, file_hash,
                   is_chunked, upload_id
            FROM filecodes;

            DROP TABLE filecodes;
            ALTER TABLE filecodes_new RENAME TO filecodes;
            CREATE INDEX IF NOT EXISTS idx_filecodes_code_1c7ee7 ON filecodes (code);
            COMMIT;
        """)
