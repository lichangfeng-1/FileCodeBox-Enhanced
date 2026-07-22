import asyncio
import unittest

from core.ua_parser import parse_user_agent
from core.ip_location import _is_private_ip, get_ip_location


class UAParserTests(unittest.TestCase):
    def test_chrome_windows(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        result = parse_user_agent(ua)
        self.assertEqual(result.browser, "Chrome")
        self.assertEqual(result.browser_version, "126.0.0.0")
        self.assertEqual(result.os, "Windows")
        self.assertEqual(result.os_version, "10/11")
        self.assertEqual(result.device_type, "pc")

    def test_firefox_linux(self):
        ua = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
        result = parse_user_agent(ua)
        self.assertEqual(result.browser, "Firefox")
        self.assertEqual(result.os, "Linux")
        self.assertEqual(result.device_type, "pc")

    def test_safari_iphone(self):
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
        result = parse_user_agent(ua)
        self.assertEqual(result.browser, "Safari")
        self.assertEqual(result.os, "iOS")
        self.assertEqual(result.device_type, "mobile")

    def test_edge_windows(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
        result = parse_user_agent(ua)
        self.assertEqual(result.browser, "Edge")
        self.assertEqual(result.os, "Windows")

    def test_android_mobile(self):
        ua = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/126.0.0.0 Mobile Safari/537.36"
        result = parse_user_agent(ua)
        self.assertEqual(result.os, "Android")
        self.assertEqual(result.device_type, "mobile")

    def test_ipad_tablet(self):
        ua = "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Version/17.5 Safari/604.1"
        result = parse_user_agent(ua)
        self.assertEqual(result.device_type, "tablet")

    def test_bot_detection(self):
        ua = "python-requests/2.31.0"
        result = parse_user_agent(ua)
        self.assertEqual(result.browser, "Bot")
        self.assertEqual(result.device_type, "bot")

    def test_empty_ua(self):
        result = parse_user_agent("")
        self.assertEqual(result.device_type, "unknown")

    def test_none_ua(self):
        result = parse_user_agent(None)
        self.assertEqual(result.device_type, "unknown")

    def test_to_dict(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0"
        result = parse_user_agent(ua).to_dict()
        self.assertIn("browser", result)
        self.assertIn("device_type", result)
        self.assertEqual(result["browser"], "Chrome")


class IPLocationTests(unittest.TestCase):
    def test_private_ip_10(self):
        self.assertTrue(_is_private_ip("10.0.0.1"))

    def test_private_ip_172(self):
        self.assertTrue(_is_private_ip("172.16.0.1"))

    def test_private_ip_192(self):
        self.assertTrue(_is_private_ip("192.168.1.100"))

    def test_private_ip_127(self):
        self.assertTrue(_is_private_ip("127.0.0.1"))

    def test_public_ip(self):
        self.assertFalse(_is_private_ip("8.8.8.8"))

    def test_get_location_private(self):
        self.assertEqual(get_ip_location("192.168.1.1"), "内网")

    def test_get_location_empty(self):
        self.assertIsNone(get_ip_location(""))
        self.assertIsNone(get_ip_location(None))

    def test_get_location_public_ip(self):
        # 有离线库时公网IP应返回归属地
        result = get_ip_location("8.8.8.8")
        # 有 xdb 文件时返回非空，无 xdb 时返回 None
        if result is not None:
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)


if __name__ == "__main__":
    unittest.main()
