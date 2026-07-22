"""BUG-001: quota.py 多数据库 SQL 占位符兼容测试

验证 _sql_placeholders 根据数据库类型生成正确的占位符，
确保存储配额功能在 SQLite/PostgreSQL/MySQL 下都能正常执行 SQL。
"""
import unittest
from unittest.mock import patch

from apps.base import quota
from core.db_config import DB_TYPE_MYSQL, DB_TYPE_POSTGRES, DB_TYPE_SQLITE


class SqlPlaceholderTests(unittest.TestCase):
    def test_sqlite_uses_question_marks(self):
        """SQLite 使用 ? 占位符"""
        with patch.object(quota, "get_db_type", return_value=DB_TYPE_SQLITE):
            self.assertEqual(quota._sql_placeholders(6), ["?"] * 6)

    def test_postgres_uses_numbered_dollars(self):
        """PostgreSQL 使用 $1/$2/... 编号占位符"""
        with patch.object(quota, "get_db_type", return_value=DB_TYPE_POSTGRES):
            self.assertEqual(
                quota._sql_placeholders(6),
                ["$1", "$2", "$3", "$4", "$5", "$6"],
            )

    def test_mysql_uses_percent_s(self):
        """MySQL 使用 %s 占位符"""
        with patch.object(quota, "get_db_type", return_value=DB_TYPE_MYSQL):
            self.assertEqual(quota._sql_placeholders(6), ["%s"] * 6)

    def test_placeholder_count_matches_request(self):
        """占位符数量与请求一致，且编号连续"""
        with patch.object(quota, "get_db_type", return_value=DB_TYPE_POSTGRES):
            self.assertEqual(quota._sql_placeholders(3), ["$1", "$2", "$3"])
        with patch.object(quota, "get_db_type", return_value=DB_TYPE_SQLITE):
            self.assertEqual(len(quota._sql_placeholders(1)), 1)


if __name__ == "__main__":
    unittest.main()
