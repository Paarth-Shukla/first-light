#!/usr/bin/env python3
"""Typesets the First Light "Broadsheet" prototype from ../../fixture.json.

Writes index.html (the front page) and components.html (the specimen sheet)
next to this file. Static output, no dependencies:  python3 build.py

The rules it encodes are the design, so they are worth reading:
  * lead      = highest sourceCount (ties: World first, then freshest)
  * tier      = step on the headline scale, from sourceCount
  * --cov     = sourceCount, drives headline weight and the dot row
  * .bare     = story with no summary; set in italic, on purpose
"""
import hashlib
import html
import json
import math
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent.parent / "fixture.json"
STORIES = json.loads(FIXTURE.read_text(encoding="utf-8"))["stories"]

PRESS = datetime(2026, 11, 11, 6, 0)          # the edition goes to press at 06:00 IST
EDITION_NO = 47
BUILD = "47·4f2a91c"
WIRE_NEW = 128

DESKS = {
    "world": "World", "india": "India", "ai": "AI", "ml": "Machine Learning", "llm": "LLMs",
    "labs": "Frontier Labs", "companies": "Companies", "markets": "Markets",
    "india-markets": "Dalal Street", "science": "Science",
}
DESK_COUNT = {k: sum(1 for s in STORIES if s["section"] == k) for k in DESKS}
OUTLETS = sorted({s["source"] for s in STORIES})

e = html.escape


def find(key):
    hits = [s for s in STORIES if key in s["title"]]
    assert len(hits) == 1, (key, len(hits))
    return hits[0]


# ---------------------------------------------------------------- text helpers

OVERRIDE = {
    "Falkland Islanders": "Countries clash over Sea Lion project as Hamburg tribunal risks deepening sovereignty dispute. "
                          "The people of the Falkland Islands face “devastating consequences” if Argentina is successful "
                          "in blocking development of its offshore oilfield …",
    "Kenyan doomsday": "Paul Mackenzie convicted over deaths of children and one adult after followers were ordered to "
                       "starve themselves and their families.",
    "Cork Takes the Heat": "Amorim Cork Solutions is contributing its P50 cork-based thermal protection material to DRACO, "
                           "a European Space Agency mission designed to capture rare in-flight data.",
    "Yonkers Rises": "I realized I didn't know where Yonkers was, so I looked it up on Google Maps and then, to help embed "
                     "its location and shape in my head, I prompted Fable 5.2 Medium …",
}


def typo(t):
    """Typographer's quotes and tidy spacing for wire copy."""
    t = re.sub(r"\s+([.,;:!?])", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r'(^|[\s(\[—-])"', r"\1“", t)
    t = t.replace('"', "”")
    t = re.sub(r"(^|[\s(\[—-])'", r"\1‘", t)
    t = t.replace("'", "’")
    t = t.replace(" - ", " – ")
    return t


def summary(s, limit=230):
    for key, text in OVERRIDE.items():
        if key in s["title"]:
            return typo(text)
    raw = (s.get("summary") or "").strip()
    if not raw:
        return ""
    raw = re.sub(r"\s*\[…\].*$", " …", raw)
    raw = re.sub(r"\s*The post .*? appeared first on .*$", "", raw)
    raw = typo(raw)
    raw = re.sub(r"\b(Dr|Mr|Mrs|Ms|St|Ltd|Inc|Co|No|vs)\. ", "\\1.\u00a0", raw)   # keep abbreviations with what follows
    parts = re.split(r"(?<=[.!?…])[”’]?\s+(?=[A-Z“‘0-9])", raw)
    out = ""
    for p in parts:
        complete = bool(re.search(r"[.!?…][”’)]?$", p))
        cand = (out + " " + p).strip()
        if len(cand) <= limit and (complete or p is not parts[-1] or len(raw) < 255):
            out = cand
        elif not out:
            cut = p[:limit].rsplit(" ", 1)[0].rstrip(",;:–—-")
            out = cut + " …"
            break
        else:
            break
    if out and not re.search(r"[.!?…][”’)]?$", out):
        out += "."
    return out


def tier(cov):
    return 1 if cov >= 8 else 2 if cov >= 5 else 3 if cov == 4 else 4 if cov == 3 else 5


def stamp(s):
    """Clock time the story was filed, derived from ageHours (minutes are synthetic)."""
    h = int(hashlib.md5(s["title"].encode()).hexdigest(), 16)
    t = PRESS - timedelta(hours=s["ageHours"] - 1, minutes=8 + h % 50)
    label = t.strftime("%H:%M") if t.date() == PRESS.date() else t.strftime("%a %H:%M")
    return f'<time datetime="{t.isoformat()}">{label}</time>'


def cov_mark(cov, label=True):
    if cov < 2:
        return ""
    txt = f"{cov} outlets" if label else str(cov)
    return f'<span class="cov" role="img" aria-label="Covered by {cov} outlets"><i></i>{txt}</span>'


LONG = {"w": 72, "n": 58}     # characters; a longer headline drops one step on its scale


def story(s, slot="n", kicker=False, clamp=None, cls="", limit=None, h="h3", ruled=False, want_dek=True):
    cov = s["sourceCount"]
    limit = limit or (230 if slot == "w" else 170)
    dek = summary(s, limit) if want_dek else ""
    bare = not (s.get("summary") or "").strip()
    long = len(s["title"]) > LONG[slot]
    classes = (["story", slot, f"t{tier(cov)}"] + (["long"] if long else []) + (["bare"] if bare else [])
               + (["ruled"] if ruled else []) + ([cls] if cls else []))
    eyebrow = ""
    bits = []
    if kicker:
        bits.append(f'<a class="kicker caps" href="#desk-{s["section"]}">{e(DESKS[s["section"]])}</a>')
    if cov >= 2:
        bits.append(cov_mark(cov))
    if bits:
        eyebrow = f'<p class="eyebrow">{"".join(bits)}</p>'
    dek_html = ""
    if dek:
        c = f' clamp" style="--lines:{clamp}' if clamp else ""
        dek_html = f'<p class="dek{c}">{e(dek)}</p>'
    return (
        f'<article class="{" ".join(classes)}" style="--cov:{cov}">'
        f'{eyebrow}<{h} class="hed"><a href="#">{e(typo(s["title"]))}</a></{h}>'
        f'{dek_html}'
        f'<p class="slug"><span class="src">{e(s["source"])}</span>{stamp(s)}</p>'
        f'</article>'
    )


# ---------------------------------------------------------------- figures (illustrative)

MARKETS = [
    # name, venue, last, change, pct, unit-format
    ("Nifty 50", "NSE", 27480.15, 114.90, 0.42),
    ("Sensex", "BSE", 89612.40, 349.21, 0.39),
    ("Nifty Bank", "NSE", 61204.85, -88.30, -0.14),
    ("S&P 500", "NYSE", 7104.52, -50.83, -0.71),
    ("Nasdaq", "Nasdaq", 24318.77, -455.20, -1.84),
    ("Rupee / $", "FX", 93.69, -0.22, -0.23),
    ("India 10-yr", "Yield %", 6.71, 0.06, 0.90),
    ("Brent", "$ / bbl", 61.40, -1.32, -2.10),
]


def signed(v, places=2, suffix=""):
    sign = "+" if v > 0 else "−" if v < 0 else ""
    return f'<span class="sign">{sign}</span>{abs(v):,.{places}f}{suffix}'


def direction(v):
    return "up" if v > 0 else "down" if v < 0 else "flat"


def dir_word(v):
    return "up" if v > 0 else "down" if v < 0 else "unchanged"


def series(name, pct, n=30):
    rnd = random.Random(name)
    xs = [0.0]
    for _ in range(n - 1):
        xs.append(xs[-1] + rnd.gauss(0, 1))
    # bend the walk so the last step agrees with the day's move
    drift = (abs(xs[-1] - xs[-2]) + 0.8) * (1 if pct > 0 else -1)
    xs[-1] = xs[-2] + drift * min(1.6, 0.5 + abs(pct))
    return xs


def spark(name, pct, w=120, hgt=28, pad=3):
    xs = series(name, pct)
    lo, hi = min(xs), max(xs)
    pts = [(pad + i * (w - 2 * pad) / (len(xs) - 1), hgt - pad - (x - lo) / (hi - lo or 1) * (hgt - 2 * pad)) for i, x in enumerate(xs)]
    d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    base = pts[-2][1]
    lx, ly = pts[-1]
    return (
        f'<svg class="spark" viewBox="0 0 {w} {hgt}" preserveAspectRatio="xMinYMid meet" role="img" '
        f'aria-label="{e(name)}, last 30 sessions, {dir_word(pct)} on the day">'
        f'<path class="base" d="M{pad} {base:.1f} H{w - pad}"/><path d="{d}"/><circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.4"/></svg>'
    )


def fmt_last(v):
    return f"{v:,.2f}"


# ---------------------------------------------------------------- shared chrome

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<script>
/* Edition: ?theme=dark|light wins, then the reader's saved choice, then the system. */
(function(){{var q=new URLSearchParams(location.search).get('theme'),s=null;try{{s=localStorage.getItem('fl-theme')}}catch(e){{}}var t=q||s;if(t==='dark'||t==='light')document.documentElement.setAttribute('data-theme',t)}})();
</script>
<link rel="preload" href="fonts/Newsreader-Roman-200_800-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="styles.css">
</head>
<body>
<a class="skip" href="#edition">Skip to the edition</a>
"""

FOOT = """<script src="script.js" defer></script>
</body>
</html>
"""


def emblem():
    cx, cy = 39.0, 47.0
    rays = []
    for i, a in enumerate(range(12, 169, 13)):
        r1, r2 = 19.0, (31.0 if i % 2 == 0 else 25.5)
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        rays.append(f'<path d="M{cx - r1 * ca:.2f} {cy - r1 * sa:.2f} L{cx - r2 * ca:.2f} {cy - r2 * sa:.2f}"/>')
    return (
        '<svg class="emblem" viewBox="0 0 78 50" aria-hidden="true" focusable="false">'
        '<g class="day" fill="none" stroke="currentColor" stroke-width="1.15" stroke-linecap="round">'
        f'{"".join(rays)}<path d="M25 47 A14 14 0 0 1 53 47 Z" fill="currentColor" stroke="none"/></g>'
        '<g class="night" fill="currentColor">'
        '<path d="M45.5 13.5 A13.5 13.5 0 1 0 56.6 34.2 A11 11 0 0 1 45.5 13.5 Z"/>'
        '<circle cx="22" cy="14" r="1.1"/><circle cx="60" cy="9" r=".9"/><circle cx="14" cy="31" r=".8"/><circle cx="66" cy="23" r="1.1"/></g>'
        '<path d="M2 47.5 H76" stroke="currentColor" stroke-width="1.15" fill="none"/>'
        '</svg>'
    )


NAV_ITEMS = [
    ("Front Page", None, True, "1"),
    ("The Wire", str(WIRE_NEW), False, "2"),
    ("Desks", None, False, "3"),
    ("Markets", None, False, "4"),
    ("Weekend Review", None, False, "5"),
    ("Claude Desk", None, False, "6"),
    ("Clippings", "4", False, "7"),
    ("Back Issues", None, False, "8"),
]


def toggle():
    return ('<button class="edition-toggle" type="button" data-theme-toggle>'
            '<span class="glyph" aria-hidden="true"></span>'
            '<span class="to-night">Night edition</span><span class="to-day">Day edition</span></button>')


def nav_strip(id_suffix=""):
    lis = []
    for name, count, current, _ in NAV_ITEMS:
        cur = ' aria-current="page"' if current else ""
        extra = ""
        if name == "The Wire":
            extra = f'<span class="live" aria-hidden="true"></span><span class="count">{count}<span class="sr-only"> new</span></span>'
        elif count:
            extra = f'<span class="count">{count}</span>'
        href = "index.html" if current else "#desks" if name == "Desks" else "#"
        lis.append(f'<li><a href="{href}"{cur}>{name}{extra}</a></li>')
    return (
        f'<nav class="index" aria-label="The paper{id_suffix}"><div class="page index-inner"><ul>{"".join(lis)}</ul>'
        '<div class="index-tools">'
        f'<label class="searchbox"><span class="sr-only">Search the paper</span><input type="search" placeholder="Search the paper" data-search><kbd aria-hidden="true">/</kbd></label>'
        f'{toggle()}</div></div></nav>'
    )


def index_sheet():
    toc = []
    for name, count, current, _ in NAV_ITEMS:
        if name == "Desks":
            continue
        cur = ' aria-current="page"' if current else ""
        n = {"Front Page": f"{edition_tally()[0]} stories", "The Wire": f"{WIRE_NEW} new", "Markets": "at close", "Weekend Review": "12 papers",
             "Claude Desk": "No. 47", "Clippings": "4 kept", "Back Issues": "46"}[name]
        toc.append(f'<li><a href="#"{cur}>{name}<span class="n">{n}</span></a></li>')
    desks = "".join(f'<li><a href="#desk-{k}">{v}</a></li>' for k, v in DESKS.items())
    return (
        '<nav class="index-sheet" aria-label="Index">'
        f'<ul class="toc">{"".join(toc)}</ul>'
        '<h3 class="caps">Desks</h3>'
        f'<ul class="desks">{desks}</ul>'
        f'<div class="sheet-foot">{toggle()}<a class="textbtn" href="#colophon">Colophon</a></div>'
        '</nav>'
    )


def phonebar(live=True):
    if live:
        left = f'<details class="idx"><summary class="barbtn"><span class="bars" aria-hidden="true"></span>Index</summary>{index_sheet()}</details>'
    else:
        left = '<span class="barbtn"><span class="bars is-x" aria-hidden="true"></span>Index</span>'
    return (
        '<div class="phonebar">'
        f'<div class="phonebar-row">{left}<span class="here caps">Front Page</span>'
        '<a class="barbtn" href="#search">Search</a></div>'
        '<div class="progress" aria-hidden="true"></div>'
        '</div>'
    )


def masthead():
    rows = []
    for name in ("Nifty 50", "Sensex", "S&P 500", "Rupee / $"):
        m = next(m for m in MARKETS if m[0] == name)
        rows.append(
            f'<tr class="{direction(m[4])}"><th scope="row">{e(m[0])}</th><td class="lastv">{fmt_last(m[2])}</td>'
            f'<td class="chg"><i class="arr" aria-hidden="true"></i>{signed(m[4], 2, "%")}</td></tr>'
        )
    total, minutes = edition_tally()
    return f"""<header class="masthead page">
  <div class="masthead-top">
    <aside class="ear ear-left" aria-label="Markets at close">
      <p class="ear-title caps"><span>Markets at close</span><span>Tue 10 Nov</span></p>
      <table><tbody>{"".join(rows)}</tbody></table>
    </aside>
    <div class="nameplate">
      <a href="index.html" aria-label="First Light, front page"><h1><span>First</span>{emblem()}<span>Light</span></h1></a>
    </div>
    <aside class="ear ear-right" aria-label="This edition">
      <p class="ear-title caps"><span>This edition</span><span>No. {EDITION_NO}</span></p>
      <dl>
        <div><dt>Reading time</dt><dd>about {minutes} min</dd></div>
        <div><dt>Stories</dt><dd>{total}<span class="wide-only">, from {len(OUTLETS)} outlets</span></dd></div>
        <div><dt>Went to press</dt><dd>06:00 IST</dd></div>
        <div class="wide-only"><dt>Build</dt><dd>{BUILD}</dd></div>
      </dl>
    </aside>
  </div>
  <div class="dateline">
    <p class="caps"><b>Wednesday</b>, November 11, 2026</p>
    <p class="motto">One edition a day. It ends.</p>
    <p class="caps">Morning edition · Vol. I, No. {EDITION_NO}</p>
  </div>
</header>
"""


# ---------------------------------------------------------------- the edition

LEAD = max(STORIES, key=lambda s: (s["sourceCount"], s["section"] == "world", -s["ageHours"]))
FRONT = [find("office suite"), find("metro rail"), find("impeach Defence"), find("Grok Build")]
BRIEFS = [find(k) for k in (
    "defamation case against BBC", "Collision of two trains", "Rupee touches strongest", "Claude Code is accidentally",
    "Six arrested", "Baird downgrades", "ESCAPADE",
)]
DESK_PICKS = {
    "world": ("Vinícius", "Kenyan doomsday", "Kennedys sue"),
    "india": ("Vinay Chand", "KCHR", "Punjab in a State"),
    "ai": ("fiber-optic", "eBay appears", "ASIMOV"),
    "ml": ("Genie 4", "accelerates real-world", "Speeding up planning"),
    "llm": ("mysterious beep", "Yonkers Rises", "Quoting Prompting"),
    "labs": ("Singapore Airlines", "veterans", "Cogent"),
    "companies": ("Lucid CEO", "Cork Takes", "China sales crash"),
    "markets": ("Mortgage rates", "biggest moves premarket", "rebound 5%"),
    "india-markets": ("Treasury rout hands", "Bajaj Finance", "Sell-Off Deepens"),
    "science": ("plesiosaur", "anthropologist", "postdoc rules"),
}


def edition_tally():
    total = 1 + len(FRONT) + len(BRIEFS) + sum(len(v) for v in DESK_PICKS.values())
    return total, max(1, round(total * 11.5 / 60))


def flag(key, label):
    return (f'<header class="flag desk-flag"><h2 id="desk-{key}">{e(label)}</h2>'
            f'<a class="more" href="#">All {DESK_COUNT[key]} on the desk</a></header>')


def desk(key, span, ruled, form="auto", limits=(None, None, None)):
    """Desk block. `form` chooses how three stories share the columns:
       row    A across two columns, B and C one column each          (span 4)
       stack  A across two columns, B over C in the third            (span 3)
       under  A across two columns with C beneath it, B in the third (span 3)
       pair   A across both columns, B and C side by side beneath    (span 2)
       pile   A, B, C each across both columns                       (span 2)"""
    a, b, c = (find(k) for k in DESK_PICKS[key])
    la, lb, lc = limits
    label = DESKS[key]
    if form == "auto":
        form = {4: "row", 3: "stack", 2: "pair"}[span]
    cls = f"desk span-{span} form-{form}" + (" ruled" if ruled else "")
    rule = '<hr class="rowrule">'
    if form == "row":
        body = story(a, "w", limit=la) + story(b, "n", ruled=True, limit=lb) + story(c, "n", ruled=True, limit=lc)
    elif form == "stack":
        body = story(a, "w", limit=la) + '<div class="stack ruled">' + story(b, "n", limit=lb) + story(c, "n", limit=lc) + "</div>"
    elif form == "under":
        body = ('<div class="under">' + story(a, "w", limit=la) + rule + story(c, "w", limit=lc, cls="minor") + "</div>"
                + story(b, "n", ruled=True, limit=lb))
    elif form == "pile":
        body = story(a, "w", limit=la) + rule + story(b, "w", limit=lb, cls="minor") + rule + story(c, "w", limit=lc, cls="minor")
    else:
        body = story(a, "w", limit=la) + rule + story(b, "n", limit=lb) + story(c, "n", ruled=True, limit=lc)
    return f'<section class="{cls}" aria-labelledby="desk-{key}">{flag(key, label)}{body}</section>'


def front():
    s = LEAD
    n = len(s["title"])
    fit = "fit-short" if n <= 45 else "fit-long" if n > 70 else "fit-mid"
    lead = (
        f'<article class="story lead {fit}" style="--cov:{s["sourceCount"]}">'
        f'<p class="eyebrow"><a class="kicker caps" href="#desk-{s["section"]}">{DESKS[s["section"]]}</a>{cov_mark(s["sourceCount"])}</p>'
        f'<h3 class="hed"><a href="#">{e(typo(s["title"]))}</a></h3>'
        f'<p class="dek">{e(summary(s, 260))}</p>'
        '<div class="docket">'
        f'<p class="slug"><span class="src">{e(s["source"])}</span>{stamp(s)}</p>'
        f'<p class="why">Leads the edition: carried by {s["sourceCount"]} outlets, more than any other story this morning.</p>'
        '<p class="acts"><a class="textbtn" href="#">Read at source</a><button class="textbtn" type="button" data-clip aria-pressed="false">Clip</button></p>'
        '</div></article>'
    )
    s2, s3, s4, s5 = FRONT
    briefs = "".join(
        f'<li><a class="kicker caps" href="#desk-{b["section"]}">{DESKS[b["section"]]}</a>'
        f'<a href="#">{e(typo(b["title"]))}</a><span class="by">{e(b["source"])}</span></li>'
        for b in BRIEFS
    )
    return f"""<section class="sheet front" aria-labelledby="front-h">
  <h2 id="front-h" class="sr-only">Front page</h2>
  {lead}
  {story(s2, "w", kicker=True, cls="s2")}
  <hr class="rowrule">
  {story(s3, "w", kicker=True, cls="s3")}
  {story(s4, "n", kicker=True, cls="s4", ruled=True)}
  {story(s5, "n", kicker=True, cls="s5", ruled=True)}
  <section class="briefs" aria-labelledby="briefs-h">
    <header class="flag"><h2 id="briefs-h">In brief</h2><span class="more">{len(BRIEFS)} one-liners</span></header>
    <ol>{briefs}</ol>
  </section>
</section>
"""


def key():
    """The legend: how outlet count becomes headline size and weight."""
    steps = []
    for cov, label in ((9, "9"), (6, "6"), (4, "4"), (3, "3"), (1, "1")):
        mark = f'<span class="cov"><i></i>{label}</span>' if cov > 1 else '<span class="cov">1 · no mark</span>'
        steps.append(f'<li class="t{tier(cov)}" style="--cov:{cov}"><b class="hed" aria-hidden="true">Aa</b>{mark}</li>')
    return (
        '<aside class="key sheet" aria-label="How to read this page">'
        '<h2 class="caps">How to read <span>this page</span></h2>'
        f'<ol aria-label="Headline size by number of outlets">{"".join(steps)}</ol>'
        '<p>One dot for each outlet that carried the story. The more outlets, the larger and heavier the headline. '
        '<i>An italic headline</i> means the outlet filed a headline and nothing else.</p>'
        '</aside>'
    )


def tape():
    ticks = []
    for name, venue, last, chg, pct in MARKETS:
        ticks.append(
            f'<article class="tick {direction(pct)}"><h3>{e(name)}</h3><span class="last">{fmt_last(last)}</span>'
            f'<span class="chg"><i class="arr" aria-hidden="true"></i>{signed(pct, 2, "%")}'
            f'<span class="sr-only"> {dir_word(pct)}</span></span>{spark(name, pct)}</article>'
        )
    return f"""<section class="tape-band" aria-labelledby="tape-h">
  <header class="flag"><h2 id="tape-h">The tape</h2><span class="more">Close of Tuesday 10 November · line shows 30 sessions · dotted line is the previous close</span></header>
  <div class="tape">{"".join(ticks)}</div>
</section>
"""


PROMPT = """&lt;document&gt;
<span class="slot">{{paste the report}}</span>
&lt;/document&gt;

First, copy the passages that bear on my question into &lt;quotes&gt; tags, word for word.

Then answer using only those quotes. If the quotes do not settle it, say so.

Question: <span class="slot">{{your question}}</span>"""


def adopt(name, checked="tried"):
    opts = [("not", "Not tried"), ("tried", "Tried"), ("workflow", "In my workflow")]
    labels = "".join(
        f'<label><input type="radio" name="{name}" value="{v}"{" checked" if v == checked else ""}><span class="box" aria-hidden="true"></span>{t}</label>'
        for v, t in opts
    )
    return f'<fieldset class="adopt" data-adopt><legend class="caps">Where are you with this?</legend><div class="adopt-opts">{labels}</div></fieldset>'


EARLIER = """<div class="cd-earlier">
      <h4 class="caps">Earlier on the desk</h4>
      <ol>
        <li><span class="mono">46</span><a href="#">Give it the failing test, not the bug report</a><span class="state is-in">In my workflow</span></li>
        <li><span class="mono">45</span><a href="#">Ask for the plan before the patch</a><span class="state is-tried">Tried</span></li>
        <li><span class="mono">44</span><a href="#">Put the long document first, the question last</a><span class="state">Not tried</span></li>
      </ol>
    </div>
"""


def claude_desk(name="adopt-front", cls="claude-desk", earlier=""):
    return f"""<section class="{cls}" aria-labelledby="{name}-h">
  <div class="cd-body">
    <header class="cd-flag"><h2 id="{name}-h">Claude Desk</h2><span>Technique No. {EDITION_NO} · one to try at work today</span></header>
    <h3 class="cd-title">Quote first, then answer</h3>
    <p class="cd-when"><b>Reach for it when</b>you are asking about a long document (a contract, an incident report, a transcript) and need to see where the answer came from. Asking for the passages first keeps the answer honest.</p>
    {adopt(name)}
{earlier}  </div>
  <div class="cd-prompt prompt">
    <div class="prompt-head"><span class="caps">Prompt</span><button class="copybtn" type="button" data-copy>Copy</button></div>
    <pre>{PROMPT}</pre>
  </div>
</section>"""


def index_page():
    total, minutes = edition_tally()
    ruler = '<div class="ruler" aria-hidden="true"><ol>' + "<li></li>" * 90 + "</ol></div>"
    bands = f"""
{key()}
<div class="sheet band after-key" id="desks">
  {desk("world", 3, False, "under")}
  {desk("india", 3, True, "under")}
</div>
<div class="sheet band">
  {desk("ai", 3, False, "under")}
  {desk("ml", 3, True, "under")}
</div>
<div class="sheet band">
  {desk("llm", 2, False, "pile")}
  {desk("labs", 2, True)}
  {desk("companies", 2, True)}
</div>
{tape()}
<div class="sheet band">
  {desk("markets", 2, False)}
  {desk("india-markets", 4, True, limits=(300, 230, 230))}
</div>
<div class="sheet band">
  {desk("science", 2, False)}
  {claude_desk()}
</div>
"""
    return (
        HEAD.format(title="First Light — Wednesday, November 11, 2026")
        + phonebar()
        + masthead()
        + nav_strip()
        + f'<main class="page"><div class="edition" id="edition">{ruler}{front()}{bands}'
        + f"""<footer class="endmark">
  <p class="thirty"><span aria-hidden="true">30</span><span class="sr-only">Thirty. End of the edition.</span></p>
  <p class="tally">That’s the edition. {total} stories, about {minutes} minutes.</p>
  <p class="next caps">Next edition at first light tomorrow · 06:00 IST</p>
  <p class="onward"><a class="textbtn" href="#">The Wire has {WIRE_NEW} newer items</a><a class="textbtn" href="#">Back Issues</a><a class="textbtn" href="components.html">Specimen sheet</a></p>
</footer>
</div></main>
<div class="gauge" aria-hidden="true"><span><b data-inch>0</b><small data-inch-total>in.</small></span></div>
<footer class="page"><div class="colophon" id="colophon">
  <span>Colophon. Set in Newsreader, Archivo and IBM Plex Mono. Typeset by software, not by hand.</span>
  <span>Went to press 06:00:14 IST · build {BUILD} · market figures in this prototype are placeholders</span>
</div></footer>
"""
        + FOOT
    )


# ---------------------------------------------------------------- specimen sheet

PAPERS = [
    {
        "rank": 1, "id": "2611.14483", "cat": "cs.CL",
        "title": "Mechanistic Interpretability Needs a Logic of Inference",
        "authors": "Zhimin Hu, Chen Jiang, Hanbo Xie, N. Apurva Ratan Murty, Sashank Varma",
        "chips": [("Desk", "LLMs"), ("Kind", "position paper"), ("Filed", "this week")],
        "digest": [
            "As these tools improve, attention is shifting from what can be observed inside a model to how those observations support mechanistic explanations.",
            "We propose five principles and organize them into a recursive logic for a more rigorous procedure of mechanistic inference.",
            "Evidence beyond MI is ultimately required to establish what model mechanisms reveal about the world.",
        ],
    },
    {
        "rank": 2, "id": "2611.14459", "cat": "cs.CL",
        "title": "When does text encoding matter for language modeling?",
        "authors": "Eugene Jang, Catherine Arnett, Terra Blevins",
        "chips": [("Desk", "LLMs"), ("Tests", "4 languages"), ("Filed", "this week")],
        "digest": [
            "UTF-8’s role as the de facto encoding standard in language models introduces cross-lingual inequities due to its variable-length design.",
            "However, the effect that this encoding choice has on model performance remains largely unexamined.",
            "In light of these findings, we argue that text encoding should be a language-specific design decision, rather than a universal default.",
        ],
    },
    {
        "rank": 3, "id": "2611.14515", "cat": "cs.CL",
        "title": "AutoScaffold: AI-Guided Scaffolding for Reinforcement Learning of Language Models",
        "authors": "Zijian Zhang, Rizhen Hu, Jiangweizhi Peng, Shiyang Li, Sujay Bhatt, Sihan Zeng, Mingyi Hong",
        "chips": [("Desk", "Machine Learning"), ("Result", "+7.2 pts ALFWorld"), ("Filed", "this week")],
        "digest": [
            "Reinforcement learning with verifiable rewards (RLVR) produces rich training experience, yet outcome rewards reduce each attempt to a single number and leave most of this information unused.",
            "We introduce AutoScaffold, a unified AI-for-AI framework that turns a student’s training experience into adaptive scaffolds, with minimal domain-specific information and no human intervention during training.",
            "The scaffolds are removed at evaluation.",
        ],
    },
]


def paper_card(p):
    chips = "".join(f'<span class="chip">{e(k)} <b>{e(v)}</b></span>' for k, v in p["chips"])
    digest = "".join(f"<li>{e(d)}</li>" for d in p["digest"])
    return (
        f'<article class="paper"><p class="rank" aria-label="Rank {p["rank"]}">{p["rank"]}</p>'
        f'<h3><a href="#">{e(p["title"])}</a></h3>'
        f'<p class="authors">{e(p["authors"])}</p>'
        f'<p class="chips" aria-label="Why it surfaced">{chips}</p>'
        f'<ol class="digest" aria-label="Digest, three lines from the abstract">{digest}</ol>'
        f'<p class="foot">arXiv:{p["id"]} · {p["cat"]}</p></article>'
    )


def wire_rows():
    picks = [
        ("09:42", "Does Meta think", True, False),
        ("09:37", "Thomas Markle", True, False),
        ("09:31", "ANC faces bruising", True, True),
        ("09:18", "Speeding up planning", False, False),
        ("09:06", "Lucid CEO", True, False),
        ("08:54", "postdoc rules", False, False),
        ("08:40", "Tesla launches Robotaxi", False, False),
        ("08:22", "llm-anthropic 0.31", False, False),
    ]
    rows = []
    for t, key, unread, cursor in picks:
        s = find(key)
        cls = "wire-row" + (" unread" if unread else "") + (" is-cursor" if cursor else "")
        state = "Unread" if unread else "Read"
        cur_attr = ' aria-current="true"' if cursor else ""
        rows.append(
            f'<li class="{cls}" style="--cov:{s["sourceCount"]}"{cur_attr}>'
            f'<span class="mark" role="img" aria-label="{state}"></span>'
            f'<time datetime="2026-11-11T{t}">{t}</time><span class="tag">{e(DESKS[s["section"]])}</span>'
            f'<a class="wh" href="#">{e(typo(s["title"]))}</a>'
            f'{cov_mark(s["sourceCount"], label=False) or "<span></span>"}'
            f'<span class="wsrc">{e(s["source"])}</span></li>'
        )
    return "".join(rows)


def search_results():
    hits = [s for s in STORIES if re.search(r"Nvidia|Huang", s["title"])]
    hits.sort(key=lambda s: (-s["sourceCount"], s["ageHours"]))
    rows = []
    for s in hits[:6]:
        title = re.sub(r"(Nvidia|Jensen Huang|Huang|chipmaker)", r"<mark>\1</mark>", e(typo(s["title"])))
        rows.append(
            f'<li style="--cov:{s["sourceCount"]}"><span class="tag">{e(DESKS[s["section"]])}</span>'
            f'<a class="wh" href="#">{title}</a>{cov_mark(s["sourceCount"], label=False) or "<span></span>"}'
            f'<span class="wsrc">{e(s["source"])}</span></li>'
        )
    return "".join(rows)


def market_table():
    body = []
    for name, venue, last, chg, pct in MARKETS[:5]:
        rnd = random.Random(name + "r")
        pos = rnd.uniform(0.12, 0.88) if pct else 0.5
        pos = 0.5 + (pos / 2 if pct > 0 else -pos / 2) * 0.9
        body.append(
            f'<tr class="{direction(pct)}"><th scope="row">{e(name)}<small>{e(venue)}</small></th>'
            f'<td class="last">{fmt_last(last)}</td>'
            f'<td class="chg hide-s">{signed(chg)}</td>'
            f'<td class="chg"><i class="arr" aria-hidden="true"></i>{signed(pct, 2, "%")}<span class="sr-only"> {dir_word(pct)}</span></td>'
            f'<td class="range hide-s"><div class="rangebar" role="img" aria-label="Closed at {round(pos * 100)} percent of the day’s range"><i style="left:{pos * 100:.0f}%"></i></div></td>'
            f'<td>{spark(name, pct)}</td></tr>'
        )
    return (
        '<table class="mkt"><caption class="sr-only">Markets at close, Tuesday 10 November</caption><thead><tr>'
        '<th scope="col">Instrument</th><th scope="col">Last</th><th scope="col" class="hide-s">Change</th><th scope="col">%</th>'
        '<th scope="col" class="hide-s">Day’s range</th><th scope="col">30 sessions</th></tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>'
    )


def swatches():
    items = [
        ("Paper", "--paper"), ("Paper, shade", "--paper-shade"), ("Paper, deep", "--paper-deep"), ("Ink", "--ink"), ("Ink, soft", "--ink-soft"),
        ("Ink, mute", "--ink-mute"), ("Rule", "--rule"), ("Rule, hair", "--rule-hair"), ("Rule, faint", "--rule-faint"), ("Spot", "--spot"),
    ]
    return "".join(
        f'<div class="swatch"><div class="chip-col" style="background:var({v})"></div><b>{n}</b><span>{v}</span><span data-token="{v}"></span></div>'
        for n, v in items
    )


def scale_rows():
    samples = [
        (9, find("office suite"), find("Bajaj Finance")),
        (6, find("metro rail"), find("veterans")),
        (4, find("Kennedys sue"), find("Cogent")),
        (3, find("eBay appears"), find("Quoting Prompting")),
        (1, find("Pope Leo"), find("Gemini 4 Carbon is now")),
    ]
    rows = []
    for cov, wide, narrow in samples:
        w = dict(wide, sourceCount=cov)
        n = dict(narrow, sourceCount=cov)
        t = tier(cov)
        rows.append(
            f'<div class="scale-row" style="--cov:{cov}"><p class="k">{cov_mark(cov) or "<span class=cov>1 outlet · no mark</span>"}<br>tier {t} · wght {404 + 26 * cov}<br>.w.t{t} / .n.t{t}</p>'
            f'<div class="scale-pair">{story(w, "w", want_dek=False)}{story(n, "n", want_dek=False)}</div></div>'
        )
    return "".join(rows)


def components_page():
    nvidia = sum(1 for s in STORIES if re.search(r"Nvidia|Huang", s["title"] + " " + (s.get("summary") or "")))
    nv_desks = len({s["section"] for s in STORIES if re.search(r"Nvidia|Huang", s["title"] + " " + (s.get("summary") or ""))})
    bare = find("plesiosaur")
    with_dek = find("Hegseth")
    return (
        HEAD.format(title="First Light — Specimen sheet")
        + f"""<main class="page" id="edition">
<header class="spec-head">
  <div>
    <p class="caps" style="color:var(--spot)">First Light · The Broadsheet</p>
    <h1>Specimen sheet</h1>
    <p>The parts the rest of the paper is built from. Every colour, size and space on this sheet is a custom property in <span class="mono" style="font-size:.85em">styles.css</span>; nothing is styled twice.</p>
  </div>
  <div class="meta"><a class="textbtn" href="index.html">Front Page</a><br><br>{toggle()}</div>
</header>

<section class="spec" aria-labelledby="sp1">
  <header><p class="no">01</p><h2 id="sp1">Paper and two inks</h2><p>Black, and one spot colour used the way a second ink was: labels, marks and losses. Never a headline.</p></header>
  <div class="body"><div class="swatches">{swatches()}</div></div>
</section>

<section class="spec" aria-labelledby="sp2">
  <header><p class="no">02</p><h2 id="sp2">Weight is coverage</h2><p>The outlet count picks the step on the scale and the weight of the face. Wide measure on the left, one column on the right.</p></header>
  <div class="body"><div class="scale">{scale_rows()}</div></div>
</section>

<section class="spec" aria-labelledby="sp3">
  <header><p class="no">03</p><h2 id="sp3">A story, three ways</h2><p>With a summary. Without one, set in italic so the gap reads as a choice. As a one-liner.</p></header>
  <div class="body"><div class="threeup">
    <div><p class="cap caps">With summary</p>{story(with_dek, "n", kicker=True)}</div>
    <div><p class="cap caps">Headline only</p>{story(bare, "n", kicker=True)}</div>
    <div><p class="cap caps">In brief, and clipped</p>
      <ol class="briefs" style="border-top-width:1px"><li><a class="kicker caps" href="#">World</a><a href="#">{e(typo(find("Collision of two trains")["title"]))}</a><span class="by">The Guardian</span></li></ol>
      <p style="margin-top:var(--s4);display:flex;gap:var(--s3)"><button class="clip" type="button" data-clip aria-pressed="false">Clip</button><button class="clip" type="button" data-clip aria-pressed="true">Clipped</button></p>
    </div>
  </div></div>
</section>

<section class="spec" aria-labelledby="sp4">
  <header><p class="no">04</p><h2 id="sp4">Getting around</h2><p>Laptop: one index line under the nameplate; the current page is reversed out of ink. Phone: a bar that opens the Index, set like a contents page.</p></header>
  <div class="body"><div class="navs">
    <div>
      <p class="cap caps" style="margin-top:0">Desk flag</p>
      <div style="border-top:var(--rule-heavy) solid var(--rule);padding-top:var(--s2)">{flag("india-markets", "Dalal Street")}</div>
      <p class="cap caps">Search, expanded</p>
      <div class="search-big" id="search">
        <div class="field"><label class="caps" for="q">Search</label><input id="q" type="search" value="nvidia" aria-describedby="also"></div>
        <div class="also" id="also"><span class="lbl">Also searching:</span>
          <span class="chip x">NVDA<button type="button" aria-label="Stop searching NVDA">×</button></span>
          <span class="chip x">Jensen Huang<button type="button" aria-label="Stop searching Jensen Huang">×</button></span>
          <span class="chip x">chipmaker<button type="button" aria-label="Stop searching chipmaker">×</button></span>
          <span class="chip x off">GPU<button type="button" aria-label="Search GPU again">+</button></span>
        </div>
        <p class="result-line">{nvidia} stories on {nv_desks} desks · this edition and the Wire · press Enter to open the first</p>
        <ol class="results">{search_results()}</ol>
      </div>
    </div>
    <div>
      <p class="cap caps">Phone, Index open</p>
      <div class="phone-frame">{phonebar(live=False)}{index_sheet()}</div>
    </div>
  </div></div>
  <div class="full">
    <p class="cap caps">Laptop index line, full width</p>
    <div class="frame">{nav_strip(", sample")}</div>
    <p class="frame-note">Keys: 1 to 8 change page · / search · g then a desk’s first letter jumps to it · n switches to the night edition</p>
  </div>
</section>

<section class="spec" aria-labelledby="sp5">
  <header><p class="no">05</p><h2 id="sp5">The Wire</h2><p>Everything since the edition closed. One line each, newest first, driven from the keyboard.</p></header>
  <div class="body">
    <div class="wire">
      <div class="wire-head" aria-hidden="true"><span></span><span class="caps">Filed</span><span class="caps">Desk</span><span class="caps">Headline</span><span class="caps">Outlets</span><span class="caps" style="text-align:right">Source</span></div>
      <ol>{wire_rows()}</ol>
      <p class="wire-keys"><span><kbd>j</kbd><kbd>k</kbd> move</span><span><kbd>Enter</kbd> open</span><span><kbd>c</kbd> clip</span><span><kbd>u</kbd> mark unread</span><span><kbd>g</kbd><kbd>f</kbd> front page</span></p>
    </div>
  </div>
</section>

<section class="spec" aria-labelledby="sp6">
  <header><p class="no">06</p><h2 id="sp6">Markets table</h2><p>Sign and arrow on every move; the second ink marks a fall. Figures are tabular.</p></header>
  <div class="body">{market_table()}</div>
</section>

<section class="spec" aria-labelledby="sp7">
  <header><p class="no">07</p><h2 id="sp7">Weekend Review</h2><p>A ranked reading list of papers. Each card says why it surfaced and quotes three lines of the abstract.</p></header>
  <div class="body"><div class="papers">{"".join(paper_card(p) for p in PAPERS)}</div></div>
</section>

<section class="spec" aria-labelledby="sp8">
  <header><p class="no">08</p><h2 id="sp8">Claude Desk</h2><p>One technique, when to reach for it, a prompt to copy, and a ballot for where you are with it.</p></header>
  <div class="body"><div class="sheet" style="--cols:4">{claude_desk("adopt-spec", earlier=EARLIER)}</div></div>
</section>

<footer class="colophon" style="border-top:0"><span>Specimen sheet for the Broadsheet direction. Headlines are real, fetched 11 November 2026; outlet counts and market figures are synthetic.</span><span>Papers: arXiv listing of the same day.</span></footer>
</main>
"""
        + FOOT
    )


if __name__ == "__main__":
    (HERE / "index.html").write_text(index_page(), encoding="utf-8")
    (HERE / "components.html").write_text(components_page(), encoding="utf-8")
    total, minutes = edition_tally()
    print(f"lead: {LEAD['title']}")
    print(f"{total} stories, about {minutes} minutes; {len(OUTLETS)} outlets")
