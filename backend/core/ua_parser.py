# @Time    : 2026/7/19
# @File    : ua_parser.py
# @Desc    : 轻量级 User-Agent 解析，纯正则实现，无第三方依赖
import re
from typing import Optional


# Bot 特征
_BOT_PATTERN = re.compile(
    r"bot|spider|crawler|curl|wget|python-requests|httpx|aiohttp|scrapy|feed|monitor",
    re.IGNORECASE,
)

# 浏览器识别（按优先级排序）
_BROWSER_PATTERNS = [
    (re.compile(r"Edg(?:e|A|iOS)?/(\d+[\.\d]*)", re.IGNORECASE), "Edge"),
    (re.compile(r"OPR/(\d+[\.\d]*)|Opera.*Version/(\d+[\.\d]*)", re.IGNORECASE), "Opera"),
    (re.compile(r"Chrome/(\d+[\.\d]*)", re.IGNORECASE), "Chrome"),
    (re.compile(r"Firefox/(\d+[\.\d]*)", re.IGNORECASE), "Firefox"),
    (re.compile(r"Version/(\d+[\.\d]*).*Safari", re.IGNORECASE), "Safari"),
    (re.compile(r"MSIE (\d+[\.\d]*)|Trident/.*rv:(\d+[\.\d]*)", re.IGNORECASE), "IE"),
]

# 操作系统识别
_OS_PATTERNS = [
    (re.compile(r"Windows NT (\d+[\.\d]*)", re.IGNORECASE), "Windows"),
    (re.compile(r"Mac OS X (\d+[_\.\d]*)", re.IGNORECASE), "macOS"),
    (re.compile(r"Android (\d+[\.\d]*)", re.IGNORECASE), "Android"),
    (re.compile(r"(?:iPhone|iPad|iOS) OS (\d+[_\.\d]*)", re.IGNORECASE), "iOS"),
    (re.compile(r"Linux", re.IGNORECASE), "Linux"),
]

# Windows 版本映射
_WINDOWS_VERSIONS = {
    "5.1": "XP",
    "6.0": "Vista",
    "6.1": "7",
    "6.2": "8",
    "6.3": "8.1",
    "10.0": "10/11",
}

# 设备类型
_MOBILE_PATTERN = re.compile(r"Mobile|Android.*Mobile|iPhone|iPod", re.IGNORECASE)
_TABLET_PATTERN = re.compile(r"Tablet|iPad|Android(?!.*Mobile)", re.IGNORECASE)


class UAParseResult:
    """UA 解析结果"""

    __slots__ = ("browser", "browser_version", "os", "os_version", "device_type")

    def __init__(
        self,
        browser: Optional[str] = None,
        browser_version: Optional[str] = None,
        os: Optional[str] = None,
        os_version: Optional[str] = None,
        device_type: Optional[str] = None,
    ):
        self.browser = browser
        self.browser_version = browser_version
        self.os = os
        self.os_version = os_version
        self.device_type = device_type

    def to_dict(self) -> dict:
        return {
            "browser": self.browser,
            "browser_version": self.browser_version,
            "os": self.os,
            "os_version": self.os_version,
            "device_type": self.device_type,
        }


def parse_user_agent(ua: Optional[str]) -> UAParseResult:
    """解析 User-Agent 字符串

    Args:
        ua: 原始 User-Agent 字符串

    Returns:
        UAParseResult 包含浏览器、操作系统、设备类型信息
    """
    if not ua or not ua.strip():
        return UAParseResult(device_type="unknown")

    ua = ua.strip()

    # Bot 检测
    if _BOT_PATTERN.search(ua):
        return UAParseResult(browser="Bot", device_type="bot")

    # 浏览器识别
    browser = None
    browser_version = None
    for pattern, name in _BROWSER_PATTERNS:
        match = pattern.search(ua)
        if match:
            browser = name
            # 取第一个非空捕获组
            browser_version = next((g for g in match.groups() if g), None)
            break

    # 操作系统识别
    os_name = None
    os_version = None
    for pattern, name in _OS_PATTERNS:
        match = pattern.search(ua)
        if match:
            os_name = name
            raw_version = next((g for g in match.groups() if g), None)
            if raw_version:
                raw_version = raw_version.replace("_", ".")
                # Windows 特殊映射
                if name == "Windows":
                    os_version = _WINDOWS_VERSIONS.get(raw_version, raw_version)
                else:
                    os_version = raw_version
            break

    # 设备类型
    if _TABLET_PATTERN.search(ua):
        device_type = "tablet"
    elif _MOBILE_PATTERN.search(ua):
        device_type = "mobile"
    else:
        device_type = "pc"

    return UAParseResult(
        browser=browser,
        browser_version=browser_version,
        os=os_name,
        os_version=os_version,
        device_type=device_type,
    )
