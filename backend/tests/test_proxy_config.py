import ipaddress
import unittest


class ProxyValidationTests(unittest.TestCase):
    """信任代理 IP/CIDR 格式校验测试"""

    def _validate(self, item: str) -> bool:
        """模拟 proxy_update 中的校验逻辑"""
        try:
            if "/" in item:
                ipaddress.ip_network(item, strict=False)
            else:
                ipaddress.ip_address(item)
            return True
        except ValueError:
            return False

    def test_valid_ipv4(self):
        self.assertTrue(self._validate("192.168.1.1"))

    def test_valid_ipv4_cidr(self):
        self.assertTrue(self._validate("10.0.0.0/8"))

    def test_valid_ipv6(self):
        self.assertTrue(self._validate("::1"))

    def test_valid_ipv6_cidr(self):
        self.assertTrue(self._validate("fc00::/7"))

    def test_valid_172_cidr(self):
        self.assertTrue(self._validate("172.16.0.0/12"))

    def test_invalid_text(self):
        self.assertFalse(self._validate("not-an-ip"))

    def test_invalid_out_of_range(self):
        self.assertFalse(self._validate("256.1.1.1"))

    def test_invalid_cidr_prefix(self):
        self.assertFalse(self._validate("10.0.0.0/33"))

    def test_invalid_empty(self):
        self.assertFalse(self._validate(""))

    def test_invalid_partial(self):
        self.assertFalse(self._validate("192.168.1"))


if __name__ == "__main__":
    unittest.main()
