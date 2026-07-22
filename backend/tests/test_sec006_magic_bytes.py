"""SEC-006: 文件类型 magic bytes 深度校验测试

验证危险文件类型（可执行文件/脚本/宏文档）即使改了扩展名也会被拦截，
正常文件（图片/文档/压缩包）不受影响。

测试设计：每个场景独立用例，AAA 模式。
"""
import asyncio
import io
import unittest

from fastapi import HTTPException
from starlette.datastructures import UploadFile

from apps.base.views import DANGEROUS_MAGIC, validate_file_content, _detect_type_mismatch
from core.settings import settings


def _make_upload(content: bytes, filename: str = "test.bin") -> UploadFile:
    """构造模拟上传文件"""
    return UploadFile(file=io.BytesIO(content), filename=filename)


class MagicBytesValidationTests(unittest.TestCase):
    """SEC-006 magic bytes 校验：每个攻击向量独立用例"""

    def _run(self, coro):
        return asyncio.run(coro)

    # ---------- 危险文件：拦截模式（blockDangerousTypes=1） ----------

    def test_windows_exe_blocked_when_enabled(self):
        """开启拦截时，Windows 可执行文件被拦截"""
        original = dict(settings.user_config)
        settings.blockDangerousTypes = 1
        try:
            file = _make_upload(b"MZ\x90\x00\x03\x00\x00\x00", "photo.jpg")
            with self.assertRaises(HTTPException) as ctx:
                self._run(validate_file_content(file))
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("Windows可执行文件", ctx.exception.detail)
        finally:
            settings.user_config = original

    def test_linux_elf_blocked_when_enabled(self):
        """开启拦截时，Linux ELF 被拦截"""
        original = dict(settings.user_config)
        settings.blockDangerousTypes = 1
        try:
            file = _make_upload(b"\x7fELF\x02\x01\x01\x00", "document.pdf")
            with self.assertRaises(HTTPException) as ctx:
                self._run(validate_file_content(file))
            self.assertEqual(ctx.exception.status_code, 400)
        finally:
            settings.user_config = original

    def test_shell_script_blocked_when_enabled(self):
        """开启拦截时，Shell 脚本被拦截"""
        original = dict(settings.user_config)
        settings.blockDangerousTypes = 1
        try:
            file = _make_upload(b"#!/bin/bash\nrm -rf /", "notes.txt")
            with self.assertRaises(HTTPException) as ctx:
                self._run(validate_file_content(file))
            self.assertEqual(ctx.exception.status_code, 400)
        finally:
            settings.user_config = original

    def test_office_macro_blocked_when_enabled(self):
        """开启拦截时，Office 宏文档被拦截"""
        original = dict(settings.user_config)
        settings.blockDangerousTypes = 1
        try:
            file = _make_upload(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "report.docx")
            with self.assertRaises(HTTPException) as ctx:
                self._run(validate_file_content(file))
            self.assertEqual(ctx.exception.status_code, 400)
        finally:
            settings.user_config = original

    # ---------- 危险文件：默认仅提示模式（blockDangerousTypes=0） ----------

    def test_exe_warns_by_default(self):
        """默认不拦截 EXE，仅返回警告"""
        file = _make_upload(b"MZ\x90\x00\x03\x00\x00\x00", "installer.exe")
        warning = self._run(validate_file_content(file))
        self.assertIsNotNone(warning)
        self.assertIn("Windows可执行文件", warning)

    def test_script_warns_by_default(self):
        """默认不拦截脚本，仅返回警告"""
        file = _make_upload(b"#!/bin/bash\necho hi", "deploy.sh")
        warning = self._run(validate_file_content(file))
        self.assertIsNotNone(warning)
        self.assertIn("脚本文件", warning)

    # ---------- 正常文件应放行 ----------

    def test_jpeg_allowed(self):
        """JPEG 文件（FF D8 FF 头）正常通过"""
        file = _make_upload(b"\xff\xd8\xff\xe0\x00\x10JFIF", "photo.jpg")
        self._run(validate_file_content(file))  # 不抛异常 = 通过

    def test_png_allowed(self):
        """PNG 文件正常通过"""
        file = _make_upload(b"\x89PNG\r\n\x1a\n", "image.png")
        self._run(validate_file_content(file))

    def test_pdf_allowed(self):
        """PDF 文件正常通过"""
        file = _make_upload(b"%PDF-1.4 ...", "document.pdf")
        self._run(validate_file_content(file))

    def test_zip_allowed(self):
        """ZIP/DOCX/XLSX 文件正常通过"""
        file = _make_upload(b"PK\x03\x04...", "archive.zip")
        self._run(validate_file_content(file))

    def test_plain_text_allowed(self):
        """纯文本文件正常通过"""
        file = _make_upload(b"Hello, this is a normal text file.", "readme.txt")
        self._run(validate_file_content(file))

    def test_empty_file_allowed(self):
        """空文件不触发拦截（无 magic bytes 可匹配）"""
        file = _make_upload(b"", "empty.bin")
        self._run(validate_file_content(file))

    # ---------- 文件指针重置验证 ----------

    def test_file_pointer_reset_after_validation(self):
        """校验后文件指针回到开头（不影响后续保存）"""
        content = b"normal file content here"
        file = _make_upload(content)
        self._run(validate_file_content(file))
        # 校验后底层文件指针应回到 0（与实际存储代码一致）
        self.assertEqual(file.file.tell(), 0)
        self.assertEqual(file.file.read(), content)

    # ---------- 扩展名与内容不匹配检测 ----------

    def test_mismatch_pdf_renamed_to_jpg(self):
        """PDF 改名为 .jpg → 检测到不匹配，返回警告"""
        file = _make_upload(b"%PDF-1.4 content", "photo.jpg")
        warning = self._run(validate_file_content(file))
        self.assertIsNotNone(warning)
        self.assertIn(".pdf", warning)
        self.assertIn(".jpg", warning)

    def test_mismatch_png_renamed_to_docx(self):
        """PNG 改名为 .docx → 检测到不匹配"""
        file = _make_upload(b"\x89PNG\r\n\x1a\n...", "report.docx")
        warning = self._run(validate_file_content(file))
        self.assertIsNotNone(warning)
        self.assertIn(".png", warning)

    def test_match_jpeg_correct_extension(self):
        """JPEG 扩展名正确 → 无警告"""
        file = _make_upload(b"\xff\xd8\xff\xe0\x00\x10JFIF", "photo.jpg")
        warning = self._run(validate_file_content(file))
        self.assertIsNone(warning)

    def test_strict_mode_blocks_mismatch(self):
        """严格模式下，扩展名不匹配 → 403 拦截"""
        original = dict(settings.user_config)
        settings.fileTypeStrict = 1
        try:
            file = _make_upload(b"%PDF-1.4 content", "image.png")
            with self.assertRaises(HTTPException) as ctx:
                self._run(validate_file_content(file))
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertIn("不匹配", ctx.exception.detail)
        finally:
            settings.user_config = original

    def test_unknown_type_no_warning(self):
        """未识别的文件类型 → 不做判断，无警告"""
        file = _make_upload(b"\x00\x01\x02\x03\x04\x05", "data.custom")
        warning = self._run(validate_file_content(file))
        self.assertIsNone(warning)

    # ---------- 改名绕过白名单拦截 ----------

    def test_renamed_pdf_blocked_by_whitelist(self):
        """管理员只允许 jpg/png，PDF 改名为 .jpg 仍被拦截"""
        original = dict(settings.user_config)
        settings.allowed_file_types = [".jpg", ".png"]
        try:
            file = _make_upload(b"%PDF-1.4 content", "photo.jpg")
            with self.assertRaises(HTTPException) as ctx:
                self._run(validate_file_content(file))
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertIn("不匹配", ctx.exception.detail)
        finally:
            settings.user_config = original

    def test_renamed_jpeg_within_whitelist_allowed(self):
        """管理员允许 jpg，.jpeg 改名为 .jpg → 真实类型在白名单内，仅提示"""
        original = dict(settings.user_config)
        settings.allowed_file_types = [".jpg", ".jpeg", ".png"]
        try:
            # JPEG 内容改名为 .png（真实类型 .jpg/.jpeg 在白名单内）
            file = _make_upload(b"\xff\xd8\xff\xe0\x00\x10JFIF", "image.png")
            warning = self._run(validate_file_content(file))
            # 不拦截，仅提示（因为真实类型 jpeg 在白名单内）
            self.assertIsNotNone(warning)  # 有提示
        finally:
            settings.user_config = original

    def test_wildcard_whitelist_allows_all(self):
        """白名单为 * 时，不拦截但仍提示不匹配（友好提醒）"""
        original = dict(settings.user_config)
        settings.allowed_file_types = ["*"]
        try:
            file = _make_upload(b"%PDF-1.4 content", "anything.xyz")
            warning = self._run(validate_file_content(file))
            # 不拦截（不抛异常），但有提示
            self.assertIsNotNone(warning)
        finally:
            settings.user_config = original


if __name__ == "__main__":
    unittest.main()
