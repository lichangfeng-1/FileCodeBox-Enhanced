import unittest

from core.webhook import validate_webhook_url


class WebhookUrlValidationTests(unittest.TestCase):
    def test_valid_https_url(self):
        self.assertIsNone(validate_webhook_url("https://example.com/webhook"))

    def test_valid_http_url(self):
        self.assertIsNone(validate_webhook_url("http://api.example.com:8080/hook"))

    def test_rejects_ftp_scheme(self):
        self.assertIsNotNone(validate_webhook_url("ftp://example.com/file"))

    def test_rejects_localhost(self):
        self.assertIsNotNone(validate_webhook_url("http://localhost/hook"))

    def test_rejects_127_0_0_1(self):
        self.assertIsNotNone(validate_webhook_url("http://127.0.0.1:8000/hook"))

    def test_rejects_10_x(self):
        self.assertIsNotNone(validate_webhook_url("http://10.0.0.1/hook"))

    def test_rejects_172_16(self):
        self.assertIsNotNone(validate_webhook_url("http://172.16.0.1/hook"))

    def test_rejects_192_168(self):
        self.assertIsNotNone(validate_webhook_url("http://192.168.1.100/hook"))

    def test_rejects_link_local(self):
        self.assertIsNotNone(validate_webhook_url("http://169.254.1.1/hook"))

    def test_rejects_local_domain(self):
        self.assertIsNotNone(validate_webhook_url("http://myhost.local/hook"))

    def test_rejects_internal_domain(self):
        self.assertIsNotNone(validate_webhook_url("http://app.internal/hook"))

    def test_rejects_empty_url(self):
        self.assertIsNotNone(validate_webhook_url(""))

    def test_rejects_no_host(self):
        self.assertIsNotNone(validate_webhook_url("http:///path"))

    def test_allows_public_ip(self):
        self.assertIsNone(validate_webhook_url("https://203.0.113.50/webhook"))

    def test_allows_subdomain(self):
        self.assertIsNone(validate_webhook_url("https://hooks.myapp.com/fcb"))


if __name__ == "__main__":
    unittest.main()
