#!/usr/bin/env python3
"""Typesets the First Light "Bulletin" prototype from ../../fixture.json.

    python3 build.py        -> index.html (front page), components.html (stylebook)

Standard library only. The output is plain static HTML; styles.css carries
the whole design system. This script stands in for the real app's typesetter:
it shows which decisions are data (headline step from sourceCount) and which
are editorial (which stories make the front).
"""
import hashlib
import html
import json
import math
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
FIXTURE = HERE.parent.parent / "fixture.json"

EDITION_NO = 315
EDITION_DATE = "Wednesday 11 November 2026"
EDITION_ISO = "2026-11-11"
FROZEN = "05:30"
FROZEN_MIN = 5 * 60 + 30

DESKS = [  # key, number, name
    ("world", "01", "World"),
    ("india", "02", "India"),
    ("ai", "03", "AI"),
    ("ml", "04", "Machine Learning"),
    ("llm", "05", "LLMs"),
    ("labs", "06", "Frontier Labs"),
    ("companies", "07", "Companies"),
    ("markets", "08", "Markets"),
    ("india-markets", "09", "Dalal Street"),
    ("science", "10", "Science"),
]
DESK = {k: (n, name) for k, n, name in DESKS}

# Feed summaries arrive truncated or with boilerplate. The app trims to whole
# sentences; these are the cases where the trim needs a hand.
SUMMARY_FIX = {
    "Falkland Islanders": "The people of the Falkland Islands face “devastating consequences” if Argentina is successful in blocking development of its offshore oilfield …",
    "Anthropic has its own": "For years, Anthropic has been known for its focus on enterprise and coding tools that attract high-flying corporate clients, inspiring competing frontier labs – like OpenAI, SpaceXSI, and Meta – to copy its strategies.",
    "Kenyan doomsday": "Paul Mackenzie convicted over deaths of children and one adult after followers were ordered to starve themselves and their families.",
    "Yonkers Rises": "",
    "Cork Takes the Heat": "Amorim Cork Solutions is contributing its P50 cork-based thermal protection material to DRACO, a European Space Agency mission.",
    "Bajaj Finance": "Bajaj Finance Ltd. is gearing up for a major share sale aimed at raising an impressive 117 billion rupees.",
    "Lucid CEO": "Lucid CEO Silvio Napoli admitted on the company’s Q3 earnings call that, as recently as this summer, the automaker “did not even know where cars were.”",
    "Locating the source": "Our house has a box room, full of boxes that we still haven’t unpacked from our last move. A couple of weeks ago something in that room started intermittently beeping.",
    "Stocks making the biggest": "",
}
LEAD_DECK = "Countries clash over Sea Lion project as Hamburg tribunal risks deepening sovereignty dispute"


def smart(s):
    """Typesetter's quotes and dashes: feeds send typewriter ones."""
    s = re.sub(r"(?<=\w)'(?=\w)", "’", s)                 # Trump's
    s = re.sub(r'(^|[\s(\[])"', r"\1“", s)                 # opening
    s = s.replace('"', "”")                                # the rest close
    s = re.sub(r"(^|[\s(\[])'", r"\1‘", s)
    s = s.replace("'", "’")
    s = s.replace(" - ", " – ").replace(" — ", " – ")
    return s


def esc(s):
    return html.escape(smart(s), quote=True)


def hl(s):
    """A headline: typeset, and never broken inside a compound such as 10-year."""
    return re.sub(r"(\d[\d,.]*-[A-Za-z]+)", r'<span class="nb">\1</span>', esc(s))


def load():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return data["stories"]


STORIES = load()


def find(fragment):
    for s in STORIES:
        if fragment in s["title"]:
            return s
    raise KeyError(fragment)


def summary(s, sentences=2):
    for k, v in SUMMARY_FIX.items():
        if k in s["title"]:
            return v
    raw = (s.get("summary") or "").strip()
    if not raw:
        return ""
    raw = raw.replace(" .", ".").replace(" - ", " – ")
    # a sentence ends at . ! ? (and an optional closing quote), not at a bare
    # closing quote and not after a title such as Dr. or Mr.
    guarded = re.sub(r"\b(Dr|Mr|Mrs|Ms|St|Prof|Rs|No|vs)\.\s", lambda m: m.group(1) + ".\x00", raw)
    parts = re.split(r"(?:(?<=[.!?])|(?<=[.!?][”\"’]))\s+(?=[A-Z“‘\"])", guarded)
    parts = [p.replace("\x00", " ") for p in parts]
    whole = [p for p in parts if re.search(r"[.!?][”\"’]?$", p)]
    if not whole:
        # a single unterminated line (deck-style summaries): close it and use it
        if len(raw) < 190 and not raw.endswith(("…", "[…]")) and len(parts) == 1:
            return parts[0] + "."
        return ""
    out = " ".join(whole[:sentences])
    return out


def stamp(s):
    """Absolute time: the edition is frozen, so ages are too."""
    jitter = int(hashlib.md5(s["title"].encode()).hexdigest(), 16) % 47
    m = FROZEN_MIN - s["ageHours"] * 60 - jitter
    day = "Wed"
    iso_day = "2026-11-11"
    if m < 0:
        m += 24 * 60
        day = "Tue"
        iso_day = "2026-11-10"
    hh, mm = divmod(m, 60)
    clock = f"{hh:02d}:{mm:02d}"
    label = clock if day == "Wed" else f"Tue {clock}"
    return f'<time datetime="{iso_day}T{clock}+05:30">{label}</time>', clock, day


def tier(n):
    return 4 if n >= 9 else 3 if n >= 6 else 2 if n >= 3 else 1


FRONT_STEP = {4: "hl-5", 3: "hl-4", 2: "hl-3", 1: "hl-1"}
DESK_STEP = {4: "hl-4", 3: "hl-3", 2: "hl-2", 1: "hl-1"}


def arw(kind, extra=""):
    return f'<svg class="arw {extra}" aria-hidden="true" focusable="false"><use href="#a-{kind}"/></svg>'


def ticks(n):
    return f'<span class="ticks" style="--n:{min(n, 12)}" aria-hidden="true"></span>'


def cov_small(n):
    word = "outlet" if n == 1 else "outlets"
    return f'<span class="cov" title="Carried by {n} {word}">{ticks(n)}<span><b>{n}</b> {word}</span></span>'


def cov_foot(s):
    """The lead's coverage numeral, one size down: closes the first column of a wide desk."""
    n = s["sourceCount"]
    word = "outlet" if n == 1 else "outlets"
    others = "alone" if n == 1 else f"+ {n - 1} other{'s' if n > 2 else ''}"
    return (f'<p class="cov-foot" title="Carried by {n} {word}"><span class="cov-foot__n">{n}</span>'
            f'<span class="cov-foot__what">{ticks(n)}<span class="label"><b>{word}<br>carried<br>this</b></span></span>'
            f'<span class="cov-foot__who label">{esc(s["source"])}<br>{others}</span></p>')


def cov_large(n):
    word = "outlet" if n == 1 else "outlets"
    return (f'<span class="cov-l" title="Carried by {n} {word}"><span class="cov-l__n">{n}</span>'
            f'{ticks(n)}<span class="label"><b>{word}</b></span></span>')


SHOWN = []  # every story placed on the page, for the count and reading time


def story(s, step, cov="s", show_sum=True, clamp=None, desk_tag=False, tag="h3", cls=""):
    SHOWN.append(s)
    n = s["sourceCount"]
    t, _, _ = stamp(s)
    sm = summary(s) if show_sum else ""
    SHOWN_WORDS.append(len((s["title"] + " " + sm).split()))
    bare = "" if sm else " story--bare"
    right = t
    if desk_tag:
        no, name = DESK[s["section"]]
        right = f'<span><b>{no}</b> {esc(name)} · {t}</span>'
    if cov == "l":
        meta = f'<p class="story__meta story__meta--l label">{cov_large(n)}{right}</p>'
    elif cov == "foot":
        # the count is set large underneath the story instead (see cov_foot)
        meta = f'<p class="story__meta label"><span class="cov cov--inline">{ticks(n)}<span><b>{n}</b> {"outlet" if n == 1 else "outlets"}</span></span><b class="top">Top of the desk</b>{right}</p>'
    else:
        meta = f'<p class="story__meta label">{cov_small(n)}{right}</p>'
    clampc = f" story__sum--clamp{clamp}" if clamp else ""
    sum_html = f'\n  <p class="story__sum{clampc}">{esc(sm)}</p>' if sm else ""
    return f'''<article class="story{bare} {cls}" data-outlets="{n}">
  {meta}
  <{tag} class="story__hl {step}"><a href="#">{hl(s["title"])}</a></{tag}>{sum_html}
  <p class="story__src label"><b>{esc(s["source"])}</b>{arw("ne")}</p>
</article>'''


SHOWN_WORDS = []

# --------------------------------------------------------------------------
# Markets (placeholder figures: the fixture carries headlines only)
# --------------------------------------------------------------------------
MARKETS = [  # name, last, change text, direction, 52w position
    ("Nifty 50", "27,418.35", "0.62%", 1, 0.93),
    ("Sensex", "89,204.10", "0.58%", 1, 0.91),
    ("S&P 500", "7,312.44", "0.84%", -1, 0.78),
    ("Nasdaq 100", "24,106.92", "1.61%", -1, 0.66),
    ("USD/INR", "93.69", "0.21%", -1, 0.22),
    ("India 10Y", "6.71%", "9 bp", 1, 0.58),
    ("Brent", "61.20", "1.92%", -1, 0.12),
    ("Gold", "4,412.60", "0.35%", 1, 0.88),
]


def chg(text, direction):
    if direction > 0:
        return f'<span class="chg chg--up">{arw("up")}<span>+{text}</span><span class="vh"> up</span></span>'
    if direction < 0:
        return f'<span class="chg chg--down">{arw("down")}<span>−{text}</span><span class="vh"> down</span></span>'
    return f'<span class="chg chg--flat">{arw("flat")}<span>0.00%</span><span class="vh"> unchanged</span></span>'


def spark(name, direction, w=100, h=32, n=28):
    seed = int(hashlib.md5(name.encode()).hexdigest(), 16)
    vals = [0.0]
    x = seed
    for i in range(1, n):
        x = (x * 6364136223846793005 + 1442695040888963407) % (2 ** 64)
        r = ((x >> 33) % 2000) / 1000.0 - 1.0
        vals.append(vals[-1] + r + direction * 0.42)
    # make sure the close agrees with the sign of the change
    if (vals[-1] > 0) != (direction > 0):
        vals = [v + (direction * (abs(vals[-1]) + 1.2)) * i / (n - 1) for i, v in enumerate(vals)]
    lo, hi = min(vals), max(vals)
    pad = 3
    span = (hi - lo) or 1

    def y(v):
        return round(h - pad - (v - lo) / span * (h - 2 * pad), 1)

    pts = " ".join(f"{round(i * (w - 4) / (n - 1), 1)},{y(v)}" for i, v in enumerate(vals))
    word = "up" if direction > 0 else "down"
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none" role="img" aria-label="{esc(name)} through the session, closing {word}">'
            f'<line class="spark__base" x1="0" x2="{w}" y1="{y(0)}" y2="{y(0)}"/>'
            f'<polyline class="spark__line" points="{pts}"/>'
            f'<circle class="spark__now" cx="{w - 4}" cy="{y(vals[-1])}" r="2.6"/></svg>')


# --------------------------------------------------------------------------
# Shared chrome
# --------------------------------------------------------------------------
SPRITE = '''<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <defs>
    <symbol id="a-up" viewBox="0 0 12 12"><path d="M6 11V2M2 6l4-4 4 4" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="square"/></symbol>
    <symbol id="a-down" viewBox="0 0 12 12"><path d="M6 1v9M2 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="square"/></symbol>
    <symbol id="a-flat" viewBox="0 0 12 12"><path d="M2 6h8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="square"/></symbol>
    <symbol id="a-right" viewBox="0 0 12 12"><path d="M1 6h9M6 2l4 4-4 4" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="square"/></symbol>
    <symbol id="a-ne" viewBox="0 0 12 12"><path d="M2.5 9.5l7-7M4 2.5h5.5V8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="square"/></symbol>
    <symbol id="a-copy" viewBox="0 0 12 12"><path d="M4 4h7v7H4zM1 8V1h7" fill="none" stroke="currentColor" stroke-width="1.8"/></symbol>
    <symbol id="a-find" viewBox="0 0 16 16"><circle cx="6.5" cy="6.5" r="4.5" fill="none" stroke="currentColor" stroke-width="2.4"/><path d="M10 10l4.5 4.5" stroke="currentColor" stroke-width="2.4" stroke-linecap="square"/></symbol>
  </defs>
</svg>'''

HEAD = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="First Light: a personal daily newspaper. One finite edition every morning.">
<meta name="theme-color" content="#0b0b0b">
<link rel="preload" href="fonts/archivo-var-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="styles.css">
<script>
/* Theme before first paint: ?theme=dark|light, then the saved choice, else the OS. */
(function () {{
  var t = new URLSearchParams(location.search).get("theme");
  if (!t) {{ try {{ t = localStorage.getItem("fl-theme"); }} catch (e) {{}} }}
  if (t === "dark" || t === "light") document.documentElement.setAttribute("data-theme", t);
}})();
</script>
</head>
<body>
<a class="skip" href="#edition">Skip to the edition</a>
<div class="progress" aria-hidden="true"></div>
'''

SCRIPT = '''<script>
(function () {
  var root = document.documentElement;
  function current() {
    return root.getAttribute("data-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  }
  var btn = document.querySelector(".theme-toggle");
  function sync() { if (btn) btn.setAttribute("aria-pressed", String(current() === "dark")); }
  if (btn) btn.addEventListener("click", function () {
    var next = current() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("fl-theme", next); } catch (e) {}
    sync(); frames();
  });
  sync();
  /* "/" puts the cursor in search */
  document.addEventListener("keydown", function (e) {
    if (e.key !== "/" || /input|textarea/i.test(e.target.tagName)) return;
    var f = document.querySelector("[data-search]");
    if (f) { e.preventDefault(); f.focus(); }
  });
  /* copy a prompt block */
  document.querySelectorAll(".copy").forEach(function (b) {
    b.addEventListener("click", function () {
      var pre = b.closest(".prompt").querySelector("pre");
      var done = function () { b.setAttribute("data-done", ""); b.lastChild.textContent = "Copied"; };
      if (navigator.clipboard) navigator.clipboard.writeText(pre.textContent).then(done, done); else done();
    });
  });
  /* stylebook only: phone previews follow the page theme */
  function frames() {
    document.querySelectorAll("iframe[data-src]").forEach(function (f) {
      var parts = f.getAttribute("data-src").split("#");
      f.src = parts[0] + "?theme=" + current() + (parts[1] ? "#" + parts[1] : "");
    });
  }
  frames();
})();
</script>
</body>
</html>
'''

NAV = [("Front Page", "index.html", "F"), ("The Wire", "#", "W"), ("Markets", "#", "M"),
       ("Weekend Review", "#", "R"), ("Claude Desk", "#", "C"), ("Clippings", "#", "K")]


def topbar():
    return f'''<div class="topbar">
  <div class="wrap topbar__in">
    <p class="topbar__date label"><b><time datetime="{EDITION_ISO}">{EDITION_DATE}</time></b><span>Morning edition</span><span>Frozen {FROZEN} IST</span></p>
    <ul class="topbar__links label">
      <li><a href="#">Back Issues</a></li>
      <li><a href="components.html">Stylebook</a></li>
      <li><a href="#colophon">Colophon</a></li>
    </ul>
    <button class="theme-toggle label" type="button" aria-pressed="false">
      <span class="theme-toggle__lamp" aria-hidden="true"></span>
      <span class="when-light">Night edition</span><span class="when-dark">Day edition</span>
    </button>
  </div>
</div>'''


def nav(current="Front Page"):
    items = []
    for name, href, key in NAV:
        cur = ' aria-current="page"' if name == current else ""
        extra = ""
        if name == "The Wire":
            extra = '<span class="nav__count"><span class="unread" aria-hidden="true"></span>42<span class="vh"> new</span></span>'
        if name == "Clippings":
            extra = '<span class="nav__count">7</span>'
        items.append(f'<li><a href="{href}"{cur}>{name}{extra}<kbd aria-hidden="true">{key}</kbd></a></li>')
    desks = "".join(
        f'<li><a href="#desk-{no}"><span class="num">{no}</span>{esc(name)}</a></li>' for _, no, name in DESKS)
    return f'''<nav class="nav" aria-label="Primary">
  <div class="wrap grid nav__in">
    <ul class="nav__main">
      {"".join(items)}
    </ul>
    <form class="search" role="search" action="#">
      <svg class="search__glyph" aria-hidden="true"><use href="#a-find"/></svg>
      <label class="vh" for="q">Search every edition</label>
      <input id="q" data-search type="search" placeholder="Search every edition" autocomplete="off">
      <kbd aria-hidden="true">/</kbd>
    </form>
  </div>
</nav>
<nav class="desks" aria-label="Desks">
  <div class="wrap desks__in">
    <span class="label">Desks</span>
    <ul>{desks}</ul>
  </div>
</nav>'''


def ear_markets():
    rows = "".join(
        f'<tr><th scope="row">{esc(n)}</th><td class="last-cell">{last}</td><td class="chg-cell">{chg(c, d)}</td></tr>'
        for n, last, c, d, _ in MARKETS[:5])
    return f'''<aside class="ear ear--markets" aria-label="Markets at close">
      <p class="ear__head"><span class="label">Markets at close</span><span class="label">Tue 10 Nov</span></p>
      <table class="quotes data">
        <tbody>{rows}</tbody>
      </table>
    </aside>'''


def ear_edition(count, minutes):
    digits = "".join(f"<span>{d}</span>" for d in str(EDITION_NO))
    return f'''<aside class="ear ear--edition" aria-label="This edition">
      <p class="ear__head"><span class="label">Edition No.</span><span class="label">Next: Thu {FROZEN}</span></p>
      <div class="edition">
        <p class="edition__no"><span class="flap" role="img" aria-label="{EDITION_NO}">{digits}</span></p>
        <div class="edition__facts">
          <p class="label"><b>{count} stories · {minutes} min</b></p>
          <p class="label">Built {FROZEN}:04 IST</p>
          <p class="label">61 feeds · a41c9e2</p>
        </div>
      </div>
    </aside>'''


def nameplate(tag="h1"):
    return f'''<div class="nameplate">
      <p class="nameplate__tag label">A personal daily · typeset by software<span class="opt"> · finite by design</span></p>
      <{tag} class="nameplate__row"><a class="nameplate__name" href="index.html">First Light</a><span class="sun" aria-hidden="true"></span></{tag}>
    </div>'''


def tabbar(current="Front"):
    tabs = [("Front", "index.html", f"No. {EDITION_NO}"), ("Wire", "#", '<span class="unread"></span>42 new'),
            ("Desks", "#desk-index", "01–10"), ("Markets", "#", "At close"), ("More", "#", "Search")]
    out = []
    for name, href, sub in tabs:
        cur = ' aria-current="page"' if name == current else ""
        out.append(f'<a href="{href}"{cur}>{name}<span class="label">{sub}</span></a>')
    return f'<nav class="tabbar" aria-label="Sections">{"".join(out)}</nav>'


def sheet():
    counts = {}
    for s in STORIES:
        counts[s["section"]] = counts.get(s["section"], 0) + 1
    rows = "".join(
        f'<li><a href="#desk-{no}"><span class="num">{no}</span><span class="name">{esc(name)}</span>'
        f'<span class="label">{counts[k]} today</span>{arw("right")}</a></li>'
        for k, no, name in DESKS)
    return f'''<div class="sheet" id="desk-index" role="dialog" aria-label="Desks">
  <div class="sheet__head">
    <p class="sheet__title">Desks</p>
    <a class="sheet__close label" href="#edition">Close</a>
  </div>
  <ul class="sheet__list">{rows}</ul>
  <div class="sheet__more">
    <a href="#">Weekend Review {arw("right")}</a><a href="#">Claude Desk {arw("right")}</a>
    <a href="#">Clippings {arw("right")}</a><a href="#">Back Issues {arw("right")}</a>
  </div>
</div>'''


def colophon():
    keys = [("Front Page", "F"), ("The Wire", "W"), ("Next / previous story", "J K"), ("Open at source", "O"),
            ("Clip it", "S"), ("Search", "/"), ("Night edition", "N")]
    krows = "".join(
        f'<li><span>{a}</span><span>{"".join(f"<kbd>{k}</kbd>" for k in b.split())}</span></li>' for a, b in keys)
    return f'''<footer class="colophon" id="colophon">
  <div class="wrap grid colophon__in">
    <div class="colophon__col colophon__col--wide">
      <p class="colophon__name">First Light</p>
      <p>One edition every morning at {FROZEN} IST. It is frozen when it is built and it ends. Anything that happens after that is on The Wire.</p>
      <p>Headline size is not decoration: it is the number of outlets that carried the story.</p>
    </div>
    <div class="colophon__col colophon__col--narrow">
      <span class="label">The paper</span>
      <ul>
        <li><a href="index.html">Front Page</a></li><li><a href="#">The Wire</a></li><li><a href="#">Markets</a></li>
        <li><a href="#">Weekend Review</a></li><li><a href="#">Claude Desk</a></li><li><a href="#">Clippings</a></li>
        <li><a href="#">Back Issues</a></li><li><a href="components.html">Stylebook</a></li>
      </ul>
    </div>
    <div class="colophon__col colophon__keys">
      <span class="label">Keys</span>
      <ul>{krows}</ul>
    </div>
    <div class="colophon__col">
      <span class="label">Colophon</span>
      <p>Set in Archivo, one variable file from 62 to 125 per cent wide, and Martian Mono for figures. Both open licence, both served from this site.</p>
      <p>No tracking, no images, no framework. A few lines of script run the theme switch, the copy button and the / key.</p>
      <p>Prototype note: headlines are real, fetched 11 Nov 2026. Outlet counts, times and market figures are placeholders.</p>
    </div>
  </div>
</footer>'''


# --------------------------------------------------------------------------
# Front page
# --------------------------------------------------------------------------
def front_page():
    lead = find("Falkland Islanders")
    sec_a = find("Anthropic has its own")
    sec_b = find("China sales crash")
    sec_c = find("Hegseth")
    sec_d = find("Grok Build")
    briefs = [find(k) for k in (
        "ANC faces", "Rupee touches", "Claude Code is accidentally", "Gemini 4 Carbon with agent",
        "Collision of two trains", "Baird downgrades", "$10bn defamation", "Pope Leo",
        "Anthropic targets", "ESCAPADE")]
    # (title fragment, summary lines). None = whole summary, 0 = headline only.
    # The second number is the typesetter's fit pass: it trims summaries in
    # the tallest column of a row until the columns end near each other.
    desk_picks = {
        "world": [("Vinícius", None), ("Kenyan doomsday", 3), ("Kennedys sue", 3)],
        "india": [("Vinay Chand", None), ("Cabinet approves", 0), ("Opposition slams", 0)],
        "ai": [("Ukraine", None), ("eBay appears", 0), ("affair becomes", 2)],
        "ml": [("Genie 4", None), ("Robotics 2.5 accelerates", 2), ("AlphaProof", 0)],
        "llm": [("mysterious beep", None), ("Yonkers", 0), ("Quoting Prompting", 3)],
        "labs": [("Singapore Airlines", None), ("veterans", None), ("Work at the Frontier", None)],
        "companies": [("Lucid CEO", None), ("Cork Takes", None), ("Cybertruck isn", None)],
        "markets": [("Mortgage rates", None), ("biggest moves", 0), ("rebound 5%", 0)],
        "india-markets": [("Treasury rout hands", 3), ("Realty firms", 0), ("midcap", 0)],
        "science": [("plesiosaur", None), ("physics project", None), ("Chile", None)],
    }

    def placed(pick, step, cov="s"):
        frag, lines = pick
        s = find(frag)
        return story(s, step(s), cov=cov, show_sum=lines != 0, clamp=lines or None)
    counts = {}
    for s in STORIES:
        counts[s["section"]] = counts.get(s["section"], 0) + 1

    # ---- lead
    SHOWN.append(lead)
    lead_sum = summary(lead)
    SHOWN_WORDS.append(len((lead["title"] + " " + LEAD_DECK + " " + lead_sum).split()))
    n = lead["sourceCount"]
    t, _, _ = stamp(lead)
    no, dname = DESK[lead["section"]]
    long = " lead__hl--long" if len(lead["title"]) > 100 else ""
    lead_html = f'''<article class="lead" data-outlets="{n}">
        <p class="lead__kicker label"><span class="flag">The lead</span><span><b>{no}</b> {dname}</span><span class="push"><b>{esc(lead["source"])}</b> · {t}</span></p>
        <h3 class="lead__hl{long}"><a href="#">{hl(lead["title"])}</a></h3>
        <div class="lead__foot">
          <div class="cov-xl" title="Carried by {n} outlets">
            <span class="cov-xl__n">{n}</span>
            <span class="cov-xl__what">{ticks(n)}<span class="label">outlets<br>carried<br>this</span></span>
            <p class="cov-xl__who label">{esc(lead["source"])} + {n - 1} others</p>
          </div>
          <p class="lead__deck">{esc(LEAD_DECK)}</p>
          <div class="lead__body">
            <p>{esc(lead_sum)}</p>
            <a class="readon" href="#">Read at {esc(lead["source"])} {arw("ne")}</a>
          </div>
        </div>
      </article>'''

    # ---- four more
    seconds = f'''<div class="seconds">
        <div class="seconds__row">
          <div class="seconds__wide">{story(sec_a, "hl-6", cov="l", desk_tag=True)}</div>
          <div class="seconds__narrow">{story(sec_b, FRONT_STEP[tier(sec_b["sourceCount"])], cov="l", desk_tag=True)}</div>
        </div>
        <div class="seconds__row">
          <div class="seconds__wide">{story(sec_c, FRONT_STEP[tier(sec_c["sourceCount"])], desk_tag=True)}</div>
          <div class="seconds__narrow">{story(sec_d, FRONT_STEP[tier(sec_d["sourceCount"])], desk_tag=True)}</div>
        </div>
      </div>'''

    # ---- in brief
    items = []
    briefs.sort(key=lambda b: b["ageHours"] * 60 + int(hashlib.md5(b["title"].encode()).hexdigest(), 16) % 47)
    for b in briefs:
        SHOWN.append(b)
        SHOWN_WORDS.append(len(b["title"].split()))
        tt, clock, day = stamp(b)
        no_b, name_b = DESK[b["section"]]
        word = "outlet" if b["sourceCount"] == 1 else "outlets"
        items.append(f'''<li class="brief">
            <span class="brief__time">{clock}{"<small>Tue</small>" if day == "Tue" else ""}</span>
            <p class="brief__hl"><a href="#">{hl(b["title"])}</a></p>
            <p class="brief__meta label" title="{b["sourceCount"]} {word}">{ticks(b["sourceCount"])}<span class="vh">{b["sourceCount"]} {word} · </span><span>{esc(name_b)} · {esc(b["source"])}</span></p>
          </li>''')
    briefs_html = f'''<aside class="briefs board" aria-labelledby="brief-h">
        <div class="briefs__head"><h3 class="briefs__title" id="brief-h">In brief</h3><span class="label">{len(briefs)} lines</span></div>
        <ol class="briefs__list">
          {"".join(items)}
        </ol>
        <div class="briefs__wire">
          <p class="label">Since this edition closed</p>
          <a href="#"><span>The Wire · 42 new</span>{arw("right")}</a>
        </div>
      </aside>'''

    # ---- desks
    def desk_head(key):
        no_d, name_d = DESK[key]
        return (f'<header class="desk__head"><span class="tile" aria-hidden="true">{no_d}</span>'
                f'<h2 class="desk__name" id="desk-{no_d}">{esc(name_d)}</h2>'
                f'<a class="desk__more label more" href="#" aria-label="All {counts[key]} on the {esc(name_d)} desk"><b>{counts[key]}</b>{arw("right")}</a></header>')

    def desk_narrow(key, span=3):
        body = [placed(pk, lambda s: DESK_STEP[tier(s["sourceCount"])]) for pk in desk_picks[key]]
        no_d = DESK[key][0]
        return f'''<section class="desk desk--{span}" aria-labelledby="desk-{no_d}">
        {desk_head(key)}
        <div class="desk__body">
          {"".join(body)}
        </div>
      </section>'''

    def desk_wide(key, flip=False):
        picks = desk_picks[key]
        wide_step = {4: "hl-5", 3: "hl-4", 2: "hl-3", 1: "hl-1"}
        first = placed(picks[0], lambda s: wide_step[tier(s["sourceCount"])], cov="foot") + cov_foot(find(picks[0][0]))
        rest = "".join(placed(pk, lambda s: DESK_STEP[tier(s["sourceCount"])]) for pk in picks[1:])
        no_d = DESK[key][0]
        fl = " desk--flip" if flip else ""
        return f'''<section class="desk desk--6{fl}" aria-labelledby="desk-{no_d}">
        {desk_head(key)}
        <div class="desk__body">
          <div class="desk__first">{first}</div>
          <div class="desk__stack">{rest}</div>
        </div>
      </section>'''

    def desk_rail(key):
        ss = [find(k) for k, _ in desk_picks[key]]
        spans = {4: "span-5", 3: "span-4", 2: "span-3", 1: "span-3"}
        steps = {4: "hl-6", 3: "hl-5", 2: "hl-4", 1: "hl-2"}
        body = "".join(story(s, steps[tier(s["sourceCount"])], cls=spans[tier(s["sourceCount"])]) for s in ss)
        no_d = DESK[key][0]
        return f'''<section class="desk desk--12" aria-labelledby="desk-{no_d}">
        {desk_head(key)}
        <div class="desk__body">{body}</div>
      </section>'''

    row_a = f'''<div class="grid deskrow">
      {desk_wide("world")}
      {desk_narrow("india")}
      {desk_narrow("ai")}
    </div>'''
    row_b = f'''<div class="grid deskrow">
      {desk_narrow("ml")}
      {desk_narrow("llm")}
      {desk_wide("labs", flip=True)}
    </div>'''
    row_c = f'''<div class="grid deskrow">
      {desk_wide("companies")}
      {desk_narrow("markets")}
      {desk_narrow("india-markets")}
    </div>'''
    row_d = f'''<div class="grid deskrow">
      {desk_rail("science")}
    </div>'''

    # ---- tape
    quotes = "".join(f'''<div class="quote">
        <p class="quote__name label">{esc(nm)}</p>
        <p class="quote__last">{last}</p>
        {spark(nm, d)}
        <p class="quote__chg data">{chg(c, d)}</p>
      </div>''' for nm, last, c, d, _ in MARKETS[:6])
    tape = f'''<section class="tape" aria-labelledby="tape-h">
    <div class="wrap grid tape__in">
      <div class="tape__head"><h2 class="tape__title" id="tape-h">Markets at close</h2><span class="label">Tuesday 10 November<span class="opt"> · dotted line is the previous close</span></span><a class="more label" href="#"><b>All markets</b><kbd aria-hidden="true">M</kbd></a></div>
      {quotes}
    </div>
  </section>'''

    count = len(SHOWN)
    minutes = max(1, math.ceil(sum(SHOWN_WORDS) / 200))

    claude = f'''<section class="claude" aria-labelledby="claude-h">
      <header class="claude__head"><span class="tile" aria-hidden="true">C</span><h2 class="claude__name" id="claude-h">Claude Desk</h2><span class="label">One technique to try at work today</span></header>
      <div class="claude__pitch">
        <h3 class="claude__title">Quotes first, answer second</h3>
        <p class="claude__when"><b>Reach for it when</b> the document is long and a confident wrong answer would cost you: a contract, an RFC, an incident log. Asking for the exact passages first keeps the answer tied to the page.</p>
        <div class="adopt">
          <span class="label" id="adopt-l">Where are you with this?</span>
          <div class="seg" role="radiogroup" aria-labelledby="adopt-l">
            <label><input type="radio" name="adopt" checked><span>Not tried</span></label>
            <label><input type="radio" name="adopt"><span>Tried</span></label>
            <label><input type="radio" name="adopt"><span>In my workflow</span></label>
          </div>
        </div>
      </div>
      <div class="claude__work">
        <div class="prompt">
          <div class="prompt__bar"><span class="label">Prompt · two slots to fill</span><button class="copy" type="button"><svg class="arw" aria-hidden="true"><use href="#a-copy"/></svg><span>Copy</span></button></div>
<pre><span class="tag">&lt;document&gt;</span>
<span class="slot">{{{{PASTE THE DOCUMENT}}}}</span>
<span class="tag">&lt;/document&gt;</span>

First, copy the passages that bear on my question into <span class="tag">&lt;quotes&gt;</span> tags, word for word, numbered.

Then answer in <span class="tag">&lt;answer&gt;</span> tags using only those quotes, citing the numbers. If the quotes do not settle it, say so.

Question: <span class="slot">{{{{YOUR QUESTION}}}}</span></pre>
        </div>
      </div>
    </section>'''

    end = f'''<footer class="end">
      <p class="end__mark" aria-label="End of edition">— 30 —</p>
      <p class="end__line">That’s the edition. {count} stories, about {minutes} minutes.</p>
      <p class="end__next label"><span>Next edition Thursday {FROZEN} IST</span><a class="more" href="#"><b>The Wire is still moving</b>{arw("right")}</a><a class="more" href="#"><b>Back Issues</b>{arw("right")}</a></p>
    </footer>'''

    key = "".join(f'<span class="cov">{ticks(k)}<span>{k}</span></span>' for k in (1, 3, 6, 9))
    body = f'''{SPRITE}
<header class="mast">
  {topbar()}
  <div class="wrap grid plate">
    {ear_markets()}
    {nameplate()}
    {ear_edition(count, minutes)}
  </div>
  {nav()}
</header>

<main id="edition">
  <div class="wrap">
    <div class="folio label">
      <p><b>Front Page</b> · <span class="opt">Edition </span>No. {EDITION_NO} · {count} stories<span class="opt"> · about {minutes} minutes · it ends</span></p>
      <p class="folio__key"><span>Key<span class="long">: the more outlets carry a story, the bigger it is set</span></span>{key}</p>
    </div>
    <h2 class="vh">Front page</h2>
    <div class="grid front">
      {lead_html}
      {seconds}
      {briefs_html}
    </div>
    {row_a}
    {row_b}
  </div>
  {tape}
  <div class="wrap">
    {row_c}
    {row_d}
    {claude}
    {end}
  </div>
</main>
{colophon()}
{sheet()}
{tabbar()}
'''
    return HEAD.format(title=f"First Light · No. {EDITION_NO} · {EDITION_DATE}") + body + SCRIPT, count, minutes


# --------------------------------------------------------------------------
# Stylebook: the parts the other pages are built from
# --------------------------------------------------------------------------
def spec(no, name, note, classes, body, wide=False):
    return f'''<section class="grid spec" aria-labelledby="spec-{no}">
      <div class="spec__label">
        <div class="spec__head"><span class="tile" aria-hidden="true">{no}</span><h2 class="spec__name" id="spec-{no}">{name}</h2></div>
        <p class="spec__note">{note}</p>
        <p class="label">{classes}</p>
      </div>
      <div class="spec__body">
        {body}
      </div>
    </section>'''


def stylebook():
    # 01 coverage ladder --------------------------------------------------
    rungs = [
        ("Genie 4", "lead__hl", "The lead", "step 7 · 108 px · width 62 · weight 800", "9"),
        ("plesiosaur", "story__hl hl-6", "9+ outlets", "step 6 · 64 px · second story, headline rail", "9"),
        ("Singapore Airlines", "story__hl hl-5", "9+ outlets", "step 5 · 46 px · front page, first on a wide desk", "9"),
        ("physics project", "story__hl hl-4", "6 to 8", "step 4 · 34 px · width 68 · weight 800", "6"),
        ("Chile", "story__hl hl-3", "3 to 5", "step 3 · 26 px · width 74 · weight 750", "3"),
        ("eBay appears", "story__hl hl-2", "3 to 5, on a desk", "step 2 · 20 px · width 82 · weight 700", "3"),
        ("Students need", "story__hl hl-1", "1 or 2", "step 1 · 17 px · width 90 · weight 650", "1"),
    ]
    ladder = "".join(f'''<div class="rung">
          <div class="rung__cov"><span class="cov-l"><span class="cov-l__n">{n}</span>{ticks(int(n))}</span><p class="label"><b>{who}</b><br>{how}</p></div>
          <p class="rung__hl {cls}">{esc(find(frag)["title"])}</p>
        </div>''' for frag, cls, who, how, n in rungs)
    s1 = spec("01", "Coverage scale",
              "The one idea. A headline is set at the step its coverage earns: more outlets, bigger and narrower type, wider column. Ticks repeat the count, one stroke per outlet. The lead and the top story of a wide desk also carry it as a numeral.",
              ".lead__hl · .hl-6 to .hl-1 · .cov · .ticks · .cov-xl · .cov-foot",
              f'<div class="ladder">{ladder}</div>')

    # 02 navigation ---------------------------------------------------------
    s2 = spec("02", "Navigation",
              "On a laptop it is the two rows at the top of this page: six places with their keys, then ten numbered desks. On a phone the same places sit in a bar under the thumb, and Desks opens a board.",
              ".nav · .desks · .tabbar · .sheet",
              '''<div class="phones">
          <figure class="phone"><iframe title="Front Page on a phone" data-src="index.html" loading="eager"></iframe><figcaption class="label"><b>Phone</b> · Front Page, tab bar</figcaption></figure>
          <figure class="phone"><iframe title="Desk index on a phone" data-src="index.html#desk-index" loading="eager"></iframe><figcaption class="label"><b>Phone</b> · Desks tab pressed</figcaption></figure>
        </div>''')

    # 03 the wire --------------------------------------------------------------
    wire_rows = [  # fragment, clock, state
        ("Nvidia Stock Sell-Off", "09:41", ""),
        ("Tesla launches Robotaxi", "09:38", "is-cursor"),
        ("Nasdaq futures jump", "09:22", ""),
        ("Hundreds of Italian schools", "09:07", ""),
        ("Introducing Businesses in ChatGPT", "08:51", ""),
        ("Deadly floods hit Iraq", "08:30", "is-read"),
        ("Adobe is going all in", "08:12", "is-read"),
        ("Bajaj Finance", "07:55", ""),
        ("llm-anthropic 0.31", "07:40", "is-read"),
        ("Six arrested", "07:18", ""),
    ]
    rows = []
    for frag, clock, state in wire_rows:
        s = find(frag)
        no, name = DESK[s["section"]]
        n = s["sourceCount"]
        wt = " wire__hl--3" if n >= 6 else " wire__hl--1" if n <= 2 else ""
        cur = ' aria-current="true"' if state == "is-cursor" else ""
        word = "outlet" if n == 1 else "outlets"
        rows.append(f'''<li class="wire__row {state}"{cur}>
            <span class="unread" title="Unread"></span>
            <time class="wire__time">{clock}</time>
            <span class="wire__desk"><span class="tile tile--sm" aria-hidden="true">{no}</span><span class="label">{esc(name)}</span></span>
            <a class="wire__hl{wt}" href="#">{hl(s["title"])}</a>
            <span class="cov label" title="{n} {word}">{ticks(n)}<b>{n}</b></span>
            <span class="wire__src label">{esc(s["source"])}</span>
          </li>''')
    wire = f'''<div class="wire">
          <div class="wire__bar label">
            <span class="live"><span class="unread" aria-hidden="true"></span>Live · 42 new since 05:30</span>
            <span>All desks</span><span>Any coverage</span>
            <span class="push"><span>Unread only</span><kbd>U</kbd></span>
          </div>
          <div class="wire__row wire__row--head label" aria-hidden="true"><span></span><span>Time</span><span>Desk</span><span>Headline</span><span>Outlets</span><span style="text-align:right">Source</span></div>
          <ol>
            {"".join(rows)}
          </ol>
          <p class="wire__keys label"><span><kbd>J</kbd><kbd>K</kbd> move</span><span><kbd>O</kbd> open at source</span><span><kbd>S</kbd> clip</span><span><kbd>X</kbd> mark read</span><span><kbd>1</kbd>–<kbd>0</kbd> filter to a desk</span><span><kbd>/</kbd> search</span></p>
        </div>'''
    s3 = spec("03", "The Wire row",
              "Live, dense, one line each, built for the keyboard. Weight still follows coverage. The black row is the cursor. A square marks unread; read rows step back.",
              ".wire__row · .is-cursor · .is-read · .unread", wire)

    # 04 markets table -------------------------------------------------------------
    absolute = {"Nifty 50": "168.90", "Sensex": "514.25", "S&P 500": "61.94", "Nasdaq 100": "394.45",
                "USD/INR": "0.20", "India 10Y": "0.09", "Brent": "1.20", "Gold": "15.40"}
    tick = {"Nifty 50": "NSE", "Sensex": "BSE", "S&P 500": "SPX", "Nasdaq 100": "NDX", "USD/INR": "FX",
            "India 10Y": "G-SEC", "Brent": "ICE", "Gold": "COMEX"}
    mrows = []
    for nm, last, pct, d, pos in MARKETS:
        sign = "+" if d > 0 else "−"
        mrows.append(f'''<tr>
              <td><span class="mkt__name"><b>{esc(nm)}</b><span class="label">{tick[nm]}</span></span></td>
              <td class="data mkt__last">{last}</td>
              <td class="data">{chg(pct, d)}</td>
              <td class="data">{sign}{absolute[nm]}</td>
              <td class="data"><span class="range" style="--at:{int(pos * 100)}%" title="Position in the 52-week range"><i></i></span></td>
              <td>{spark(nm, d, w=120, h=28)}</td>
            </tr>''')
    mkt = f'''<table class="mkt">
          <caption class="vh">Markets at close, Tuesday 10 November</caption>
          <thead><tr class="label"><th scope="col">Instrument</th><th scope="col">Last</th><th scope="col">Change</th><th scope="col">Points</th><th scope="col">52-week range</th><th scope="col">Session</th></tr></thead>
          <tbody>
            {"".join(mrows)}
          </tbody>
        </table>'''
    s4 = spec("04", "Markets row",
              "Figures in tabular mono, right-aligned. Direction is said three times: sign, arrow, and only then colour on the falling arrow. The dot is the close; the dotted line is the previous close.",
              ".mkt · .chg--up · .chg--down · .spark · .range", mkt)

    # 05 weekend review ---------------------------------------------------------------
    papers = [
        ("Attention Is All You Need",
         "Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser, Illia Polosukhin",
         "arXiv 1706.03762", ["Desk match: LLMs", "On 3 reading lists", "Code released"],
         ["We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.",
          "Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train.",
          "Our model achieves 28.4 BLEU on the WMT 2014 English-to-German translation task, improving over the existing best results, including ensembles, by over 2 BLEU."]),
        ("Deep Residual Learning for Image Recognition",
         "Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun",
         "arXiv 1512.03385", ["Desk match: Machine Learning", "Cited by a clipping"],
         ["We present a residual learning framework to ease the training of networks that are substantially deeper than those used previously.",
          "We explicitly reformulate the layers as learning residual functions with reference to the layer inputs, instead of learning unreferenced functions.",
          "An ensemble of these residual nets achieves 3.57% error on the ImageNet test set."]),
        ("Adam: A Method for Stochastic Optimization",
         "Diederik P. Kingma, Jimmy Ba",
         "arXiv 1412.6980", ["Desk match: Machine Learning", "Short read"],
         ["We introduce Adam, an algorithm for first-order gradient-based optimization of stochastic objective functions, based on adaptive estimates of lower-order moments.",
          "The method is straightforward to implement, is computationally efficient, has little memory requirements, is invariant to diagonal rescaling of the gradients, and is well suited for problems that are large in terms of data and/or parameters.",
          "Empirical results demonstrate that Adam works well in practice and compares favorably to other stochastic optimization methods."]),
    ]
    cards = []
    for i, (title, authors, ref, chips, digest) in enumerate(papers, 1):
        chip_html = "".join(f'<li class="chip{" chip--solid" if j == 0 else ""}">{esc(ch)}</li>' for j, ch in enumerate(chips))
        cards.append(f'''<article class="paper">
            <span class="paper__rank" aria-label="Rank {i}">{i}</span>
            <div class="paper__main">
              <h3 class="paper__title"><a href="#">{esc(title)}</a></h3>
              <p class="paper__authors">{esc(authors)}</p>
              <ul class="chips" aria-label="Why it surfaced">{chip_html}</ul>
              <p class="paper__foot label"><b>{ref}</b><span>PDF {arw("ne")}</span><span>Clip <kbd>S</kbd></span></p>
            </div>
            <ol class="paper__digest" aria-label="Three lines from the abstract">
              {"".join(f"<li>{esc(d)}</li>" for d in digest)}
            </ol>
          </article>''')
    s5 = spec("05", "Weekend Review",
              "Saturday’s reading list of papers. The numeral is the rank. Chips say why it surfaced. The digest is extractive: three sentences lifted from the abstract, never rewritten. Stand-in data: three well-known papers; the chips are placeholders.",
              ".paper · .paper__rank · .chip · .paper__digest", f'<div class="papers">{"".join(cards)}</div>')

    # 06 claude desk feature ----------------------------------------------------------------
    feature = f'''<article class="claude claude--paper">
          <header class="claude__head"><span class="tile" aria-hidden="true">C</span><p class="claude__name">Claude Desk</p><span class="label">Technique 14 · coding</span></header>
          <div class="claude__pitch">
            <h3 class="claude__title">Give it the test command</h3>
            <p class="claude__when"><b>Reach for it when</b> you hand over a coding task you do not want to babysit. Say how the work gets checked: the command to run and what passing looks like. Then it can check itself before it reports back.</p>
            <div class="adopt">
              <span class="label" id="adopt-2">Where are you with this?</span>
              <div class="seg seg--paper" role="radiogroup" aria-labelledby="adopt-2">
                <label><input type="radio" name="adopt2"><span>Not tried</span></label>
                <label><input type="radio" name="adopt2"><span>Tried</span></label>
                <label><input type="radio" name="adopt2" checked><span>In my workflow</span></label>
              </div>
            </div>
          </div>
          <div class="claude__work">
            <div class="prompt">
              <div class="prompt__bar"><span class="label">Prompt · two slots to fill</span><button class="copy" type="button"><svg class="arw" aria-hidden="true"><use href="#a-copy"/></svg><span>Copy</span></button></div>
<pre>Fix <span class="slot">{{{{THE BUG}}}}</span>.

Before you say you are done, run <span class="slot">{{{{TEST COMMAND}}}}</span> and read the output. If anything fails, keep going.

When it passes, show me the last 20 lines of the run.</pre>
            </div>
          </div>
        </article>'''
    s6 = spec("06", "Claude Desk card",
              "One technique: a name, when to reach for it, a prompt to copy, and where you are with it. On the Front Page it runs as the one solid block of spot colour. In the desk’s own list it sits on paper, as here.",
              ".claude · .claude--paper · .prompt · .copy · .seg", feature)

    # 07 search ------------------------------------------------------------------------------
    hits = [
        ("Baird downgrades", "No. 315 · In brief", "Baird downgrades <mark>Nvidia</mark> on CEO <mark>Huang</mark> worries, AI uncertainty"),
        ("rebound 5%", "No. 315 · Markets", "<mark>Nvidia</mark> shares rebound 5% as <mark>Huang</mark> faces scrutiny ahead of earnings"),
        ("could have blown it", "No. 315 · The Wire", "The US is winning the AI race. <mark>Jensen Huang</mark> could have blown it"),
        ("affair becomes", "No. 314 · AI", "<mark>Nvidia</mark> CEO’s affair becomes a national security problem"),
    ]
    hit_html = "".join(
        f'<li class="hit"><span class="label">{where}</span><a class="story__hl hl-2" href="#">{marked}</a>'
        f'<span class="label"><b>{esc(find(frag)["source"])}</b></span></li>' for frag, where, marked in hits)
    search = f'''<form class="find" role="search" action="#">
          <svg class="search__glyph" aria-hidden="true"><use href="#a-find"/></svg>
          <label class="vh" for="q2">Search every edition</label>
          <input id="q2" type="search" value="nvidia" autocomplete="off">
          <span class="find__count label"><b>23 stories</b> · 9 editions</span>
          <kbd aria-hidden="true">/</kbd>
        </form>
        <p class="also"><span class="label">Also searching</span>
          <button class="chip" type="button" aria-label="Stop searching NVDA">NVDA<span class="x" aria-hidden="true">×</span></button>
          <button class="chip" type="button" aria-label="Stop searching Jensen Huang">Jensen Huang<span class="x" aria-hidden="true">×</span></button>
          <button class="chip" type="button" aria-label="Stop searching Huang">Huang<span class="x" aria-hidden="true">×</span></button>
          <button class="chip" type="button" aria-label="Stop searching GeForce">GeForce<span class="x" aria-hidden="true">×</span></button>
          <span class="label">Tap a chip to drop it</span>
        </p>
        <ol>{hit_html}</ol>'''
    s7 = spec("07", "Search",
              "One field, set as large as a headline. The query is widened with names, tickers and spellings, and the widening is shown, so nothing is searched behind your back.",
              ".find · .also · .chip · .hit mark", search)

    # 08 tokens ----------------------------------------------------------------------------------
    sw = [("paper", "--paper"), ("paper 2", "--paper-2"), ("ink", "--ink"), ("ink 2", "--ink-2"), ("ink 3", "--ink-3"),
          ("hair", "--hair"), ("spot", "--spot"), ("spot ink", "--spot-ink"), ("board", "--board")]
    swatches = "".join(f'<div class="swatch"><i style="background:var({v})"></i><span class="label"><b>{n}</b><br>{v}</span></div>' for n, v in sw)
    steps = "".join(f'<div><i style="width:var(--sp-{i})"></i><span class="label">sp-{i}</span></div>' for i in range(1, 10))
    rules = "".join(
        f'<div style="border-top:var({v}) solid var(--rule)"><span class="label"><b>{n}</b> · {v}</span></div>'
        for n, v in (("hair", "--rule-hair"), ("thin", "--rule-thin"), ("thick", "--rule-thick"), ("bar", "--rule-bar")))
    parts = f'''<div class="parts">
          <span class="tile">07</span><span class="tile tile--sm">07</span>
          <span class="flap" role="img" aria-label="315"><span>3</span><span>1</span><span>5</span></span>
          <div class="parts__foot">{cov_foot(find("Genie 4"))}</div>
          {cov_large(6)}<span class="label">{cov_small(3)}</span>
          <span class="data">{chg("0.62%", 1)}</span><span class="data">{chg("1.61%", -1)}</span><span class="data">{chg("", 0)}</span>
          <span class="chip chip--solid">Chip</span><span class="chip">Chip</span>
          <kbd>J</kbd><span class="unread" title="Unread"></span>
          <a class="readon" href="#">Read at source {arw("ne")}</a>
        </div>'''
    specimen = '''<div class="specimen">
          <div><p class="specimen__a">Aa 315</p><span class="label"><b>Display</b> · Archivo, 62 to 90 wide, 650 to 900</span></div>
          <div><p class="specimen__b">Aa 315</p><span class="label"><b>Text</b> · Archivo, 84 to 100 wide, 400 to 600</span></div>
          <div><p class="specimen__c">Aa 315</p><span class="label"><b>Data</b> · Martian Mono, 75 wide, 500 to 700</span></div>
        </div>'''
    tokens = f'''<div class="swatches">{swatches}</div>
        {specimen}
        {parts}
        <div class="steps">{steps}</div>
        <div class="rules-demo">{rules}</div>'''
    s8 = spec("08", "Tokens",
              "Every colour, size, space and rule is a custom property at the top of styles.css. The night edition swaps the colour block and nothing else.",
              "--paper · --ink · --spot · --step-1…7 · --sp-1…9 · --rule-*", tokens)

    body = f'''{SPRITE}
<header class="mast">
  {topbar()}
  <div class="wrap grid plate plate--inner">
    {nameplate(tag="p")}
    <div class="plate__title"><p class="label">For whoever builds the rest</p><h1 class="pagehead">The Stylebook</h1></div>
  </div>
  {nav(current="")}
</header>

<main id="edition" class="book">
  <div class="wrap">
    <div class="folio label">
      <p><b>Stylebook</b> · eight parts<span class="opt"> · every sample is set from today’s fixture</span></p>
      <p class="folio__key"><span>Day and night share one sheet: styles.css</span></p>
    </div>
    {s1}
    {s2}
    {s3}
    {s4}
    {s5}
    {s6}
    {s7}
    {s8}
  </div>
</main>
{colophon()}
{sheet()}
{tabbar(current="")}
'''
    return HEAD.format(title="First Light · The Stylebook") + body + SCRIPT


if __name__ == "__main__":
    page, count, minutes = front_page()
    (HERE / "index.html").write_text(page, encoding="utf-8")
    print(f"index.html: {count} stories, about {minutes} min, {len(page):,} bytes")
    book = stylebook()
    (HERE / "components.html").write_text(book, encoding="utf-8")
    print(f"components.html: {len(book):,} bytes")
