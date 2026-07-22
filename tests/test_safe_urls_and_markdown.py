import unittest

from ogma.markdown import render_rule_content
from ogma.safe_urls import ExternalHttpUrl, InternalPath, UnsafeUrl


class SafeUrlAndMarkdownTests(unittest.TestCase):
    def test_external_url_allows_only_http_without_credentials(self) -> None:
        self.assertEqual(
            "https://example.com/path",
            ExternalHttpUrl.parse("https://example.com/path").value,
        )
        for value in (
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "file:///C:/secret.txt",
            "//evil.example/path",
            "https://user:pass@example.com/",
            "https:\\\\evil.example\\path",
        ):
            with self.subTest(value=value):
                with self.assertRaises(UnsafeUrl):
                    ExternalHttpUrl.parse(value)

    def test_internal_path_rejects_protocol_relative_and_backslashes(self) -> None:
        self.assertEqual("/rules?rule=one", InternalPath.parse("/rules?rule=one").value)
        for value in ("//evil.example/path", "\\\\evil.example\\path", "rules/one"):
            with self.subTest(value=value):
                with self.assertRaises(UnsafeUrl):
                    InternalPath.parse(value)

    def test_markdown_does_not_emit_click_xss_or_active_image_source(self) -> None:
        rendered = str(
            render_rule_content(
                "[click](javascript:alert(1))\n\n"
                "![payload](data:image/svg+xml,<svg onload=alert(1)>)"
            )
        )
        self.assertNotIn('href="javascript:', rendered)
        self.assertNotIn('src="data:', rendered)
        self.assertNotIn("<svg", rendered)


if __name__ == "__main__":
    unittest.main()
