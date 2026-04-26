import unittest
from pathlib import Path

from backend.main import open_api


class ApiDocsContentTests(unittest.TestCase):
    def setUp(self):
        self.content = Path(__file__).resolve().parents[1].joinpath(
            "frontend", "src", "components", "ApiDocs.vue"
        ).read_text(encoding="utf-8")

    def test_profile_delete_endpoint_is_documented(self):
        self.assertIn("path: '/profiles/{profile_id}'", self.content)
        self.assertIn("method: 'DELETE'", self.content)
        self.assertIn('curl -X DELETE', self.content)
        self.assertIn("deleteTitle: '删除浏览器配置'", self.content)
        self.assertIn("deleteTitle: 'Delete a browser profile'", self.content)

    def test_profile_delete_endpoint_exists_in_open_api(self):
        routes = [
            (getattr(route, "path", ""), set(getattr(route, "methods", set())))
            for route in open_api.routes
        ]

        self.assertIn(("/profiles/{profile_id}", {"DELETE"}), routes)

    def test_firefox_selenium_ports_are_documented(self):
        self.assertIn("marionette_port", self.content)
        self.assertIn("selenium_port", self.content)
        self.assertIn("runtime.marionette_port", self.content)
        self.assertIn("geckodriver --connect-existing --marionette-port", self.content)


if __name__ == "__main__":
    unittest.main()
