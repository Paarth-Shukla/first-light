# Browser tests

End-to-end tests that drive a real headless Chrome over the DevTools protocol.
Python 3.9 standard library only: no Node, no Playwright, no pip.

| File | What it is |
|---|---|
| `cdp.py` | RFC 6455 WebSocket client and a DevTools session (commands, replies, events) |
| `browser.py` | `Browser` (launches and always cleans up Chrome) and the `Page` API below |
| `run.py` | the runner: static server, discovery, report, screenshots, exit status |
| `scenarios/test_*.py` | the tests |
| `fixtures/` | pages the harness tests itself against |
| `../../scripts/shot.py` | screenshot a URL or a local page from the command line |

## Run

```
python3 -m pipeline build                      # the runner builds nothing; dist/ must exist
python3 tests/e2e/run.py                       # everything, against dist/
python3 tests/e2e/run.py -k wire               # only tests whose "scenario::test" contains "wire"
python3 tests/e2e/run.py --shots               # also keep a screenshot of every passing test
python3 tests/e2e/run.py --headed -k palette   # watch it happen in a visible window
python3 tests/e2e/run.py --list                # what would run
python3 tests/e2e/run.py --dir some/folder     # serve another directory at /
python3 tests/e2e/run.py --trace               # full Python tracebacks on failure
```

Exit status: 0 all passed, 1 something failed or nothing matched, 2 could not start
(no `dist/`, no Chrome). Chrome is found at `CHROME_BIN`, else the usual macOS and
Linux locations; extra flags go in `CHROME_EXTRA_ARGS` (for example `--no-sandbox` in a
container that cannot run Chrome's sandbox).

Failure screenshots are full-page PNGs in `tests/e2e/artifacts/<scenario>-<test>.png`
(git-ignored). A test that passes again has its old screenshot removed.

When in doubt, check the harness itself first (about 30 s; the last six tests each start
another Chrome, and only run when the fixture directory is the one being served):

```
python3 tests/e2e/run.py --dir tests/e2e/fixtures/selfcheck -k harness_selfcheck
```

## What the runner guarantees

- **A fresh page per test**, in its own browser context: empty localStorage, cookies and caches.
- **Same starting conditions everywhere**: 1280x800 viewport, light colour scheme, full motion,
  whatever the machine running the tests is set to.
- **No internet.** Every host except this machine fails to resolve, instantly. Such requests
  are listed in `page.blocked_requests` and are not errors, so remote images simply fail to
  load, as they would for a reader offline. `--allow-external` turns this off.
- **Errors fail the test.** If the page logged an uncaught exception, an unhandled promise
  rejection, a `console.error`, or a failed resource (a 404 is a console error in Chrome),
  the test fails even if every assertion passed. Opt out per test with `@allow_errors`.
- **The repository is mounted at `/__repo__/`** next to the served directory, so a test page
  can use relative URLs into the source tree: `base_url + "/__repo__/tests/js/index.html"`
  can import `../../site/js/core/textutil.js` and fetch `../fixtures/stem-vectors.json`.

## Write a scenario

Add `tests/e2e/scenarios/test_<area>.py`. Every module-level function named `test_*` is a
test and receives a fresh `page` and the server's `base_url` (no trailing slash).

```python
from tests.e2e.run import allow_errors


def test_slash_focuses_search(page, base_url):
    page.goto(base_url + "/#/wire")
    page.wait_for(".wire-item")              # the app renders after load: wait for what you need
    page.press("/")
    assert page.eval("document.activeElement.id") == "search-input"
    page.type("nvidia")
    page.press("Enter")
    assert "nvidia" in page.wait_for_text("#results h1", "nvidia").lower()


@allow_errors("ERR_INTERNET_DISCONNECTED")   # only this error is expected; any other still fails
def test_offline_banner(page, base_url):
    page.goto(base_url + "/")
    page.set_offline(True)
    page.wait_for("#offline-banner", visible=True)
```

Habits that keep tests reliable:

- After `goto`, a click or a key press, **wait for the result** (`wait_for`, `wait_for_text`)
  instead of sleeping. `text`, `attr`, `click`, `hover` and `fill` already wait up to 5 s
  for their element to exist; `count`, `exists`, `visible` and `texts` answer about right now.
- Put the actual value in assertion messages: `assert n == 3, n`.
- To start from a known state, seed it before the app boots:
  `page.add_init_script("localStorage.setItem('fl.visit', '...')")`, then `goto`.
- Times shown to the reader depend on the machine's zone unless you call `page.set_timezone(...)`.
- `page.note("...")` adds a line under the test in the report.

### Browser unit tests

Every top-level `tests/js/*.html` is run automatically as a test named `js::<file>`. Such a
page runs its own tests and publishes the outcome:

```js
window.__tests = { done: false, passed: 0, failed: 0, results: [] };   // {name, ok, error}
// ... run, push results, count ...
window.__tests.done = true;
```

Each result becomes a line in the report; one failure, or no results at all, fails the test.
From a scenario: `run_js_tests(page, base_url + "/__repo__/tests/js/index.html")`.

## Page API

Navigation
- `goto(url, wait="load", timeout=15)`: `wait` is `load`, `domcontentloaded`, `networkidle`
  or `commit`. Changing only the `#route` is a same-document navigation; `goto` returns once
  the page's `hashchange` handlers have run. Raises `NavigationError`.
- `reload(wait="load")`, `url` (property), `title()`.

Waiting
- `wait_for(selector, timeout=5, visible=False)`: element exists (and, with `visible`, has a
  size and is not hidden).
- `wait_for(js="expression", timeout=5)`: expression is truthy; returns its value.
- `wait_for_text(selector, text, timeout=5)`: visible text contains `text`; returns the text.
- All raise `WaitTimeout` naming what never happened.

Reading
- `eval(js, *args)`: value of a JS expression as Python data; promises are awaited. With
  `args`, `js` is a function: `page.eval("(a, b) => a + b", 1, 2)`. Raises `JSError` with the
  page's stack. Use expressions, not `const x = ...` statements (a second evaluation would
  redeclare `x`).
- `text(selector)`, `texts(selector)`, `attr(selector, name)`, `count(selector)`,
  `exists(selector)`, `visible(selector)`.

Mouse and keyboard (real, trusted events: the site's own listeners fire)
- `click(selector)`: scrolls into view, waits until the element holds still and is not
  covered or disabled, then presses and releases at its centre. Raises `ClickError` saying
  what was in the way.
- `hover(selector)`.
- `press(key, modifiers=())`: `press("Escape")`, `press("/")`, `press("j")`,
  `press("Meta+k")`, `press("k", ["Meta"])`. Keys: one US-keyboard character, or `Enter Tab
  Escape Backspace Delete Space ArrowLeft ArrowUp ArrowRight ArrowDown Home End PageUp
  PageDown`. Modifiers: `Alt Control Meta Shift` (`Ctrl`, `Cmd`, `Option` also accepted).
  OS shortcuts are not emulated: `Meta+a` reaches the page's handler but does not select all.
- `type(text)`: one key press per character into the focused element; `\n` is Enter.
  Characters no US keyboard has are inserted as an input method would.
- `fill(selector, text)`: click an input or textarea, clear it, type.

Emulation
- `set_viewport(width, height, mobile=False, scale=1)`: `mobile=True` adds touch.
- `emulate_dark(True)`, `emulate_reduced_motion(True)`, `set_timezone("Asia/Kolkata")`.
- `set_offline(True)`: requests fail and `navigator.onLine` flips.
- `add_init_script(js)`: runs before the page's own scripts on every later load.

Storage
- `local_storage_get(key)` returns the raw string or `None`;
  `local_storage_set(key, value)` stores a string as is and anything else as JSON.
- `clear_storage()`: wipes the origin's localStorage, sessionStorage, IndexedDB, caches and
  cookies. Reload afterwards to see a first visit.

Files and dialogs
- `screenshot(path, full_page=False)`.
- `set_files(selector, [paths])` for `<input type="file">`.
- `wait_for_download()` returns `Download(filename, path)`; downloads land in the temporary
  profile, never in `~/Downloads`.
- `alert`/`confirm`/`prompt` are answered automatically from `page.dialog_answer` (`True`
  accept, `False` dismiss, a string as the prompt's text) and recorded in `page.dialogs`.

What the page logged
- `console`: `ConsoleMessage(type, text, url, line)` for every `console.*` call and browser log entry.
- `errors`: uncaught exceptions and unhandled rejections, as text with the stack.
- `failed_requests`: `FailedRequest(url, status, error, method, kind)` for network failures
  and HTTP status 400 or above. Requests the page itself aborted are not listed, nor is
  Chrome's own `/favicon.ico` probe, nor are requests made inside a Web Worker (a worker's
  `console.error` and uncaught exceptions are captured in `console`).
- `blocked_requests`: URLs on other hosts that were refused.
- `sync()`: wait until everything logged so far has arrived; call it before asserting on the
  lists above right after an action. `page_problems(page)` (from `tests.e2e.run`) returns
  what the runner would fail the test for.
- `cdp`: the raw DevTools session (`page.cdp.send("Domain.method", {...})`,
  `page.cdp.wait_for_event(name, predicate, timeout)`) for anything not wrapped here.

## Screenshots from the command line

```
python3 scripts/shot.py dist/index.html out.png
python3 scripts/shot.py "dist/index.html#/wire" wire.png --full --dark
python3 scripts/shot.py dist/ phone.png --mobile --wait-for ".front-page" --delay 300
python3 scripts/shot.py http://localhost:8080/ out.png --width 1440 --height 900 --eval "document.title"
```

A local path is served over HTTP (from the current directory when the file is inside it, so
`../` references work; `--root DIR` overrides). `--wait-for` waits for a visible element,
then `--eval` runs and its value is printed, then `--delay`, then the capture. Unlike the
tests, `shot.py` lets the page reach the internet, so real images appear. Page errors and
failed requests are listed on stderr; the exit status is 1 if the page could not be opened
or the `--wait-for` element never appeared (the screenshot is still written).
