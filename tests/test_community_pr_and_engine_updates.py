from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.browser_manager import BrowserManager, ProfileNameConflictError, _fetch_ws_debugger_url
from backend.config import CHROME_INSTALLER_URL, ENGINE_METADATA, FIREFOX_INSTALLER_URL
from backend.main import _attach_cdp_proxy_url, app, open_api
from backend.models import BrowserProfile
from backend.services.network import normalize_proxy_config, proxy_to_profile_proxy
from backend.storage import JsonStorage


class _TempJsonStorage(JsonStorage):
    def __init__(self, root: str) -> None:
        super().__init__()
        self.data_dir = Path(root)
        self.downloads_dir = self.data_dir / "downloads"
        self.settings_file = self.data_dir / "settings.json"
        self.profiles_file = self.data_dir / "profiles.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)


class _Request:
    class _Url:
        scheme = "http"
        netloc = "127.0.0.1:8000"

    url = _Url()


class CommunityPullRequestTests(unittest.TestCase):
    def test_proxy_url_is_accepted_by_profile_model(self):
        profile = BrowserProfile.model_validate({
            "proxy": "socks5://user%40mail:p%3Ass@[2001:db8::1]:1080",
        })

        self.assertEqual(profile.proxy.type, "socks5")
        self.assertEqual(profile.proxy.host, "2001:db8::1")
        self.assertEqual(profile.proxy.port, 1080)
        self.assertEqual(profile.proxy.username, "user@mail")
        self.assertEqual(profile.proxy.password, "p:ss")

        normalized = proxy_to_profile_proxy(profile.proxy.model_dump(mode="json"))
        self.assertEqual(normalized["server"], "socks5://[2001:db8::1]:1080")
        self.assertEqual(
            normalized["request_proxy"],
            "socks5h://user%40mail:p%3Ass@[2001:db8::1]:1080",
        )

    def test_proxy_url_without_scheme_defaults_to_http(self):
        normalized = normalize_proxy_config("127.0.0.1:8080")

        self.assertEqual(normalized["scheme"], "http")
        self.assertEqual(normalized["host"], "127.0.0.1")
        self.assertEqual(normalized["port"], 8080)

    def test_create_and_start_removes_profile_when_launch_fails(self):
        with TemporaryDirectory() as temp_dir:
            manager = BrowserManager()
            manager.storage = _TempJsonStorage(temp_dir)

            with patch.object(manager, "start_profile", side_effect=FileNotFoundError("missing engine")):
                with self.assertRaises(FileNotFoundError):
                    manager.create_and_start_profile("task-1", "http://127.0.0.1:8080")

            self.assertEqual(manager.storage.load_profiles(), [])

    def test_create_and_start_reports_duplicate_task_id_as_conflict(self):
        with TemporaryDirectory() as temp_dir:
            manager = BrowserManager()
            manager.storage = _TempJsonStorage(temp_dir)
            manager.save_profile({"name": "task-1", "engine": "chrome"})

            with self.assertRaises(ProfileNameConflictError):
                manager.create_and_start_profile("task-1", "http://127.0.0.1:8080")

    def test_cdp_proxy_url_is_only_attached_to_chrome(self):
        request = _Request()
        chrome = _attach_cdp_proxy_url(request, {"id": "chrome-1", "engine": "chrome", "debug_url": "old"})
        firefox = _attach_cdp_proxy_url(request, {"id": "firefox-1", "engine": "firefox", "debug_url": "bidi"})

        self.assertEqual(chrome["debug_url"], "ws://127.0.0.1:8000/ws/cdp/chrome-1")
        self.assertEqual(firefox["debug_url"], "bidi")

    def test_new_open_api_routes_are_registered(self):
        routes = {
            (getattr(route, "path", ""), frozenset(getattr(route, "methods", set())))
            for route in open_api.routes
        }

        self.assertIn(("/profiles", frozenset({"DELETE"})), routes)
        self.assertIn(("/profiles/create-and-start", frozenset({"POST"})), routes)
        self.assertIn(("/proxy/check-ip", frozenset({"POST"})), routes)

    def test_frontend_shell_is_not_reused_from_an_older_install(self):
        route = next(
            route
            for route in app.routes
            if getattr(route, "path", "") == "/{full_path:path}"
        )
        response = route.endpoint("")

        self.assertEqual(
            response.headers.get("cache-control"),
            "no-store, no-cache, must-revalidate",
        )

    def test_local_cdp_version_endpoint_is_read_with_curl_cffi(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                payload = json.dumps({"webSocketDebuggerUrl": "ws://127.0.0.1/devtools/browser/test"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args: object) -> None:
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.assertEqual(
                _fetch_ws_debugger_url(server.server_port, timeout=2),
                "ws://127.0.0.1/devtools/browser/test",
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class EngineUpdateTests(unittest.TestCase):
    def test_engine_metadata_uses_requested_releases(self):
        self.assertIn("148.0.7778.215", CHROME_INSTALLER_URL)
        self.assertTrue(CHROME_INSTALLER_URL.endswith("installer_x64.exe"))
        self.assertIn("firefox-155.0a1", FIREFOX_INSTALLER_URL)
        self.assertTrue(FIREFOX_INSTALLER_URL.endswith("20260803.zip"))
        self.assertEqual(ENGINE_METADATA["chrome"]["name"], "Fingerprint Chromium 148")
        self.assertEqual(ENGINE_METADATA["firefox"]["name"], "Firefox Fingerprint Browser 155")

    def test_existing_settings_are_migrated_to_new_downloads(self):
        with TemporaryDirectory() as temp_dir:
            storage = _TempJsonStorage(temp_dir)
            settings = storage._default_settings()
            settings.chrome.installer_url = "https://example.invalid/chrome-144.exe"
            settings.firefox.installer_url = "https://example.invalid/firefox-151.exe"
            settings.chrome.download_path = str(storage.downloads_dir / "chrome-144.exe")
            settings.firefox.download_path = str(storage.downloads_dir / "firefox-151.exe")
            storage.save_settings(settings)

            migrated = storage.load_settings()

            self.assertEqual(migrated.chrome.installer_url, CHROME_INSTALLER_URL)
            self.assertEqual(migrated.firefox.installer_url, FIREFOX_INSTALLER_URL)
            self.assertTrue(migrated.chrome.download_path.endswith(ENGINE_METADATA["chrome"]["download_name"]))
            self.assertTrue(migrated.firefox.download_path.endswith(ENGINE_METADATA["firefox"]["download_name"]))


if __name__ == "__main__":
    unittest.main()
