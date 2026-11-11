"""Night edition and accessibility basics: tokens, headings, names, focus, motion, contrast."""

from tests.e2e.scenarios import support as S

CONTRAST = """
(selectors) => {
  const parse = (c) => { const m = (c.match(/[\\d.]+/g) || [0, 0, 0, 0]).map(Number); return m.length >= 4 ? m.slice(0, 4) : [...m, 1]; };
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const bg = (el) => { for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c[3] > 0.5) return c; } return [255, 255, 255, 1]; };
  const ratio = (el) => { const a = lum(parse(getComputedStyle(el).color)), b = lum(bg(el)); return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05); };
  const out = {};
  for (const sel of selectors) {
    const els = [...document.querySelectorAll(sel)].filter((e) => e.getClientRects().length && e.textContent.trim() && getComputedStyle(e).visibility !== 'hidden');
    if (els.length) {
      let worst = null;
      for (const el of els.slice(0, 40)) { const r = ratio(el); if (!worst || r < worst.r) worst = { r: Math.round(r * 100) / 100, text: el.textContent.trim().slice(0, 40) }; }
      out[sel] = worst;
    }
  }
  return out;
}
"""

TEXT = [".story__sum", ".row__sum", ".lead__deck", ".brief__hl", ".row__title", ".hit__sum", ".colophon p", ".notice__body", ".method", ".prose p"]
LABELS = [".folio p", ".story__meta", ".story__src", ".brief__meta", ".lead__why", ".wire__src", ".wire__time", ".nameplate__tag", ".topbar__date span",
          ".end__next", ".desks .num", ".cov", ".tag", ".tabbar .label", ".tape .label", ".chg--down", ".chg--up", ".thread", ".tag--spot", ".is-stale",
          ".story.is-read .story__hl a", ".wire__row.is-read .wire__hl", "kbd", ".clipper"]

NAMELESS = """
(() => {
  const name = (el) => {
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
    const by = el.getAttribute('aria-labelledby');
    if (by) return by.split(/\\s+/).map((id) => document.getElementById(id)?.textContent || '').join(' ');
    if (el.labels && el.labels.length) return [...el.labels].map((l) => l.textContent).join(' ');
    const text = [...el.childNodes].map((n) => n.nodeType === 3 ? n.textContent : (n.getAttribute && n.getAttribute('aria-hidden') === 'true' ? '' : n.textContent)).join('');
    return text.trim() || el.getAttribute('title') || el.getAttribute('placeholder') || '';
  };
  return [...document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, [role=button]')]
    .filter((el) => !el.hidden && !(el.type === 'file'))
    .filter((el) => !name(el).trim())
    .map((el) => el.outerHTML.slice(0, 160));
})()
"""


def routes():
    book = S.playbook()
    story = S.latest()["stories"][0]
    return ["/", "/wire", "/s/" + S.manifest()["sections"][0]["id"], "/story/{0}?d={1}".format(story["id"], story["day"]), "/markets",
            "/weekend", "/claude", "/claude/updates", "/claude/playbook", "/claude/feature/" + book["features"][0]["id"],
            "/claude/recipe/" + book["recipes"][0]["id"], "/search?q=markets", "/clippings", "/archive", "/settings", "/colophon"]


def test_night_edition_uses_dark_tokens(page, base_url):
    S.open_route(page, base_url, "/")
    light = page.eval("({paper: getComputedStyle(document.documentElement).getPropertyValue('--paper').trim(), bg: getComputedStyle(document.body).backgroundColor, ink: getComputedStyle(document.body).color})")
    page.emulate_dark(True)
    page.wait_for(js="getComputedStyle(document.body).backgroundColor !== {0!r}".format(light["bg"]))
    dark = page.eval("({paper: getComputedStyle(document.documentElement).getPropertyValue('--paper').trim(), bg: getComputedStyle(document.body).backgroundColor, ink: getComputedStyle(document.body).color})")
    assert dark["paper"] != light["paper"], (light, dark)
    lum = page.eval("(c) => { const [r, g, b] = c.match(/\\d+/g).map(Number); return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255; }", dark["bg"])
    assert lum < 0.15, "night paper is not dark: " + dark["bg"]
    ink = page.eval("(c) => { const [r, g, b] = c.match(/\\d+/g).map(Number); return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255; }", dark["ink"])
    assert ink > 0.75, "night ink is not light: " + dark["ink"]
    # the toggle and the browser chrome colour follow the system change (a matchMedia listener)
    page.wait_for(js="document.querySelector('.theme-toggle').getAttribute('aria-pressed') === 'true'"
                     " && document.querySelector('meta[name=theme-color]').content === '#0a0a0b'", timeout=3)
    # an explicit day edition wins over the system
    page.click(".theme-toggle")
    assert page.eval("document.documentElement.dataset.theme") == "light"
    assert page.eval("getComputedStyle(document.body).backgroundColor") == light["bg"]


def test_one_h1_names_and_alt_on_every_page(page, base_url):
    S.open_route(page, base_url, "/")
    problems = []
    for route in routes():
        S.go(page, route)
        h1 = page.count("h1")
        if h1 != 1:
            problems.append((route, "{0} h1".format(h1)))
        alt = page.eval("[...document.images].filter((i) => !i.hasAttribute('alt')).map((i) => i.src)")
        if alt:
            problems.append((route, "img without alt", alt[:3]))
        nameless = page.eval(NAMELESS)
        if nameless:
            problems.append((route, "no accessible name", nameless[:3]))
        ids = page.eval("(() => { const seen = {}; for (const e of document.querySelectorAll('[id]')) seen[e.id] = (seen[e.id] || 0) + 1; return Object.keys(seen).filter((k) => seen[k] > 1); })()")
        if ids:
            problems.append((route, "duplicate ids", ids))
    if not S.has_data("status.json"):
        S.forgive_missing(page, "status.json")
    assert not problems, problems


RING = (
    "(() => { const e = document.activeElement; const s = getComputedStyle(e);"
    " const form = e.closest('form'); const row = e.closest('.is-cursor');"
    " const ring = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || s.boxShadow !== 'none'"
    "   || (form && getComputedStyle(form).boxShadow !== 'none') || (row && getComputedStyle(row).backgroundColor !== getComputedStyle(document.body).backgroundColor);"
    " return {tag: e.tagName, cls: e.className, text: e.textContent.trim().slice(0, 30), ring}; })()"
)


def tab_through(page, count, shift=False):
    invisible, seen = [], []
    for _ in range(count):
        page.press("Tab", ["Shift"] if shift else [])
        state = page.eval(RING)
        seen.append(state["tag"])
        if not state["ring"]:
            invisible.append(state)
    return invisible, seen


def test_focus_is_visible_on_tab(page, base_url):
    for route, count in (("/", 20), ("/wire", 30), ("/claude", 20)):
        S.open_route(page, base_url, route)
        invisible, seen = tab_through(page, count)
        assert not invisible, "{0}: focused without a visible ring: {1}".format(route, invisible[:5])
        assert "A" in seen and len(seen) == count
    # backwards from the page reaches the masthead navigation, with a ring there too
    S.open_route(page, base_url, "/")
    invisible, _ = tab_through(page, 12, shift=True)
    assert not invisible, invisible[:5]


def test_skip_link_shows_and_moves_to_the_view(page, base_url):
    S.open_route(page, base_url, "/wire")
    page.eval("document.querySelector('a.skip').focus()")
    box = page.eval("(() => { const r = document.activeElement.getBoundingClientRect(); return {top: r.top, h: r.height, w: r.width}; })()")
    assert box["top"] >= 0 and box["h"] > 0 and box["w"] > 1, "the skip link does not show when focused: {0}".format(box)
    assert page.eval(RING)["ring"]
    page.press("Enter")
    page.wait_for(js="document.activeElement.id === 'view'")
    assert page.eval("location.hash") in ("#/wire", "#view"), page.eval("location.hash")


def test_no_running_animations_with_reduced_motion(page, base_url):
    page.emulate_reduced_motion(True)
    S.open_route(page, base_url, "/")
    page.press("n")
    page.click(".lead .clipper")
    running = page.eval("document.getAnimations().filter((a) => a.playState === 'running').map((a) => (a.animationName || a.transitionProperty || 'anim') + ' on ' + (a.effect?.target?.className || ''))")
    assert not running, running
    page.set_viewport(390, 844, mobile=True)
    page.click("#tabbar [data-sheet=true]")
    running = page.eval("document.getAnimations().filter((a) => a.playState === 'running').map((a) => (a.animationName || a.transitionProperty || 'anim') + ' on ' + (a.effect?.target?.className || ''))")
    assert not running, running
    durations = page.eval("[...document.querySelectorAll('#desk-index, #toast, .sun, .flap span')].map((e) => getComputedStyle(e).transitionDuration + '/' + getComputedStyle(e).animationName)")
    for value in durations:
        duration, name = value.split("/")
        assert all(float(d.strip().rstrip("s") or 0) == 0 for d in duration.split(",")) and name == "none", durations


def contrast_problems(page, minimum=4.5):
    found = page.eval(CONTRAST, TEXT + LABELS)
    return {sel: v for sel, v in found.items() if v["r"] < minimum}, found


def test_contrast_day_and_night(page, base_url):
    read = S.edition()["front"][0]["id"]
    page.add_init_script("localStorage.setItem('fl.read', JSON.stringify({{{0!r}: Date.now()}}))".format(read))
    failures = []
    for dark in (False, True):
        page.emulate_dark(dark)
        S.open_route(page, base_url, "/")
        for route in ("/", "/wire", "/markets", "/claude/updates", "/colophon"):
            S.go(page, route)
            bad, found = contrast_problems(page)
            if bad:
                failures.append(("night" if dark else "day", route, bad))
        page.note("{0}: body text {1}".format("night" if dark else "day", {k: v["r"] for k, v in found.items() if k in TEXT}))
    if not S.has_data("status.json"):
        S.forgive_missing(page, "status.json")
    assert not failures, failures
