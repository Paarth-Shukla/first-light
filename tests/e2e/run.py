#!/usr/bin/env python3
"""Run the browser tests in headless Chrome.

    python3 tests/e2e/run.py [--dir dist] [-k TEXT] [--shots] [--headed]

The runner builds nothing. It serves a directory (the built site by default) on
a free local port, opens one Chrome, and runs every `test_*(page, base_url)`
function found in `tests/e2e/scenarios/test_*.py`, each with a fresh page in a
fresh browser context. Every top-level `tests/js/*.html` page is also run as a
browser unit-test page (see `run_js_tests`).

A test fails if it raises, and also if its page logged an uncaught exception or
a console error, unless the test opts out with `@allow_errors`. The exit status
is non-zero when anything failed or nothing ran.
"""

import argparse
import http.server
import importlib.util
import os
import signal
import sys
import threading
import time
import traceback
from collections import namedtuple

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(E2E_DIR))

if __name__ == "__main__":
    # Started as a script, Python puts tests/e2e/ first on the path, which would
    # let `import browser` and `import tests.e2e.browser` load two copies. Use the
    # repository root instead, and let scenarios' `from tests.e2e.run import ...`
    # find this running module rather than import a second one.
    if sys.path and os.path.abspath(sys.path[0]) == E2E_DIR:
        sys.path[0] = ROOT
    sys.modules.setdefault("tests.e2e.run", sys.modules["__main__"])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests.e2e.browser import Browser, BrowserError, WaitTimeout  # noqa: E402

# The repository is always reachable under this path, whatever --dir is served
# at the root, so test pages can load sources and fixtures by relative URL.
REPO_MOUNT = "/__repo__/"
JS_TESTS_DIR = os.path.join(ROOT, "tests", "js")
DEFAULT_SCENARIOS = os.path.join(E2E_DIR, "scenarios")
DEFAULT_ARTIFACTS = os.path.join(E2E_DIR, "artifacts")
ERROR_CONSOLE_TYPES = ("error", "assert")

Case = namedtuple("Case", "scenario name function source")
Outcome = namedtuple("Outcome", "case failure seconds notes screenshot")


# -- static file server ----------------------------------------------------------


class _FileHandler(http.server.SimpleHTTPRequestHandler):
    """Serve files from the server's root, or from a mounted directory, never cached."""

    extensions_map = dict(
        http.server.SimpleHTTPRequestHandler.extensions_map,
        **{
            ".js": "text/javascript",
            ".mjs": "text/javascript",
            ".json": "application/json",
            ".svg": "image/svg+xml",
            ".woff2": "font/woff2",
            ".webmanifest": "application/manifest+json",
        }
    )

    def translate_path(self, path):
        self.directory = self.server.root
        for prefix, directory in self.server.mounts.items():
            if path.startswith(prefix):
                self.directory = directory
                path = path[len(prefix) - 1 :]
                break
        return super().translate_path(path)

    def end_headers(self):
        # A test must always see the files as they are on disk now.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format, *args):
        """Stay quiet: a request log would bury the test report."""


class _FileServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        """Ignore a browser hanging up mid-response; report anything else."""
        if isinstance(sys.exc_info()[1], ConnectionError):
            return
        super().handle_error(request, client_address)


class StaticServer:
    """Serve `directory` at http://127.0.0.1:<free port>/ from a background thread.

    `mounts` maps a URL prefix such as "/__repo__/" to another directory.
    """

    def __init__(self, directory, mounts=None):
        self._server = _FileServer(("127.0.0.1", 0), _FileHandler)
        self._server.root = os.path.abspath(directory)
        self._server.mounts = dict(mounts or {})
        self.url = "http://127.0.0.1:{0}".format(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, name="static-server", daemon=True)
        self._thread.start()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self):
        """Stop serving and release the port."""
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(5.0)


# -- helpers for scenarios -------------------------------------------------------


def allow_errors(*patterns):
    """Decorator: do not fail this test for errors its page logs.

    `@allow_errors` allows every console error and uncaught exception;
    `@allow_errors("404", "offline")` allows only those whose text or URL contains
    one of the given strings, and still fails the test for any other.
    """
    if len(patterns) == 1 and callable(patterns[0]):
        patterns[0].e2e_allowed_errors = ("",)
        return patterns[0]

    def mark(function):
        function.e2e_allowed_errors = patterns
        return function

    return mark


def page_problems(page, allowed=()):
    """Return the uncaught exceptions and console errors `page` logged, minus the allowed ones."""
    problems = ["uncaught exception: " + error for error in page.errors]
    for message in page.console:
        if message.type in ERROR_CONSOLE_TYPES:
            problems.append("console {0}: {1}".format(message.type, _describe_console(message)))
    return [problem for problem in problems if not any(pattern in problem for pattern in allowed)]


def run_js_tests(page, url, timeout=30.0):
    """Run a browser unit-test page and report each of its tests on its own line.

    The page must set `window.__tests = {done, passed, failed, results: [{name, ok,
    error}]}` and flip `done` to true when finished. Raises AssertionError if any
    test failed, if none ran, or if the page never finished. Returns the results.
    """
    page.goto(url)
    try:
        page.wait_for(js="window.__tests && window.__tests.done === true", timeout=timeout)
    except WaitTimeout as exc:
        seen = page.eval("window.__tests ? (window.__tests.results || []).length : null")
        state = "window.__tests was never set" if seen is None else "{0} results so far".format(seen)
        raise AssertionError("{0} did not finish within {1:g}s ({2})".format(url, timeout, state)) from exc
    report = page.eval(
        "({passed: __tests.passed, failed: __tests.failed, results: __tests.results.map((r) => "
        "({name: String(r.name), ok: r.ok === true, error: r.error == null ? '' : String(r.error)}))})"
    )
    results = report["results"]
    failed = [result for result in results if not result["ok"]]
    for result in results:
        line = ("ok    " if result["ok"] else "FAIL  ") + result["name"]
        page.note(line if result["ok"] else line + ": " + result["error"])
    if not results:
        raise AssertionError("{0} finished without running a single test".format(url))
    if report["failed"] != len(failed) or report["passed"] != len(results) - len(failed):
        raise AssertionError(
            "{0} reports {1} passed and {2} failed, but its results list has {3} and {4}".format(
                url, report["passed"], report["failed"], len(results) - len(failed), len(failed)
            )
        )
    if failed:
        names = ", ".join(result["name"] for result in failed)
        raise AssertionError("{0} of {1} browser tests failed: {2}".format(len(failed), len(results), names))
    return results


# -- finding tests ---------------------------------------------------------------


def load_scenarios(directory):
    """Import every test_*.py in `directory`; return (cases, [(file, traceback)] for broken files)."""
    cases, broken = [], []
    for filename in sorted(os.listdir(directory)):
        if not (filename.startswith("test_") and filename.endswith(".py")):
            continue
        path = os.path.join(directory, filename)
        stem = filename[:-3]
        try:
            module = _import_file("e2e_scenario_" + stem, path)
        except Exception:
            broken.append((filename, traceback.format_exc()))
            continue
        for name, value in vars(module).items():
            if name.startswith("test_") and callable(value) and getattr(value, "__module__", "") == module.__name__:
                cases.append(Case(stem[len("test_") :], name[len("test_") :], value, path))
    return cases, broken


def _import_file(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def js_test_cases():
    """One case per top-level tests/js/*.html page, each run through `run_js_tests`."""
    if not os.path.isdir(JS_TESTS_DIR):
        return []
    cases = []
    for filename in sorted(os.listdir(JS_TESTS_DIR)):
        if not filename.endswith(".html"):
            continue
        path = REPO_MOUNT + "tests/js/" + filename

        def run_page(page, base_url, path=path):
            run_js_tests(page, base_url + path)

        cases.append(Case("js", filename[: -len(".html")], run_page, os.path.join(JS_TESTS_DIR, filename)))
    return cases


# -- running one test ------------------------------------------------------------


def run_case(browser, case, base_url, artifacts, always_shoot, full_trace):
    """Run one test with a fresh page and return its `Outcome`."""
    shot_path = os.path.join(artifacts, "{0}-{1}.png".format(case.scenario, case.name))
    _remove_stale(shot_path)
    started = time.monotonic()
    failure, notes, screenshot, page = None, [], None, None
    try:
        page = browser.new_page()
        failure = _exercise(page, case, base_url, full_trace)
        notes = list(page.notes)
        if failure is not None:
            failure = _with_diagnostics(failure, page)
        if failure is not None or always_shoot:
            screenshot, shot_error = _try_screenshot(page, shot_path)
            if shot_error:
                notes.append(shot_error)
    except Exception:
        # Not the test's fault: the browser itself could not give us a page.
        failure = "harness error:\n" + traceback.format_exc().rstrip()
    finally:
        close_error = _try_close(page)
        if close_error and failure is None:
            failure = close_error
    return Outcome(case, failure, time.monotonic() - started, notes, screenshot)


def _exercise(page, case, base_url, full_trace):
    """Call the test function, then check what its page logged. Return a failure text or None."""
    try:
        case.function(page, base_url)
        page.sync()
    except Exception as exc:
        return _describe_exception(exc, case.source, full_trace)
    problems = page_problems(page, getattr(case.function, "e2e_allowed_errors", ()))
    if problems:
        return "the page logged errors (allow expected ones with @allow_errors):\n" + "\n".join(problems)
    return None


def _describe_exception(exc, source, full_trace):
    """Say where in the scenario file the test failed, then what the failure was."""
    if full_trace:
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
    lines = []
    for frame in traceback.extract_tb(exc.__traceback__):
        if os.path.abspath(frame.filename) == os.path.abspath(source):
            lines.append("{0}:{1}  {2}".format(os.path.basename(frame.filename), frame.lineno, frame.line))
    message = str(exc)
    lines.append(type(exc).__name__ + (": " + message if message else ""))
    return "\n".join(lines)


def _with_diagnostics(failure, page):
    """Append what the page was doing when the test failed: its URL, its recent errors and
    warnings, its failed requests. Lines the failure already contains are not repeated."""
    lines = []
    try:
        lines.append("page: " + page.url)
    except Exception as exc:
        lines.append("page: (unreachable: {0})".format(exc))
    for error in page.errors[-5:]:
        lines.append("uncaught exception: " + error)
    for message in [m for m in page.console if m.type in ERROR_CONSOLE_TYPES + ("warning",)][-5:]:
        lines.append("console {0}: {1}".format(message.type, _describe_console(message)))
    for request in page.failed_requests[-5:]:
        lines.append("failed request: {0} {1} {2}".format(request.method, request.status or request.error, request.url))
    return "\n".join([failure] + [line for line in lines if line not in failure])


def _describe_console(message):
    where = ""
    if message.url:
        where = " ({0}{1})".format(message.url, ":{0}".format(message.line) if message.line else "")
    return message.text + where


def _display_path(path):
    """A path as a person would type it: relative when inside the current directory."""
    relative = os.path.relpath(path)
    return path if relative.startswith(os.pardir) else relative


def _try_screenshot(page, path):
    """Return (path, None) on success, (None, why) if the page could not be captured."""
    try:
        return page.screenshot(path, full_page=True), None
    except Exception as exc:
        return None, "screenshot failed: {0}".format(exc)


def _try_close(page):
    """Close the page; return a failure text if that was not possible."""
    if page is None:
        return None
    try:
        page.close()
    except Exception as exc:
        return "could not close the page: {0}".format(exc)
    return None


def _remove_stale(path):
    """Delete the previous run's screenshot so a passing test never keeps an old failure image."""
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


# -- reporting -------------------------------------------------------------------


class Reporter:
    """Print results as they happen: one line per test, details indented beneath."""

    def __init__(self, stream):
        self._stream = stream
        self._colour = stream.isatty()
        self._scenario = None

    def line(self, text=""):
        self._stream.write(text + "\n")
        self._stream.flush()

    def _paint(self, text, code):
        return "\033[{0}m{1}\033[0m".format(code, text) if self._colour else text

    def outcome(self, outcome):
        case = outcome.case
        if case.scenario != self._scenario:
            self._scenario = case.scenario
            self.line()
            self.line(case.scenario)
        status = self._paint("ok  ", "32") if outcome.failure is None else self._paint("FAIL", "1;31")
        self.line("  {0}  {1:<52} {2:6.2f}s".format(status, case.name, outcome.seconds))
        for note in outcome.notes:
            self.line("          " + note)
        if outcome.failure is not None:
            for text in outcome.failure.split("\n"):
                self.line("        " + text)
        if outcome.screenshot:
            self.line("        screenshot: " + _display_path(outcome.screenshot))

    def broken_scenario(self, filename, trace):
        self.line()
        self.line(self._paint("FAIL", "1;31") + "  {0} could not be imported".format(filename))
        for text in trace.rstrip().split("\n"):
            self.line("        " + text)

    def summary(self, outcomes, broken, seconds):
        failed = [outcome for outcome in outcomes if outcome.failure is not None]
        self.line()
        for outcome in failed:
            self.line("failed: {0}::{1}".format(outcome.case.scenario, outcome.case.name))
        for filename, _ in broken:
            self.line("failed: {0} (import error)".format(filename))
        counts = "{0} passed, {1} failed".format(len(outcomes) - len(failed), len(failed) + len(broken))
        self.line(self._paint(counts, "1;31" if failed or broken else "32") + " in {0:.2f}s".format(seconds))


# -- command line ----------------------------------------------------------------


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description="Run the First Light browser tests in headless Chrome.")
    parser.add_argument("--dir", default=os.path.join(ROOT, "dist"), help="directory to serve (default: dist/)")
    parser.add_argument("-k", dest="keyword", default="", help="only run tests whose 'scenario::test' contains this")
    parser.add_argument("--shots", action="store_true", help="save a screenshot of every test, not only failures")
    parser.add_argument("--headed", action="store_true", help="show the browser window (for debugging)")
    parser.add_argument("--trace", action="store_true", help="print full Python tracebacks for failures")
    parser.add_argument("--list", action="store_true", help="list the tests that would run and exit")
    parser.add_argument(
        "--allow-external",
        action="store_true",
        help="let pages reach the internet (by default every host but this machine is unreachable)",
    )
    parser.add_argument("--scenarios", default=DEFAULT_SCENARIOS, help="directory of test_*.py scenario files")
    parser.add_argument("--artifacts", default=DEFAULT_ARTIFACTS, help="directory for screenshots")
    return parser.parse_args(argv)


def _exit_on_sigterm(signum, frame):
    """Turn SIGTERM into a normal exit so Chrome and the temp profile are cleaned up."""
    sys.exit(128 + signum)


def run_cases(cases, base_url, options, reporter):
    """Run every case in one Chrome, replacing Chrome if a test managed to kill it."""

    def launch():
        return Browser(headless=not options.headed, block_external=not options.allow_external)

    outcomes = []
    browser = launch()
    try:
        reporter.line(
            "{0} ({1}), serving {2} at {3}".format(
                browser.version, "headed" if options.headed else "headless", _display_path(options.dir), base_url
            )
        )
        for case in cases:
            if not browser.alive:
                reporter.line("  Chrome is gone (crashed in the previous test?); starting a new one")
                browser.close()
                browser = launch()
            outcome = run_case(browser, case, base_url, options.artifacts, options.shots, options.trace)
            reporter.outcome(outcome)
            outcomes.append(outcome)
    finally:
        browser.close()
    return outcomes


def main(argv=None):
    options = parse_arguments(argv)
    signal.signal(signal.SIGTERM, _exit_on_sigterm)
    reporter = Reporter(sys.stdout)
    if not os.path.isdir(options.dir):
        reporter.line(
            "{0} is not a directory. Build the site first (python3 -m pipeline build) "
            "or pass --dir.".format(options.dir)
        )
        return 2
    if not os.path.isdir(options.scenarios):
        reporter.line("{0} is not a directory of scenarios.".format(options.scenarios))
        return 2
    cases, broken = load_scenarios(options.scenarios)
    cases = js_test_cases() + cases
    cases = [case for case in cases if options.keyword in "{0}::{1}".format(case.scenario, case.name)]
    if options.list:
        for case in cases:
            reporter.line("{0}::{1}".format(case.scenario, case.name))
        return 0
    started = time.monotonic()
    outcomes = []
    if cases:
        try:
            with StaticServer(options.dir, {REPO_MOUNT: ROOT}) as server:
                outcomes = run_cases(cases, server.url, options, reporter)
        except BrowserError as exc:
            reporter.line("cannot run the browser tests: {0}".format(exc))
            return 2
        except KeyboardInterrupt:
            reporter.line("interrupted")
            return 130
    for filename, trace in broken:
        reporter.broken_scenario(filename, trace)
    if not cases and not broken:
        reporter.line("no tests matched" + (" -k {0!r}".format(options.keyword) if options.keyword else ""))
        return 1
    reporter.summary(outcomes, broken, time.monotonic() - started)
    return 1 if broken or any(outcome.failure is not None for outcome in outcomes) else 0


if __name__ == "__main__":
    sys.exit(main())
