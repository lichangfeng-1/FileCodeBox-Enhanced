"""SEC-001: LocalFileClass 路径穿越漏洞修复测试

验证管理后台本地文件操作（列表/删除/分享）无法逃逸出 data/local 目录。
"""
import unittest

from apps.admin.services import LocalFileClass
from core.settings import data_root
from fastapi import HTTPException


class PathTraversalTests(unittest.TestCase):
    """路径穿越攻击向量测试"""

    def _base_dir(self):
        return (data_root / "local").resolve()

    # ---------- 正常文件名应放行 ----------

    def test_normal_filename_allowed(self):
        """普通文件名正常工作，路径落在 local 目录内"""
        f = LocalFileClass("report.pdf")
        self.assertTrue(str(f.path).startswith(str(self._base_dir())))

    def test_filename_with_chinese_and_spaces_allowed(self):
        """含中文、空格、多重扩展名的正常文件名不受影响"""
        for name in ["我的 文件.tar.gz", "photo 2024.jpg", "a.b.c.txt"]:
            f = LocalFileClass(name)
            self.assertTrue(str(f.path).startswith(str(self._base_dir())))

    def test_subdirectory_filename_allowed(self):
        """子目录形式的合法文件名（仍在 local 内）放行"""
        f = LocalFileClass("sub/dir/file.txt")
        self.assertTrue(str(f.path).startswith(str(self._base_dir())))

    # ---------- 路径穿越攻击应拦截 ----------

    def test_parent_traversal_blocked(self):
        """../ 跳出 local 目录 → 400"""
        with self.assertRaises(HTTPException) as ctx:
            LocalFileClass("../settings.py")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_deep_traversal_blocked(self):
        """../../ 多级穿越 → 400"""
        with self.assertRaises(HTTPException) as ctx:
            LocalFileClass("../../etc/passwd")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_nested_traversal_blocked(self):
        """先进子目录再穿出（subdir/../../）→ 400"""
        with self.assertRaises(HTTPException) as ctx:
            LocalFileClass("subdir/../../settings.py")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_absolute_path_blocked(self):
        """绝对路径（/etc/passwd）→ 400"""
        with self.assertRaises(HTTPException) as ctx:
            LocalFileClass("/etc/passwd")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_sibling_dir_prefix_bypass_blocked(self):
        """假前缀绕过：../local_secret 与 local 有相同前缀但不是其子目录 → 400

        这是 startswith 写法的经典绕过场景，is_relative_to 可正确防御。
        """
        with self.assertRaises(HTTPException) as ctx:
            LocalFileClass("../local_secret/secret.txt")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_encoded_traversal_still_contained(self):
        """....// 等变体无法逃逸（即使不报 400，路径也必须在 local 内）"""
        try:
            f = LocalFileClass("....//....//etc/passwd")
            # 若未抛异常，路径必须仍在 local 目录内（.... 被当作普通目录名）
            self.assertTrue(str(f.path).startswith(str(self._base_dir())))
        except HTTPException as e:
            self.assertEqual(e.status_code, 400)


if __name__ == "__main__":
    unittest.main()
