"""Headless Chrome for the end-to-end tests: launch it, attach to a page, drive the page.

`Browser` owns one Chrome process with a throwaway profile and guarantees both are
gone when the tests end, however they end. `Page` is the API scenarios use; it
drives a real tab through the DevTools protocol (`cdp.py`), so clicks and key
presses are trusted events that reach the site's own listeners, exactly as a
reader's would.

Each page lives in its own browser context (its own localStorage, cookies and
caches), which is what makes "a fresh page per test" true.
"""

import atexit
import base64
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import namedtuple
from urllib.parse import urlsplit

from tests.e2e.cdp import CDPError, CDPSession, CDPTimeout

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
)
CHROME_COMMANDS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")

LOOPBACK_HOSTS = frozenset(["127.0.0.1", "localhost", "::1"])
DEFAULT_VIEWPORT = (1280, 800)
STARTUP_TIMEOUT = 30.0
# Chrome cannot rasterise a surface taller than this many device pixels in one
# piece; a taller full-page screenshot is cut off at this height.
MAX_SCREENSHOT_PIXELS = 16000

ConsoleMessage = namedtuple("ConsoleMessage", "type text url line")
FailedRequest = namedtuple("FailedRequest", "url status error method kind")
Dialog = namedtuple("Dialog", "type message")
Download = namedtuple("Download", "filename path")
Key = namedtuple("Key", "key code keycode text shift")


class BrowserError(Exception):
    """Chrome could not be started, reached or made to do what was asked."""


class NavigationError(BrowserError):
    """A navigation failed: the address could not be reached or loaded."""


class LoadTimeout(NavigationError):
    """The page started loading but did not reach the requested load state in time."""


class WaitTimeout(BrowserError):
    """A condition a test waited for never became true."""


class ClickError(BrowserError):
    """An element could not be clicked the way a reader would click it."""


class JSError(Exception):
    """JavaScript evaluated in the page threw. The text is the page's own stack."""

    def __init__(self, name, text):
        super().__init__(text)
        self.name = name


# -- launching ---------------------------------------------------------------


def find_chrome():
    """Return the Chrome binary: CHROME_BIN if set, else the usual macOS and Linux places."""
    override = os.environ.get("CHROME_BIN")
    if override:
        if not os.path.isfile(override):
            raise BrowserError("CHROME_BIN points to {0!r}, which does not exist".format(override))
        return override
    for path in CHROME_CANDIDATES:
        if os.path.isfile(path):
            return path
    for command in CHROME_COMMANDS:
        found = shutil.which(command)
        if found:
            return found
    raise BrowserError(
        "Chrome not found. Install Google Chrome or set CHROME_BIN to the binary. "
        "Looked in: " + ", ".join(CHROME_CANDIDATES)
    )


def chrome_arguments(profile, headless, block_external, viewport):
    """Build the Chrome command-line flags for a quiet, deterministic test browser."""
    flags = [
        "--remote-debugging-port=0",
        "--user-data-dir=" + profile,
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "--hide-scrollbars",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-sync",
        "--disable-default-apps",
        "--disable-search-engine-choice-screen",
        "--disable-features=Translate,MediaRouter,OptimizationHints",
        "--metrics-recording-only",
        # No crash reporter: nothing may be uploaded from a test run, and its helper
        # outlives Chrome and re-creates the profile directory after we delete it.
        "--disable-crash-reporter",
        "--disable-breakpad",
        "--no-pings",
        "--mute-audio",
        # Without these macOS asks for Keychain access on a brand-new profile.
        "--use-mock-keychain",
        "--password-store=basic",
        # Timers and rendering must not slow down because a tab is not in front.
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        # Same colours in screenshots on every machine.
        "--force-color-profile=srgb",
        "--window-size={0},{1}".format(*viewport),
    ]
    if headless:
        flags.append("--headless=new")
    if block_external:
        # Tests must not depend on the internet: every host but this machine fails
        # to resolve, at once, without a packet leaving. The proxy is bypassed
        # because a proxy would resolve the names for us.
        flags.append("--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost")
        flags.append("--no-proxy-server")
    if sys.platform.startswith("linux") and os.geteuid() == 0:
        # Chrome refuses to start its sandbox as root (some CI containers).
        flags.append("--no-sandbox")
    flags.extend(shlex.split(os.environ.get("CHROME_EXTRA_ARGS", "")))
    flags.append("about:blank")
    return flags


class Browser:
    """One Chrome process with a temporary profile, cleaned up on every exit path.

    Use as a context manager. `close()` also runs at interpreter exit, so an
    exception or `sys.exit()` between construction and `with` cannot leak Chrome.
    """

    def __init__(self, headless=True, block_external=True, viewport=DEFAULT_VIEWPORT):
        self.headless = headless
        self.block_external = block_external
        self.viewport = viewport
        self.version = ""
        self.cdp = None
        self._process = None
        self._profile = None
        self._port = None
        atexit.register(self.close)
        try:
            self._launch()
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _launch(self):
        binary = find_chrome()
        self._profile = tempfile.mkdtemp(prefix="firstlight-chrome-")
        self._stderr_path = os.path.join(self._profile, "chrome-stderr.log")
        flags = chrome_arguments(self._profile, self.headless, self.block_external, self.viewport)
        with open(self._stderr_path, "wb") as stderr:
            try:
                # Its own session, so Ctrl-C reaches Python (which then closes Chrome
                # in order) and so the whole process group can be killed at once.
                self._process = subprocess.Popen(
                    [binary] + flags, stdout=subprocess.DEVNULL, stderr=stderr, start_new_session=True
                )
            except OSError as exc:
                raise BrowserError("cannot start Chrome at {0!r}: {1}".format(binary, exc)) from exc
        port, browser_path = self._read_devtools_port()
        self._port = port
        self.cdp = CDPSession("ws://127.0.0.1:{0}{1}".format(port, browser_path))
        self.version = self.cdp.send("Browser.getVersion")["product"]

    def _read_devtools_port(self):
        """Wait for Chrome to write the port it chose into DevToolsActivePort."""
        port_file = os.path.join(self._profile, "DevToolsActivePort")
        deadline = time.monotonic() + STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            code = self._process.poll()
            if code is not None:
                raise BrowserError(
                    "Chrome exited with code {0} during startup.\n{1}".format(code, self._stderr_tail())
                )
            try:
                with open(port_file, "r") as handle:
                    lines = handle.read().split("\n")
            except FileNotFoundError:
                lines = []
            # The file is written in two steps; wait until both lines are there.
            if len(lines) >= 2 and lines[0].isdigit() and lines[1].startswith("/devtools/"):
                return int(lines[0]), lines[1]
            time.sleep(0.02)
        raise BrowserError(
            "Chrome did not open a DevTools port within {0:g}s.\n{1}".format(STARTUP_TIMEOUT, self._stderr_tail())
        )

    def _stderr_tail(self):
        try:
            with open(self._stderr_path, "rb") as handle:
                text = handle.read()[-2000:].decode("utf-8", "replace").strip()
        except OSError as exc:
            return "(Chrome's stderr could not be read: {0})".format(exc)
        if not text:
            return "(Chrome wrote nothing to stderr)"
        hint = ""
        if "sandbox" in text.lower():
            hint = "\nIf this is a container without user namespaces, set CHROME_EXTRA_ARGS=--no-sandbox."
        return "Chrome stderr:\n" + text + hint

    # -- pages -------------------------------------------------------------

    def new_page(self):
        """Open a blank tab in a new, empty browser context and return its `Page`."""
        context_id = self.cdp.send("Target.createBrowserContext", {"disposeOnDetach": True})["browserContextId"]
        try:
            target_id = self.cdp.send(
                "Target.createTarget", {"url": "about:blank", "browserContextId": context_id}
            )["targetId"]
            download_dir = os.path.join(self._profile, "downloads", target_id)
            os.makedirs(download_dir)
            # Without this an "Export" button would write into the user's real
            # Downloads folder.
            self.cdp.send(
                "Browser.setDownloadBehavior",
                {
                    "behavior": "allowAndName",
                    "downloadPath": download_dir,
                    "browserContextId": context_id,
                    "eventsEnabled": True,
                },
            )
            session = CDPSession(self._page_socket_url(target_id))
            return Page(self, session, target_id, context_id, download_dir)
        except BaseException:
            self._discard(None, context_id)
            raise

    def _page_socket_url(self, target_id):
        """Find the new tab in Chrome's /json/list and return its WebSocket URL."""
        # Never through a proxy: the endpoint is on this machine.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        url = "http://127.0.0.1:{0}/json/list".format(self._port)
        deadline = time.monotonic() + 5.0
        while True:
            try:
                with opener.open(url, timeout=5.0) as response:
                    targets = json.load(response)
            except (OSError, ValueError) as exc:
                raise BrowserError("cannot read {0}: {1}".format(url, exc)) from exc
            for target in targets:
                if target.get("id") == target_id and target.get("type") == "page":
                    return target["webSocketDebuggerUrl"]
            if time.monotonic() >= deadline:
                raise BrowserError("new tab {0} never appeared in {1}".format(target_id, url))
            time.sleep(0.02)

    def _discard(self, target_id, context_id):
        """Close a tab and its context. A dead browser has nothing left to close."""
        if self.cdp is None or self.cdp.closed:
            return
        if target_id is not None:
            self.cdp.send("Target.closeTarget", {"targetId": target_id})
        self.cdp.send("Target.disposeBrowserContext", {"browserContextId": context_id})

    @property
    def alive(self):
        """True while Chrome is running and its DevTools connection is open."""
        return (
            self._process is not None
            and self._process.poll() is None
            and self.cdp is not None
            and not self.cdp.closed
        )

    # -- shutdown ----------------------------------------------------------

    def close(self):
        """Stop Chrome and delete the temporary profile. Safe to call repeatedly."""
        atexit.unregister(self.close)
        if self.cdp is not None:
            self.cdp.close()
            self.cdp = None
        if self._process is not None:
            self._stop_process()
            self._process = None
        if self._profile is not None:
            self._remove_profile()
            self._profile = None

    def _stop_process(self):
        """Ask the Chrome process group to quit, then force it.

        Returns only when the whole group is gone: a helper that is still alive
        could write into the profile while it is being deleted.
        """
        for sig in (signal.SIGTERM, signal.SIGKILL):
            if self._group_gone():
                return
            try:
                os.killpg(self._process.pid, sig)
            except ProcessLookupError:
                return  # the last process exited between the check and the signal
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if self._group_gone():
                    return
                time.sleep(0.01)
        sys.stderr.write("warning: Chrome (pid {0}) survived SIGKILL\n".format(self._process.pid))

    def _group_gone(self):
        """True when no process is left in Chrome's process group."""
        self._process.poll()  # reap Chrome itself; a zombie would keep the group alive
        try:
            os.killpg(self._process.pid, 0)
        except (ProcessLookupError, PermissionError):
            # No such group. macOS answers EPERM, not ESRCH, while only zombies remain.
            return True
        return False

    def _remove_profile(self):
        """Delete the profile; Chrome's helpers may still be writing for a moment."""
        for _ in range(20):
            shutil.rmtree(self._profile, ignore_errors=True)
            if not os.path.exists(self._profile):
                return
            time.sleep(0.1)
        sys.stderr.write("warning: could not remove temporary Chrome profile {0}\n".format(self._profile))


# -- JavaScript snippets run in the page ---------------------------------------

_JS_EXISTS = "(sel) => document.querySelector(sel) !== null"

_JS_VISIBLE = """(sel) => {
  const el = document.querySelector(sel);
  if (!el) return false;
  const box = el.getBoundingClientRect();
  return box.width > 0 && box.height > 0 && getComputedStyle(el).visibility !== "hidden";
}"""

# Where a reader would click: the centre of the element, after scrolling it into
# view, and only if the element (not something lying over it) would get the click.
_JS_CLICK_POINT = """(sel) => {
  const el = document.querySelector(sel);
  if (!el) return {problem: "no element matches the selector"};
  el.scrollIntoView({block: "center", inline: "center", behavior: "instant"});
  const box = el.getBoundingClientRect();
  if (box.width === 0 || box.height === 0) return {problem: "the element has no size (hidden?)"};
  if (getComputedStyle(el).visibility === "hidden") return {problem: "the element is not visible"};
  if (el.disabled) return {problem: "the element is disabled"};
  const x = box.left + box.width / 2, y = box.top + box.height / 2;
  if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) {
    return {problem: "the element's centre is outside the viewport"};
  }
  const hit = document.elementFromPoint(x, y);
  if (hit !== el && !el.contains(hit)) {
    const name = !hit ? "nothing" : hit.tagName.toLowerCase() + (hit.id ? "#" + hit.id : "") +
      (typeof hit.className === "string" && hit.className ? "." + hit.className.trim().split(/\\s+/).join(".") : "");
    return {problem: "it is covered by <" + name + ">, which would receive the click"};
  }
  return {x, y};
}"""

_JS_TEXT = "(el) => (el.innerText === undefined ? el.textContent : el.innerText).trim()"

_JS_SELECT_ALL = """(sel) => {
  const el = document.querySelector(sel);
  if (!el || typeof el.select !== "function") {
    throw new Error("fill() needs an <input> or <textarea>, got " + (el ? el.tagName.toLowerCase() : "nothing"));
  }
  el.focus();
  el.select();
  return el.value.length;
}"""

_LIFECYCLE_EVENTS = {
    "load": "load",
    "domcontentloaded": "DOMContentLoaded",
    "networkidle": "networkIdle",
    "commit": None,
}

# -- keyboard ------------------------------------------------------------------

_MODIFIER_BITS = {"Alt": 1, "Control": 2, "Meta": 4, "Shift": 8}
_MODIFIER_ALIASES = {"Ctrl": "Control", "Cmd": "Meta", "Command": "Meta", "Option": "Alt"}
_NAMED_KEYS = {
    "Enter": Key("Enter", "Enter", 13, "\r", False),
    "Tab": Key("Tab", "Tab", 9, "", False),
    "Escape": Key("Escape", "Escape", 27, "", False),
    "Backspace": Key("Backspace", "Backspace", 8, "", False),
    "Delete": Key("Delete", "Delete", 46, "", False),
    "Space": Key(" ", "Space", 32, " ", False),
    "ArrowLeft": Key("ArrowLeft", "ArrowLeft", 37, "", False),
    "ArrowUp": Key("ArrowUp", "ArrowUp", 38, "", False),
    "ArrowRight": Key("ArrowRight", "ArrowRight", 39, "", False),
    "ArrowDown": Key("ArrowDown", "ArrowDown", 40, "", False),
    "Home": Key("Home", "Home", 36, "", False),
    "End": Key("End", "End", 35, "", False),
    "PageUp": Key("PageUp", "PageUp", 33, "", False),
    "PageDown": Key("PageDown", "PageDown", 34, "", False),
    "Shift": Key("Shift", "ShiftLeft", 16, "", False),
    "Control": Key("Control", "ControlLeft", 17, "", False),
    "Alt": Key("Alt", "AltLeft", 18, "", False),
    "Meta": Key("Meta", "MetaLeft", 91, "", False),
}
# (plain, shifted, KeyboardEvent.code, Windows virtual key code) on a US keyboard.
_PUNCTUATION = (
    ("`", "~", "Backquote", 192),
    ("-", "_", "Minus", 189),
    ("=", "+", "Equal", 187),
    ("[", "{", "BracketLeft", 219),
    ("]", "}", "BracketRight", 221),
    ("\\", "|", "Backslash", 220),
    (";", ":", "Semicolon", 186),
    ("'", '"', "Quote", 222),
    (",", "<", "Comma", 188),
    (".", ">", "Period", 190),
    ("/", "?", "Slash", 191),
)
_SHIFTED_DIGITS = ")!@#$%^&*("


def _character_keys():
    """Map every character a US keyboard can type to the key that types it."""
    keys = {" ": _NAMED_KEYS["Space"], "\n": _NAMED_KEYS["Enter"], "\t": _NAMED_KEYS["Tab"]}
    for letter in "abcdefghijklmnopqrstuvwxyz":
        code, keycode = "Key" + letter.upper(), ord(letter.upper())
        keys[letter] = Key(letter, code, keycode, letter, False)
        keys[letter.upper()] = Key(letter.upper(), code, keycode, letter.upper(), True)
    for digit, shifted in zip("0123456789", _SHIFTED_DIGITS):
        keys[digit] = Key(digit, "Digit" + digit, ord(digit), digit, False)
        keys[shifted] = Key(shifted, "Digit" + digit, ord(digit), shifted, True)
    for plain, shifted, code, keycode in _PUNCTUATION:
        keys[plain] = Key(plain, code, keycode, plain, False)
        keys[shifted] = Key(shifted, code, keycode, shifted, True)
    return keys


_CHARACTER_KEYS = _character_keys()


def _lookup_key(name):
    """Resolve a key name ("Escape", "k", "/") to its `Key`, or explain what is allowed."""
    key = _NAMED_KEYS.get(name) or _CHARACTER_KEYS.get(name)
    if key is None:
        raise ValueError(
            "unknown key {0!r}: use one character from a US keyboard or one of {1}".format(
                name, ", ".join(sorted(_NAMED_KEYS))
            )
        )
    return key


def _split_chord(chord, modifiers):
    """Split "Meta+k" (plus any extra `modifiers`) into (ordered modifier names, key name)."""
    if chord == "+" or chord.endswith("++"):
        names, main = [n for n in chord[:-1].split("+") if n], "+"
    else:
        names = chord.split("+")
        main = names.pop()
    held = []
    for name in list(names) + list(modifiers):
        name = _MODIFIER_ALIASES.get(name, name)
        if name not in _MODIFIER_BITS:
            raise ValueError("unknown modifier {0!r}: use Alt, Control, Meta or Shift".format(name))
        if name not in held:
            held.append(name)
    return held, main


# -- values crossing the protocol ------------------------------------------------

_UNSERIALIZABLE = {"NaN": float("nan"), "Infinity": float("inf"), "-Infinity": float("-inf"), "-0": -0.0}


def _python_value(remote):
    """Convert a DevTools RemoteObject (returned by value) to a Python value."""
    if "value" in remote:
        return remote["value"]
    special = remote.get("unserializableValue")
    if special is None:
        return None  # undefined
    if special in _UNSERIALIZABLE:
        return _UNSERIALIZABLE[special]
    if special.endswith("n"):
        return int(special[:-1])  # BigInt
    raise BrowserError("cannot convert JavaScript value {0!r}".format(special))


def _expression(js, args):
    """Turn `js` (an expression, or a function when `args` are given) into evaluable source."""
    if args:
        return "({0}\n)({1})".format(js, ", ".join(json.dumps(arg) for arg in args))
    stripped = js.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        # Same rule as the DevTools console: a bare {...} is meant as an object
        # literal, but a script would parse it as a block.
        return "({0}\n)".format(js)
    return js


def _exception(details):
    """Build a `JSError` from DevTools exceptionDetails, keeping the page's stack."""
    exception = details.get("exception", {})
    if "description" in exception:
        body = exception["description"]
    elif "value" in exception:
        body = exception["value"] if isinstance(exception["value"], str) else json.dumps(exception["value"])
    else:
        body = ""
    head = details.get("text", "Uncaught")
    first_line, _, stack = body.partition("\n")
    if not body:
        text = head
    elif first_line in head:
        # Chrome sometimes repeats the message in the headline; keep only the stack.
        text = head + ("\n" + stack if stack else "")
    else:
        text = head + " " + body
    if details.get("url") and details["url"] not in text:
        text += "\n    at {0}:{1}".format(details["url"], details.get("lineNumber", 0) + 1)
    # "TypeError: x is not a function" -> "TypeError"; DOMExceptions name themselves
    # the same way ("SyntaxError: ... is not a valid selector").
    name = first_line.split(":", 1)[0].strip()
    if not name.isidentifier():
        name = exception.get("className", "")
    return JSError(name, text)


def _preview(preview):
    """Render a console argument's object preview the way the DevTools console does."""
    parts = []
    for prop in preview.get("properties", []):
        value = prop.get("value", "")
        if prop.get("type") == "string":
            value = json.dumps(value)
        parts.append(value if preview.get("subtype") == "array" else "{0}: {1}".format(prop["name"], value))
    if preview.get("overflow"):
        parts.append("…")
    opening, closing = ("[", "]") if preview.get("subtype") == "array" else ("{", "}")
    return opening + ", ".join(parts) + closing


def _console_argument(remote):
    """Render one console.log argument as text."""
    if "value" in remote:
        value = remote["value"]
        return value if isinstance(value, str) else json.dumps(value)
    if "unserializableValue" in remote:
        return remote["unserializableValue"]
    if remote.get("subtype") != "error" and remote.get("preview"):
        return _preview(remote["preview"])
    return remote.get("description", remote.get("type", ""))


def _context_lost(error):
    """True when an evaluation failed only because the page navigated underneath it."""
    text = str(error)
    return "context" in text.lower() or "navigated" in text


def _is_implicit_favicon(url):
    """Chrome asks for /favicon.ico on its own; a site without one has not made a bad request."""
    return urlsplit(url).path == "/favicon.ico"


class Page:
    """One browser tab, driven the way a reader would drive it.

    Lists that fill in as the page runs (appended to by the DevTools reader thread):
      console          every console.* call and browser log entry, as `ConsoleMessage`
      errors           uncaught exceptions and unhandled rejections, as text with stack
      failed_requests  requests that failed or answered HTTP >= 400, as `FailedRequest`
      blocked_requests URLs of off-machine requests the harness refused to make
      dialogs          alert/confirm/prompt dialogs that opened, as `Dialog`
      notes            lines a test wants shown under its result (see `note()`)
    `cdp` is the raw DevTools session, for the rare thing this class does not wrap.
    """

    def __init__(self, browser, session, target_id, context_id, download_dir):
        self.browser = browser
        self.cdp = session
        self.console = []
        self.errors = []
        self.failed_requests = []
        self.blocked_requests = []
        self.dialogs = []
        self.notes = []
        # How alert/confirm/prompt are answered: True accepts, False dismisses,
        # a string accepts a prompt with that text.
        self.dialog_answer = True
        self._target_id = target_id
        self._context_id = context_id
        self._download_dir = download_dir
        self._requests = {}
        self._media = {}
        self._closed = False
        self._listen()
        for method in ("Page.enable", "Runtime.enable", "Log.enable", "Network.enable"):
            self.cdp.send(method)
        self.cdp.send("Page.setLifecycleEventsEnabled", {"enabled": True})
        # A headless tab does not have focus by default; without it focus events,
        # :focus styles and some key handling behave differently from a real window.
        self.cdp.send("Emulation.setFocusEmulationEnabled", {"enabled": True})
        self._frame_id = self.cdp.send("Page.getFrameTree")["frameTree"]["frame"]["id"]
        self.set_viewport(*browser.viewport)
        # Headless Chrome inherits the operating system's appearance settings; start
        # every page from the same ones so a test passes on a dark-mode laptop and
        # on a CI runner alike.
        self._media["prefers-reduced-motion"] = "no-preference"
        self.emulate_dark(False)

    # -- capture (reader thread) -------------------------------------------

    def _listen(self):
        self.cdp.on("Runtime.consoleAPICalled", self._on_console)
        self.cdp.on("Runtime.exceptionThrown", self._on_exception)
        self.cdp.on("Log.entryAdded", self._on_log_entry)
        self.cdp.on("Network.requestWillBeSent", self._on_request)
        self.cdp.on("Network.responseReceived", self._on_response)
        self.cdp.on("Network.loadingFailed", self._on_loading_failed)
        self.cdp.on("Page.javascriptDialogOpening", self._on_dialog)
        self.cdp.on("Inspector.targetCrashed", lambda params: self.errors.append("the page crashed"))

    def _on_console(self, params):
        frames = params.get("stackTrace", {}).get("callFrames", [])
        url = frames[0].get("url", "") if frames else ""
        line = frames[0].get("lineNumber", 0) + 1 if frames else None
        text = " ".join(_console_argument(arg) for arg in params.get("args", []))
        self.console.append(ConsoleMessage(params["type"], text, url, line))

    def _on_exception(self, params):
        self.errors.append(str(_exception(params["exceptionDetails"])))

    def _on_log_entry(self, params):
        entry = params["entry"]
        url = entry.get("url", "")
        if entry.get("source") == "network" and (self._is_blocked(url) or _is_implicit_favicon(url)):
            return
        line = entry["lineNumber"] + 1 if "lineNumber" in entry else None
        self.console.append(ConsoleMessage(entry["level"], entry["text"], url, line))

    def _on_request(self, params):
        request = params["request"]
        self._requests[params["requestId"]] = (request["url"], request.get("method", ""))

    def _on_response(self, params):
        response = params["response"]
        if response["status"] < 400 or _is_implicit_favicon(response["url"]):
            return
        _, method = self._requests.get(params["requestId"], ("", ""))
        reason = response.get("statusText", "")
        self.failed_requests.append(
            FailedRequest(response["url"], response["status"], reason, method, params.get("type", ""))
        )

    def _on_loading_failed(self, params):
        url, method = self._requests.get(params["requestId"], ("(unknown URL)", ""))
        if params.get("canceled"):
            # The page itself gave up (navigation away, AbortController): not a failure.
            return
        if self._is_blocked(url):
            self.blocked_requests.append(url)
            return
        if _is_implicit_favicon(url):
            return
        self.failed_requests.append(
            FailedRequest(url, None, params.get("errorText", ""), method, params.get("type", ""))
        )

    def _on_dialog(self, params):
        self.dialogs.append(Dialog(params["type"], params["message"]))
        answer = self.dialog_answer
        reply = {"accept": answer is not False}
        if isinstance(answer, str):
            reply["promptText"] = answer
        # post(), not send(): this runs on the reader thread, which cannot wait for
        # a reply to itself. A failed reply shows up in `errors` via sync().
        self.cdp.post("Page.handleJavaScriptDialog", reply)

    def _is_blocked(self, url):
        """True for a URL the browser was launched to refuse (anything off this machine)."""
        if not self.browser.block_external:
            return False
        parts = urlsplit(url)
        return parts.scheme in ("http", "https", "ws", "wss") and parts.hostname not in LOOPBACK_HOSTS

    # -- navigation --------------------------------------------------------

    def goto(self, url, wait="load", timeout=15.0):
        """Navigate and wait for `wait`: "load", "domcontentloaded", "networkidle" or "commit".

        A change of only the #fragment is a same-document navigation: no load event
        will ever fire, so this returns once the page's hashchange handlers have run.
        """
        if wait not in _LIFECYCLE_EVENTS:
            raise ValueError("wait must be one of {0}, got {1!r}".format(sorted(_LIFECYCLE_EVENTS), wait))
        result = self.cdp.send("Page.navigate", {"url": url}, timeout=timeout)
        if result.get("errorText"):
            raise NavigationError("cannot open {0}: {1}".format(url, result["errorText"]))
        loader_id = result.get("loaderId")
        if loader_id is None:
            self.eval("new Promise((resolve) => setTimeout(resolve, 0))")
            return
        self._await_lifecycle(_LIFECYCLE_EVENTS[wait], loader_id, url, timeout)

    def reload(self, wait="load", timeout=15.0):
        """Reload the page and wait as `goto` does."""
        if wait not in _LIFECYCLE_EVENTS:
            raise ValueError("wait must be one of {0}, got {1!r}".format(sorted(_LIFECYCLE_EVENTS), wait))
        self.cdp.forget_events("Page.lifecycleEvent")
        self.cdp.send("Page.reload")
        try:
            # "init" is the first lifecycle event of the new document; its loader id
            # tells this reload's events apart from the old document's stragglers.
            started = self.cdp.wait_for_event(
                "Page.lifecycleEvent",
                lambda event: event["name"] == "init" and event["frameId"] == self._frame_id,
                timeout,
            )
        except CDPTimeout as exc:
            raise NavigationError("reload did not start within {0:g}s".format(timeout)) from exc
        self._await_lifecycle(_LIFECYCLE_EVENTS[wait], started["loaderId"], "reload", timeout)

    def _await_lifecycle(self, name, loader_id, what, timeout):
        if name is None:
            return

        def reached(event):
            return (
                event["name"] == name
                and event.get("loaderId") == loader_id
                and event["frameId"] == self._frame_id
            )

        try:
            self.cdp.wait_for_event("Page.lifecycleEvent", reached, timeout)
        except CDPTimeout as exc:
            raise LoadTimeout("{0} did not reach '{1}' within {2:g}s".format(what, name, timeout)) from exc

    @property
    def url(self):
        """The page's current URL, including the #fragment."""
        return self.eval("location.href")

    def title(self):
        """The document title."""
        return self.eval("document.title")

    # -- JavaScript --------------------------------------------------------

    def eval(self, js, *args, timeout=None):
        """Evaluate `js` in the page and return its value as Python data.

        `js` is an expression (`"document.title"`); with `args` it must be a function,
        which is called with them (`page.eval("(a, b) => a + b", 1, 2)`). A returned
        promise is awaited. Raises `JSError`, carrying the page's stack, if it throws.
        """
        result = self.cdp.send(
            "Runtime.evaluate",
            {
                "expression": _expression(js, args),
                "awaitPromise": True,
                "returnByValue": True,
                "userGesture": True,
            },
            timeout=timeout,
        )
        if "exceptionDetails" in result:
            raise _exception(result["exceptionDetails"])
        return _python_value(result["result"])

    def wait_for(self, selector=None, js=None, timeout=5.0, visible=False):
        """Wait until `selector` matches an element, or until the JS expression `js` is truthy.

        With `visible=True` the element must also have a size and not be hidden.
        Returns the final value. A predicate that throws is retried (the app may not
        have booted yet); the last error is reported if the wait times out.
        """
        if (selector is None) == (js is None):
            raise ValueError("pass a selector or js=..., not both and not neither")
        if js is None:
            expression = _expression(_JS_VISIBLE if visible else _JS_EXISTS, (selector,))
            what = "{0}element {1!r}".format("visible " if visible else "", selector)
        else:
            expression = js
            what = "JS condition {0!r}".format(js)
        return self._poll(lambda: self.eval(expression), what, timeout)

    def wait_for_text(self, selector, text, timeout=5.0):
        """Wait until the element's visible text contains `text`; return the full text."""
        expression = _expression(
            "(sel, text) => {{ const el = document.querySelector(sel); "
            "if (!el) return null; const have = ({0})(el); "
            "return have.includes(text) ? {{text: have}} : null; }}".format(_JS_TEXT),
            (selector, text),
        )
        what = "{0!r} to contain {1!r}".format(selector, text)
        return self._poll(lambda: self.eval(expression), what, timeout)["text"]

    def _poll(self, probe, what, timeout):
        """Call `probe` every 20 ms until it returns something truthy; explain a timeout."""
        deadline = time.monotonic() + timeout
        last_error = None
        while True:
            try:
                value = probe()
                if value:
                    return value
                last_error = None
            except JSError as exc:
                if exc.name == "SyntaxError":
                    raise
                last_error = exc
            except CDPError as exc:
                if not _context_lost(exc):
                    raise
                last_error = exc
            if time.monotonic() >= deadline:
                detail = "; last error: {0}".format(last_error) if last_error else ""
                raise WaitTimeout("timed out after {0:g}s waiting for {1}{2}".format(timeout, what, detail))
            time.sleep(0.02)

    # -- reading the page --------------------------------------------------

    def _on_element(self, selector, function, timeout):
        """Wait for `selector`, then return `function(element)` evaluated in the page."""
        expression = _expression(
            "(sel) => {{ const el = document.querySelector(sel); "
            "return el ? {{value: ({0})(el)}} : null; }}".format(function),
            (selector,),
        )
        found = self._poll(lambda: self.eval(expression), "element {0!r}".format(selector), timeout)
        return found.get("value")

    def text(self, selector, timeout=5.0):
        """The visible text of the first match, trimmed. Waits for the element to exist."""
        return self._on_element(selector, _JS_TEXT, timeout)

    def texts(self, selector):
        """The visible text of every match, in document order (no waiting)."""
        return self.eval(
            "(sel) => Array.from(document.querySelectorAll(sel), {0})".format(_JS_TEXT), selector
        )

    def attr(self, selector, name, timeout=5.0):
        """An attribute of the first match (None if absent). Waits for the element."""
        return self._on_element(selector, "(el) => el.getAttribute({0})".format(json.dumps(name)), timeout)

    def count(self, selector):
        """How many elements match right now."""
        return self.eval("(sel) => document.querySelectorAll(sel).length", selector)

    def exists(self, selector):
        """True if at least one element matches right now."""
        return self.eval(_JS_EXISTS, selector)

    def visible(self, selector):
        """True if the first match exists, has a size and is not hidden, right now."""
        return self.eval(_JS_VISIBLE, selector)

    # -- mouse -------------------------------------------------------------

    def click(self, selector, timeout=5.0):
        """Click the centre of the first match with real, trusted mouse events.

        Waits until the element exists, is visible, has stopped moving and is not
        covered by something else; raises `ClickError` saying which of those failed.
        """
        x, y = self._click_point(selector, timeout)
        self._mouse("mouseMoved", x, y)
        self._mouse("mousePressed", x, y, button="left", buttons=1, clickCount=1)
        self._mouse("mouseReleased", x, y, button="left", clickCount=1)

    def hover(self, selector, timeout=5.0):
        """Move the mouse over the centre of the first match."""
        x, y = self._click_point(selector, timeout)
        self._mouse("mouseMoved", x, y)

    def _click_point(self, selector, timeout):
        """Return viewport coordinates that are safe to click, once they hold still."""
        deadline = time.monotonic() + timeout
        previous = None
        while True:
            try:
                state = self.eval(_JS_CLICK_POINT, selector)
            except CDPError as exc:
                if not _context_lost(exc):
                    raise
                state = {"problem": "the page was navigating"}
            point = (state["x"], state["y"]) if "x" in state else None
            # Two identical samples in a row: the element is not mid-animation.
            if point is not None and point == previous:
                return point
            if time.monotonic() >= deadline:
                problem = state.get("problem", "the element keeps moving")
                raise ClickError("cannot click {0!r}: {1}".format(selector, problem))
            previous = point
            time.sleep(0.016)

    def _mouse(self, kind, x, y, **extra):
        self.cdp.send("Input.dispatchMouseEvent", dict(type=kind, x=x, y=y, **extra))

    # -- keyboard ----------------------------------------------------------

    def press(self, key, modifiers=()):
        """Press one key, optionally with modifiers: `press("Escape")`, `press("Meta+k")`,
        `press("k", ["Meta"])`. The page receives real keydown/keyup events.

        Browser and OS shortcuts are not emulated (Meta+A does not select all); only
        the page's own key handlers and the key's default action run.
        """
        held, name = _split_chord(key, modifiers)
        definition = _lookup_key(name)
        if "Shift" in held and len(name) == 1 and name.isalpha():
            definition = _lookup_key(name.upper())
        bits = 0
        for modifier in held:
            bits |= _MODIFIER_BITS[modifier]
            self._key("rawKeyDown", _NAMED_KEYS[modifier], bits)
        self._stroke(definition, bits)
        for modifier in reversed(held):
            bits &= ~_MODIFIER_BITS[modifier]
            self._key("keyUp", _NAMED_KEYS[modifier], bits)

    def type(self, text):
        """Type `text` into the focused element, one real key press per character.

        Characters a US keyboard cannot type (accents, ₹, CJK) are inserted the way
        an input method would insert them: input events fire, key events do not.
        """
        composed = ""
        for char in text:
            definition = _CHARACTER_KEYS.get(char)
            if definition is None:
                composed += char
                continue
            if composed:
                self.cdp.send("Input.insertText", {"text": composed})
                composed = ""
            self._stroke(definition, 0)
        if composed:
            self.cdp.send("Input.insertText", {"text": composed})

    def fill(self, selector, text, timeout=5.0):
        """Click an input or textarea, clear it, and type `text` (replacing what was there)."""
        self.click(selector, timeout)
        if self.eval(_JS_SELECT_ALL, selector):
            self.press("Backspace")
        self.type(text)

    def _stroke(self, definition, held_bits):
        """Key down and up for one key. Text is produced only when no command modifier is held."""
        bits = held_bits | (_MODIFIER_BITS["Shift"] if definition.shift else 0)
        commanding = held_bits & (_MODIFIER_BITS["Alt"] | _MODIFIER_BITS["Control"] | _MODIFIER_BITS["Meta"])
        text = "" if commanding else definition.text
        self._key("keyDown" if text else "rawKeyDown", definition, bits, text)
        self._key("keyUp", definition, bits)

    def _key(self, kind, definition, bits, text=""):
        params = {
            "type": kind,
            "key": definition.key,
            "code": definition.code,
            "windowsVirtualKeyCode": definition.keycode,
            "modifiers": bits,
        }
        if text:
            params["text"] = text
            params["unmodifiedText"] = text
        self.cdp.send("Input.dispatchKeyEvent", params)

    # -- emulation ---------------------------------------------------------

    def set_viewport(self, width, height, mobile=False, scale=1):
        """Resize the viewport. `mobile=True` also emulates a touch device; `scale` is the
        device pixel ratio (screenshots are `scale` times larger)."""
        self.cdp.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": height, "deviceScaleFactor": scale, "mobile": mobile},
        )
        touch = {"enabled": mobile}
        if mobile:
            touch["maxTouchPoints"] = 5
        self.cdp.send("Emulation.setTouchEmulationEnabled", touch)

    def emulate_dark(self, dark=True):
        """Make `prefers-color-scheme` report dark (or light)."""
        self._emulate_media("prefers-color-scheme", "dark" if dark else "light")

    def emulate_reduced_motion(self, reduce=True):
        """Make `prefers-reduced-motion` report reduce (or no-preference)."""
        self._emulate_media("prefers-reduced-motion", "reduce" if reduce else "no-preference")

    def _emulate_media(self, feature, value):
        # The protocol replaces the whole list each time, so remember earlier choices.
        self._media[feature] = value
        features = [{"name": name, "value": setting} for name, setting in sorted(self._media.items())]
        self.cdp.send("Emulation.setEmulatedMedia", {"features": features})

    def set_timezone(self, timezone):
        """Make the page's clock and `Intl` use an IANA zone such as "Asia/Kolkata", so
        rendered times do not depend on the machine running the test."""
        self.cdp.send("Emulation.setTimezoneOverride", {"timezoneId": timezone})

    def set_offline(self, offline=True):
        """Cut (or restore) the page's network: requests fail and navigator.onLine flips."""
        self.cdp.send(
            "Network.emulateNetworkConditions",
            {"offline": offline, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1},
        )

    def add_init_script(self, js):
        """Run `js` in every document this page loads from now on, before the page's own
        scripts. For seeding localStorage or pinning `Date` before the app boots."""
        self.cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": js})

    # -- storage -----------------------------------------------------------

    def clear_storage(self):
        """Wipe everything the current origin has stored (localStorage, sessionStorage,
        IndexedDB, caches, cookies, service workers). The running page keeps what it
        already read into memory; reload to see a first visit."""
        origin = self.eval("location.origin")
        if not origin or origin == "null":
            raise BrowserError("clear_storage() needs a loaded page; {0} has no origin".format(self.url))
        self.cdp.send("Storage.clearDataForOrigin", {"origin": origin, "storageTypes": "all"})
        self.eval("sessionStorage.clear()")

    def local_storage_get(self, key):
        """The raw string stored under `key`, or None."""
        return self.eval("(key) => localStorage.getItem(key)", key)

    def local_storage_set(self, key, value):
        """Store `value` under `key`. A string is stored as is; anything else as JSON."""
        raw = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
        self.eval("(key, value) => localStorage.setItem(key, value)", key, raw)

    # -- files -------------------------------------------------------------

    def screenshot(self, path, full_page=False):
        """Save a PNG of the viewport, or of the whole scrollable page, to `path`."""
        params = {"format": "png", "captureBeyondViewport": bool(full_page)}
        if full_page:
            size = self.cdp.send("Page.getLayoutMetrics")["cssContentSize"]
            scale = self.eval("window.devicePixelRatio")
            height = min(size["height"], MAX_SCREENSHOT_PIXELS / scale)
            params["clip"] = {"x": 0, "y": 0, "width": size["width"], "height": height, "scale": 1}
        data = self.cdp.send("Page.captureScreenshot", params)["data"]
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(base64.b64decode(data))
        return path

    def set_files(self, selector, paths, timeout=5.0):
        """Choose local files in an `<input type="file">`, as the file dialog would."""
        missing = [path for path in paths if not os.path.isfile(path)]
        if missing:
            raise BrowserError("set_files(): no such file: {0}".format(", ".join(missing)))
        self.wait_for(selector, timeout=timeout)
        node = self.cdp.send(
            "Runtime.evaluate", {"expression": "document.querySelector({0})".format(json.dumps(selector))}
        )["result"]
        if "objectId" not in node:
            raise BrowserError("set_files(): {0!r} disappeared before files could be set".format(selector))
        self.cdp.send(
            "DOM.setFileInputFiles",
            {"files": [os.path.abspath(path) for path in paths], "objectId": node["objectId"]},
        )

    def wait_for_download(self, timeout=5.0):
        """Wait for a download this page started and return it as `Download(filename, path)`.

        Downloads are saved inside the temporary profile, never in the user's
        Downloads folder; read `path` before the browser closes.
        """
        browser_cdp = self.browser.cdp
        try:
            begun = browser_cdp.wait_for_event(
                "Browser.downloadWillBegin", lambda event: event["frameId"] == self._frame_id, timeout
            )
            finished = browser_cdp.wait_for_event(
                "Browser.downloadProgress",
                lambda event: event["guid"] == begun["guid"] and event["state"] != "inProgress",
                timeout,
            )
        except CDPTimeout as exc:
            raise WaitTimeout("no download finished within {0:g}s".format(timeout)) from exc
        if finished["state"] != "completed":
            raise BrowserError("download of {0} was {1}".format(begun["suggestedFilename"], finished["state"]))
        return Download(begun["suggestedFilename"], os.path.join(self._download_dir, begun["guid"]))

    # -- bookkeeping -------------------------------------------------------

    def note(self, text):
        """Attach a line to this test's entry in the runner's report."""
        self.notes.append(text)

    def sync(self):
        """Wait until every console message and error the page has produced so far has
        been recorded, so a check of `console` / `errors` right after an action is not a race."""
        self.cdp.send("Runtime.evaluate", {"expression": "0"})
        while self.cdp.background_errors:
            self.errors.append("harness: " + self.cdp.background_errors.pop(0))

    def close(self):
        """Close the tab and throw away its browser context."""
        if self._closed:
            return
        self._closed = True
        self.cdp.close()
        self.browser._discard(self._target_id, self._context_id)
