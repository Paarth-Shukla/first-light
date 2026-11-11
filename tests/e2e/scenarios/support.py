"""Shared helpers for the First Light scenarios (not a scenario itself: no test_ functions).

Expectations are always derived from the data the site actually serves, read from the
served directory on disk, so the suite keeps passing as the news changes.
"""

import functools
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata

from tests.e2e.run import StaticServer, parse_arguments

SECTIONS = ["world", "india", "ai", "ml", "llm", "labs", "companies", "markets", "india-markets", "science"]

# The coverage scale from site/js/core/ui.js (DESIGN.md: "Coverage is the typography").
FRONT_STEP = {4: "hl-5", 3: "hl-4", 2: "hl-3", 1: "hl-1"}
DESK_STEP = {4: "hl-4", 3: "hl-3", 2: "hl-2", 1: "hl-1"}
WIDE_STEP = {4: "hl-5", 3: "hl-4", 2: "hl-3", 1: "hl-1"}
RAIL_STEP = {4: "hl-6", 3: "hl-5", 2: "hl-4", 1: "hl-2"}


def tier(n):
    n = n or 1
    return 4 if n >= 9 else 3 if n >= 6 else 2 if n >= 3 else 1


# -- the served site on disk ---------------------------------------------------------


@functools.lru_cache(maxsize=1)
def site_root():
    """The directory the runner is serving (its --dir), or $FL_E2E_DIR."""
    if os.environ.get("FL_E2E_DIR"):
        return os.path.abspath(os.environ["FL_E2E_DIR"])
    try:
        options = parse_arguments(sys.argv[1:])
        return os.path.abspath(options.dir)
    except SystemExit:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "dist"))


def data_path(path):
    return os.path.join(site_root(), "data", path)


def has_data(path):
    return os.path.exists(data_path(path))


@functools.lru_cache(maxsize=64)
def data(path):
    """A published JSON file as the site would load it."""
    with open(data_path(path), encoding="utf-8") as handle:
        return json.load(handle)


def manifest():
    return data("manifest.json")


def edition():
    return data("editions/{0}.json".format(manifest()["edition"]["date"]))


def edition_stories(ed=None):
    ed = ed or edition()
    stories = [ed.get("lead")] + list(ed.get("front") or []) + list(ed.get("briefs") or [])
    for section in ed.get("sections") or []:
        stories.extend(section.get("stories") or [])
    return [story for story in stories if story]


def latest():
    return data("latest.json")


def playbook():
    return data("claude/playbook.json")


def updates():
    return data("claude/updates.json")


def markets():
    return data("markets.json")


def weekend_index():
    return data("weekend/index.json")


def search_docs():
    """Every search doc the worker would load: the static docs and every month shard."""
    info = data("search/manifest.json")
    docs = []
    if info.get("static"):
        docs.extend(data("search/" + info["static"]))
    for shard in info.get("shards") or []:
        if has_data("search/" + shard["file"]):
            docs.extend(data("search/" + shard["file"]))
    return docs


def lexicon():
    return data("search/lexicon.json")


STOPWORDS = set(
    """a about above across after again against all almost also although always am among an and
another any are aren around as at be because been before being below between both but by can
cannot could couldn did didn do does doesn doing don down during each either even ever every
few for from further had hadn has hasn have haven having he her here hers herself him himself
his how however i if in into is isn it its itself just ll may me might more most much must my
myself neither no nor not now of off often on once only or other our ours ourselves out over
own per rather re same shall she should shouldn since so some still such than that the their
theirs them themselves then there these they this those though through to too toward towards
under until up upon ve very was wasn we were weren what when where whether which while who
whom whose why will with within without won would wouldn yet you your yours yourself yourselves
says said new report reports amid via video watch live update updates""".split()
)

_CANDIDATE = re.compile(r"[a-z0-9]+(?:[&.\-][a-z0-9]+)*(?:\++(?![a-z0-9+]))?")


def tokenize(text):
    """The tokenizer from ARCHITECTURE.md (mirrors site/js/search/engine.js)."""
    folded = unicodedata.normalize("NFKD", str(text or ""))
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch)).lower()
    out = []
    for match in _CANDIDATE.finditer(folded):
        candidate = match.group(0)
        parts = [candidate] if re.search(r"[0-9]", candidate) else re.split(r"[.\-]", candidate)
        for part in parts:
            if len(part) > 1 or re.fullmatch(r"[0-9]", part):
                out.append(part)
    return out


# -- driving the app -----------------------------------------------------------------

# Records the last hash the app has reacted to (after every hashchange listener ran, and
# on replaceState), so "ready" never means "the previous view was ready".
HASH_HOOK = """
(() => {
  window.__flHash = location.hash;
  addEventListener('hashchange', () => setTimeout(() => { window.__flHash = location.hash; }, 0));
  const replace = history.replaceState.bind(history);
  history.replaceState = (...args) => { replace(...args); window.__flHash = location.hash; };
})();
"""

READY = (
    "(() => { const v = document.querySelector('#view');"
    " return !!v && !v.hasAttribute('aria-busy') && !v.querySelector('.boot')"
    " && (window.__flHash === undefined || window.__flHash === location.hash)"
    " && !!document.querySelector('#mast') && !!document.querySelector('#mast').children.length; })()"
)


def hook(page):
    if not getattr(page, "_fl_hooked", False):
        page.add_init_script(HASH_HOOK)
        page._fl_hooked = True


def wait_ready(page, timeout=10):
    """Wait until the router has finished setting the view for the current hash."""
    page.wait_for(js=READY, timeout=timeout)


def open_route(page, base_url, route="/", timeout=10):
    """Load the app fresh at `route` (e.g. "/wire" or "/search?q=x") and wait for the view."""
    hook(page)
    page.goto("{0}/#{1}".format(base_url, route))
    wait_ready(page, timeout)


def go(page, route, timeout=10):
    """Same-document navigation to `route`, as a link click would do."""
    page.eval("(r) => { location.hash = '#' + r; }", route)
    wait_ready(page, timeout)


def wait_route(page, prefix, timeout=10):
    """After a click or key that navigates: wait for the hash, then for its view."""
    page.wait_for(js="location.hash.startsWith({0})".format(json.dumps(prefix)), timeout=timeout)
    wait_ready(page, timeout)


def wait_text(page, selector, text, timeout=10):
    """Wait until the element's textContent contains `text`, ignoring case (labels are
    upper-cased by CSS, which innerText would report). Returns the textContent."""
    return page.wait_for(
        js="(() => {{ const el = document.querySelector({0}); const t = el ? el.textContent : '';"
        " return t.toLowerCase().includes({1}) ? t : null; }})()".format(json.dumps(selector), json.dumps(text.lower())),
        timeout=timeout,
    )


def text_of(page, selector):
    """textContent of the first match, whitespace collapsed (no CSS case transforms)."""
    return page.eval("(s) => (document.querySelector(s)?.textContent || '').replace(/\\s+/g, ' ').trim()", selector)


def texts_of(page, selector):
    return page.eval("(s) => [...document.querySelectorAll(s)].map((e) => e.textContent.replace(/\\s+/g, ' ').trim())", selector)


def route_of(page):
    return page.eval("location.hash")


def query_of(page):
    """The current hash route's query as a dict."""
    return page.eval("Object.fromEntries(new URLSearchParams((location.hash.split('?')[1] || '')))")


def reload(page, timeout=10):
    page.reload()
    wait_ready(page, timeout)


def storage_json(page, key):
    raw = page.local_storage_get(key)
    return None if raw is None else json.loads(raw)


def fetch_text(page, path):
    """GET a URL relative to the page; returns {status, type, text}."""
    return page.eval(
        "(p) => fetch(p, {cache: 'no-store'}).then(async (r) => ({status: r.status, type: r.headers.get('content-type'), text: await r.text()}))",
        path,
    )


def click_button(page, container, text, tag="button"):
    """Click the first `tag` inside `container` whose text, trimmed and case-folded, equals or starts with `text`."""
    index = page.eval(
        "(c, t, tag) => { const all = [...document.querySelectorAll(c + ' ' + tag)];"
        " const want = t.toLowerCase();"
        " let i = all.findIndex((b) => b.textContent.trim().toLowerCase() === want);"
        " if (i < 0) i = all.findIndex((b) => b.textContent.trim().toLowerCase().startsWith(want));"
        " if (i < 0) return -1; all.forEach((b) => b.removeAttribute('data-e2e-target'));"
        " all[i].setAttribute('data-e2e-target', '1'); return i; }",
        container,
        text,
        tag,
    )
    assert index >= 0, "no {0} {1!r} in {2}".format(tag, text, container)
    page.click("[data-e2e-target='1']")
    page.eval("document.querySelector(\"[data-e2e-target='1']\")?.removeAttribute('data-e2e-target')")


def grant_clipboard(page, base_url):
    """Let the page read and write the clipboard without a prompt."""
    page.browser.cdp.send(
        "Browser.grantPermissions",
        {
            "permissions": ["clipboardReadWrite", "clipboardSanitizedWrite"],
            "origin": base_url,
            "browserContextId": page._context_id,
        },
    )


def read_clipboard(page):
    return page.eval("navigator.clipboard.readText()")


def forgive_missing(page, path):
    """Drop the console line Chrome logs for a 404 on `path`, for a file this build legitimately lacks."""
    page.sync()
    page.console[:] = [m for m in page.console if not (m.type == "error" and path in (m.url or "") + m.text)]


def no_horizontal_scroll(page):
    return page.eval("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")


# -- a modified copy of the site -----------------------------------------------------


class SiteVariant:
    """Serve a copy of the site with some files removed or replaced, on its own port.

    The copy is a tree of symlinks into the real site, so it costs almost nothing;
    only the directories that hold a changed file are real. Use as a context manager:

        with SiteVariant(remove=["data/markets.json"]) as site:
            page.goto(site.url + "/#/markets")
    """

    def __init__(self, remove=(), replace=None, source=None, page=None):
        self.page = page
        self.source = os.path.abspath(source or site_root())
        self.remove = set(os.path.normpath(p) for p in remove)
        self.replace = {os.path.normpath(k): v for k, v in (replace or {}).items()}
        self.root = None
        self.server = None
        self.url = None

    def __enter__(self):
        self.root = tempfile.mkdtemp(prefix="fl-e2e-site-")
        touched = self.remove | set(self.replace)
        self._mirror(self.source, self.root, "", touched)
        for rel, content in self.replace.items():
            target = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.islink(target):
                os.unlink(target)
            if not isinstance(content, (str, bytes)):
                content = json.dumps(content)
            mode = "wb" if isinstance(content, bytes) else "w"
            with open(target, mode, **({} if mode == "wb" else {"encoding": "utf-8"})) as handle:
                handle.write(content)
        self.server = StaticServer(self.root)
        self.url = self.server.url
        return self

    def _mirror(self, src, dst, rel, touched):
        os.makedirs(dst, exist_ok=True)
        for name in os.listdir(src):
            child_rel = os.path.normpath(os.path.join(rel, name)) if rel else name
            if child_rel in self.remove:
                continue
            source_path = os.path.join(src, name)
            target = os.path.join(dst, name)
            inside = any(path.startswith(child_rel + os.sep) for path in touched)
            if inside and os.path.isdir(source_path):
                self._mirror(source_path, target, child_rel, touched)
            elif child_rel in self.replace:
                continue
            else:
                os.symlink(os.path.realpath(source_path), target)

    def __exit__(self, exc_type, exc, tb):
        if self.page is not None:
            # leave the copy before it stops being served, so no late request (an icon) fails
            try:
                self.page.goto("about:blank")
            except Exception:
                pass
        if self.server:
            self.server.close()
        if self.root:
            shutil.rmtree(self.root, ignore_errors=True)
