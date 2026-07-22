from tortoise import connections

from core.db_config import get_db_type


async def migrate():
    conn = connections.get("default")
    db_type = get_db_type()

    if db_type == "postgres":
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS webhookconfig (
                id SERIAL PRIMARY KEY,
                name VARCHAR(128) NOT NULL,
                url VARCHAR(1024) NOT NULL,
                events JSONB NOT NULL,
                headers JSONB,
                enabled BOOLEAN DEFAULT TRUE NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            CREATE TABLE IF NOT EXISTS webhooklog (
                id SERIAL PRIMARY KEY,
                webhook_id INT NOT NULL,
                event_type VARCHAR(64) NOT NULL,
                payload JSONB,
                response_status INT,
                response_body TEXT,
                success BOOLEAN DEFAULT FALSE NOT NULL,
                attempt INT DEFAULT 1 NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_webhooklog_webhook_id ON webhooklog (webhook_id);
            CREATE INDEX IF NOT EXISTS idx_webhooklog_created_at ON webhooklog (created_at);
        """)
    elif db_type == "mysql":
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS webhookconfig (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(128) NOT NULL,
                url VARCHAR(1024) NOT NULL,
                events JSON NOT NULL,
                headers JSON,
                enabled BOOLEAN DEFAULT TRUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            CREATE TABLE IF NOT EXISTS webhooklog (
                id INT AUTO_INCREMENT PRIMARY KEY,
                webhook_id INT NOT NULL,
                event_type VARCHAR(64) NOT NULL,
                payload JSON,
                response_status INT,
                response_body TEXT,
                success BOOLEAN DEFAULT FALSE NOT NULL,
                attempt INT DEFAULT 1 NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                INDEX idx_webhooklog_webhook_id (webhook_id),
                INDEX idx_webhooklog_created_at (created_at)
            );
        """)
    else:
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS webhookconfig (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(128) NOT NULL,
                url VARCHAR(1024) NOT NULL,
                events JSON NOT NULL,
                headers JSON,
                enabled BOOLEAN DEFAULT 1 NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            CREATE TABLE IF NOT EXISTS webhooklog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                webhook_id INT NOT NULL,
                event_type VARCHAR(64) NOT NULL,
                payload JSON,
                response_status INT,
                response_body TEXT,
                success BOOLEAN DEFAULT 0 NOT NULL,
                attempt INT DEFAULT 1 NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_webhooklog_webhook_id ON webhooklog (webhook_id);
            CREATE INDEX IF NOT EXISTS idx_webhooklog_created_at ON webhooklog (created_at);
        """)
