from tortoise import connections

from core.db_config import get_db_type


async def create_file_codes_table():
    conn = connections.get("default")
    db_type = get_db_type()

    if db_type == "postgres":
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS filecodes (
                id             SERIAL PRIMARY KEY,
                code           VARCHAR(255) NOT NULL UNIQUE,
                prefix         VARCHAR(255) DEFAULT '' NOT NULL,
                suffix         VARCHAR(255) DEFAULT '' NOT NULL,
                uuid_file_name VARCHAR(255),
                file_path      VARCHAR(255),
                size           INT DEFAULT 0 NOT NULL,
                text           TEXT,
                expired_at     TIMESTAMPTZ,
                expired_count  INT DEFAULT 0 NOT NULL,
                used_count     INT DEFAULT 0 NOT NULL,
                created_at     TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_filecodes_code_1c7ee7 ON filecodes (code);
        """)
    elif db_type == "mysql":
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS filecodes (
                id             INT AUTO_INCREMENT PRIMARY KEY,
                code           VARCHAR(255) NOT NULL UNIQUE,
                prefix         VARCHAR(255) DEFAULT '' NOT NULL,
                suffix         VARCHAR(255) DEFAULT '' NOT NULL,
                uuid_file_name VARCHAR(255),
                file_path      VARCHAR(255),
                size           INT DEFAULT 0 NOT NULL,
                text           TEXT,
                expired_at     TIMESTAMP NULL,
                expired_count  INT DEFAULT 0 NOT NULL,
                used_count     INT DEFAULT 0 NOT NULL,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                INDEX idx_filecodes_code_1c7ee7 (code)
            );
        """)
    else:
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS filecodes (
                id             INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                code           VARCHAR(255) NOT NULL UNIQUE,
                prefix         VARCHAR(255) DEFAULT '' NOT NULL,
                suffix         VARCHAR(255) DEFAULT '' NOT NULL,
                uuid_file_name VARCHAR(255),
                file_path      VARCHAR(255),
                size           INT DEFAULT 0 NOT NULL,
                text           TEXT,
                expired_at     TIMESTAMP,
                expired_count  INT DEFAULT 0 NOT NULL,
                used_count     INT DEFAULT 0 NOT NULL,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_filecodes_code_1c7ee7 ON filecodes (code);
        """)


async def create_key_value_table():
    conn = connections.get("default")
    db_type = get_db_type()

    if db_type == "postgres":
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS keyvalue (
                id         SERIAL PRIMARY KEY,
                key        VARCHAR(255) NOT NULL UNIQUE,
                value      JSONB,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_keyvalue_key_eab890 ON keyvalue (key);
        """)
    elif db_type == "mysql":
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS keyvalue (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                `key`      VARCHAR(255) NOT NULL UNIQUE,
                value      JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                INDEX idx_keyvalue_key_eab890 (`key`)
            );
        """)
    else:
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS keyvalue (
                id         INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                key        VARCHAR(255) NOT NULL UNIQUE,
                value      JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_keyvalue_key_eab890 ON keyvalue (key);
        """)


async def migrate():
    await create_file_codes_table()
    await create_key_value_table()
