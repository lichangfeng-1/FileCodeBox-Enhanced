import os
import unittest
from unittest.mock import patch

from core.db_config import (
    DB_TYPE_MYSQL,
    DB_TYPE_POSTGRES,
    DB_TYPE_SQLITE,
    _parse_database_url,
    build_tortoise_config,
    get_db_type,
)
from core.settings import settings


class ParseDatabaseUrlTests(unittest.TestCase):
    def test_parse_postgres_url(self):
        result = _parse_database_url(
            "postgres://fcb:secret@db.example.com:5433/mydb"
        )
        self.assertEqual(result["db_type"], DB_TYPE_POSTGRES)
        self.assertEqual(result["host"], "db.example.com")
        self.assertEqual(result["port"], 5433)
        self.assertEqual(result["database"], "mydb")
        self.assertEqual(result["user"], "fcb")
        self.assertEqual(result["password"], "secret")

    def test_parse_postgresql_scheme(self):
        result = _parse_database_url("postgresql://u:p@localhost/db")
        self.assertEqual(result["db_type"], DB_TYPE_POSTGRES)

    def test_parse_mysql_url(self):
        result = _parse_database_url("mysql://root:pass@127.0.0.1:3307/testdb")
        self.assertEqual(result["db_type"], DB_TYPE_MYSQL)
        self.assertEqual(result["host"], "127.0.0.1")
        self.assertEqual(result["port"], 3307)
        self.assertEqual(result["database"], "testdb")
        self.assertEqual(result["user"], "root")
        self.assertEqual(result["password"], "pass")

    def test_parse_sqlite_url(self):
        result = _parse_database_url("sqlite:///data/app.db")
        self.assertEqual(result["db_type"], DB_TYPE_SQLITE)
        self.assertIn("app.db", result["file_path"])

    def test_parse_url_encoded_password(self):
        result = _parse_database_url("postgres://u:p%40ss%23@host/db")
        self.assertEqual(result["password"], "p@ss#")

    def test_parse_postgres_default_port(self):
        result = _parse_database_url("postgres://u:p@localhost/db")
        self.assertEqual(result["port"], 5432)

    def test_parse_mysql_default_port(self):
        result = _parse_database_url("mysql://u:p@localhost/db")
        self.assertEqual(result["port"], 3306)

    def test_unknown_scheme_falls_back_to_sqlite(self):
        result = _parse_database_url("mongodb://localhost/db")
        self.assertEqual(result["db_type"], DB_TYPE_SQLITE)


class GetDbTypeTests(unittest.TestCase):
    def test_default_is_sqlite(self):
        original = dict(settings.user_config)
        try:
            settings.user_config = {}
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(get_db_type(), DB_TYPE_SQLITE)
        finally:
            settings.user_config = original

    def test_env_database_url_postgres(self):
        with patch.dict(
            os.environ, {"DATABASE_URL": "postgres://u:p@host/db"}, clear=True
        ):
            self.assertEqual(get_db_type(), DB_TYPE_POSTGRES)

    def test_env_db_type_mysql(self):
        original = dict(settings.user_config)
        try:
            settings.user_config = {}
            with patch.dict(os.environ, {"DB_TYPE": "mysql"}, clear=True):
                self.assertEqual(get_db_type(), DB_TYPE_MYSQL)
        finally:
            settings.user_config = original

    def test_settings_db_type(self):
        original = dict(settings.user_config)
        try:
            settings.db_type = "postgres"
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(get_db_type(), DB_TYPE_POSTGRES)
        finally:
            settings.user_config = original


class BuildConfigTests(unittest.TestCase):
    def test_sqlite_config_structure(self):
        original = dict(settings.user_config)
        try:
            settings.user_config = {}
            with patch.dict(os.environ, {}, clear=True):
                config = build_tortoise_config()
                conn = config["connections"]["default"]
                self.assertEqual(conn["engine"], "tortoise.backends.sqlite")
                self.assertIn("file_path", conn["credentials"])
                self.assertEqual(conn["credentials"]["journal_mode"], "WAL")
        finally:
            settings.user_config = original

    def test_postgres_config_via_env(self):
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgres://fcb:pass@db:5432/fcbdb"},
            clear=True,
        ):
            config = build_tortoise_config()
            conn = config["connections"]["default"]
            self.assertEqual(conn["engine"], "tortoise.backends.asyncpg")
            self.assertEqual(conn["credentials"]["host"], "db")
            self.assertEqual(conn["credentials"]["port"], 5432)
            self.assertEqual(conn["credentials"]["database"], "fcbdb")
            self.assertEqual(conn["credentials"]["user"], "fcb")

    def test_mysql_config_via_env(self):
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "mysql://root:pw@mysql-host:3307/app"},
            clear=True,
        ):
            config = build_tortoise_config()
            conn = config["connections"]["default"]
            self.assertEqual(conn["engine"], "tortoise.backends.mysql")
            self.assertEqual(conn["credentials"]["host"], "mysql-host")
            self.assertEqual(conn["credentials"]["port"], 3307)

    def test_apps_config_unchanged(self):
        with patch.dict(os.environ, {}, clear=True):
            config = build_tortoise_config()
            self.assertEqual(
                config["apps"]["models"]["models"], ["apps.base.models"]
            )
            self.assertEqual(config["timezone"], "Asia/Shanghai")


if __name__ == "__main__":
    unittest.main()
