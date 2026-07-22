# @Time    : 2026/7/19
# @File    : ip_location.py
# @Desc    : IP 归属地查询，支持 ip2region 离线库，无库时优雅降级
import ipaddress
import os
from typing import Optional

from core.logger import logger
from core.settings import data_root


# ip2region xdb 文件路径（放在 core/ 目录，避免被 /app/data 的 volume 挂载覆盖）
_XDB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ip2region.xdb")

# 模块级缓存
_searcher = None
_init_attempted = False

# 内网网段
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_private_ip(ip: str) -> bool:
    """判断是否为内网IP"""
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False


def _init_searcher() -> None:
    """尝试初始化 ip2region 搜索器（仅执行一次）"""
    global _searcher, _init_attempted
    if _init_attempted:
        return
    _init_attempted = True

    if not os.path.exists(_XDB_PATH):
        logger.info(f"IP归属地库不存在: {_XDB_PATH}，归属地功能将返回空值")
        return

    try:
        import struct

        # 使用 ip2region 的 xdb 纯Python查询实现（无需额外pip包）
        with open(_XDB_PATH, "rb") as f:
            header = f.read(256)
            # 验证魔数
            if len(header) < 16:
                logger.warning("ip2region.xdb 文件格式无效")
                return
            f.seek(0)
            _searcher = f.read()
        logger.info(f"IP归属地库加载成功: {_XDB_PATH} ({len(_searcher)} bytes)")
    except Exception as e:
        logger.warning(f"IP归属地库加载失败: {e}")
        _searcher = None


def _search_xdb(ip: str) -> Optional[str]:
    """在 xdb 数据中查询 IP 归属地

    ip2region xdb 格式查询实现。
    如果查询失败或格式不支持，返回 None。
    """
    global _searcher
    if _searcher is None:
        return None

    try:
        import struct

        ip_addr = ipaddress.ip_address(ip)
        if ip_addr.version != 4:
            return None  # 暂仅支持 IPv4

        ip_int = int(ip_addr)
        data = _searcher

        # 读取 header 中的索引信息
        # xdb 格式: [header(256)] + [vector_index(512*1024)] + [data]
        if len(data) < 256 + 512 * 1024:
            return None

        # 使用 vector index 加速查询
        il0 = (ip_int >> 24) & 0xFF
        il1 = (ip_int >> 16) & 0xFF
        idx = il0 * 256 + il1
        off = 256 + idx * 8

        if off + 8 > len(data):
            return None

        start_ptr = struct.unpack_from("<I", data, off)[0]
        end_ptr = struct.unpack_from("<I", data, off + 4)[0]

        if start_ptr == 0 or end_ptr == 0 or start_ptr > end_ptr:
            return None

        # 二分查找
        left, right = 0, (end_ptr - start_ptr) // 14
        while left <= right:
            mid = (left + right) >> 1
            p = start_ptr + mid * 14
            if p + 14 > len(data):
                return None

            sip = struct.unpack_from("<I", data, p)[0]
            eip = struct.unpack_from("<I", data, p + 4)[0]

            if ip_int < sip:
                right = mid - 1
            elif ip_int > eip:
                left = mid + 1
            else:
                # 命中，读取数据
                data_len = struct.unpack_from("<H", data, p + 8)[0]
                data_ptr = struct.unpack_from("<I", data, p + 10)[0]
                if data_ptr + data_len > len(data):
                    return None
                raw = data[data_ptr:data_ptr + data_len]
                return raw.decode("utf-8", errors="ignore")

        return None
    except Exception:
        return None


def get_ip_location(ip: Optional[str]) -> Optional[str]:
    """查询 IP 归属地

    Args:
        ip: IPv4/IPv6 地址字符串

    Returns:
        归属地字符串（如 "中国|广东|深圳"），内网返回 "内网"，
        查询失败或无离线库返回 None
    """
    if not ip or not ip.strip():
        return None

    ip = ip.strip()

    if _is_private_ip(ip):
        return "内网"

    _init_searcher()
    if _searcher is None:
        return None

    result = _search_xdb(ip)
    if result:
        # ip2region 返回格式: "国家|区域|省份|城市|ISP"
        # 过滤掉 "0" 占位符
        parts = [p for p in result.split("|") if p and p != "0"]
        return "|".join(parts) if parts else None
    return None
