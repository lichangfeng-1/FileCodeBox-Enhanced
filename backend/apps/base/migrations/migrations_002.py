from tortoise import connections

from core.db_config import get_db_type


async def create_upload_chunk_and_update_file_codes_table():
    conn = connections.get("default")
    db_type = get_db_type()

    if db_type == "postgres":
        await conn.execute_script("""
            ALTER TABLE filecodes ADD COLUMN IF NOT EXISTS file_hash VARCHAR(128);
            ALTER TABLE filecodes ADD COLUMN IF NOT EXISTS is_chunked BOOL NOT NULL DEFAULT False;
            ALTER TABLE filecodes ADD COLUMN IF NOT EXISTS upload_id VARCHAR(128);
            CREATE TABLE IF NOT EXISTS uploadchunk (
                id  SERIAL PRIMARY KEY,
                upload_id VARCHAR(36) NOT NULL,
                chunk_index INT NOT NULL,
                chunk_hash VARCHAR(128) NOT NULL,
                total_chunks INT NOT NULL,
                file_size BIGINT NOT NULL,
                chunk_size INT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                file_name VARCHAR(255) NOT NULL,
                completed BOOL NOT NULL DEFAULT False
            );
        """)
    elif db_type == "mysql":
        # MySQL 不支持 ALTER TABLE ADD COLUMN IF NOT EXISTS，逐列检测
        for col, ddl in [
            ("file_hash", "ALTER TABLE filecodes ADD COLUMN file_hash VARCHAR(128)"),
            ("is_chunked", "ALTER TABLE filecodes ADD COLUMN is_chunked BOOL NOT NULL DEFAULT False"),
            ("upload_id", "ALTER TABLE filecodes ADD COLUMN upload_id VARCHAR(128)"),
        ]:
            result = await conn.execute_query(
                "SELECT COUNT(1) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() "
                "AND table_name = 'filecodes' AND column_name = %s",
                [col],
            )
            if not result[1] or result[1][0][0] == 0:
                await conn.execute_script(ddl)
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS uploadchunk (
                id  INT AUTO_INCREMENT PRIMARY KEY,
                upload_id VARCHAR(36) NOT NULL,
                chunk_index INT NOT NULL,
                chunk_hash VARCHAR(128) NOT NULL,
                total_chunks INT NOT NULL,
                file_size BIGINT NOT NULL,
                chunk_size INT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                file_name VARCHAR(255) NOT NULL,
                completed BOOL NOT NULL DEFAULT False
            );
        """)
    else:
        # SQLite 不支持 ALTER TABLE ADD COLUMN IF NOT EXISTS，用 try/except 保护
        for ddl in [
            'ALTER TABLE "filecodes" ADD "file_hash" VARCHAR(128)',
            'ALTER TABLE "filecodes" ADD "is_chunked" BOOL NOT NULL DEFAULT False',
            'ALTER TABLE "filecodes" ADD "upload_id" VARCHAR(128)',
        ]:
            try:
                await conn.execute_script(ddl)
            except Exception:
                pass  # 字段已存在（从旧版升级），跳过
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS "uploadchunk" (
                id  INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                "upload_id" VARCHAR(36) NOT NULL,
                "chunk_index" INT NOT NULL,
                "chunk_hash" VARCHAR(128) NOT NULL,
                "total_chunks" INT NOT NULL,
                "file_size" BIGINT NOT NULL,
                "chunk_size" INT NOT NULL,
                "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                "file_name" VARCHAR(255) NOT NULL,
                "completed" BOOL NOT NULL DEFAULT False
            );
        """)


async def migrate():
    await create_upload_chunk_and_update_file_codes_table()
