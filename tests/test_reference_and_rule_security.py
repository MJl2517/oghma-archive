import unittest

from ogma.errors import ValidationError
from ogma.services.rules import _safe_rule_url


class RuleSecurityTests(unittest.TestCase):
    def test_rule_urls_reject_click_xss(self):
        self.assertEqual(_safe_rule_url("javascript:alert(1)"), "")
        self.assertEqual(_safe_rule_url("file:///C:/secret"), "")
        self.assertEqual(_safe_rule_url("//evil.example"), "")
        with self.assertRaises(ValidationError):
            _safe_rule_url("javascript:alert(1)", reject_invalid=True)
        self.assertEqual(_safe_rule_url("https://example.com/book"), "https://example.com/book")
        self.assertEqual(_safe_rule_url("/resources?book=1"), "/resources?book=1")


if __name__ == "__main__":
    unittest.main()
