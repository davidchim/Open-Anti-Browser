import tempfile
import unittest
from pathlib import Path

from backend.services.chrome import _build_chrome_proxy_bypass_list
from backend.services.firefox import _write_firefox_user_js
from backend.models import BrowserProfile, ProxyBypassRule
from backend.services.network import build_firefox_no_proxy_list, normalize_bypass_rules


class ProxyBypassDomainTests(unittest.TestCase):
    def test_chrome_proxy_bypass_list_matches_domain_and_subdomains(self):
        result = _build_chrome_proxy_bypass_list([
            "example.com",
            "https://api.test.com/path",
            "*.foo.bar",
            "127.0.0.1:8080",
            "example.com",
        ])

        self.assertEqual(
            result,
            "example.com;*.example.com;api.test.com;*.api.test.com;foo.bar;*.foo.bar;127.0.0.1",
        )

    def test_chrome_proxy_bypass_list_supports_exact_match_mode(self):
        result = _build_chrome_proxy_bypass_list([
            {"domain": "example.com", "match_mode": "exact"},
            {"domain": "test.com", "match_mode": "subdomains"},
        ])

        self.assertEqual(result, "example.com;test.com;*.test.com")

    def test_firefox_no_proxy_list_matches_domain_and_subdomains(self):
        result = build_firefox_no_proxy_list([
            "example.com",
            "sub.test.local",
            "http://localhost:3000",
            "192.168.1.8",
            "example.com",
        ])

        self.assertEqual(
            result,
            "example.com,.example.com,sub.test.local,.sub.test.local,localhost,192.168.1.8",
        )

    def test_firefox_no_proxy_list_supports_exact_match_mode(self):
        result = build_firefox_no_proxy_list([
            {"domain": "example.com", "match_mode": "exact"},
            {"domain": "test.com", "match_mode": "subdomains"},
        ])

        self.assertEqual(result, "example.com,test.com,.test.com")

    def test_legacy_bypass_domain_list_migrates_to_rules(self):
        profile = BrowserProfile.model_validate({
            "engine": "chrome",
            "proxy_bypass_domains": ["example.com", "api.test.com"],
        })

        self.assertEqual(
            [item.model_dump(mode="json") for item in profile.proxy_bypass_rules],
            [
                {"domain": "example.com", "match_mode": "subdomains"},
                {"domain": "api.test.com", "match_mode": "subdomains"},
            ],
        )

    def test_normalize_bypass_rules_accepts_text_and_rule_objects(self):
        self.assertEqual(
            normalize_bypass_rules([
                "https://Example.com/path",
                {"domain": "*.Exact.test", "match_mode": "exact"},
                {"domain": "bad-mode.test", "match_mode": "unknown"},
            ]),
            [
                {"domain": "example.com", "match_mode": "subdomains"},
                {"domain": "exact.test", "match_mode": "exact"},
                {"domain": "bad-mode.test", "match_mode": "subdomains"},
            ],
        )

    def test_bypass_builders_accept_profile_model_rules(self):
        rule = ProxyBypassRule(domain="ipwho.is", match_mode="subdomains")

        self.assertEqual(
            normalize_bypass_rules([rule]),
            [{"domain": "ipwho.is", "match_mode": "subdomains"}],
        )
        self.assertEqual(
            _build_chrome_proxy_bypass_list([rule]),
            "ipwho.is;*.ipwho.is",
        )
        self.assertEqual(
            build_firefox_no_proxy_list([rule]),
            "ipwho.is,.ipwho.is",
        )

    def test_firefox_user_js_writes_no_proxy_list(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            user_js = Path(temp_dir) / "user.js"
            _write_firefox_user_js(
                user_js,
                browser_proxy="http://127.0.0.1:7890",
                width=1440,
                height=900,
                has_extensions=False,
                no_proxy_list="example.com,.example.com",
            )

            content = user_js.read_text(encoding="utf-8")

        self.assertIn('user_pref("network.proxy.no_proxies_on", "example.com,.example.com");', content)

    def test_frontend_profile_form_has_bypass_domain_config(self):
        store_content = Path(__file__).resolve().parents[1].joinpath(
            "frontend", "src", "stores", "profile.js"
        ).read_text(encoding="utf-8")
        dialog_content = Path(__file__).resolve().parents[1].joinpath(
            "frontend", "src", "components", "ProfileDialog.vue"
        ).read_text(encoding="utf-8")

        self.assertIn("proxy_bypass_rules", store_content)
        self.assertIn("bypassDomains", dialog_content)
        self.assertIn("bypassDomainsText", dialog_content)
        self.assertIn("exportBypassRules", dialog_content)
        self.assertIn("handleBypassImport", dialog_content)
        self.assertIn("result = upsertBypassRuleToList(result, rule)", dialog_content)


if __name__ == "__main__":
    unittest.main()
