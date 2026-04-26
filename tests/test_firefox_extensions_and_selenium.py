import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from backend.browser_manager import BrowserManager
from backend.models import AppSettings, BrowserProfile, EngineSettings, ManagedExtension, RuntimeSession
from backend.services.firefox import _prepare_firefox_extensions, _write_firefox_user_js, launch_firefox_profile


def _make_settings(temp_dir: Path, managed_extensions=None) -> AppSettings:
    return AppSettings(
        user_data_root=str(temp_dir / "browser-data"),
        chrome=EngineSettings(executable_path="", installer_url="", download_path=""),
        firefox=EngineSettings(executable_path="", installer_url="", download_path=""),
        managed_extensions=list(managed_extensions or []),
    )


def _write_xpi(path: Path, addon_id: str = "yescaptcha@example.com") -> Path:
    manifest = {
        "manifest_version": 2,
        "name": "YesCaptcha Assistant",
        "version": "0.3.2",
        "browser_specific_settings": {"gecko": {"id": addon_id}},
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("manifest.json", json.dumps(manifest))
        zip_file.writestr("background.js", "")
    return path


class FirefoxExtensionAndSeleniumTests(unittest.TestCase):
    def test_firefox_xpi_is_installed_with_manifest_addon_id_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            source = _write_xpi(temp_dir / "yescaptcha_assistant-0.3.2.xpi", "yescaptcha@example.com")
            profile = BrowserProfile(engine="firefox")
            profile.firefox.extension_paths = [str(source)]
            user_data_dir = temp_dir / "profile"

            installed = _prepare_firefox_extensions(profile, _make_settings(temp_dir), user_data_dir)

            self.assertEqual(installed, [user_data_dir / "extensions" / "yescaptcha@example.com.xpi"])
            self.assertTrue((user_data_dir / "extensions" / "yescaptcha@example.com.xpi").exists())

    def test_managed_firefox_xpi_uses_manifest_addon_id_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            source = _write_xpi(temp_dir / "uploaded.xpi", "{managed-addon@example.com}")
            managed = ManagedExtension(
                id="managed-1",
                engine="firefox",
                name="Managed",
                stored_path=str(source),
                enabled=True,
            )
            profile = BrowserProfile(engine="firefox")
            user_data_dir = temp_dir / "profile"

            installed = _prepare_firefox_extensions(profile, _make_settings(temp_dir, [managed]), user_data_dir)

            self.assertEqual(installed, [user_data_dir / "extensions" / "{managed-addon@example.com}.xpi"])
            self.assertTrue((user_data_dir / "extensions" / "{managed-addon@example.com}.xpi").exists())

    def test_launch_firefox_profile_exposes_marionette_port_for_selenium(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            firefox_exe = temp_dir / "firefox.exe"
            firefox_exe.write_bytes(b"")
            fake_process = Mock(pid=4321)
            profile = BrowserProfile(engine="firefox")
            app_settings = _make_settings(temp_dir)

            with (
                patch("backend.services.firefox.bundled_engine_executable", return_value=firefox_exe),
                patch("backend.services.firefox.resolve_geo_profile", return_value={
                    "ip": "",
                    "timezone": "Asia/Shanghai",
                    "language": "zh-CN",
                }),
                patch("backend.services.firefox.find_free_port", side_effect=[9333, 2829]),
                patch("backend.services.firefox.subprocess.Popen", return_value=fake_process) as popen,
            ):
                result = launch_firefox_profile(profile, app_settings, temp_dir / "profile")

            command = popen.call_args.args[0]
            self.assertEqual(result["remote_debugging_port"], 9333)
            self.assertEqual(result["marionette_port"], 2829)
            self.assertIn("--remote-debugging-port=9333", command)
            self.assertIn("--marionette", command)
            self.assertIn("--marionette-port", command)
            self.assertIn("2829", command)
            self.assertIn('user_pref("marionette.port", 2829);', (temp_dir / "profile" / "user.js").read_text(encoding="utf-8"))
            self.assertIn('user_pref("marionette.port", 2829);', (temp_dir / "profile" / "prefs.js").read_text(encoding="utf-8"))

    def test_firefox_user_js_writes_marionette_port_when_provided(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            user_js = temp_dir / "user.js"
            _write_firefox_user_js(
                user_js,
                browser_proxy=None,
                width=1440,
                height=900,
                marionette_port=2829,
            )

            self.assertIn('user_pref("marionette.port", 2829);', user_js.read_text(encoding="utf-8"))

    def test_runtime_response_includes_marionette_and_selenium_port_aliases(self):
        manager = BrowserManager()
        profile = BrowserProfile(id="profile-1", engine="firefox", name="firefox")
        session = RuntimeSession(
            profile_id=profile.id,
            engine="firefox",
            pid=4321,
            user_data_dir="D:/tmp/profile",
            executable_path="D:/tmp/firefox.exe",
            command=[],
            remote_debugging_port=9333,
            marionette_port=2829,
        )
        manager.runtime_sessions[profile.id] = {"session": session, "process": Mock()}

        with (
            patch("backend.browser_manager.psutil.pid_exists", return_value=True),
            patch("backend.browser_manager.psutil.Process", return_value=Mock(status=lambda: "running")),
        ):
            payload = manager._profile_response(profile)

        self.assertEqual(payload["runtime"]["marionette_port"], 2829)
        self.assertEqual(payload["marionette_port"], 2829)
        self.assertEqual(payload["selenium_port"], 2829)


if __name__ == "__main__":
    unittest.main()
