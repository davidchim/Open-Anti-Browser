from __future__ import annotations

import json
import queue
import random
import threading
import time
import urllib.request
from collections import deque
from typing import Any, Callable

import websocket


SYNC_EVENT_PREFIX = "__OAB_SYNC__"
SYNC_HEARTBEAT_SECONDS = 1.2
SYNC_DISCOVERY_TIMEOUT = 5
SYNC_COMMAND_TIMEOUT = 6
SYNC_WORKER_QUEUE_LIMIT = 280

MASTER_INJECT_SCRIPT = r"""
(() => {
  if (window.__oabSyncInstalled) {
    return 'installed';
  }

  const prefix = '__OAB_SYNC__';
  const state = {
    lastLocation: location.href,
    inputTimer: null,
    moveFrame: null,
    movePayload: null,
    scrollTimer: null,
    wheelFrame: null,
    wheelPayload: null,
    lastWheelAt: 0,
    suppressScrollUntil: 0,
  };

  const cssEscape = (value) => {
    try {
      if (window.CSS && typeof window.CSS.escape === 'function') {
        return window.CSS.escape(String(value));
      }
    } catch (error) {
      // ignore
    }
    return String(value).replace(/([^a-zA-Z0-9_-])/g, '\\$1');
  };

  const selectorEscape = (value) => String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"');

  const buildSelector = (node) => {
    if (!node || node.nodeType !== 1) {
      return '';
    }
    if (node.id) {
      return `#${cssEscape(node.id)}`;
    }
    const directAttr = node.getAttribute && (node.getAttribute('data-testid') || node.getAttribute('data-test') || node.getAttribute('name'));
    if (directAttr) {
      const attrName = node.getAttribute('data-testid') ? 'data-testid' : (node.getAttribute('data-test') ? 'data-test' : 'name');
      const selector = `${node.localName.toLowerCase()}[${attrName}="${selectorEscape(directAttr)}"]`;
      try {
        if (document.querySelectorAll(selector).length === 1) {
          return selector;
        }
      } catch (error) {
        // ignore
      }
    }

    const parts = [];
    let current = node;
    while (current && current.nodeType === 1 && parts.length < 7) {
      let part = current.localName.toLowerCase();
      if (current.id) {
        part = `#${cssEscape(current.id)}`;
        parts.unshift(part);
        break;
      }
      const nameValue = current.getAttribute && current.getAttribute('name');
      if (nameValue) {
        part += `[name="${selectorEscape(nameValue)}"]`;
      }
      const parent = current.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(item => item.localName === current.localName);
        if (siblings.length > 1) {
          part += `:nth-of-type(${siblings.indexOf(current) + 1})`;
        }
      }
      parts.unshift(part);
      try {
        const selector = parts.join(' > ');
        if (document.querySelectorAll(selector).length === 1) {
          return selector;
        }
      } catch (error) {
        // ignore
      }
      current = current.parentElement;
    }
    return parts.join(' > ');
  };

  const emit = (type, payload) => {
    const body = JSON.stringify({
      type,
      payload,
      href: location.href,
      ts: Date.now(),
    });
    try {
      if (typeof window.__oabSyncBinding === 'function') {
        window.__oabSyncBinding(body);
        return;
      }
    } catch (error) {
      // ignore
    }
    try {
      console.debug(prefix + body);
    } catch (error) {
      // ignore
    }
  };

  const buildPoint = (event) => ({
    x: Number(event.clientX || 0),
    y: Number(event.clientY || 0),
    rx: window.innerWidth ? Number(event.clientX || 0) / window.innerWidth : 0,
    ry: window.innerHeight ? Number(event.clientY || 0) / window.innerHeight : 0,
  });

  const maxScrollTop = () => Math.max(document.documentElement.scrollHeight, document.body.scrollHeight) - window.innerHeight;
  const maxScrollLeft = () => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth;

  document.addEventListener('click', (event) => {
    emit('click', {
      ...buildPoint(event),
      selector: buildSelector(event.target),
      button: Number(event.button || 0),
      ctrlKey: !!event.ctrlKey,
      shiftKey: !!event.shiftKey,
      altKey: !!event.altKey,
      metaKey: !!event.metaKey,
    });
  }, true);

  const emitInput = (type, event) => {
    const target = event.target;
    if (!target || target.nodeType !== 1) return;
    const tag = (target.tagName || '').toLowerCase();
    if (!['input', 'textarea', 'select'].includes(tag) && !target.isContentEditable) {
      return;
    }
    const payload = {
      selector: buildSelector(target),
      tag,
      inputType: target.type || '',
      value: target.isContentEditable ? target.innerText : (typeof target.value === 'string' ? target.value : ''),
      checked: typeof target.checked === 'boolean' ? !!target.checked : null,
    };
    emit(type, payload);
  };

  document.addEventListener('input', (event) => {
    window.clearTimeout(state.inputTimer);
    state.inputTimer = window.setTimeout(() => emitInput('input', event), 40);
  }, true);

  document.addEventListener('change', (event) => {
    emitInput('change', event);
  }, true);

  document.addEventListener('keydown', (event) => {
    const shouldSync = ['Enter', 'Tab', 'Escape'].includes(event.key) || event.ctrlKey || event.metaKey || event.altKey;
    if (!shouldSync) return;
    emit('keydown', {
      selector: buildSelector(event.target),
      key: event.key,
      code: event.code,
      ctrlKey: !!event.ctrlKey,
      shiftKey: !!event.shiftKey,
      altKey: !!event.altKey,
      metaKey: !!event.metaKey,
    });
  }, true);

  const emitScrollState = (target) => {
    if (target && target.nodeType === 1 && target !== document.body && target !== document.documentElement) {
      const selector = buildSelector(target);
      const maxY = Math.max(0, Number(target.scrollHeight || 0) - Number(target.clientHeight || 0));
      const maxX = Math.max(0, Number(target.scrollWidth || 0) - Number(target.clientWidth || 0));
      emit('scroll', {
        mode: 'element',
        selector,
        scrollTop: Number(target.scrollTop || 0),
        scrollLeft: Number(target.scrollLeft || 0),
        ratioX: maxX > 0 ? Number(target.scrollLeft || 0) / maxX : 0,
        ratioY: maxY > 0 ? Number(target.scrollTop || 0) / maxY : 0,
      });
      return;
    }
    emit('scroll', {
      mode: 'window',
      x: Number(window.scrollX || 0),
      y: Number(window.scrollY || 0),
      ratioX: maxScrollLeft() > 0 ? Number(window.scrollX || 0) / maxScrollLeft() : 0,
      ratioY: maxScrollTop() > 0 ? Number(window.scrollY || 0) / maxScrollTop() : 0,
    });
  };

  const scheduleScrollEmit = (target) => {
    window.clearTimeout(state.scrollTimer);
    state.scrollTimer = window.setTimeout(() => {
      emitScrollState(target);
    }, 80);
  };

  const scheduleMoveEmit = (event) => {
    state.movePayload = buildPoint(event);
    if (state.moveFrame) {
      return;
    }
    state.moveFrame = window.requestAnimationFrame(() => {
      state.moveFrame = null;
      if (!state.movePayload) {
        return;
      }
      emit('mouse_move', state.movePayload);
      state.movePayload = null;
    });
  };

  const patchWindowScroll = (name) => {
    const original = window[name];
    if (typeof original !== 'function') {
      return;
    }
    window[name] = function (...args) {
      const result = original.apply(this, args);
      window.setTimeout(() => {
        if (Date.now() >= state.suppressScrollUntil) {
          emitScrollState(null);
        }
      }, 60);
      return result;
    };
  };

  document.addEventListener('mousemove', scheduleMoveEmit, true);
  document.addEventListener('wheel', (event) => {
    state.lastWheelAt = Date.now();
    state.suppressScrollUntil = state.lastWheelAt + 1500;
    const nextPayload = {
      ...buildPoint(event),
      deltaX: Number(event.deltaX || 0),
      deltaY: Number(event.deltaY || 0),
      deltaMode: Number(event.deltaMode || 0),
      ctrlKey: !!event.ctrlKey,
      shiftKey: !!event.shiftKey,
      altKey: !!event.altKey,
      metaKey: !!event.metaKey,
    };
    if (state.wheelPayload) {
      state.wheelPayload.deltaX += nextPayload.deltaX;
      state.wheelPayload.deltaY += nextPayload.deltaY;
      state.wheelPayload.x = nextPayload.x;
      state.wheelPayload.y = nextPayload.y;
      state.wheelPayload.rx = nextPayload.rx;
      state.wheelPayload.ry = nextPayload.ry;
      state.wheelPayload.ctrlKey = nextPayload.ctrlKey;
      state.wheelPayload.shiftKey = nextPayload.shiftKey;
      state.wheelPayload.altKey = nextPayload.altKey;
      state.wheelPayload.metaKey = nextPayload.metaKey;
    } else {
      state.wheelPayload = nextPayload;
    }
    if (state.wheelFrame) {
      return;
    }
    state.wheelFrame = window.requestAnimationFrame(() => {
      state.wheelFrame = null;
      if (!state.wheelPayload) {
        return;
      }
      emit('wheel', state.wheelPayload);
      state.wheelPayload = null;
    });
  }, { capture: true, passive: true });

  document.addEventListener('scroll', (event) => {
    if (Date.now() < state.suppressScrollUntil) {
      return;
    }
    const rawTarget = event.target && event.target !== document ? event.target : null;
    const target = rawTarget && rawTarget.nodeType === 1 ? rawTarget : null;
    scheduleScrollEmit(target);
  }, true);
  patchWindowScroll('scrollTo');
  patchWindowScroll('scrollBy');

  const emitNavigate = () => {
    if (state.lastLocation === location.href) {
      return;
    }
    state.lastLocation = location.href;
    emit('navigate', { url: location.href });
  };

  const patchHistory = (name) => {
    const original = history[name];
    if (typeof original !== 'function') {
      return;
    }
    history[name] = function (...args) {
      const result = original.apply(this, args);
      window.setTimeout(emitNavigate, 0);
      return result;
    };
  };

  patchHistory('pushState');
  patchHistory('replaceState');
  window.addEventListener('hashchange', emitNavigate, true);
  window.addEventListener('popstate', emitNavigate, true);
  window.addEventListener('load', emitNavigate, true);
  window.setInterval(emitNavigate, 700);

  window.__oabSyncInstalled = true;
  return 'installed';
})();
"""


def _http_json(url: str, timeout: float = SYNC_DISCOVERY_TIMEOUT) -> Any:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Open-Anti-Browser-Syncer"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="ignore"))


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


class CdpPageClient:
    def __init__(
        self,
        profile_id: str,
        port: int,
        event_handler: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.profile_id = profile_id
        self.port = int(port)
        self._event_handler = event_handler
        self._lock = threading.RLock()
        self._pending: dict[int, queue.Queue] = {}
        self._message_id = 0
        self._ws: websocket.WebSocket | None = None
        self._recv_thread: threading.Thread | None = None
        self._connected = False
        self._last_error = ""
        self._target: dict[str, Any] = {}
        self._last_seen_at: str | None = None

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return bool(self._connected and self._ws)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "profile_id": self.profile_id,
                "port": self.port,
                "connected": self._connected,
                "target_id": self._target.get("id") or "",
                "target_url": self._target.get("url") or "",
                "target_title": self._target.get("title") or "",
                "last_seen_at": self._last_seen_at,
                "last_error": self._last_error,
            }

    def current_target_id(self) -> str:
        with self._lock:
            return str(self._target.get("id") or "")

    def connect(self, target_id: str | None = None) -> None:
        target = self._discover_target(target_id=target_id)
        ws_url = target.get("webSocketDebuggerUrl")
        if not ws_url:
            raise RuntimeError(f"{self.profile_id} 未找到可用调试页面")

        self.close()
        with self._lock:
            self._target = target
            self._last_error = ""
            self._message_id = 0
            self._pending = {}
            self._ws = websocket.create_connection(
                ws_url,
                timeout=SYNC_DISCOVERY_TIMEOUT,
                enable_multithread=True,
                suppress_origin=True,
            )
            self._ws.settimeout(1)
            self._connected = True
            self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._recv_thread.start()

        self.send("Runtime.enable")
        self.send("Page.enable")
        self._mark_seen()

    def close(self) -> None:
        with self._lock:
            ws = self._ws
            recv_thread = self._recv_thread
            pending = list(self._pending.values())
            self._pending = {}
            self._ws = None
            self._recv_thread = None
            self._connected = False
        for item in pending:
            try:
                item.put_nowait({"error": {"message": "connection_closed"}})
            except Exception:
                pass
        if ws:
            try:
                ws.close()
            except Exception:
                pass
        if recv_thread and recv_thread.is_alive() and recv_thread is not threading.current_thread():
            recv_thread.join(timeout=1)

    def refresh_target(self) -> None:
        try:
            target = self._discover_target()
        except Exception:
            return
        with self._lock:
            self._target.update({
                "url": target.get("url") or self._target.get("url") or "",
                "title": target.get("title") or self._target.get("title") or "",
            })

    def sync_to_current_target(self) -> str:
        target = self._discover_target()
        target_id = str(target.get("id") or "")
        if target_id and target_id != self.current_target_id():
            self.switch_target(target_id)
        return target_id

    def ensure_ready(self) -> None:
        if self.is_connected:
            return
        self.connect()

    def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = SYNC_COMMAND_TIMEOUT,
        wait: bool = True,
    ) -> dict[str, Any]:
        self.ensure_ready()
        response_queue: queue.Queue | None = queue.Queue(maxsize=1) if wait else None
        with self._lock:
            if not self._ws or not self._connected:
                raise RuntimeError(f"{self.profile_id} 调试连接不可用")
            self._message_id += 1
            message_id = self._message_id
            if response_queue:
                self._pending[message_id] = response_queue
            payload = json.dumps({
                "id": message_id,
                "method": method,
                "params": params or {},
            })
            self._ws.send(payload)
        if not response_queue:
            return {}
        try:
            response = response_queue.get(timeout=timeout)
        except queue.Empty as exc:
            with self._lock:
                self._pending.pop(message_id, None)
            raise RuntimeError(f"{self.profile_id} 调试命令超时：{method}") from exc

        if response.get("error"):
            error = response["error"]
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise RuntimeError(f"{self.profile_id} 调试命令失败：{message}")
        return response.get("result") or {}

    def evaluate(self, expression: str) -> Any:
        result = self.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
                "userGesture": True,
            },
        )
        if result.get("exceptionDetails"):
            raise RuntimeError(f"{self.profile_id} 页面脚本执行失败")
        remote_object = result.get("result") or {}
        if "value" in remote_object:
            return remote_object.get("value")
        return remote_object.get("description")

    def dispatch_mouse_event(self, payload: dict[str, Any], wait: bool = True) -> None:
        self.send("Input.dispatchMouseEvent", payload, wait=wait)

    def dispatch_key_event(self, payload: dict[str, Any]) -> None:
        self.send("Input.dispatchKeyEvent", payload)

    def insert_text(self, text: str) -> None:
        self.send("Input.insertText", {"text": text})

    def create_target(self, url: str, background: bool = False) -> str:
        result = self.send("Target.createTarget", {"url": url, "background": bool(background)})
        return str(result.get("targetId") or "")

    def close_target(self, target_id: str) -> None:
        self.send("Target.closeTarget", {"targetId": target_id})

    def activate_target(self, target_id: str) -> None:
        if target_id:
            self.send("Target.activateTarget", {"targetId": target_id})

    def switch_target(self, target_id: str) -> bool:
        target_id = str(target_id or "").strip()
        if not target_id:
            return False
        if self.current_target_id() == target_id and self.is_connected:
            return False
        self.connect(target_id=target_id)
        return True

    def list_targets(self) -> list[dict[str, Any]]:
        payload = _http_json(f"http://127.0.0.1:{self.port}/json/list")
        return payload if isinstance(payload, list) else []

    def navigate(self, url: str) -> None:
        self.send("Page.navigate", {"url": url})
        with self._lock:
            self._target["url"] = url
            self._last_seen_at = _now_iso()

    def get_location(self) -> str:
        value = self.evaluate("location.href")
        if isinstance(value, str):
            with self._lock:
                self._target["url"] = value
        return str(value or "")

    def _mark_seen(self) -> None:
        with self._lock:
            self._last_seen_at = _now_iso()

    def _discover_target(self, target_id: str | None = None) -> dict[str, Any]:
        wanted_id = str(target_id or "").strip()
        for path in ("/json/list", "/json"):
            try:
                payload = _http_json(f"http://127.0.0.1:{self.port}{path}")
            except Exception:
                continue

            targets = payload if isinstance(payload, list) else payload.get("targets") if isinstance(payload, dict) else []
            if not isinstance(targets, list):
                continue
            candidates = []
            for item in targets:
                if not isinstance(item, dict):
                    continue
                if not item.get("webSocketDebuggerUrl"):
                    continue
                target_type = str(item.get("type") or "page").lower()
                if target_type not in {"page", "tab"}:
                    continue
                if str(item.get("url") or "").startswith("devtools://"):
                    continue
                candidates.append(item)
            if wanted_id:
                for item in candidates:
                    if str(item.get("id") or "") == wanted_id:
                        return item
                continue
            if candidates:
                return candidates[0]
        raise RuntimeError(f"{self.profile_id} 未找到调试页面")

    def _recv_loop(self) -> None:
        while True:
            with self._lock:
                ws = self._ws
                connected = self._connected
            if not ws or not connected:
                break
            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as exc:
                with self._lock:
                    self._last_error = str(exc)
                break
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                continue

            if isinstance(payload, dict) and "id" in payload:
                item = None
                with self._lock:
                    item = self._pending.pop(int(payload["id"]), None)
                if item:
                    try:
                        item.put_nowait(payload)
                    except Exception:
                        pass
                continue

            self._mark_seen()
            if self._event_handler and isinstance(payload, dict):
                try:
                    self._event_handler(payload)
                except Exception:
                    continue

        self.close()


class _FollowerWorker:
    def __init__(
        self,
        follower_id: str,
        client_getter: Callable[[], CdpPageClient | None],
        apply_handler: Callable[[CdpPageClient, str, dict[str, Any]], None],
        error_handler: Callable[[str, Exception], None],
    ) -> None:
        self.follower_id = follower_id
        self._client_getter = client_getter
        self._apply_handler = apply_handler
        self._error_handler = error_handler
        self._items: deque[tuple[str, dict[str, Any]]] = deque()
        self._condition = threading.Condition()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.5)

    def submit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._stop_event.is_set():
            return
        item = (event_type, dict(payload))
        with self._condition:
            items = list(self._items)
            if event_type == "mouse_move":
                items = [existing for existing in items if existing[0] != "mouse_move"]
                items.append(item)
            elif event_type == "scroll":
                items = [existing for existing in items if existing[0] not in {"scroll", "wheel"}]
                items.append(item)
            elif event_type == "wheel":
                items = [existing for existing in items if existing[0] not in {"scroll", "mouse_move"}]
                for index in range(len(items) - 1, -1, -1):
                    if items[index][0] == "wheel":
                        items[index] = ("wheel", _merge_wheel_payload(items[index][1], payload))
                        break
                else:
                    items.append(item)
            else:
                items.append(item)
            while len(items) >= SYNC_WORKER_QUEUE_LIMIT:
                items.pop(0)
            self._items = deque(items)
            self._condition.notify()

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            with self._condition:
                if not self._items:
                    self._condition.wait(timeout=0.3)
                if not self._items:
                    continue
                event_type, payload = self._items.popleft()
            client = self._client_getter()
            if not client:
                continue
            try:
                self._apply_handler(client, event_type, payload)
            except Exception as exc:
                self._error_handler(self.follower_id, exc)


def _coerce_sync_options(options: dict[str, Any] | None = None) -> dict[str, bool]:
    payload = dict(options or {})
    defaults = {
        "sync_navigation": True,
        "sync_click": True,
        "sync_input": True,
        "sync_scroll": True,
        "sync_keyboard": True,
        "sync_mouse_move": False,
        "sync_current_url_on_start": True,
        "sync_browser_ui": True,
    }
    for key, value in defaults.items():
        payload[key] = bool(payload.get(key, value))
    return payload


class BrowserSynchronizer:
    def __init__(
        self,
        runtime_resolver: Callable[[str], dict[str, Any] | None],
        profile_resolver: Callable[[str], dict[str, Any] | None],
    ) -> None:
        self._runtime_resolver = runtime_resolver
        self._profile_resolver = profile_resolver
        self._lock = threading.RLock()
        self._session: _SyncSession | None = None

    def start(self, master_profile_id: str, follower_profile_ids: list[str], options: dict[str, Any] | None = None) -> dict[str, Any]:
        master_profile_id = str(master_profile_id or "").strip()
        if not master_profile_id:
            raise ValueError("请选择主浏览器")
        follower_ids = [str(item).strip() for item in follower_profile_ids if str(item).strip()]
        follower_ids = list(dict.fromkeys(item for item in follower_ids if item != master_profile_id))
        if not follower_ids:
            raise ValueError("请至少选择一个跟随浏览器")

        session = _SyncSession(
            runtime_resolver=self._runtime_resolver,
            profile_resolver=self._profile_resolver,
            master_profile_id=master_profile_id,
            follower_profile_ids=follower_ids,
            options=_coerce_sync_options(options),
        )
        session.start()
        with self._lock:
            if self._session:
                self._session.stop()
            self._session = session
        return session.snapshot()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            session = self._session
            self._session = None
        if session:
            session.stop()
        return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            session = self._session
        if not session:
            return {
                "running": False,
                "master_profile_id": None,
                "follower_profile_ids": [],
                "followers": [],
                "options": _coerce_sync_options(),
                "last_event": None,
                "last_error": "",
                "started_at": None,
            }
        if not session.is_running:
            with self._lock:
                if self._session is session:
                    self._session = None
            session.stop()
            return {
                "running": False,
                "master_profile_id": None,
                "follower_profile_ids": [],
                "followers": [],
                "options": _coerce_sync_options(),
                "last_event": session.last_event,
                "last_error": session.last_error,
                "started_at": None,
            }
        return session.snapshot()

    def navigate(self, url: str, include_master: bool = True) -> dict[str, Any]:
        url = str(url or "").strip()
        if not url:
            raise ValueError("请输入网址")
        with self._lock:
            session = self._session
        if not session or not session.is_running:
            raise RuntimeError("同步器还没有启动")
        session.navigate(url, include_master=include_master)
        return session.snapshot()

    def sync_master_url(self) -> dict[str, Any]:
        with self._lock:
            session = self._session
        if not session or not session.is_running:
            raise RuntimeError("同步器还没有启动")
        session.sync_master_url_to_followers()
        return session.snapshot()


class _SyncSession:
    def __init__(
        self,
        runtime_resolver: Callable[[str], dict[str, Any] | None],
        profile_resolver: Callable[[str], dict[str, Any] | None],
        master_profile_id: str,
        follower_profile_ids: list[str],
        options: dict[str, bool],
    ) -> None:
        self._runtime_resolver = runtime_resolver
        self._profile_resolver = profile_resolver
        self.master_profile_id = master_profile_id
        self.follower_profile_ids = follower_profile_ids
        self.options = options
        self.started_at = _now_iso()
        self.last_event: dict[str, Any] | None = None
        self.last_error = ""
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._master_client: CdpPageClient | None = None
        self._follower_clients: dict[str, CdpPageClient] = {}
        self._follower_workers: dict[str, _FollowerWorker] = {}
        self._master_target_ids: list[str] = []
        self._master_target_urls: dict[str, str] = {}
        self._master_active_target_id = ""
        self._recent_navigate_urls: deque[str] = deque(maxlen=6)

    @property
    def is_running(self) -> bool:
        return not self._stop_event.is_set()

    def start(self) -> None:
        self._ensure_clients(initial=True)
        self._install_master_script()
        self._refresh_master_target_snapshot()
        if self.options.get("sync_current_url_on_start"):
            self.sync_master_url_to_followers()
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
        self._close_all_clients()

    def snapshot(self) -> dict[str, Any]:
        master_profile = self._profile_resolver(self.master_profile_id) or {}
        master_state = self._master_client.snapshot() if self._master_client else {
            "profile_id": self.master_profile_id,
            "port": None,
            "connected": False,
            "target_url": "",
            "target_title": "",
            "last_seen_at": None,
            "last_error": self.last_error,
        }
        followers = []
        for follower_id in self.follower_profile_ids:
            profile = self._profile_resolver(follower_id) or {}
            client = self._follower_clients.get(follower_id)
            state = client.snapshot() if client else {
                "profile_id": follower_id,
                "port": None,
                "connected": False,
                "target_url": "",
                "target_title": "",
                "last_seen_at": None,
                "last_error": "",
            }
            state.update({
                "name": profile.get("name") or follower_id[:8],
                "engine": profile.get("engine") or "",
                "status": profile.get("status") or "stopped",
            })
            followers.append(state)
        master_state.update({
            "name": master_profile.get("name") or self.master_profile_id[:8],
            "engine": master_profile.get("engine") or "",
            "status": master_profile.get("status") or "stopped",
        })
        return {
            "running": self.is_running,
            "started_at": self.started_at,
            "master_profile_id": self.master_profile_id,
            "master": master_state,
            "follower_profile_ids": list(self.follower_profile_ids),
            "followers": followers,
            "follower_count": len(self.follower_profile_ids),
            "connected_followers": sum(1 for item in followers if item.get("connected")),
            "options": dict(self.options),
            "last_event": self.last_event,
            "last_error": self.last_error,
        }

    def navigate(self, url: str, include_master: bool = True) -> None:
        self._ensure_clients(initial=False)
        if include_master and self._master_client:
            self._master_client.navigate(url)
        for follower_id in self.follower_profile_ids:
            client = self._follower_clients.get(follower_id)
            if not client:
                continue
            try:
                client.navigate(url)
            except Exception as exc:
                self._set_error(f"{self._profile_label(follower_id)} 打开网址失败：{exc}")
        self._record_event("manual_navigate", {"url": url})

    def sync_master_url_to_followers(self) -> None:
        self._ensure_clients(initial=False)
        if not self._master_client:
            raise RuntimeError("主浏览器不可用")
        url = self._master_client.get_location()
        if not url:
            raise RuntimeError("主浏览器当前标签页没有可同步的网址")
        for follower_id in self.follower_profile_ids:
            client = self._follower_clients.get(follower_id)
            if not client:
                continue
            try:
                client.navigate(url)
            except Exception as exc:
                self._set_error(f"{self._profile_label(follower_id)} 同步网址失败：{exc}")
        self._record_event("sync_current_url", {"url": url})

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(SYNC_HEARTBEAT_SECONDS):
            try:
                self._ensure_clients(initial=False)
                self._install_master_script()
                if self._master_client:
                    self._master_client.refresh_target()
                self._sync_browser_ui_changes()
                for client in self._follower_clients.values():
                    client.refresh_target()
            except Exception as exc:
                self._set_error(str(exc))
                if not self._runtime_resolver(self.master_profile_id):
                    self._stop_event.set()
                    break
        self._close_all_clients()

    def _ensure_clients(self, initial: bool) -> None:
        master_runtime = self._runtime_resolver(self.master_profile_id)
        if not master_runtime or not master_runtime.get("remote_debugging_port"):
            raise RuntimeError("主浏览器还没有启动，无法开启同步器")
        self._master_client = self._ensure_client(
            existing=self._master_client,
            profile_id=self.master_profile_id,
            runtime=master_runtime,
            is_master=True,
        )

        for follower_id in list(self.follower_profile_ids):
            runtime = self._runtime_resolver(follower_id)
            if not runtime or not runtime.get("remote_debugging_port"):
                if initial:
                    raise RuntimeError(f"跟随浏览器未启动：{self._profile_label(follower_id)}")
                self._close_follower_client(follower_id)
                continue
            self._follower_clients[follower_id] = self._ensure_client(
                existing=self._follower_clients.get(follower_id),
                profile_id=follower_id,
                runtime=runtime,
                is_master=False,
            )
            self._ensure_follower_worker(follower_id)

    def _ensure_client(
        self,
        existing: CdpPageClient | None,
        profile_id: str,
        runtime: dict[str, Any],
        is_master: bool,
    ) -> CdpPageClient:
        port = int(runtime.get("remote_debugging_port") or 0)
        if not port:
            raise RuntimeError(f"{self._profile_label(profile_id)} 没有可用的调试端口")
        if existing and existing.port == port and existing.is_connected:
            return existing
        if existing:
            existing.close()
        client = CdpPageClient(
            profile_id=profile_id,
            port=port,
            event_handler=self._handle_master_event if is_master else None,
        )
        client.connect()
        return client

    def _ensure_follower_worker(self, follower_id: str) -> None:
        worker = self._follower_workers.get(follower_id)
        if worker:
            return
        worker = _FollowerWorker(
            follower_id=follower_id,
            client_getter=lambda profile_id=follower_id: self._follower_clients.get(profile_id),
            apply_handler=self._apply_event_to_follower,
            error_handler=self._handle_worker_error,
        )
        self._follower_workers[follower_id] = worker
        worker.start()

    def _install_master_script(self) -> None:
        if not self._master_client:
            return
        try:
            self._master_client.send("Runtime.addBinding", {"name": "__oabSyncBinding"})
        except Exception:
            pass
        try:
            self._master_client.evaluate(MASTER_INJECT_SCRIPT)
        except Exception as exc:
            self._set_error(f"同步脚本注入失败：{exc}")

    def _refresh_master_target_snapshot(self) -> None:
        targets = self._list_master_targets()
        self._master_target_ids = [str(item.get("id") or "") for item in targets if item.get("id")]
        self._master_target_urls = {
            str(item.get("id") or ""): str(item.get("url") or "")
            for item in targets
            if item.get("id")
        }
        self._master_active_target_id = self._master_target_ids[0] if self._master_target_ids else ""

    def _list_master_targets(self) -> list[dict[str, Any]]:
        if not self._master_client:
            return []
        try:
            targets = self._master_client.list_targets()
        except Exception as exc:
            self._set_error(f"读取主窗口标签页失败：{exc}")
            return []
        result: list[dict[str, Any]] = []
        for item in targets:
            if not isinstance(item, dict):
                continue
            target_type = str(item.get("type") or "").lower()
            if target_type not in {"page", "tab"}:
                continue
            target_id = str(item.get("id") or "")
            if not target_id:
                continue
            result.append(item)
        return result

    def _sync_browser_ui_changes(self) -> None:
        targets = self._list_master_targets()
        if not targets:
            return
        previous_ids = list(self._master_target_ids)
        previous_urls = dict(self._master_target_urls)
        previous_active_target_id = str(self._master_active_target_id or "")
        current_ids = [str(item.get("id") or "") for item in targets if item.get("id")]
        current_urls = {
            str(item.get("id") or ""): str(item.get("url") or "")
            for item in targets
            if item.get("id")
        }
        active_target_id = current_ids[0] if current_ids else ""
        new_ids = [target_id for target_id in current_ids if target_id and target_id not in previous_ids]

        if self.options.get("sync_browser_ui"):
            for target_id in new_ids:
                self._broadcast_browser_ui_event("browser_new_tab", {
                    "url": current_urls.get(target_id, ""),
                    "activate": target_id == active_target_id,
                })
            if new_ids:
                first_new_id = new_ids[0]
                self._record_event("browser_new_tab", {"url": current_urls.get(first_new_id, ""), "count": len(new_ids)})

            closed_ids = [target_id for target_id in previous_ids if target_id and target_id not in current_ids]
            for _ in closed_ids:
                self._broadcast_browser_ui_event("browser_close_current", {})
            if closed_ids:
                self._record_event("browser_close_current", {"count": len(closed_ids)})

            if previous_active_target_id and active_target_id and active_target_id != previous_active_target_id and active_target_id not in new_ids:
                active_url = current_urls.get(active_target_id, "")
                self._broadcast_browser_ui_event("browser_activate_tab", {"url": active_url})
                self._record_event("browser_activate_tab", {"url": active_url})

        for target_id, url in current_urls.items():
            previous_url = previous_urls.get(target_id, "")
            if url == previous_url:
                continue
            if target_id in new_ids:
                continue
            if _should_sync_browser_url(url):
                self._broadcast_navigation(url)

        self._master_target_ids = current_ids
        self._master_target_urls = current_urls
        if active_target_id and active_target_id != previous_active_target_id:
            if self._switch_master_target(active_target_id):
                self._install_master_script()
        self._master_active_target_id = active_target_id

    def _switch_master_target(self, target_id: str) -> bool:
        if not self._master_client:
            return False
        try:
            return self._master_client.switch_target(target_id)
        except Exception as exc:
            self._set_error(f"切换主控标签页失败：{exc}")
            return False

    def _broadcast_browser_ui_event(self, event_type: str, payload: dict[str, Any]) -> None:
        for follower_id in self.follower_profile_ids:
            client = self._follower_clients.get(follower_id)
            if not client:
                continue
            worker = self._follower_workers.get(follower_id)
            if worker:
                worker.submit(event_type, payload)
                continue
            try:
                self._apply_event_to_follower(client, event_type, payload)
            except Exception as exc:
                self._handle_worker_error(follower_id, exc)

    def _broadcast_navigation(self, url: str) -> None:
        normalized = str(url or "").strip()
        if not normalized:
            return
        if normalized in self._recent_navigate_urls:
            return
        self._recent_navigate_urls.append(normalized)
        self._dispatch_master_event({
            "type": "navigate",
            "payload": {"url": normalized},
        })

    def _handle_master_event(self, payload: dict[str, Any]) -> None:
        method = str(payload.get("method") or "")
        if method == "Runtime.bindingCalled":
            self._handle_binding_event(payload.get("params") or {})
            return
        if method == "Runtime.consoleAPICalled":
            self._handle_console_event(payload.get("params") or {})
            return
        if method == "Page.frameNavigated":
            params = payload.get("params") or {}
            frame = params.get("frame") or {}
            if isinstance(frame, dict) and not frame.get("parentId"):
                url = str(frame.get("url") or "").strip()
                if url and _should_sync_browser_url(url):
                    self._broadcast_navigation(url)
            return
        if method == "Page.navigatedWithinDocument":
            params = payload.get("params") or {}
            url = str(params.get("url") or "").strip()
            if url and _should_sync_browser_url(url):
                self._broadcast_navigation(url)
            return
        if method == "Page.loadEventFired":
            return

    def _handle_binding_event(self, params: dict[str, Any]) -> None:
        if str(params.get("name") or "") != "__oabSyncBinding":
            return
        event = _decode_sync_event(params.get("payload"))
        if event:
            self._dispatch_master_event(event)

    def _handle_console_event(self, params: dict[str, Any]) -> None:
        args = params.get("args") or []
        if not args:
            return
        first = args[0]
        if not isinstance(first, dict):
            return
        event = _decode_sync_event(first.get("value"))
        if event:
            self._dispatch_master_event(event)

    def _dispatch_master_event(self, event: dict[str, Any]) -> None:
        event_type = str(event.get("type") or "").strip().lower()
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        page_url = str(event.get("href") or "").strip()
        if page_url:
            payload = {**payload, "page_url": page_url}

        option_map = {
            "navigate": "sync_navigation",
            "click": "sync_click",
            "input": "sync_input",
            "change": "sync_input",
            "wheel": "sync_scroll",
            "scroll": "sync_scroll",
            "keydown": "sync_keyboard",
            "mouse_move": "sync_mouse_move",
        }
        option_key = option_map.get(event_type)
        if option_key and not self.options.get(option_key):
            return

        for follower_id in self.follower_profile_ids:
            client = self._follower_clients.get(follower_id)
            if not client:
                continue
            worker = self._follower_workers.get(follower_id)
            if worker:
                worker.submit(event_type, payload)
            else:
                try:
                    self._apply_event_to_follower(client, event_type, payload)
                except Exception as exc:
                    self._handle_worker_error(follower_id, exc)
        self._record_event(event_type, payload)

    def _apply_event_to_follower(self, client: CdpPageClient, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == "browser_new_tab":
            self._open_follower_tab(client, payload)
            return
        if event_type == "browser_activate_tab":
            self._activate_follower_tab(client, payload)
            return
        if event_type == "browser_close_current":
            current_id = ""
            try:
                current_id = client.sync_to_current_target()
            except Exception:
                current_id = client.current_target_id()
            if not current_id:
                targets = client.list_targets()
                for item in targets:
                    if not isinstance(item, dict):
                        continue
                    target_id = str(item.get("id") or "")
                    target_type = str(item.get("type") or "").lower()
                    if target_id and target_type in {"page", "tab"}:
                        current_id = target_id
                        break
            if current_id:
                client.close_target(current_id)
            return

        self._align_follower_target_for_payload(client, payload)
        if event_type == "navigate":
            url = str(payload.get("url") or "").strip()
            if url:
                client.navigate(url)
            return
        if event_type == "wheel":
            client.dispatch_mouse_event(_build_wheel_payload(payload), wait=False)
            return
        if event_type == "mouse_move":
            client.dispatch_mouse_event(_build_mouse_move_payload(payload), wait=False)
            return
        if event_type == "click":
            self._sleep_for_sync_delay("click")
            point = client.evaluate(_resolve_click_point_expression(payload))
            if not isinstance(point, dict) or not point.get("ok"):
                return
            for event_payload in _build_click_mouse_events({**payload, **point}):
                wait = event_payload.get("type") == "mouseReleased"
                client.dispatch_mouse_event(event_payload, wait=wait)
            return
        if event_type in {"input", "change"}:
            self._sleep_for_sync_delay("input")
            client.evaluate(_build_input_expression(payload))
            return
        if event_type == "scroll":
            client.evaluate(_build_scroll_expression(payload))
            return
        if event_type == "keydown":
            client.evaluate(_build_key_expression(payload))
            return

    def _align_follower_target_for_payload(self, client: CdpPageClient, payload: dict[str, Any]) -> None:
        if not self.options.get("sync_browser_ui"):
            return
        page_url = str(payload.get("page_url") or "").strip()
        if not page_url:
            return
        target_id = self._find_matching_target_id(client, page_url)
        if not target_id:
            return
        if target_id == client.current_target_id():
            return
        try:
            client.activate_target(target_id)
        except Exception:
            pass
        client.switch_target(target_id)

    def _open_follower_tab(self, client: CdpPageClient, payload: dict[str, Any]) -> None:
        requested_url = str(payload.get("url") or "").strip()
        create_url = self._new_tab_url_for_profile(client.profile_id, requested_url)
        activate = bool(payload.get("activate", True))
        try:
            target_id = client.create_target(create_url, background=not activate)
        except Exception:
            if create_url == "about:blank":
                raise
            target_id = client.create_target("about:blank", background=not activate)
        if activate and target_id:
            try:
                client.activate_target(target_id)
            except Exception:
                pass
            client.switch_target(target_id)

    def _activate_follower_tab(self, client: CdpPageClient, payload: dict[str, Any]) -> None:
        target_id = self._find_matching_target_id(client, str(payload.get("url") or "").strip())
        if not target_id:
            return
        try:
            client.activate_target(target_id)
        except Exception:
            pass
        client.switch_target(target_id)

    def _new_tab_url_for_profile(self, profile_id: str, raw_url: str) -> str:
        url = str(raw_url or "").strip()
        if _should_sync_browser_url(url):
            return url
        profile = self._profile_resolver(profile_id) or {}
        engine = str(profile.get("engine") or "").strip().lower()
        if engine == "firefox":
            return "about:newtab"
        if engine == "chrome":
            return "chrome://newtab/"
        return url or "about:blank"

    def _find_matching_target_id(self, client: CdpPageClient, target_url: str) -> str:
        normalized_url = str(target_url or "").strip()
        if not normalized_url:
            return ""
        candidates = []
        try:
            candidates = client.list_targets()
        except Exception:
            return ""
        target_is_blank = _is_browser_blank_url(normalized_url)
        for item in candidates:
            if not isinstance(item, dict):
                continue
            target_id = str(item.get("id") or "")
            target_type = str(item.get("type") or "").lower()
            if not target_id or target_type not in {"page", "tab"}:
                continue
            candidate_url = str(item.get("url") or "").strip()
            if target_is_blank:
                if _is_browser_blank_url(candidate_url):
                    return target_id
                continue
            if candidate_url == normalized_url:
                return target_id
        return ""

    def _sleep_for_sync_delay(self, delay_type: str) -> None:
        if delay_type == "click":
            enabled = bool(self.options.get("delay_click_enabled"))
            minimum = int(self.options.get("delay_click_min_ms") or 0)
            maximum = int(self.options.get("delay_click_max_ms") or minimum)
        else:
            enabled = bool(self.options.get("delay_input_enabled"))
            minimum = int(self.options.get("delay_input_min_ms") or 0)
            maximum = int(self.options.get("delay_input_max_ms") or minimum)
        if not enabled:
            return
        minimum, maximum = sorted((max(0, minimum), max(0, maximum)))
        delay_ms = random.randint(minimum, maximum) if maximum > minimum else minimum
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)

    def _handle_worker_error(self, follower_id: str, exc: Exception) -> None:
        self._set_error(f"{self._profile_label(follower_id)} 同步失败：{exc}")
        client = self._follower_clients.get(follower_id)
        if client:
            client.close()

    def _record_event(self, event_type: str, payload: dict[str, Any]) -> None:
        summary = ""
        if event_type in {"navigate", "manual_navigate", "sync_current_url"}:
            summary = str(payload.get("url") or "")
        elif event_type in {"click", "input", "change"}:
            summary = str(payload.get("selector") or "") or event_type
        elif event_type == "wheel":
            summary = f"ΔY {int(round(float(payload.get('deltaY') or 0)))}"
        elif event_type == "scroll":
            if payload.get("mode") == "element":
                summary = f"{int(payload.get('scrollLeft') or 0)}, {int(payload.get('scrollTop') or 0)}"
            else:
                summary = f"{int(payload.get('x') or 0)}, {int(payload.get('y') or 0)}"
        elif event_type == "keydown":
            summary = str(payload.get("key") or "")
        elif event_type == "browser_close_current":
            summary = f"已关闭 {int(payload.get('count') or 1)} 个标签页"
        self.last_event = {
            "type": event_type,
            "summary": summary,
            "at": _now_iso(),
        }

    def _set_error(self, message: str) -> None:
        self.last_error = str(message or "").strip()

    def _close_follower_client(self, follower_id: str) -> None:
        worker = self._follower_workers.pop(follower_id, None)
        if worker:
            worker.stop()
        client = self._follower_clients.pop(follower_id, None)
        if client:
            client.close()

    def _close_all_clients(self) -> None:
        if self._master_client:
            self._master_client.close()
            self._master_client = None
        for worker in list(self._follower_workers.values()):
            worker.stop()
        self._follower_workers = {}
        for client in list(self._follower_clients.values()):
            client.close()
        self._follower_clients = {}

    def _profile_label(self, profile_id: str) -> str:
        payload = self._profile_resolver(profile_id) or {}
        return str(payload.get("name") or profile_id[:8])


def _decode_sync_event(raw_payload: Any) -> dict[str, Any] | None:
    if not isinstance(raw_payload, str):
        return None
    value = raw_payload.strip()
    if not value:
        return None
    if value.startswith(SYNC_EVENT_PREFIX):
        value = value[len(SYNC_EVENT_PREFIX):]
    try:
        event = json.loads(value)
    except Exception:
        return None
    if not isinstance(event, dict):
        return None
    return event


def _should_sync_browser_url(url: str) -> bool:
    value = str(url or "").strip()
    if not value:
        return False
    if value.startswith("devtools://"):
        return False
    if _is_browser_blank_url(value):
        return False
    return True


def _is_browser_blank_url(url: str) -> bool:
    value = str(url or "").strip().lower()
    return value in {"about:blank", "about:newtab", "chrome://newtab/", "chrome://new-tab-page/"}


def _mouse_modifiers(payload: dict[str, Any]) -> int:
    modifiers = 0
    if payload.get("altKey"):
        modifiers |= 1
    if payload.get("ctrlKey"):
        modifiers |= 2
    if payload.get("metaKey"):
        modifiers |= 4
    if payload.get("shiftKey"):
        modifiers |= 8
    return modifiers


def _normalize_wheel_delta(delta: float, delta_mode: int) -> float:
    if delta_mode == 1:
        return delta * 40
    if delta_mode == 2:
        return delta * 700
    return delta


def _build_wheel_payload(payload: dict[str, Any]) -> dict[str, Any]:
    x = int(round(float(payload.get("x") or 0)))
    y = int(round(float(payload.get("y") or 0)))
    return {
        "type": "mouseWheel",
        "x": x,
        "y": y,
        "deltaX": float(_normalize_wheel_delta(float(payload.get("deltaX") or 0), int(payload.get("deltaMode") or 0))),
        "deltaY": float(_normalize_wheel_delta(float(payload.get("deltaY") or 0), int(payload.get("deltaMode") or 0))),
        "modifiers": _mouse_modifiers(payload),
        "pointerType": "mouse",
    }


def _build_mouse_move_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "mouseMoved",
        "x": int(round(float(payload.get("x") or 0))),
        "y": int(round(float(payload.get("y") or 0))),
        "modifiers": _mouse_modifiers(payload),
        "button": "none",
        "buttons": 0,
        "pointerType": "mouse",
    }


def _button_name(button: int) -> str:
    mapping = {
        1: "middle",
        2: "right",
    }
    return mapping.get(int(button or 0), "left")


def _button_mask(button: int) -> int:
    mapping = {
        1: 4,
        2: 2,
    }
    return mapping.get(int(button or 0), 1)


def _build_click_mouse_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    x = int(round(float(payload.get("x") or 0)))
    y = int(round(float(payload.get("y") or 0)))
    button = int(payload.get("button") or 0)
    button_name = _button_name(button)
    button_mask = _button_mask(button)
    base = {
        "x": x,
        "y": y,
        "modifiers": _mouse_modifiers(payload),
        "pointerType": "mouse",
    }
    return [
        {
            **base,
            "type": "mouseMoved",
            "button": "none",
            "buttons": 0,
        },
        {
            **base,
            "type": "mousePressed",
            "button": button_name,
            "buttons": button_mask,
            "clickCount": 1,
        },
        {
            **base,
            "type": "mouseReleased",
            "button": button_name,
            "buttons": 0,
            "clickCount": 1,
        },
    ]


def _merge_wheel_payload(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    merged["deltaX"] = float(base.get("deltaX") or 0) + float(incoming.get("deltaX") or 0)
    merged["deltaY"] = float(base.get("deltaY") or 0) + float(incoming.get("deltaY") or 0)
    for key in ("x", "y", "rx", "ry", "deltaMode", "ctrlKey", "shiftKey", "altKey", "metaKey"):
        if key in incoming:
            merged[key] = incoming.get(key)
    return merged


def _resolve_click_point_expression(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"""
(() => {{
  const payload = {data};
  const clampPoint = (point) => ({{
    x: Math.max(1, Math.min(window.innerWidth - 1, Math.round(Number(point.x || 0)))),
    y: Math.max(1, Math.min(window.innerHeight - 1, Math.round(Number(point.y || 0)))),
  }});
  const pickTarget = () => {{
    let target = null;
    if (payload.selector) {{
      try {{
        target = document.querySelector(payload.selector);
      }} catch (error) {{
        target = null;
      }}
    }}
    if (target) return target;
    const fallback = clampPoint({{
      x: Number.isFinite(Number(payload.x)) ? Number(payload.x) : Number(payload.rx || 0) * window.innerWidth,
      y: Number.isFinite(Number(payload.y)) ? Number(payload.y) : Number(payload.ry || 0) * window.innerHeight,
    }});
    return document.elementFromPoint(fallback.x, fallback.y);
  }};
  const target = pickTarget();
  if (!target) return {{ ok: false }};
  target.focus?.();
  const rect = target.getBoundingClientRect();
  if (!rect || rect.width < 1 || rect.height < 1) {{
    const fallback = clampPoint({{
      x: Number.isFinite(Number(payload.x)) ? Number(payload.x) : Number(payload.rx || 0) * window.innerWidth,
      y: Number.isFinite(Number(payload.y)) ? Number(payload.y) : Number(payload.ry || 0) * window.innerHeight,
    }});
    return {{ ok: true, x: fallback.x, y: fallback.y }};
  }}
  const x = rect.left + Math.min(Math.max(1, rect.width / 2), Math.max(1, rect.width - 1));
  const y = rect.top + Math.min(Math.max(1, rect.height / 2), Math.max(1, rect.height - 1));
  const point = clampPoint({{ x, y }});
  return {{ ok: true, x: point.x, y: point.y }};
}})()
"""


def _build_click_expression(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"""
(() => {{
  const payload = {data};
  const pickBySelector = () => {{
    if (!payload.selector) return null;
    try {{
      return document.querySelector(payload.selector);
    }} catch (error) {{
      return null;
    }}
  }};
  let target = pickBySelector();
  if (!target) {{
    const x = Math.max(0, Math.min(window.innerWidth - 1, Math.round(Number(payload.rx || 0) * window.innerWidth)));
    const y = Math.max(0, Math.min(window.innerHeight - 1, Math.round(Number(payload.ry || 0) * window.innerHeight)));
    target = document.elementFromPoint(x, y);
  }}
  if (!target) return false;
  target.focus?.();
  const rect = target.getBoundingClientRect();
  const clientX = rect.left + Math.max(1, rect.width / 2);
  const clientY = rect.top + Math.max(1, rect.height / 2);
  const init = {{
    bubbles: true,
    cancelable: true,
    composed: true,
    view: window,
    clientX,
    clientY,
    button: Number(payload.button || 0),
    ctrlKey: !!payload.ctrlKey,
    shiftKey: !!payload.shiftKey,
    altKey: !!payload.altKey,
    metaKey: !!payload.metaKey,
  }};
  for (const eventName of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {{
    target.dispatchEvent(new MouseEvent(eventName, init));
  }}
  if (typeof target.click === 'function') {{
    target.click();
  }}
  return true;
}})()
"""


def _build_input_expression(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"""
(() => {{
  const payload = {data};
  if (!payload.selector) return false;
  let target = null;
  try {{
    target = document.querySelector(payload.selector);
  }} catch (error) {{
    target = null;
  }}
  if (!target) return false;
  target.focus?.();
  if (payload.tag === 'select') {{
    target.value = payload.value ?? '';
    target.dispatchEvent(new Event('change', {{ bubbles: true }}));
    return true;
  }}
  if (payload.inputType === 'checkbox' || payload.inputType === 'radio') {{
    target.checked = !!payload.checked;
    target.dispatchEvent(new Event('input', {{ bubbles: true }}));
    target.dispatchEvent(new Event('change', {{ bubbles: true }}));
    return true;
  }}
  if (target.isContentEditable) {{
    target.innerText = payload.value ?? '';
  }} else if ('value' in target) {{
    target.value = payload.value ?? '';
  }} else {{
    return false;
  }}
  target.dispatchEvent(new Event('input', {{ bubbles: true }}));
  target.dispatchEvent(new Event('change', {{ bubbles: true }}));
  return true;
}})()
"""


def _build_scroll_expression(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"""
(() => {{
  const payload = {data};
  const pickTarget = () => {{
    if (payload.mode === 'element' && payload.selector) {{
      try {{
        const target = document.querySelector(payload.selector);
        if (target && typeof target.scrollTop === 'number') {{
          return target;
        }}
      }} catch (error) {{
        // ignore
      }}
    }}
    return null;
  }};
  const target = pickTarget();
  if (target) {{
    const maxY = Math.max(0, Number(target.scrollHeight || 0) - Number(target.clientHeight || 0));
    const maxX = Math.max(0, Number(target.scrollWidth || 0) - Number(target.clientWidth || 0));
    const top = Number.isFinite(Number(payload.ratioY)) && maxY > 0 ? Number(payload.ratioY) * maxY : Number(payload.scrollTop || 0);
    const left = Number.isFinite(Number(payload.ratioX)) && maxX > 0 ? Number(payload.ratioX) * maxX : Number(payload.scrollLeft || 0);
    if (typeof target.scrollTo === 'function') {{
      target.scrollTo({{ left, top, behavior: 'auto' }});
    }} else {{
      target.scrollTop = top;
      target.scrollLeft = left;
    }}
    return true;
  }}
  const maxY = Math.max(document.documentElement.scrollHeight, document.body.scrollHeight) - window.innerHeight;
  const maxX = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth;
  const top = Number.isFinite(Number(payload.ratioY)) && maxY > 0 ? Number(payload.ratioY) * maxY : Number(payload.y || 0);
  const left = Number.isFinite(Number(payload.ratioX)) && maxX > 0 ? Number(payload.ratioX) * maxX : Number(payload.x || 0);
  window.scrollTo({{ left, top, behavior: 'auto' }});
  return true;
}})()
"""


def _build_key_expression(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"""
(() => {{
  const payload = {data};
  let target = document.activeElement || document.body;
  if (payload.selector) {{
    try {{
      target = document.querySelector(payload.selector) || target;
    }} catch (error) {{
      // ignore
    }}
  }}
  target.focus?.();
  const init = {{
    key: payload.key || '',
    code: payload.code || '',
    ctrlKey: !!payload.ctrlKey,
    shiftKey: !!payload.shiftKey,
    altKey: !!payload.altKey,
    metaKey: !!payload.metaKey,
    bubbles: true,
    cancelable: true,
  }};
  target.dispatchEvent(new KeyboardEvent('keydown', init));
  target.dispatchEvent(new KeyboardEvent('keyup', init));
  return true;
}})()
"""
