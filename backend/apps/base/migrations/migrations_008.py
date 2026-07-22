from tortoise import connections

from core.db_config import get_db_type


async def migrate():
    conn = connections.get("default")
    db_type = get_db_type()

    if db_type == "postgres":
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS auditlog (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(32) NOT NULL,
                file_id INT,
                file_code VARCHAR(255),
                file_name VARCHAR(512),
                ip VARCHAR(45) NOT NULL,
                ip_location VARCHAR(255),
                user_agent TEXT,
                browser VARCHAR(64),
                browser_version VARCHAR(32),
                os VARCHAR(64),
                os_version VARCHAR(32),
                device_type VARCHAR(16),
                detail JSONB,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_auditlog_event_type ON auditlog (event_type);
            CREATE INDEX IF NOT EXISTS idx_auditlog_file_id ON auditlog (file_id);
            CREATE INDEX IF NOT EXISTS idx_auditlog_ip ON auditlog (ip);
            CREATE INDEX IF NOT EXISTS idx_auditlog_created_at ON auditlog (created_at);
        """)
    elif db_type == "mysql":
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS auditlog (
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_type VARCHAR(32) NOT NULL,
                file_id INT,
                file_code VARCHAR(255),
                file_name VARCHAR(512),
                ip VARCHAR(45) NOT NULL,
                ip_location VARCHAR(255),
                user_agent TEXT,
                browser VARCHAR(64),
                browser_version VARCHAR(32),
                os VARCHAR(64),
                os_version VARCHAR(32),
                device_type VARCHAR(16),
                detail JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                INDEX idx_auditlog_event_type (event_type),
                INDEX idx_auditlog_file_id (file_id),
                INDEX idx_auditlog_ip (ip),
                INDEX idx_auditlog_created_at (created_at)
            );
        """)
    else:
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS auditlog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type VARCHAR(32) NOT NULL,
                file_id INT,
                file_code VARCHAR(255),
                file_name VARCHAR(512),
                ip VARCHAR(45) NOT NULL,
                ip_location VARCHAR(255),
                user_agent TEXT,
                browser VARCHAR(64),
                browser_version VARCHAR(32),
                os VARCHAR(64),
                os_version VARCHAR(32),
                device_type VARCHAR(16),
                detail JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_auditlog_event_type ON auditlog (event_type);
            CREATE INDEX IF NOT EXISTS idx_auditlog_file_id ON auditlog (file_id);
            CREATE INDEX IF NOT EXISTS idx_auditlog_ip ON auditlog (ip);
            CREATE INDEX IF NOT EXISTS idx_auditlog_created_at ON auditlog (created_at);
        """)
