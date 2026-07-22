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
        await conn.execute_script("""
            ALTER TABLE filecodes ADD COLUMN file_hash VARCHAR(128);
            ALTER TABLE filecodes ADD COLUMN is_chunked BOOL NOT NULL DEFAULT False;
            ALTER TABLE filecodes ADD COLUMN upload_id VARCHAR(128);
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
        await conn.execute_script("""
            ALTER TABLE "filecodes" ADD "file_hash" VARCHAR(128);
            ALTER TABLE "filecodes" ADD "is_chunked" BOOL NOT NULL DEFAULT False;
            ALTER TABLE "filecodes" ADD "upload_id" VARCHAR(128);
            CREATE TABLE "uploadchunk" (
                id  INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                "upload_id" VARCHAR(36) NOT NULL,
                "chunk_index" INT NOT NULL,
                "chunk_hash" VARCHAR(128) NOT NULL,
                "total_chunks" INT NOT NULL,
                "file_size" BIGINT NOT NULL,
                "chunk_size" INT NOT NULL,
                "created_at" TIMESTAMPTZ NOT NULL,
                "file_name" VARCHAR(255) NOT NULL,
                "completed" BOOL NOT NULL
            );
        """)


async def migrate():
    await create_upload_chunk_and_update_file_codes_table()
