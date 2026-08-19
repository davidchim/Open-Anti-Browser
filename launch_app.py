from __future__ import annotations

import argparse
import atexit
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
from uvicorn import Config, Server

from backend.config import APP_ROOT, ASSETS_DIR, FRONTEND_DIST_DIR
from backend.main import app
from backend._g import _7 as _0x2f
from backend.runtime_control import clear_backend_only_state, find_available_port as find_backend_port, write_backend_only_state
from backend.ui_bridge import register_directory_picker_callback, register_exit_callback


APP_TITLE = "Open-Anti-Browser · 开源指纹浏览器"
DESKTOP_SOFTWARE_RENDERING_MARKER = APP_ROOT / "data" / "desktop-software-rendering.flag"
DESKTOP_LOG_PATH = APP_ROOT / "data" / "desktop.log"


def find_available_port(preferred: int = 8000, span: int = 20) -> int:
    for port in range(preferred, preferred + span):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"没有找到可用端口，请先关闭占用 {preferred}~{preferred + span - 1} 的程序。")


def wait_for_port(port: int, timeout: float = 20.0) -> None:
    stop_at = time.time() + timeout
    while time.time() < stop_at:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError("本地服务启动超时。")


def _write_desktop_log(message: str) -> None:
    try:
        DESKTOP_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if DESKTOP_LOG_PATH.exists() and DESKTOP_LOG_PATH.stat().st_size > 512 * 1024:
            tail = DESKTOP_LOG_PATH.read_bytes()[-256 * 1024:]
            DESKTOP_LOG_PATH.write_bytes(tail)
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        with DESKTOP_LOG_PATH.open("a", encoding="utf-8") as stream:
            stream.write(f"[{timestamp}] {message}\n")
    except OSError:
        pass


def _frontend_build_token() -> str:
    index_path = FRONTEND_DIST_DIR / "index.html"
    try:
        return hashlib.sha256(index_path.read_bytes()).hexdigest()[:12]
    except OSError:
        return "missing"


def desktop_shell_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/?shell=desktop&build={_frontend_build_token()}"


def resolve_window_icon_path() -> Path | None:
    candidates = [
        ASSETS_DIR / "app.ico",
        ASSETS_DIR / "logo-512.png",
        FRONTEND_DIST_DIR / "logo.png",
        FRONTEND_DIST_DIR / "logo.jpeg",
        Path(__file__).resolve().parent / "frontend" / "public" / "logo.png",
        Path(__file__).resolve().parent / "frontend" / "public" / "logo.jpeg",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def build_server(port: int) -> tuple[Server, threading.Thread]:
    config = Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
        log_config=None,
    )
    server = Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread


def _desktop_instance_server_name() -> str:
    identity = str(Path(sys.argv[0]).resolve()).lower()
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]
    return f"OpenAntiBrowserDesktop_{digest}"


def _desktop_chromium_flags() -> list[str]:
    desired_flags = [
        "--disable-features=CalculateNativeWinOcclusion,BackForwardCache",
    ]
    if _desktop_qt_opengl_backend() == "software":
        desired_flags.extend(["--disable-gpu", "--disable-gpu-compositing"])
    current_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip().split()
    merged_flags = [flag for flag in current_flags if flag]
    existing_flags = set(merged_flags)
    for flag in desired_flags:
        if flag not in existing_flags:
            merged_flags.append(flag)
            existing_flags.add(flag)
    return merged_flags


def _desktop_qt_opengl_backend() -> str:
    override = str(os.environ.get("OAB_DESKTOP_QT_OPENGL") or "").strip().lower()
    if override in {"software", "desktop", "angle"}:
        return override
    if DESKTOP_SOFTWARE_RENDERING_MARKER.exists():
        return "software"
    return "angle"


def _configure_desktop_webview_env() -> None:
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(_desktop_chromium_flags()).strip()
    os.environ["QT_OPENGL"] = _desktop_qt_opengl_backend()


def _sampled_colors_look_blank(samples: list[tuple[int, int, int]], threshold: float = 0.985) -> bool:
    if not samples:
        return True
    buckets = Counter((red // 16, green // 16, blue // 16) for red, green, blue in samples)
    return max(buckets.values()) / len(samples) >= threshold


def _desktop_restart_command(*arguments: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *arguments]
    return [sys.executable, str(Path(__file__).resolve()), *arguments]


def _wait_for_process_exit(pid: int, timeout: float = 20.0) -> None:
    if pid <= 0 or pid == os.getpid():
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and psutil.pid_exists(pid):
        time.sleep(0.15)


def run_backend_only(port: int | None = None) -> int:
    target_port = port or find_backend_port(18000, 20)
    write_backend_only_state(os.getpid(), target_port)
    atexit.register(clear_backend_only_state)
    try:
        server = Server(
            Config(
                app=app,
                host="127.0.0.1",
                port=target_port,
                log_level="warning",
                access_log=False,
                log_config=None,
            )
        )
        server.run()
        return 0
    finally:
        clear_backend_only_state()


def run_desktop() -> int:
    _configure_desktop_webview_env()
    from PySide6.QtCore import QObject, Qt, QTimer, QUrl, QUrlQuery, Signal, Slot
    from PySide6.QtGui import QAction, QCloseEvent, QIcon
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMenu, QMessageBox, QSystemTrayIcon

    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    desktop_backend = _desktop_qt_opengl_backend()
    if desktop_backend == "software":
        QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
    elif desktop_backend == "desktop":
        QApplication.setAttribute(Qt.AA_UseDesktopOpenGL, True)
    elif desktop_backend == "angle" and hasattr(Qt, "AA_UseOpenGLES"):
        QApplication.setAttribute(getattr(Qt, "AA_UseOpenGLES"), True)

    class DirectoryPickerBridge(QObject):
        pick_directory_requested = Signal(str, str)

        def __init__(self, owner: "DesktopMainWindow") -> None:
            super().__init__(owner)
            self.owner = owner
            self._result: str | None = None
            self.pick_directory_requested.connect(self._pick_directory, Qt.BlockingQueuedConnection)

        def pick_directory(self, title: str = "", initial_dir: str = "") -> str | None:
            self._result = None
            self.pick_directory_requested.emit(title, initial_dir)
            return self._result

        @Slot(str, str)
        def _pick_directory(self, title: str, initial_dir: str) -> None:
            start_dir = str(initial_dir or APP_ROOT)
            chosen = QFileDialog.getExistingDirectory(
                self.owner,
                title or "选择扩展文件夹",
                start_dir,
            )
            self._result = chosen or None

    class DesktopWebEnginePage(QWebEnginePage):
        def javaScriptConsoleMessage(self, level, message: str, line_number: int, source_id: str) -> None:
            level_name = getattr(level, "name", str(level))
            if "warning" in level_name.lower() or "error" in level_name.lower():
                _write_desktop_log(
                    f"javascript {level_name}: {message} ({source_id or 'inline'}:{line_number})"
                )

    class DesktopMainWindow(QMainWindow):
        def __init__(self, url: str, server: Server, thread: threading.Thread) -> None:
            super().__init__()
            self.url = url
            self.server = server
            self.server_thread = thread
            self._closing = False
            self._force_exit = False
            self._tray_notified = False
            self._recovering_renderer = False
            self._page_recovery_attempts = 0
            self._load_generation = 0
            self._software_restart_started = False
            self.tray_icon: QSystemTrayIcon | None = None

            self.setWindowTitle(APP_TITLE)
            self.setWindowIcon(window_icon)
            self.resize(1480, 960)
            self.setMinimumSize(1180, 760)

            self.web_profile = QWebEngineProfile(APP_TITLE, self)
            self.web_profile.setPersistentStoragePath(str(APP_ROOT / "data" / "qt-webview"))
            self.web_profile.setCachePath(str(APP_ROOT / "data" / "qt-webview-cache"))
            self.web_profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
            self.web_profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)

            self.browser = QWebEngineView(self)
            self.browser.setPage(DesktopWebEnginePage(self.web_profile, self.browser))
            self.browser.settings().setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            self.browser.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            self.browser.settings().setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
            self.browser.loadFinished.connect(self._handle_load_finished)
            self.browser.page().renderProcessTerminated.connect(self._handle_render_process_terminated)
            self.setCentralWidget(self.browser)
            self.browser.setUrl(QUrl(self.url))

            if QSystemTrayIcon.isSystemTrayAvailable():
                self._create_tray_icon()

        def _create_tray_icon(self) -> None:
            tray = QSystemTrayIcon(window_icon, self)
            tray.setToolTip(APP_TITLE)
            tray.activated.connect(self._handle_tray_activated)

            menu = QMenu()
            open_action = QAction("打开主界面", self)
            open_action.triggered.connect(self.restore_from_tray)
            exit_action = QAction("退出程序", self)
            exit_action.triggered.connect(self.force_exit)
            menu.addAction(open_action)
            menu.addSeparator()
            menu.addAction(exit_action)
            tray.setContextMenu(menu)
            tray.show()
            self.tray_icon = tray

        def _handle_load_finished(self, ok: bool) -> None:
            self._load_generation += 1
            generation = self._load_generation
            _write_desktop_log(f"page load finished: ok={ok}, url={self.browser.url().toString()}")
            if ok:
                self._recovering_renderer = False
                QTimer.singleShot(1800, lambda: self._verify_page_contents(generation))
                return
            if self._closing:
                return
            self._recover_local_page("page-load-failed")

        def _verify_page_contents(self, generation: int) -> None:
            if self._closing or generation != self._load_generation:
                return
            script = """
                (() => {
                    const app = document.getElementById('app');
                    return JSON.stringify({
                        ready: Boolean(app && app.childElementCount > 0),
                        textLength: (app?.innerText || '').trim().length,
                    });
                })()
            """
            self.browser.page().runJavaScript(
                script,
                lambda result: self._handle_page_probe(generation, result),
            )

        def _handle_page_probe(self, generation: int, result) -> None:
            if self._closing or generation != self._load_generation:
                return
            try:
                probe = json.loads(result) if isinstance(result, str) else result
            except (TypeError, ValueError):
                probe = None
            ready = bool(isinstance(probe, dict) and probe.get("ready") and probe.get("textLength", 0) > 0)
            if not ready:
                _write_desktop_log(f"page probe failed: {result!r}")
                self._recover_local_page("empty-app-root")
                return
            QTimer.singleShot(250, lambda: self._verify_rendered_pixels(generation))

        def _verify_rendered_pixels(self, generation: int) -> None:
            if self._closing or generation != self._load_generation or not self.isVisible():
                return
            pixmap = self.browser.grab()
            image = pixmap.toImage()
            if image.isNull() or image.width() < 20 or image.height() < 20:
                return
            x_step = max(1, image.width() // 30)
            y_step = max(1, image.height() // 20)
            samples = [
                image.pixelColor(x, y).getRgb()[:3]
                for y in range(y_step // 2, image.height(), y_step)
                for x in range(x_step // 2, image.width(), x_step)
            ]
            if _sampled_colors_look_blank(samples):
                _write_desktop_log("page DOM is ready but the window capture is blank")
                self._restart_with_software_rendering("window-capture-blank")

        def _recovery_url(self) -> QUrl:
            url = QUrl(self.url)
            query = QUrlQuery(url)
            query.removeAllQueryItems("recovery")
            query.addQueryItem("recovery", str(time.time_ns()))
            url.setQuery(query)
            return url

        def _recover_local_page(self, reason: str) -> None:
            if self._closing:
                return
            if self._page_recovery_attempts == 0:
                self._page_recovery_attempts += 1
                _write_desktop_log(f"clearing web cache and reloading: reason={reason}")
                self.web_profile.clearHttpCache()
                QTimer.singleShot(350, lambda: self.browser.setUrl(self._recovery_url()))
                return
            if _desktop_qt_opengl_backend() != "software":
                self._restart_with_software_rendering(reason)
                return
            QMessageBox.critical(
                self,
                APP_TITLE,
                "界面自动恢复失败。请重新打开程序；问题记录已保存在程序数据目录。",
            )

        def _restart_with_software_rendering(self, reason: str) -> None:
            if self._closing or self._software_restart_started:
                return
            if _desktop_qt_opengl_backend() == "software":
                self._recover_local_page(reason)
                return
            self._software_restart_started = True
            try:
                DESKTOP_SOFTWARE_RENDERING_MARKER.parent.mkdir(parents=True, exist_ok=True)
                DESKTOP_SOFTWARE_RENDERING_MARKER.write_text(reason, encoding="utf-8")
                command = _desktop_restart_command(
                    "--software-rendering",
                    f"--restart-wait-pid={os.getpid()}",
                )
                creation_flags = 0
                if os.name == "nt":
                    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                subprocess.Popen(command, close_fds=True, creationflags=creation_flags)
                _write_desktop_log(f"restarting with software rendering: reason={reason}")
                if self.tray_icon is not None:
                    self.tray_icon.showMessage(
                        APP_TITLE,
                        "正在切换兼容显示模式并重新打开。",
                        QSystemTrayIcon.Information,
                        2500,
                    )
                self._force_exit = True
                QTimer.singleShot(0, self.close)
            except Exception as exc:
                self._software_restart_started = False
                _write_desktop_log(f"software rendering restart failed: {exc}")
                QMessageBox.critical(self, APP_TITLE, f"界面恢复失败：{exc}")

        def _handle_render_process_terminated(self, termination_status, exit_code: int) -> None:
            if self._closing:
                return
            if self._recovering_renderer:
                return
            self._recovering_renderer = True
            _write_desktop_log(
                f"render process terminated: status={termination_status}, exit_code={exit_code}"
            )
            if _desktop_qt_opengl_backend() != "software":
                self._restart_with_software_rendering("render-process-terminated")
                return
            if self.tray_icon is not None:
                self.tray_icon.showMessage(
                    APP_TITLE,
                    "界面已自动恢复，请继续使用。",
                    QSystemTrayIcon.Warning,
                    2500,
                )
            QTimer.singleShot(450, lambda: self.browser.setUrl(self._recovery_url()))

        def _handle_tray_activated(self, reason) -> None:
            if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
                self.restore_from_tray()

        def restore_from_tray(self) -> None:
            self.showNormal()
            self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
            self.raise_()
            self.activateWindow()

        def force_exit(self) -> None:
            self._force_exit = True
            self.showNormal()
            self.close()

        def closeEvent(self, event: QCloseEvent) -> None:
            if not self._force_exit and self.tray_icon is not None:
                self.hide()
                if not self._tray_notified:
                    self.tray_icon.showMessage(
                        APP_TITLE,
                        "程序已最小化到托盘，可在托盘图标中重新打开或退出。",
                        QSystemTrayIcon.Information,
                        2500,
                    )
                    self._tray_notified = True
                event.ignore()
                return
            self.shutdown()
            event.accept()
            QTimer.singleShot(0, QApplication.instance().quit)

        def shutdown(self) -> None:
            if self._closing:
                return
            self._closing = True
            self.server.should_exit = True
            self.server.force_exit = True
            self.browser.stop()
            if self.tray_icon is not None:
                self.tray_icon.hide()
            self.server_thread.join(timeout=8)

    qt_app = QApplication.instance() or QApplication([])
    qt_app.setApplicationDisplayName(APP_TITLE)
    qt_app.setApplicationName(APP_TITLE)
    qt_app.setQuitOnLastWindowClosed(False)
    icon_path = resolve_window_icon_path()
    window_icon = QIcon(str(icon_path)) if icon_path else QIcon()
    if not window_icon.isNull():
        qt_app.setWindowIcon(window_icon)

    instance_server_name = _desktop_instance_server_name()
    activation_socket = QLocalSocket()
    activation_socket.connectToServer(instance_server_name)
    if activation_socket.waitForConnected(500):
        activation_socket.write(b"activate")
        activation_socket.flush()
        activation_socket.waitForBytesWritten(500)
        activation_socket.disconnectFromServer()
        return 0
    activation_socket.abort()

    instance_server = QLocalServer()
    if not instance_server.listen(instance_server_name):
        QLocalServer.removeServer(instance_server_name)
        if not instance_server.listen(instance_server_name):
            QMessageBox.critical(None, APP_TITLE, "程序实例检测失败，请先关闭已有程序后重试")
            return 1

    try:
        port = find_available_port(8000, 20)
        server, thread = build_server(port)
        wait_for_port(port)
    except Exception as exc:
        QMessageBox.critical(None, APP_TITLE, f"启动失败：\n{exc}")
        return 1

    window = DesktopMainWindow(desktop_shell_url(port), server, thread)
    directory_picker_bridge = DirectoryPickerBridge(window)

    def handle_instance_activation() -> None:
        while instance_server.hasPendingConnections():
            connection = instance_server.nextPendingConnection()
            if connection is None:
                break
            connection.waitForReadyRead(200)
            try:
                connection.readAll()
            except Exception:
                pass
            connection.disconnectFromServer()
        QTimer.singleShot(0, window.restore_from_tray)

    instance_server.newConnection.connect(handle_instance_activation)

    def request_exit_from_api() -> None:
        QTimer.singleShot(0, window.force_exit)

    register_exit_callback(request_exit_from_api)
    register_directory_picker_callback(directory_picker_bridge.pick_directory)
    qt_app.aboutToQuit.connect(window.shutdown)
    qt_app.aboutToQuit.connect(lambda: register_exit_callback(None))
    qt_app.aboutToQuit.connect(lambda: register_directory_picker_callback(None))
    qt_app.aboutToQuit.connect(instance_server.close)
    qt_app.aboutToQuit.connect(lambda: QLocalServer.removeServer(instance_server_name))
    window.show()
    QTimer.singleShot(120, window.activateWindow)
    return qt_app.exec()


def main(argv: list[str] | None = None) -> int:
    _0x2f("runtime")

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--software-rendering", action="store_true")
    parser.add_argument("--restart-wait-pid", type=int, default=None)
    args, _ = parser.parse_known_args(argv)

    if args.restart_wait_pid:
        _wait_for_process_exit(args.restart_wait_pid)
    if args.software_rendering:
        os.environ["OAB_DESKTOP_QT_OPENGL"] = "software"

    if args.backend_only:
        return run_backend_only(args.port)
    return run_desktop()


if __name__ == "__main__":
    raise SystemExit(main())
