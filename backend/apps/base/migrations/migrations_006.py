from tortoise import connections

from core.db_config import get_db_type


async def migrate():
    conn = connections.get("default")
    db_type = get_db_type()

    if db_type == "postgres":
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS storagereservation (
                id SERIAL PRIMARY KEY,
                token VARCHAR(64) NOT NULL UNIQUE,
                size BIGINT NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_storagereservation_token ON storagereservation (token);
            CREATE INDEX IF NOT EXISTS idx_storagereservation_expires_at ON storagereservation (expires_at);
        """)
    elif db_type == "mysql":
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS storagereservation (
                id INT AUTO_INCREMENT PRIMARY KEY,
                token VARCHAR(64) NOT NULL UNIQUE,
                size BIGINT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                UNIQUE INDEX idx_storagereservation_token (token),
                INDEX idx_storagereservation_expires_at (expires_at)
            );
        """)
    else:
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS storagereservation (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                token VARCHAR(64) NOT NULL UNIQUE,
                size BIGINT NOT NULL,
                expires_at TIMESTAMP NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_storagereservation_token ON storagereservation (token);
            CREATE INDEX IF NOT EXISTS idx_storagereservation_expires_at ON storagereservation (expires_at);
        """)
