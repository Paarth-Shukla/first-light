"""Selfcheck: prove the harness itself works before trusting it with the site.

Every capability of `cdp.py`, `browser.py`, `run.py` and `scripts/shot.py` has a
test here, run against a small fixture page (`tests/e2e/fixtures/selfcheck/`)
that has one behaviour per capability. The fixture is reached through the
runner's `/__repo__/` mount, so these tests pass whatever directory is being
served. The slow checks that start a second Chrome (the runner's verdicts and
exit codes, cleanup after a crash, the screenshot CLI) only run when the fixture
itself is served:

    python3 tests/e2e/run.py --dir tests/e2e/fixtures/selfcheck -k harness_selfcheck
"""

import base64
import http.client
import json
import math
import os
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request

from tests.e2e import cdp
from tests.e2e.browser import BrowserError, ClickError, JSError, NavigationError, WaitTimeout
from tests.e2e.run import REPO_MOUNT, ROOT, StaticServer, allow_errors, page_problems, run_js_tests

FIXTURE_DIR = os.path.join(ROOT, "tests", "e2e", "fixtures", "selfcheck")
FIXTURE_URL = REPO_MOUNT + "tests/e2e/fixtures/selfcheck/"
RUNNER = os.path.join(ROOT, "tests", "e2e", "run.py")
RUNNER_SCENARIOS = os.path.join(ROOT, "tests", "e2e", "fixtures", "runner_scenarios")
SHOT = os.path.join(ROOT, "scripts", "shot.py")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


# -- helpers -----------------------------------------------------------------------


def open_fixture(page, base_url, tail=""):
    """Load the fixture page and wait until its module has finished booting."""
    page.goto(base_url + FIXTURE_URL + "index.html" + tail)
    page.wait_for_text("#boot", "ready")


def raised(kind, action):
    """Run `action` and return the `kind` exception it raises; fail if it raises nothing."""
    try:
        action()
    except kind as exc:
        return exc
    raise AssertionError("expected {0} to be raised".format(kind.__name__))


def settle(page, ready, timeout=5.0):
    """Keep syncing with the page until `ready()` is true: for effects that land a moment
    after the action that caused them (a timer firing, a request failing)."""
    deadline = time.monotonic() + timeout
    while not ready():
        if time.monotonic() > deadline:
            raise AssertionError("the page never produced what the test was waiting for")
        time.sleep(0.02)
        page.sync()


def png_size(path):
    """Return (width, height) of a PNG file, after checking it really is one."""
    with open(path, "rb") as handle:
        head = handle.read(24)
    assert head[:8] == PNG_SIGNATURE, "{0} is not a PNG".format(path)
    return struct.unpack("!II", head[16:24])


def fetch_status(url):
    """HTTP status of a GET made from Python (not from the page), bypassing any proxy."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=5.0) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def serving_fixture(page, base_url):
    """True when the runner serves the fixture directory itself (see the module docstring)."""
    status, body = fetch_status(base_url + "/data.json")
    if status == 200 and b"harness-selfcheck" in body:
        return True
    page.note("skipped: only runs with --dir tests/e2e/fixtures/selfcheck")
    return False


def scratch_dir():
    return tempfile.mkdtemp(prefix="firstlight-selfcheck-")


# -- reading the page ----------------------------------------------------------------


def test_goto_and_reading_the_page(page, base_url):
    open_fixture(page, base_url)
    assert page.title() == "Harness selfcheck"
    assert page.url == base_url + FIXTURE_URL + "index.html"
    assert page.text("#title") == "Harness selfcheck"
    assert page.texts("#list li") == ["First", "Second", "Third"]
    assert page.count("#list li") == 3
    assert page.count(".no-such-class") == 0
    assert page.exists("#palette") and not page.exists("#no-such-id")
    assert page.visible("#title") and not page.visible("#palette") and not page.visible("#no-such-id")
    assert page.attr("#echo", "aria-label") == "Echo"
    assert page.attr("#echo", "data-absent") is None
    # The page script is an ES module that fetches JSON: both need a real HTTP server.
    assert page.text("#data") == "fetched from data.json"


def test_eval_converts_values_and_awaits_promises(page, base_url):
    open_fixture(page, base_url)
    assert page.eval("1 + 1") == 2
    assert page.eval("'a' + 'b'") == "ab"
    assert page.eval("{a: 1, b: [true, null, 'x']}") == {"a": 1, "b": [True, None, "x"]}
    assert page.eval("undefined") is None and page.eval("null") is None
    assert page.eval("Infinity") == float("inf") and math.isnan(page.eval("NaN"))
    assert page.eval("12345678901234567890n") == 12345678901234567890
    assert page.eval("(a, b) => a + b", 2, 3) == 5
    awkward = 'quote " backslash \\ newline \n rupee ₹ separator \u2028'
    assert page.eval("(text) => text", awkward) == awkward
    assert page.eval("(items) => items.length", [1, {"two": 2}, None]) == 3
    assert page.eval("new Promise((resolve) => setTimeout(() => resolve('later'), 20))") == "later"
    assert page.eval("fetch('data.json').then((response) => response.json())")["fixture"] == "harness-selfcheck"


def test_eval_raises_with_the_page_stack(page, base_url):
    open_fixture(page, base_url)
    error = raised(JSError, lambda: page.eval("(() => { null.missing })()"))
    assert error.name == "TypeError" and "Cannot read properties of null" in str(error), str(error)
    assert "at <anonymous>" in str(error), "the stack is missing: " + str(error)
    error = raised(JSError, lambda: page.eval("Promise.reject(new Error('rejected on purpose'))"))
    assert "rejected on purpose" in str(error), str(error)
    error = raised(JSError, lambda: page.eval("(() => { throw 'a bare string' })()"))
    assert "a bare string" in str(error), str(error)
    assert raised(JSError, lambda: page.eval("1 +")).name == "SyntaxError"
    assert raised(JSError, lambda: page.count("li[")).name == "SyntaxError"
    page.sync()
    # An exception from eval() belongs to the caller; it is not something the page logged.
    assert page.errors == [] and page_problems(page) == []


def test_wait_for_element_condition_and_text(page, base_url):
    open_fixture(page, base_url)
    started = time.monotonic()
    page.click("#spawn")
    page.wait_for("#late")
    # The element is added 300 ms after the click, so the wait really had to wait.
    assert time.monotonic() - started >= 0.25
    assert page.text("#late") == "Arrived late"
    assert page.wait_for(js="document.title") == "Harness selfcheck"
    assert page.wait_for(js="document.querySelectorAll('#list li').length === 3") is True
    page.wait_for("#palette")
    assert raised(WaitTimeout, lambda: page.wait_for("#palette", visible=True, timeout=0.1))
    page.press("Meta+k")
    page.wait_for("#palette", visible=True)
    assert page.wait_for_text("#counter", "Clicked") == "Clicked 0 times"
    raised(ValueError, lambda: page.wait_for())
    raised(ValueError, lambda: page.wait_for("#a", js="1"))


def test_wait_timeout_says_what_was_missing(page, base_url):
    open_fixture(page, base_url)
    started = time.monotonic()
    error = raised(WaitTimeout, lambda: page.wait_for("#never", timeout=0.2))
    assert 0.2 <= time.monotonic() - started < 2.0
    assert "'#never'" in str(error) and "0.2s" in str(error), str(error)
    error = raised(WaitTimeout, lambda: page.wait_for(js="window.app.ready", timeout=0.1))
    assert "window.app.ready" in str(error) and "last error" in str(error) and "TypeError" in str(error), str(error)
    error = raised(WaitTimeout, lambda: page.wait_for_text("#title", "Not the title", timeout=0.1))
    assert "Not the title" in str(error), str(error)
    assert "'#never'" in str(raised(WaitTimeout, lambda: page.text("#never", timeout=0.1)))
    # A predicate that can never be valid fails at once instead of burning the timeout.
    started = time.monotonic()
    raised(JSError, lambda: page.wait_for(js="1 +", timeout=10.0))
    assert time.monotonic() - started < 3.0


# -- mouse ---------------------------------------------------------------------------


def test_click_is_a_real_trusted_click(page, base_url):
    open_fixture(page, base_url)
    page.click("#counter")
    assert page.text("#counter") == "Clicked 1 time"
    assert page.text("#click-info") == "trusted=true detail=1 button=0"
    page.click("#counter")
    assert page.text("#counter") == "Clicked 2 times"


def test_click_scrolls_the_element_into_view(page, base_url):
    open_fixture(page, base_url)
    assert page.eval("scrollY") == 0
    page.click("#far")
    assert page.text("#far") == "Reached"
    assert page.eval("scrollY") > 1000
    page.click("#counter")
    assert page.text("#counter") == "Clicked 1 time"


def test_click_waits_for_a_moving_element(page, base_url):
    open_fixture(page, base_url)
    page.click("#open-drawer")
    # The drawer slides for 250 ms; clicking where the button was a moment ago would miss.
    page.click("#drawer-button")
    assert page.text("#drawer-button") == "Drawer clicked"


def test_click_refuses_what_a_reader_could_not_click(page, base_url):
    open_fixture(page, base_url)
    error = raised(ClickError, lambda: page.click("#covered", timeout=0.15))
    assert "covered by <div#overlay>" in str(error), str(error)
    assert page.text("#covered") == "Under an overlay"
    assert "disabled" in str(raised(ClickError, lambda: page.click("#disabled", timeout=0.15)))
    assert page.text("#disabled") == "Disabled"
    assert "no size" in str(raised(ClickError, lambda: page.click("#palette", timeout=0.15)))
    assert "no element matches" in str(raised(ClickError, lambda: page.click("#no-such-id", timeout=0.15)))


def test_hover(page, base_url):
    open_fixture(page, base_url)
    page.hover("#hover-target")
    assert page.text("#hover-target") == "Hovered"


# -- keyboard ------------------------------------------------------------------------


def test_type_sends_a_key_press_per_character(page, base_url):
    open_fixture(page, base_url)
    page.click("#echo")
    text = "Front page 42!"
    page.type(text)
    assert page.text("#echo-out") == text
    assert page.text("#keydowns") == str(len(text))
    assert page.text("#inputs") == str(len(text))
    assert page.text("#last-key") == "!|Digit1|shift|trusted=true"


def test_type_inserts_characters_no_keyboard_has(page, base_url):
    open_fixture(page, base_url)
    page.click("#echo")
    page.type("₹ naïve 日本")
    assert page.text("#echo-out") == "₹ naïve 日本"
    # Only the keys a US keyboard has produce key events: two spaces and n, a, v, e.
    assert page.text("#keydowns") == "6"


def test_type_enter_tab_and_editing_keys(page, base_url):
    open_fixture(page, base_url)
    page.click("#notes")
    page.type("line one\nline two")
    assert page.eval("document.getElementById('notes').value") == "line one\nline two"
    page.click("#echo")
    page.type("abc")
    page.press("ArrowLeft")
    page.press("Backspace")
    assert page.text("#echo-out") == "ac"
    page.press("Tab")
    assert page.eval("document.activeElement.id") == "notes"
    page.press("Shift+Tab")
    assert page.eval("document.activeElement.id") == "echo"


def test_fill_replaces_the_value(page, base_url):
    open_fixture(page, base_url)
    page.fill("#echo", "first draft")
    assert page.text("#echo-out") == "first draft"
    page.fill("#echo", "second")
    assert page.text("#echo-out") == "second"
    page.fill("#notes", "into a textarea")
    assert page.eval("document.getElementById('notes').value") == "into a textarea"
    assert "needs an <input>" in str(raised(JSError, lambda: page.fill("#counter", "nope")))


def test_press_slash_reaches_the_shortcut_handler(page, base_url):
    open_fixture(page, base_url)
    assert page.eval("document.activeElement.tagName") == "BODY"
    page.press("/")
    assert page.eval("document.activeElement.id") == "echo"
    assert page.text("#last-key") == "/|Slash||trusted=true"
    # The handler called preventDefault(), so the slash itself was not typed...
    assert page.eval("document.getElementById('echo').value") == ""
    # ...but inside the field it is an ordinary character.
    page.type("a/b")
    assert page.text("#echo-out") == "a/b"
    page.press("Escape")
    assert page.eval("document.activeElement.tagName") == "BODY"


def test_press_with_modifiers(page, base_url):
    open_fixture(page, base_url)
    page.press("Meta+k")
    assert page.visible("#palette")
    assert page.text("#last-key") == "k|KeyK|meta|trusted=true"
    page.press("k", ["Meta"])
    assert not page.visible("#palette")
    page.press("Control+k")
    assert page.visible("#palette")
    assert page.text("#last-key") == "k|KeyK|ctrl|trusted=true"
    page.press("Escape")
    assert not page.visible("#palette")
    page.press("Cmd+Shift+k")
    assert page.text("#last-key") == "K|KeyK|meta+shift|trusted=true"
    page.press("Alt+ArrowDown")
    assert page.text("#last-key") == "ArrowDown|ArrowDown|alt|trusted=true"


def test_press_letters_and_shifted_keys(page, base_url):
    open_fixture(page, base_url)
    assert page.text("#list li.selected") == "First"
    page.press("j")
    page.press("j")
    assert page.text("#list li.selected") == "Third"
    page.press("k")
    assert page.text("#list li.selected") == "Second"
    page.press("?")
    assert page.visible("#help")
    assert page.text("#last-key") == "?|Slash|shift|trusted=true"
    page.press("+")
    assert page.text("#last-key") == "+|Equal|shift|trusted=true"
    assert "unknown key" in str(raised(ValueError, lambda: page.press("Escpae")))
    assert "unknown modifier" in str(raised(ValueError, lambda: page.press("Hyper+k")))


# -- emulation -----------------------------------------------------------------------


def test_pages_start_light_and_full_motion_whatever_the_machine_uses(page, base_url):
    open_fixture(page, base_url)
    assert page.text("#scheme") == "light"
    assert page.text("#motion") == "full"
    assert page.eval("getComputedStyle(document.body).backgroundColor") == "rgb(246, 241, 231)"


def test_emulate_dark_and_reduced_motion(page, base_url):
    open_fixture(page, base_url)
    page.emulate_dark(True)
    page.wait_for_text("#scheme", "dark")
    assert page.eval("getComputedStyle(document.body).backgroundColor") == "rgb(20, 19, 15)"
    page.emulate_reduced_motion(True)
    page.wait_for_text("#motion", "reduced")
    assert page.text("#scheme") == "dark", "setting one media feature must not reset the other"
    page.emulate_dark(False)
    page.wait_for_text("#scheme", "light")
    assert page.text("#motion") == "reduced"
    page.emulate_reduced_motion(False)
    page.wait_for_text("#motion", "full")


def test_set_viewport_desktop_and_phone(page, base_url):
    open_fixture(page, base_url)
    assert page.text("#viewport") == "1280x800@1"
    assert page.text("#layout") == "wide" and page.text("#pointer") == "fine"
    page.set_viewport(390, 844, mobile=True, scale=2)
    page.wait_for_text("#viewport", "390x844@2")
    page.wait_for_text("#layout", "narrow")
    page.wait_for_text("#pointer", "coarse")
    assert page.eval("getComputedStyle(document.getElementById('columns')).flexDirection") == "column"
    page.click("#counter")
    assert page.text("#counter") == "Clicked 1 time"
    page.set_viewport(1024, 700)
    page.wait_for_text("#viewport", "1024x700@1")
    page.wait_for_text("#layout", "wide")
    page.wait_for_text("#pointer", "fine")


def test_set_timezone(page, base_url):
    open_fixture(page, base_url)
    half_past_midnight_utc = "new Date(Date.UTC(2026, 10, 11, 0, 30)).getHours()"
    page.set_timezone("Asia/Kolkata")
    assert page.eval(half_past_midnight_utc) == 6
    assert page.eval("new Date(Date.UTC(2026, 10, 11)).getTimezoneOffset()") == -330
    assert "6:00" in page.eval("new Date(Date.UTC(2026, 10, 11, 0, 30)).toLocaleTimeString('en-GB')")
    page.set_timezone("America/New_York")
    assert page.eval(half_past_midnight_utc) == 19


@allow_errors("ERR_INTERNET_DISCONNECTED")
def test_set_offline(page, base_url):
    open_fixture(page, base_url)
    assert page.text("#online") == "online"
    page.set_offline(True)
    page.wait_for_text("#online", "offline")
    page.click("#refetch")
    page.wait_for_text("#data", "fetch failed")
    page.set_offline(False)
    page.wait_for_text("#online", "online")
    page.click("#refetch")
    page.wait_for_text("#data", "fetched from data.json")


def test_add_init_script_runs_before_the_page(page, base_url):
    page.add_init_script(
        "window.__seed = 'seeded before boot'; localStorage.setItem('selfcheck.note', 'from the init script');"
    )
    open_fixture(page, base_url)
    assert page.text("#seed") == "seeded before boot"
    assert page.text("#note") == "from the init script"


# -- storage -------------------------------------------------------------------------


def test_local_storage_survives_a_reload(page, base_url):
    open_fixture(page, base_url)
    assert page.text("#visits") == "1"
    assert page.local_storage_get("selfcheck.visits") == "1"
    assert page.local_storage_get("selfcheck.absent") is None
    page.local_storage_set("selfcheck.note", "kept across reloads")
    page.local_storage_set("selfcheck.prefs", {"dense": True, "sections": ["ai", "world"]})
    assert page.local_storage_get("selfcheck.prefs") == '{"dense":true,"sections":["ai","world"]}'
    page.reload()
    page.wait_for_text("#boot", "ready")
    assert page.text("#visits") == "2"
    assert page.text("#note") == "kept across reloads"
    page.fill("#echo", "saved by the page")
    page.click("#save")
    assert page.local_storage_get("selfcheck.note") == "saved by the page"


def test_clear_storage(page, base_url):
    open_fixture(page, base_url)
    page.local_storage_set("selfcheck.note", "about to be wiped")
    page.eval("sessionStorage.setItem('selfcheck.session', 'x')")
    page.clear_storage()
    assert page.local_storage_get("selfcheck.note") is None
    assert page.local_storage_get("selfcheck.visits") is None
    assert page.eval("sessionStorage.length") == 0
    page.reload()
    page.wait_for_text("#boot", "ready")
    assert page.text("#visits") == "1" and page.text("#note") == "(none)"


def test_every_test_starts_with_empty_storage(page, base_url):
    # The storage tests above wrote to localStorage on this very origin.
    open_fixture(page, base_url)
    assert page.text("#visits") == "1"
    assert page.text("#note") == "(none)"


# -- what the page logged ------------------------------------------------------------


@allow_errors("deliberate console error")
def test_console_error_is_captured(page, base_url):
    open_fixture(page, base_url)
    assert page.console == [] and page_problems(page) == []
    page.click("#console-error")
    page.sync()
    assert len(page.console) == 1
    message = page.console[0]
    assert message.type == "error"
    assert message.text == "deliberate console error {code: 7}"
    assert message.url.endswith("/app.js") and message.line > 0
    problems = page_problems(page)
    assert len(problems) == 1 and "deliberate console error" in problems[0] and "app.js" in problems[0]
    assert page_problems(page, ("deliberate",)) == []
    assert page_problems(page, ("something else",)) == problems


def test_console_warning_is_captured_but_is_not_a_failure(page, base_url):
    open_fixture(page, base_url)
    page.click("#console-warn")
    page.sync()
    assert [(m.type, m.text) for m in page.console] == [("warning", 'deliberate warning [1, "two"]')]
    assert page_problems(page) == []


@allow_errors("deliberate uncaught exception")
def test_uncaught_exception_is_captured(page, base_url):
    open_fixture(page, base_url)
    page.click("#throw")
    settle(page, lambda: page.errors)
    assert len(page.errors) == 1
    assert page.errors[0].startswith("Uncaught Error: deliberate uncaught exception"), page.errors[0]
    assert "app.js:" in page.errors[0], "the stack is missing: " + page.errors[0]
    assert len(page_problems(page)) == 1


@allow_errors("deliberate unhandled rejection")
def test_unhandled_rejection_is_captured(page, base_url):
    open_fixture(page, base_url)
    page.click("#reject")
    settle(page, lambda: page.errors)
    assert "Uncaught (in promise) Error: deliberate unhandled rejection" in page.errors[0], page.errors[0]


@allow_errors("missing.json")
def test_failed_request_is_captured(page, base_url):
    open_fixture(page, base_url)
    assert page.failed_requests == []
    page.click("#missing")
    page.wait_for_text("#missing-out", "status 404")
    settle(page, lambda: page.failed_requests and page.console)
    request = page.failed_requests[0]
    assert request.url.endswith("/missing.json") and request.status == 404
    assert request.method == "GET" and request.kind == "Fetch"
    assert page.console[0].type == "error" and page.console[0].url.endswith("/missing.json")


@allow_errors("no-such-page.html")
def test_missing_document_is_a_failed_request(page, base_url):
    page.goto(base_url + FIXTURE_URL + "no-such-page.html")
    page.sync()
    assert [(r.status, r.kind) for r in page.failed_requests] == [(404, "Document")]


@allow_errors("deliberate worker")
def test_worker_errors_are_captured(page, base_url):
    open_fixture(page, base_url)
    page.click("#worker-ping")
    page.wait_for_text("#worker-out", "pong from the worker")
    page.sync()
    assert page.console == []
    page.click("#worker-error")
    page.wait_for_text("#worker-out", "logged")
    settle(page, lambda: page.console)
    message = page.console[0]
    assert (message.type, message.text) == ("error", "deliberate worker console error")
    assert message.url.endswith("/worker.js") and message.line == 7, message
    page.click("#worker-throw")
    settle(page, lambda: len(page.console) == 2)
    assert page.console[1].text == "Uncaught Error: deliberate worker exception", page.console[1]
    assert len(page_problems(page)) == 2


def test_requests_to_other_hosts_are_blocked_and_harmless(page, base_url):
    if not page.browser.block_external:
        page.note("skipped: the runner was started with --allow-external")
        return
    open_fixture(page, base_url)
    started = time.monotonic()
    page.click("#external")
    page.wait_for_text("#external-out", "failed")
    assert time.monotonic() - started < 3.0, "a blocked request must fail at once, not time out"
    settle(page, lambda: page.blocked_requests)
    assert page.blocked_requests == ["https://images.example.com/harness-selfcheck.png"]
    assert page.failed_requests == [] and page.console == [] and page_problems(page) == []


def test_missing_favicon_is_not_the_pages_fault(page, base_url):
    page.goto(base_url + FIXTURE_URL + "no-favicon.html")
    assert page.text("#ready") == "ready"
    # Chrome asks for /favicon.ico by itself shortly after load; give it time to.
    time.sleep(0.3)
    page.sync()
    assert page.failed_requests == [] and page_problems(page) == []


# -- navigation ----------------------------------------------------------------------


def test_hash_navigation_needs_no_load_event(page, base_url):
    open_fixture(page, base_url)
    assert page.text("#route") == "(none)"
    page.goto(base_url + FIXTURE_URL + "index.html#/wire")
    # Same document: goto() returns after the hashchange handler ran, and nothing reloaded.
    assert page.text("#route") == "#/wire"
    assert page.text("#visits") == "1"
    page.goto(base_url + FIXTURE_URL + "index.html#/s/ai")
    assert page.text("#route") == "#/s/ai"
    assert page.url.endswith("index.html#/s/ai")
    page.reload()
    page.wait_for_text("#boot", "ready")
    assert page.text("#route") == "#/s/ai" and page.text("#visits") == "2"


def test_goto_wait_states(page, base_url):
    for wait in ("commit", "domcontentloaded", "load", "networkidle"):
        page.goto(base_url + FIXTURE_URL + "index.html?wait=" + wait, wait=wait)
        page.wait_for_text("#boot", "ready")
    assert page.text("#visits") == "4"
    assert "wait must be one of" in str(raised(ValueError, lambda: page.goto(base_url, wait="settled")))


@allow_errors("ERR_CONNECTION_REFUSED")
def test_goto_reports_an_unreachable_address(page, base_url):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]
    error = raised(NavigationError, lambda: page.goto("http://127.0.0.1:{0}/".format(closed_port)))
    assert "ERR_CONNECTION_REFUSED" in str(error), str(error)


# -- files ---------------------------------------------------------------------------


def test_screenshot_viewport_full_page_and_scale(page, base_url):
    open_fixture(page, base_url)
    folder = scratch_dir()
    try:
        shot = page.screenshot(os.path.join(folder, "made", "on", "demand", "viewport.png"))
        assert png_size(shot) == (1280, 800)
        full = page.screenshot(os.path.join(folder, "full.png"), full_page=True)
        page_height = page.eval("document.documentElement.scrollHeight")
        assert page_height > 2400
        assert png_size(full) == (1280, page_height)
        assert os.path.getsize(full) > os.path.getsize(shot) > 5000
        page.set_viewport(390, 844, mobile=True, scale=2)
        assert png_size(page.screenshot(os.path.join(folder, "phone.png"))) == (780, 1688)
        phone_full = png_size(page.screenshot(os.path.join(folder, "phone-full.png"), full_page=True))
        assert phone_full[0] == 780 and phone_full[1] > 1688
    finally:
        shutil.rmtree(folder)


def test_dialogs_are_answered_and_recorded(page, base_url):
    open_fixture(page, base_url)
    page.click("#ask")
    assert page.text("#answer") == "confirmed"
    page.dialog_answer = False
    page.click("#ask")
    assert page.text("#answer") == "declined"
    page.dialog_answer = "Ada"
    page.click("#prompt")
    assert page.text("#answer") == "prompt: Ada"
    assert [(d.type, d.message) for d in page.dialogs] == [
        ("confirm", "Proceed?"),
        ("confirm", "Proceed?"),
        ("prompt", "Your name?"),
    ]
    page.sync()
    assert page.errors == []


def test_download_is_caught_in_the_temporary_profile(page, base_url):
    open_fixture(page, base_url)
    page.click("#export")
    download = page.wait_for_download()
    assert download.filename == "selfcheck-export.json"
    with open(download.path) as handle:
        assert json.load(handle) == {"exported": True, "visits": 1}
    assert download.path.startswith(tempfile.gettempdir()), "downloads must stay out of ~/Downloads"
    assert "no download" in str(raised(WaitTimeout, lambda: page.wait_for_download(timeout=0.2)))


def test_set_files_fills_a_file_input(page, base_url):
    open_fixture(page, base_url)
    page.set_files("#import", [os.path.join(FIXTURE_DIR, "upload.txt")])
    assert page.wait_for_text("#import-out", "upload.txt") == "upload.txt: first line of the upload"
    assert "no such file" in str(raised(BrowserError, lambda: page.set_files("#import", ["/no/such/file.txt"])))


# -- browser unit-test pages -----------------------------------------------------------


def test_run_js_tests_reports_each_result(page, base_url):
    results = run_js_tests(page, base_url + FIXTURE_URL + "jstests-pass.html")
    assert [result["name"] for result in results] == ["adds numbers", "joins strings", "finishes asynchronously"]
    assert page.notes == ["ok    adds numbers", "ok    joins strings", "ok    finishes asynchronously"]


def test_run_js_tests_fails_when_a_browser_test_fails(page, base_url):
    error = raised(AssertionError, lambda: run_js_tests(page, base_url + FIXTURE_URL + "jstests-fail.html"))
    assert "1 of 2 browser tests failed: this one fails" in str(error), str(error)
    assert page.notes == ["ok    this one passes", "FAIL  this one fails: Error: expected 3 but got 4"]
    del page.notes[:]  # they did their job; do not print a FAIL line under a passing test
    error = raised(AssertionError, lambda: run_js_tests(page, base_url + FIXTURE_URL + "jstests-empty.html"))
    assert "without running a single test" in str(error), str(error)
    error = raised(
        AssertionError, lambda: run_js_tests(page, base_url + FIXTURE_URL + "no-favicon.html", timeout=0.3)
    )
    assert "did not finish" in str(error) and "window.__tests was never set" in str(error), str(error)


# -- the static server -----------------------------------------------------------------


def test_static_server_types_and_caching(page, base_url):
    open_fixture(page, base_url)
    headers = page.eval(
        "Promise.all(['app.js', 'data.json', 'style.css', 'index.html'].map(async (name) => {"
        " const response = await fetch(name);"
        " return [name, response.headers.get('content-type'), response.headers.get('cache-control')]; }))"
    )
    types = {name: content_type for name, content_type, _ in headers}
    assert types["app.js"].startswith("text/javascript"), types
    assert types["data.json"].startswith("application/json"), types
    assert types["style.css"].startswith("text/css") and types["index.html"].startswith("text/html"), types
    assert all(cache == "no-store" for _, _, cache in headers), headers


def test_static_server_stays_inside_its_directories(page, base_url):
    folder = scratch_dir()
    try:
        for name, content in (("secret.txt", "outside"), ("served/page.txt", "served"), ("mounted/lib.txt", "mounted")):
            os.makedirs(os.path.dirname(os.path.join(folder, name)), exist_ok=True)
            with open(os.path.join(folder, name), "w") as handle:
                handle.write(content)
        with StaticServer(os.path.join(folder, "served"), {"/lib/": os.path.join(folder, "mounted")}) as server:
            port = int(server.url.rsplit(":", 1)[1])

            def get(path):
                # http.client sends the path exactly as given; a browser would tidy it first.
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
                try:
                    connection.request("GET", path)
                    response = connection.getresponse()
                    return response.status, response.read().decode("utf-8", "replace")
                finally:
                    connection.close()

            assert get("/page.txt") == (200, "served")
            assert get("/lib/lib.txt") == (200, "mounted")
            assert get("/lib.txt")[0] == 404, "a mount is only visible under its prefix"
            assert get("/lib/page.txt")[0] == 404
            escapes = (
                "/../secret.txt",
                "/%2e%2e/secret.txt",
                "/..%2fsecret.txt",
                "/lib/../secret.txt",
                "/lib/%2e%2e/secret.txt",
                "/lib/..%2f..%2fsecret.txt",
            )
            for path in escapes:
                assert get(path)[0] == 404, path + " escaped the served directory"
    finally:
        shutil.rmtree(folder)


# -- the DevTools session ----------------------------------------------------------------


def test_cdp_error_carries_the_protocol_message(page, base_url):
    error = raised(cdp.CDPError, lambda: page.cdp.send("Nope.method"))
    assert error.method == "Nope.method" and error.code == -32601
    assert "Nope.method" in str(error) and "wasn't found" in str(error), str(error)
    error = raised(cdp.CDPError, lambda: page.cdp.send("Page.navigate", {}))
    assert "Page.navigate" in str(error) and "url" in str(error), str(error)
    assert page.eval("1") == 1, "the session must stay usable after an error"


def test_cdp_wait_for_event_filters_and_consumes(page, base_url):
    open_fixture(page, base_url)
    page.eval("setTimeout(() => { console.log('noise'); console.log('marker-42'); }, 30)")

    def is_marker(event):
        return event["args"][0].get("value") == "marker-42"

    event = page.cdp.wait_for_event("Runtime.consoleAPICalled", is_marker, timeout=5.0)
    assert event["type"] == "log"
    started = time.monotonic()
    error = raised(cdp.CDPTimeout, lambda: page.cdp.wait_for_event("Runtime.consoleAPICalled", is_marker, timeout=0.2))
    assert 0.2 <= time.monotonic() - started < 2.0
    assert "Runtime.consoleAPICalled" in str(error)
    # The unmatched event before it is still queued.
    noise = page.cdp.wait_for_event("Runtime.consoleAPICalled", lambda e: e["args"][0].get("value") == "noise", 0.2)
    assert noise["type"] == "log"


# -- the WebSocket client, against a scripted server ---------------------------------------


class FakeServer:
    """A one-connection WebSocket server whose behaviour after the handshake is `script(conn)`.

    The script runs on a thread; `finish()` joins it and re-raises anything it
    raised, so assertions made on the server side fail the test.
    """

    def __init__(self, script, accept=cdp.accept_key, status="101 Switching Protocols"):
        self._listener = socket.socket()
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(1)
        self.url = "ws://127.0.0.1:{0}/devtools/fake".format(self._listener.getsockname()[1])
        self.request = ""
        self._failure = None
        self._thread = threading.Thread(target=self._serve, args=(script, accept, status), daemon=True)
        self._thread.start()

    def _serve(self, script, accept, status):
        try:
            conn, _ = self._listener.accept()
            with conn:
                conn.settimeout(5.0)
                request = b""
                while b"\r\n\r\n" not in request:
                    request += conn.recv(4096)
                self.request = request.decode("latin-1")
                key = self.header("Sec-WebSocket-Key")
                response = (
                    "HTTP/1.1 {0}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                    "Sec-WebSocket-Accept: {1}\r\n\r\n"
                ).format(status, accept(key))
                conn.sendall(response.encode("ascii"))
                script(conn)
        except Exception:
            self._failure = traceback.format_exc()
        finally:
            self._listener.close()

    def header(self, name):
        for line in self.request.split("\r\n")[1:]:
            if line.lower().startswith(name.lower() + ":"):
                return line.split(":", 1)[1].strip()
        return None

    def finish(self):
        self._thread.join(5.0)
        assert not self._thread.is_alive(), "the fake server's script never finished"
        assert self._failure is None, "the fake server failed:\n" + str(self._failure)


def server_frame(opcode, payload, final=True, masked=False, reserved=0):
    """Build a frame the way a server sends it (unmasked unless a test asks otherwise)."""
    head = bytes([(0x80 if final else 0) | reserved | opcode])
    mask_bit = 0x80 if masked else 0
    size = len(payload)
    if size < 126:
        head += bytes([mask_bit | size])
    elif size < 0x10000:
        head += bytes([mask_bit | 126]) + struct.pack("!H", size)
    else:
        head += bytes([mask_bit | 127]) + struct.pack("!Q", size)
    if masked:
        return head + b"\x00\x00\x00\x00" + payload  # an all-zero mask leaves the payload as is
    return head + payload


def read_exact(conn, size):
    data = b""
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        assert chunk, "the client hung up after {0} of {1} bytes".format(len(data), size)
        data += chunk
    return data


def read_client_frame(conn):
    """Read one frame from the client; return (opcode, payload, length form in bytes)."""
    first, second = read_exact(conn, 2)
    assert first & 0x80, "client frames in these tests are never fragmented"
    assert second & 0x80, "RFC 6455: every client frame must be masked"
    size, form = second & 0x7F, 0
    if size == 126:
        size, form = struct.unpack("!H", read_exact(conn, 2))[0], 2
    elif size == 127:
        size, form = struct.unpack("!Q", read_exact(conn, 8))[0], 8
    key = read_exact(conn, 4)
    return first & 0x0F, cdp.mask_payload(read_exact(conn, size), key), form


def close_code(payload):
    return struct.unpack("!H", payload[:2])[0]


def test_ws_handshake_is_sent_and_validated(page, base_url):
    assert cdp.accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="  # RFC 6455, 1.3
    server = FakeServer(lambda conn: None)
    cdp.WebSocket(server.url).abort()
    server.finish()
    assert server.request.startswith("GET /devtools/fake HTTP/1.1\r\n")
    assert server.header("Upgrade") == "websocket" and server.header("Connection") == "Upgrade"
    assert server.header("Sec-WebSocket-Version") == "13"
    assert server.header("Host") == server.url[len("ws://") : -len("/devtools/fake")]
    assert len(base64.b64decode(server.header("Sec-WebSocket-Key"))) == 16
    # Chrome rejects DevTools connections that carry an Origin it does not allow.
    assert server.header("Origin") is None

    server = FakeServer(lambda conn: None, accept=lambda key: cdp.accept_key("not the key we sent"))
    assert "Sec-WebSocket-Accept" in str(raised(cdp.HandshakeError, lambda: cdp.WebSocket(server.url)))
    server.finish()

    server = FakeServer(lambda conn: None, status="403 Forbidden")
    assert "403" in str(raised(cdp.HandshakeError, lambda: cdp.WebSocket(server.url)))
    server.finish()

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]
    assert "cannot connect" in str(
        raised(cdp.WebSocketError, lambda: cdp.WebSocket("ws://127.0.0.1:{0}/".format(closed_port)))
    )
    assert "only ws://" in str(raised(cdp.WebSocketError, lambda: cdp.WebSocket("wss://127.0.0.1/")))


def test_ws_client_frames_are_masked_in_every_length_form(page, base_url):
    # RFC 6455, 5.7: a masked "Hello".
    assert cdp.encode_frame(cdp.OP_TEXT, b"Hello", bytes.fromhex("37fa213d")).hex() == "818537fa213d7f9f4d5158"
    messages = ["short", "x" * 125, "y" * 126, "z" * 65535, "w" * 65536, "₹日本" * 30000]
    forms = [0, 0, 2, 2, 8, 8]

    def script(conn):
        for message, form in zip(messages, forms):
            opcode, payload, seen_form = read_client_frame(conn)
            assert opcode == cdp.OP_TEXT and seen_form == form, (opcode, seen_form, form)
            assert payload == message.encode("utf-8")

    server = FakeServer(script)
    client = cdp.WebSocket(server.url)
    for message in messages:
        client.send_text(message)
    server.finish()
    client.abort()


def test_ws_reads_every_length_form(page, base_url):
    messages = ["short", "x" * 125, "y" * 126, "z" * 65535, "w" * 65536, "₹日本" * 30000]

    def script(conn):
        # Sent in one burst, so frames also arrive glued together and split mid-header.
        conn.sendall(b"".join(server_frame(cdp.OP_TEXT, message.encode("utf-8")) for message in messages))
        conn.sendall(server_frame(cdp.OP_BINARY, bytes(range(256)) * 300))

    server = FakeServer(script)
    client = cdp.WebSocket(server.url)
    for message in messages:
        assert client.recv() == message
    assert client.recv() == bytes(range(256)) * 300
    server.finish()
    client.abort()


def test_ws_reassembles_fragments_and_answers_ping(page, base_url):
    def script(conn):
        conn.sendall(server_frame(cdp.OP_TEXT, b"Hel", final=False))
        conn.sendall(server_frame(cdp.OP_PING, b"are you there"))
        conn.sendall(server_frame(cdp.OP_CONTINUATION, b"lo, ", final=False))
        conn.sendall(server_frame(cdp.OP_PONG, b"unsolicited"))
        conn.sendall(server_frame(cdp.OP_CONTINUATION, "wörld".encode("utf-8")))
        opcode, payload, _ = read_client_frame(conn)
        assert (opcode, payload) == (cdp.OP_PONG, b"are you there")
        conn.sendall(server_frame(cdp.OP_TEXT, b"after"))

    server = FakeServer(script)
    client = cdp.WebSocket(server.url)
    assert client.recv() == "Hello, wörld"
    assert client.recv() == "after"
    server.finish()
    client.abort()


def test_ws_closing_handshake_both_ways(page, base_url):
    def server_closes(conn):
        conn.sendall(server_frame(cdp.OP_CLOSE, struct.pack("!H", 1001) + b"going away"))
        opcode, payload, _ = read_client_frame(conn)
        assert opcode == cdp.OP_CLOSE and close_code(payload) == 1001

    server = FakeServer(server_closes)
    client = cdp.WebSocket(server.url)
    error = raised(cdp.ConnectionClosed, client.recv)
    assert (error.code, error.reason) == (1001, "going away")
    server.finish()

    def client_closes(conn):
        opcode, payload, _ = read_client_frame(conn)
        assert opcode == cdp.OP_CLOSE and close_code(payload) == 1000
        conn.sendall(server_frame(cdp.OP_CLOSE, struct.pack("!H", 1000)))
        assert conn.recv(1) == b"", "the client must not send anything after its Close frame"

    server = FakeServer(client_closes)
    client = cdp.WebSocket(server.url)
    client.close()
    client.close()  # a second close must not send a second Close frame
    assert raised(cdp.ConnectionClosed, client.recv).code == 1000
    server.finish()

    server = FakeServer(lambda conn: None)  # hangs up without a Close frame
    client = cdp.WebSocket(server.url)
    assert raised(cdp.ConnectionClosed, client.recv).code == 1006
    server.finish()


def test_ws_rejects_protocol_violations(page, base_url):
    violations = [
        ("masked", server_frame(cdp.OP_TEXT, b"masked", masked=True), 1002),
        ("reserved bits", server_frame(cdp.OP_TEXT, b"rsv", reserved=0x40), 1002),
        ("continuation frame with no message", server_frame(cdp.OP_CONTINUATION, b"orphan"), 1002),
        (
            "before the previous message ended",
            server_frame(cdp.OP_TEXT, b"one", final=False) + server_frame(cdp.OP_TEXT, b"two"),
            1002,
        ),
        ("control frames", server_frame(cdp.OP_PING, b"p" * 126), 1002),
        ("control frames", server_frame(cdp.OP_PING, b"split", final=False), 1002),
        ("unknown opcode", server_frame(0x3, b"reserved opcode"), 1002),
        ("not valid UTF-8", server_frame(cdp.OP_TEXT, b"\xff\xfe"), 1007),
    ]
    for expected_text, frames, expected_code in violations:

        def script(conn, frames=frames, expected_code=expected_code):
            conn.sendall(frames)
            opcode, payload, _ = read_client_frame(conn)
            assert opcode == cdp.OP_CLOSE and close_code(payload) == expected_code, (opcode, payload)

        server = FakeServer(script)
        client = cdp.WebSocket(server.url)
        error = raised(cdp.ProtocolError, client.recv)
        assert expected_text in str(error), "{0!r} not in {1!r}".format(expected_text, str(error))
        server.finish()


def test_cdp_session_matches_replies_by_id(page, base_url):
    def send(conn, message):
        conn.sendall(server_frame(cdp.OP_TEXT, json.dumps(message).encode("utf-8")))

    def read(conn):
        return json.loads(read_client_frame(conn)[1])

    def script(conn):
        first, second = read(conn), read(conn)
        send(conn, {"method": "Custom.happened", "params": {"n": 1}})
        # Answer in the opposite order: each caller must still get its own reply.
        send(conn, {"id": second["id"], "result": {"echo": second["method"], "params": second["params"]}})
        send(conn, {"id": first["id"], "result": {"echo": first["method"], "params": first["params"]}})
        third = read(conn)
        send(conn, {"id": third["id"], "error": {"code": -32000, "message": "not today", "data": "the details"}})
        read(conn)  # a command that is never answered
        fifth = read(conn)
        send(conn, {"id": fifth["id"], "result": {}})
        opcode, payload, _ = read_client_frame(conn)
        assert opcode == cdp.OP_CLOSE and close_code(payload) == 1000
        conn.sendall(server_frame(cdp.OP_CLOSE, struct.pack("!H", 1000)))

    server = FakeServer(script)
    session = cdp.CDPSession(server.url)
    heard = []
    session.on("Custom.happened", heard.append)
    replies = {}

    def call(method, params):
        replies[method] = session.send(method, params)

    threads = [
        threading.Thread(target=call, args=("A.first", {"a": 1})),
        threading.Thread(target=call, args=("B.second", {"b": 2})),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5.0)
    assert replies == {
        "A.first": {"echo": "A.first", "params": {"a": 1}},
        "B.second": {"echo": "B.second", "params": {"b": 2}},
    }, replies
    assert session.wait_for_event("Custom.happened", timeout=1.0) == {"n": 1}
    assert heard == [{"n": 1}]
    error = raised(cdp.CDPError, lambda: session.send("C.third"))
    assert (error.method, error.code, error.message, error.data) == ("C.third", -32000, "not today", "the details")
    assert str(error) == "C.third: not today (code -32000) [the details]"
    started = time.monotonic()
    assert "no reply within 0.2s" in str(raised(cdp.CDPTimeout, lambda: session.send("D.silent", timeout=0.2)))
    assert time.monotonic() - started < 2.0
    assert session.send("E.fifth") == {}
    session.close()
    assert session.closed
    assert "connection closed" in str(raised(cdp.CDPClosed, lambda: session.send("F.late")))
    server.finish()


# -- the runner, the cleanup and the screenshot CLI (each starts another Chrome) ------------


def run_tool(arguments, temp_dir, timeout=120.0):
    """Run a harness script in a subprocess whose temp files all go to `temp_dir`."""
    env = dict(os.environ, TMPDIR=temp_dir, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable] + arguments, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout
    )


def failing_assert_line():
    """Line number of the assertion that test_fails_on_assertion is built to trip."""
    with open(os.path.join(RUNNER_SCENARIOS, "test_outcomes.py")) as handle:
        for number, line in enumerate(handle, 1):
            if "Some other title" in line:
                return number
    raise AssertionError("test_outcomes.py no longer contains its failing assertion")


def chrome_profiles(temp_dir):
    return [name for name in os.listdir(temp_dir) if name.startswith("firstlight-chrome-")]


def test_runner_gives_each_test_its_verdict_and_exits_nonzero(page, base_url):
    if not serving_fixture(page, base_url):
        return
    folder = scratch_dir()
    try:
        artifacts = os.path.join(folder, "artifacts")
        # Left over from an imaginary earlier run in which this test failed.
        stale = os.path.join(artifacts, "outcomes-passes.png")
        os.makedirs(artifacts)
        with open(stale, "wb") as handle:
            handle.write(PNG_SIGNATURE)
        result = run_tool(
            [RUNNER, "--dir", FIXTURE_DIR, "--scenarios", RUNNER_SCENARIOS, "--artifacts", artifacts,
             "-k", "outcomes::"],
            folder,
        )
        output = result.stdout
        assert result.returncode == 1, "exit {0}\n{1}\n{2}".format(result.returncode, output, result.stderr)
        verdicts = {}
        for line in output.split("\n"):
            fields = line.split()
            if len(fields) == 3 and fields[0] in ("ok", "FAIL") and fields[2].endswith("s"):
                verdicts[fields[1]] = fields[0]
        assert verdicts == {
            "passes": "ok",
            "fails_on_assertion": "FAIL",
            "fails_on_console_error": "FAIL",
            "fails_on_uncaught_exception": "FAIL",
            "passes_with_all_errors_allowed": "ok",
            "fails_on_error_outside_the_allow_list": "FAIL",
        }, output
        assert "2 passed, 4 failed" in output, output
        assert "failed: outcomes::fails_on_assertion" in output, output
        # A failure says where it happened, what was wrong, and what the page logged.
        assert "test_outcomes.py:{0}  assert page.text".format(failing_assert_line()) in output, output
        assert "AssertionError: the title was Harness selfcheck" in output, output
        assert "console error: deliberate console error {code: 7}" in output, output
        assert "uncaught exception: Uncaught Error: deliberate uncaught exception" in output, output
        # Exactly the failures have screenshots: the passing test's stale one was removed.
        shots = sorted(os.listdir(artifacts))
        assert shots == [
            "outcomes-fails_on_assertion.png",
            "outcomes-fails_on_console_error.png",
            "outcomes-fails_on_error_outside_the_allow_list.png",
            "outcomes-fails_on_uncaught_exception.png",
        ], shots
        width, height = png_size(os.path.join(artifacts, shots[0]))
        assert width == 1280 and height > 2400, "failure screenshots are full-page"
        assert chrome_profiles(folder) == [], "the runner left a Chrome profile behind"

        # A run of passing tests exits 0, and --shots keeps a screenshot of each of them.
        result = run_tool(
            [RUNNER, "--dir", FIXTURE_DIR, "--scenarios", RUNNER_SCENARIOS, "--artifacts", artifacts,
             "-k", "outcomes::passes", "--shots"],
            folder,
        )
        assert result.returncode == 0 and "2 passed, 0 failed" in result.stdout, result.stdout + result.stderr
        assert png_size(stale)[0] == 1280, "the stale placeholder should have been replaced by a real screenshot"
        assert result.stdout.count("screenshot: ") == 2, result.stdout
    finally:
        shutil.rmtree(folder)


def test_runner_replaces_a_chrome_that_died(page, base_url):
    if not serving_fixture(page, base_url):
        return
    folder = scratch_dir()
    try:
        result = run_tool(
            [RUNNER, "--dir", FIXTURE_DIR, "--scenarios", RUNNER_SCENARIOS,
             "--artifacts", os.path.join(folder, "artifacts"), "-k", "crash::"],
            folder,
        )
        output = result.stdout
        assert result.returncode == 1, output + result.stderr
        assert "FAIL  kills_chrome" in output and "connection closed" in output, output
        assert "Chrome is gone" in output, output
        assert "ok    runs_in_a_new_chrome" in output, output
        assert "1 passed, 1 failed" in output, output
        assert chrome_profiles(folder) == [], "a profile was left behind after the crash"
    finally:
        shutil.rmtree(folder)


def test_runner_exit_codes_when_nothing_can_run(page, base_url):
    if not serving_fixture(page, base_url):
        return
    folder = scratch_dir()
    try:
        common = ["--scenarios", RUNNER_SCENARIOS, "--artifacts", os.path.join(folder, "artifacts")]
        result = run_tool([RUNNER, "--dir", FIXTURE_DIR, "-k", "no-test-has-this-name"] + common, folder)
        assert result.returncode == 1 and "no tests matched" in result.stdout, result.stdout + result.stderr
        result = run_tool([RUNNER, "--dir", os.path.join(folder, "missing")] + common, folder)
        assert result.returncode == 2 and "is not a directory" in result.stdout, result.stdout + result.stderr
        result = run_tool([RUNNER, "--dir", FIXTURE_DIR, "--list", "-k", "outcomes::"] + common, folder)
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.split("\n")[0] == "outcomes::passes" and result.stdout.count("outcomes::") == 6
        broken = os.path.join(folder, "broken")
        os.makedirs(broken)
        with open(os.path.join(broken, "test_broken.py"), "w") as handle:
            handle.write("import a_module_that_does_not_exist\n")
        result = run_tool([RUNNER, "--dir", FIXTURE_DIR, "--scenarios", broken, "-k", "broken"], folder)
        assert result.returncode == 1, result.stdout + result.stderr
        assert "test_broken.py could not be imported" in result.stdout and "ModuleNotFoundError" in result.stdout
        missing_chrome = dict(os.environ, CHROME_BIN=os.path.join(folder, "no-chrome-here"), TMPDIR=folder)
        result = subprocess.run(
            [sys.executable, RUNNER, "--dir", FIXTURE_DIR, "-k", "outcomes::passes"] + common,
            cwd=ROOT, env=missing_chrome, capture_output=True, text=True, timeout=60.0,
        )
        assert result.returncode == 2 and "CHROME_BIN points to" in result.stdout, result.stdout + result.stderr
    finally:
        shutil.rmtree(folder)


def test_runner_cleans_up_when_terminated_mid_test(page, base_url):
    if not serving_fixture(page, base_url):
        return
    folder = scratch_dir()
    env = dict(os.environ, TMPDIR=folder, PYTHONDONTWRITEBYTECODE="1")
    runner = subprocess.Popen(
        [sys.executable, RUNNER, "--dir", FIXTURE_DIR, "--scenarios", RUNNER_SCENARIOS,
         "--artifacts", os.path.join(folder, "artifacts"), "-k", "hang::"],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        header = runner.stdout.readline()
        assert header.startswith("Chrome/"), header
        assert len(chrome_profiles(folder)) == 1
        time.sleep(0.3)  # let it get into the test, which sleeps for a minute
        runner.send_signal(signal.SIGTERM)
        assert runner.wait(20.0) == 128 + signal.SIGTERM
        assert chrome_profiles(folder) == [], "a terminated run left its Chrome profile behind"
    finally:
        if runner.poll() is None:
            runner.kill()
        runner.communicate()
        shutil.rmtree(folder)


CRASHING_SCRIPT = """
import os, sys
sys.path.insert(0, {root!r})
from tests.e2e.browser import Browser

def report(browser):
    print(browser._process.pid, browser._profile, flush=True)

try:
    with Browser() as browser:
        report(browser)
        raise RuntimeError("inside the with block")
except RuntimeError:
    pass
browser = Browser()          # no context manager, never closed: atexit must clean up
report(browser)
raise RuntimeError("at top level")
"""


def process_is_gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def test_browser_is_killed_and_profile_removed_on_exceptions(page, base_url):
    if not serving_fixture(page, base_url):
        return
    folder = scratch_dir()
    try:
        result = run_tool(["-c", CRASHING_SCRIPT.format(root=ROOT)], folder)
        assert result.returncode == 1 and "at top level" in result.stderr, result.stderr
        launches = [line.split(" ", 1) for line in result.stdout.strip().split("\n")]
        assert len(launches) == 2, result.stdout
        for pid, profile in launches:
            assert profile.startswith(os.path.realpath(folder)) or profile.startswith(folder), profile
            assert not os.path.exists(profile), "profile left behind: " + profile
            assert process_is_gone(int(pid)), "Chrome {0} is still running".format(pid)
        assert chrome_profiles(folder) == []
    finally:
        shutil.rmtree(folder)


def test_shot_cli(page, base_url):
    if not serving_fixture(page, base_url):
        return
    folder = scratch_dir()
    try:
        fixture = os.path.relpath(os.path.join(FIXTURE_DIR, "index.html"), ROOT)
        describe = "document.querySelector('#scheme').textContent + ' ' + document.querySelector('#layout').textContent"
        desktop = os.path.join(folder, "desktop.png")
        result = run_tool(
            [SHOT, fixture, desktop, "--width", "1000", "--height", "700", "--wait-for", "#boot",
             "--eval", describe],
            folder,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.split("\n")[0] == "light wide", result.stdout
        assert "saved " in result.stdout and "(1000x700)" in result.stdout, result.stdout
        assert png_size(desktop) == (1000, 700)

        # Phone, dark, full page, a #route, and a wait that fails: the shot is still
        # taken, but the exit status says the page never got there.
        phone = os.path.join(folder, "nested", "phone.png")
        route = os.path.relpath(FIXTURE_DIR, ROOT) + "/#/wire"
        result = run_tool(
            [SHOT, route, phone, "--mobile", "--dark", "--full", "--delay", "50",
             "--wait-for", "#never-there", "--timeout", "0.5",
             "--eval", describe + " + ' ' + document.querySelector('#route').textContent"],
            folder,
        )
        assert result.returncode == 1 and "'#never-there'" in result.stderr, result.stdout + result.stderr
        assert result.stdout.split("\n")[0] == "dark narrow #/wire", result.stdout
        width, height = png_size(phone)
        assert width == 780 and height > 1688, (width, height)

        result = run_tool([SHOT, "no/such/page.html", desktop], folder)
        assert result.returncode == 1 and "does not exist" in result.stderr, result.stdout + result.stderr
        assert chrome_profiles(folder) == []
    finally:
        shutil.rmtree(folder)
