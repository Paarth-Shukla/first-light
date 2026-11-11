#!/usr/bin/env python3
"""Typesets the Gazette prototype from design/fixture.json.

    python3 build.py        -> writes index.html and components.html beside this file

The pages are static. This script exists so the prototype is set from the real
fixture (no hand-copied headlines) and so the composition rules are written
down in one place: how coverage earns a headline tier, how dispatches are
numbered, how filed times are printed, how a tally is drawn.
"""
import html
import json
import math
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "..", "..", "fixture.json")

PRESS_HOUR, PRESS_MIN = 5, 30          # edition closes 05:30 IST
EDITION_NO = 315                        # day of year, 11 November 2026
DATE_LONG = "Wednesday, November 11, 2026"
DATE_SHORT = "Wed 11 Nov"
BUILD_STAMP = "2026.11.11-0530 · a3f9c1e"

DESKS = [  # key in fixture, name on the page, anchor
    ("world", "World", "world"),
    ("india", "India", "india"),
    ("ai", "AI", "ai"),
    ("ml", "Machine Learning", "ml"),
    ("llm", "LLMs", "llms"),
    ("labs", "Frontier Labs", "labs"),
    ("companies", "Companies", "companies"),
    ("markets", "Markets", "markets"),
    ("india-markets", "Dalal Street", "dalal-street"),
    ("science", "Science", "science"),
]
DESK_NAME = {k: n for k, n, _ in DESKS}
DESK_ANCHOR = {k: a for k, _, a in DESKS}
WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
         "thirteen", "fourteen", "fifteen", "sixteen"]


# ---------------------------------------------------------------- typography
def smart(t):
    """Straight quotes to curly, spaced hyphens to en dashes. Nothing else."""
    t = t.replace(" - ", " – ").replace(" .", ".").replace("​", "")
    t = re.sub(r'"([^"]*)"', "“\\1”", t)
    t = re.sub(r"(\w)'(\w)", "\\1’\\2", t)
    t = re.sub(r"(\w)'(\s|$)", "\\1’\\2", t)
    return t.strip()


def esc(t):
    return html.escape(t, quote=False)


def clip(text, start=None, end=None, tail=""):
    """Take a verbatim span of a fixture summary. Never rewrites, only trims."""
    if not text:
        return ""
    a = text.index(start) if start else 0
    b = text.index(end, a) + len(end) if end else len(text)
    out = text[a:b].strip() + tail
    if out and out[-1] not in ".!?…”":
        out += "."
    return smart(out)


def tier(n):
    return "a" if n >= 8 else "b" if n >= 5 else "c" if n >= 3 else "d"


def filed(age):
    """A frozen edition prints the hour a story was filed, never 'n hours ago'."""
    minutes = PRESS_HOUR * 60 + PRESS_MIN - age * 60
    day = ""
    if minutes < 0:
        minutes += 24 * 60
        day = "Tue "
    return "%s%02d:%02d" % (day, minutes // 60, minutes % 60)


def tally(n):
    """One stroke per outlet, gated in fives."""
    x, parts = 1.0, []
    full, rest = divmod(n, 5)
    for _ in range(full):
        for i in range(4):
            parts.append("M%.1f 1.5V11.5" % (x + i * 3.5))
        parts.append("M%.1f 9.6L%.1f 3.4" % (x - 1.6, x + 3 * 3.5 + 1.6))
        x += 4 * 3.5 + 3.5
    for i in range(rest):
        parts.append("M%.1f 1.5V11.5" % (x + i * 3.5))
    if rest:
        x += rest * 3.5
    w = max(3.0, x - 2.5 + 1)
    return ('<svg class="tally" width="%.1f" height="13" viewBox="0 0 %.1f 13" aria-hidden="true">'
            '<path d="%s"/></svg>') % (w, w, "".join(parts))


def outlets(n):
    return "%d outlet%s" % (n, "" if n == 1 else "s")


ARROW_UP = '<svg class="arrow arrow--up" viewBox="0 0 10 10" aria-hidden="true"><path d="M5 .8l4.6 8.4H.4z"/></svg>'
ARROW_DOWN = '<svg class="arrow arrow--down" viewBox="0 0 10 10" aria-hidden="true"><path d="M5 9.2L.4.8h9.2z"/></svg>'
ORNAMENT = ('<svg class="ornament" width="168" height="12" viewBox="0 0 168 12" aria-hidden="true">'
            '<path d="M0 6H64M104 6H168" fill="none" stroke="currentColor" stroke-width="1"/>'
            '<path class="spot" d="M84 .5l5.5 5.5-5.5 5.5L78.500 6z"/>'
            '<path d="M71 3.500l2.500 2.500-2.500 2.500L68.500 6zM97 3.500l2.500 2.500-2.500 2.500L94.500 6z" fill="currentColor"/></svg>')


def vignette():
    rays = []
    for i in range(15):
        ang = math.radians(190 + i * (160 / 14))
        r1, r2 = 18, (37 if i % 2 == 0 else 28)
        rays.append("M%.1f %.1fL%.1f %.1f" % (48 + r1 * math.cos(ang), 46 + r1 * math.sin(ang),
                                           48 + r2 * math.cos(ang), 46 + r2 * math.sin(ang)))

    def star(x, y, r=2.6, k=0.75):
        pts = [(x, y - r), (x + k, y - k), (x + r, y), (x + k, y + k), (x, y + r), (x - k, y + k), (x - r, y), (x - k, y - k)]
        return "M" + "L".join("%.1f %.1f" % p for p in pts) + "z"

    stars = "".join(star(*p) for p in [(20, 17), (76, 12), (84, 31, 2, 0.6), (12, 34, 2, 0.6), (33, 8, 1.8, 0.5)])
    return ('<svg class="vignette" viewBox="0 0 96 66" aria-hidden="true">'
            '<g class="sun"><path class="line" d="%s"/><path class="disc" d="M35 46a13 13 0 0 1 26 0z"/></g>'
            '<g class="moon"><path class="disc" d="M50 10a15 15 0 1 0 13.500 21.500A12 12 0 0 1 50 10z"/><path class="star" d="%s"/></g>'
            '<path class="line" d="M4 46H92M13 51.500H83M23 56.500H73M34 61.500H62"/></svg>') % ("".join(rays), stars)


def spark(seed, pct, n=22, w=88, h=20):
    """Five-session trace. Deterministic; the last move matches the day's sign."""
    rnd = random.Random(seed)
    v, pts = 0.0, [0.0]
    for _ in range(n - 2):
        v += rnd.uniform(-1, 1) + pct * 0.08
        pts.append(v)
    pts.append(pts[-1] + (abs(rnd.uniform(0.6, 1.4)) * (1 if pct >= 0 else -1)))
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1
    xs = [2 + i * (w - 6) / (n - 1) for i in range(n)]
    ys = [h - 2.5 - (p - lo) / span * (h - 5) for p in pts]
    d = "M" + "L".join("%.1f %.1f" % (x, y) for x, y in zip(xs, ys))
    base = ys[0]
    cls = "spark spark--down" if pct < 0 else "spark"
    return ('<svg class="%s" viewBox="0 0 %d %d" role="img" aria-label="Five sessions against the level five sessions ago, last move %s">'
            '<path class="base" d="M2 %.1fH%d"/><path class="path" d="%s"/>'
            '<circle class="end" cx="%.1f" cy="%.1f" r="2.4"/></svg>') % (
        cls, w, h, "down" if pct < 0 else "up", base, w - 2, d, xs[-1], ys[-1])


# ---------------------------------------------------------------- the edition
data = json.load(open(FIXTURE, encoding="utf-8"))
STORIES = data["stories"]


def find(key):
    hits = [s for s in STORIES if key in s["title"]]
    assert len(hits) == 1, (key, len(hits))
    return hits[0]


# (title key, summary span). None = print the fixture summary whole; "" = none.
def S(key, **cut):
    s = dict(find(key))
    raw = s.get("summary") or ""
    if cut.get("bare"):
        s["sum"] = ""
    elif cut:
        s["sum"] = clip(raw, cut.get("start"), cut.get("end"), cut.get("tail", ""))
    else:
        s["sum"] = clip(raw)
    s["title"] = smart(s["title"])
    return s


LEAD = S("Falkland", start="The people of", end="offshore oilfield, the attorney general", tail="…")
LEAD["deck"] = clip(find("Falkland")["summary"], end="sovereignty dispute").rstrip(".")
FRONT_LEFT = [
    S("Anthropic has its own", end="copy its strategies."),
    S("Bajaj Finance", end="currently being finalized."),
]
FRONT_UNDER = [
    S("Tesla’s China", end="according to CPCA data."),
    S("US House blocks"),
]
BRIEFS = [
    S("Collision of two trains"), S("Rupee touches strongest"),
    S("Google releases Gemini 4 Carbon"), S("ESCAPADE on its way"), S("llm-anthropic 0.31"),
    S("Pope Leo delivers"), S("Introducing Businesses in ChatGPT"), S("Students need AI-free"),
]
for _b in BRIEFS:
    _b["sum"] = ""   # briefs print the headline only
DESK_STORIES = {
    "world": [S("Vinícius"), S("Kenyan doomsday", end="their families"),
              S("ANC faces", end="below 2021 result")],
    "india": [S("Vinay Chand"), S("Cabinet approves"), S("Opposition slams")],
    "ai": [S("Ukraine’s fiber"), S("Grok Build"), S("DeepMind reveals")],
    "ml": [S("Genie 4"), S("Speeding up planning"), S("Introducing AlphaProof")],
    "llm": [S("Locating the source", end="intermittently beeping ."),
            S("Yonkers Rises", start="I realized", end="animation skills)", tail="…"),
            S("Quoting Prompting", end="the code it works on.")],
    "labs": [S("Singapore Airlines"), S("ChatGPT Plus for veterans", end="ChatGPT Plus."), S("Cogent")],
    "companies": [S("Lucid CEO", end="where cars were.”"),
                  S("Musk says Cybertruck", end="because it’s unprofitable."),
                  S("Tesla launches Robotaxi", end="274 square miles.")],
    "markets": [S("Mortgage rates"), S("Nvidia shares rebound"), S("Baird downgrades")],
    # the fixture summary for this story describes a different one (the rupee), so it runs bare
    "india-markets": [S("US Treasury rout", bare=True), S("Realty firms", end="has been observed."),
                      S("These 12 midcap", end="the broader index.")],
    "science": [S("plesiosaur"), S("Why your physics"), S("Chile’s postdoc")],
}

# Number the dispatches in reading order.
ORDER = [LEAD] + FRONT_LEFT + FRONT_UNDER + BRIEFS
RANGES = {"front": (1, len(ORDER))}
for key, _, _ in DESKS:
    a = len(ORDER) + 1
    ORDER += DESK_STORIES[key]
    RANGES[key] = (a, len(ORDER))
for i, s in enumerate(ORDER, 1):
    s["no"] = i
TOTAL = len(ORDER)
WORDCOUNT = sum(len((s["title"] + " " + s["sum"] + " " + s.get("deck", "")).split()) for s in ORDER)
MINUTES = max(1, round(WORDCOUNT / 200))
ON_WIRE = len(STORIES) - TOTAL


USED = {s["title"] for s in ORDER}
MORE = {k: sum(1 for s in STORIES if s["section"] == k and smart(s["title"]) not in USED) for k, _, _ in DESKS}


def desk_foot(key):
    n = MORE[key]
    if not n:
        return '<p class="desk__more">Nothing further at this desk.</p>'
    word = WORDS[n].capitalize() if n < len(WORDS) else str(n)
    return ('<p class="desk__more"><a href="#">%s more at the %s desk</a></p>') % (word, DESK_NAME[key])


def nos(key):
    a, b = RANGES[key]
    return "Nos. %d–%d" % (a, b)


def meta(s, with_time=True):
    return ('<p class="story__meta"><span class="cov">%s%s</span>'
            '<span class="by">%s%s</span></p>') % (
        tally(s["sourceCount"]), outlets(s["sourceCount"]), esc(s["source"]),
        ' <time>%s</time>' % filed(s["ageHours"]) if with_time else "")


def story(s, t=None, desk=False, why=None):
    t = t or tier(s["sourceCount"])
    cls = "story story--%s%s" % (t, "" if s["sum"] else " story--bare")
    kick = '<span class="no">No. %d</span>' % s["no"]
    if desk:
        kick += '<a class="story__desk" href="#%s">%s</a>' % (DESK_ANCHOR[s["section"]], DESK_NAME[s["section"]])
    out = ['<article class="%s" id="no-%d">' % (cls, s["no"]),
           '<p class="story__kicker">%s</p>' % kick,
           '<h3 class="story__head"><a href="#">%s</a></h3>' % esc(s["title"])]
    if s["sum"]:
        out.append('<p class="story__sum">%s</p>' % esc(s["sum"]))
    out.append(meta(s))
    if why:
        out.append('<p class="story__why"><span class="mark">†</span>%s</p>' % why)
    out.append("</article>")
    return "\n".join(out)


def desk_head(key):
    return ('<header class="desk__head"><h2 class="desk__title"><a href="#">%s</a></h2>'
            '<span class="desk__nos">%s</span></header>') % (DESK_NAME[key], nos(key))


def desk_stack(key, span):
    return ('<section class="cell cell--%d desk" id="%s" aria-label="%s desk">%s<div class="stack">%s</div>%s</section>'
            % (span, DESK_ANCHOR[key], DESK_NAME[key], desk_head(key),
               "\n".join(story(s) for s in DESK_STORIES[key]), desk_foot(key)))


def desk_tee(key, span):
    first, rest = DESK_STORIES[key][0], DESK_STORIES[key][1:]
    return ('<section class="cell cell--%d desk" id="%s" aria-label="%s desk">%s'
            '<div class="tee"><div class="tee__top">%s</div><div class="split">%s</div></div>%s</section>'
            % (span, DESK_ANCHOR[key], DESK_NAME[key], desk_head(key), story(first),
               "\n".join("<div>%s</div>" % story(s) for s in rest), desk_foot(key)))


def desk_band(key, spans):
    cells = "".join('<div class="cell cell--%d">%s</div>' % (sp, story(s)) for sp, s in zip(spans, DESK_STORIES[key]))
    return ('<section class="desk desk--band" id="%s" aria-label="%s desk">%s<div class="row row--band">%s</div>%s</section>'
            % (DESK_ANCHOR[key], DESK_NAME[key], desk_head(key), cells, desk_foot(key)))


# ---------------------------------------------------------------- markets (illustrative)
LEDGER_IN = [
    ("Nifty 50", "", "26,412.35", "+118.20", 0.45),
    ("Sensex", "", "86,204.11", "+371.48", 0.43),
    ("Nifty Bank", "", "59,870.60", "−92.65", -0.15),
    ("Rupee", "per dollar", "93.69", "−0.21", -0.22),
    ("India 10-year", "yield", "6.58%", "+0.07", 1.08),
]
LEDGER_OUT = [
    ("S&P 500", "", "7,318.42", "+54.07", 0.74),
    ("Nasdaq Composite", "", "24,903.16", "+312.88", 1.27),
    ("Dow Jones", "", "49,120.77", "−38.12", -0.08),
    ("Brent crude", "$ a barrel", "61.84", "−1.37", -2.17),
    ("Gold", "$ an ounce", "4,512.30", "+18.40", 0.41),
]


def pct(p):
    return ("+" if p >= 0 else "−") + "%.2f%%" % abs(p)


def ledger(caption, note, rows):
    body = []
    for name, unit, last, chg, p in rows:
        up = p >= 0
        body.append(
            '<tr><th scope="row">%s%s</th><td class="last">%s</td><td class="chg">%s</td><td class="pct">%s</td>'
            '<td class="dir">%s<span class="vh">%s</span></td><td class="trend">%s</td></tr>' % (
                esc(name), " <small>%s</small>" % unit if unit else "", last, chg, pct(p),
                ARROW_UP if up else ARROW_DOWN, "up" if up else "down", spark(name, p)))
    return ('<table class="ledger"><caption>%s<span>%s</span></caption><thead><tr><th scope="col">Instrument</th>'
            '<th scope="col">Last</th><th scope="col" class="chg">Change</th><th scope="col">Per cent</th>'
            '<th scope="col" class="dir"><span class="vh">Direction</span></th><th scope="col" class="trend">Five sessions</th>'
            '</tr></thead><tbody>%s</tbody></table>') % (caption, note, "\n".join(body))


def ear_row(name, last, p):
    return ('<div class="ear__row"><dt>%s</dt><dd class="last">%s</dd><dd class="chg">%s %s'
            '<span class="vh">%s</span></dd></div>') % (
        esc(name), last, ARROW_UP if p >= 0 else ARROW_DOWN, pct(p), "up" if p >= 0 else "down")


# ---------------------------------------------------------------- shared chrome
PROMPT = """<document>
<span class="slot">{{paste the document here}}</span>
</document>

First find the passages in the document that bear on my question. Copy them word for word inside <quotes> tags, numbered.

Then answer inside <answer> tags, citing the quote numbers you relied on. If the quotes do not settle the question, say so plainly instead of guessing.

My question: <span class="slot">{{your question}}</span>"""
PROMPT_HTML = re.sub(r"<(/?)(document|quotes|answer)>", r"&lt;\1\2&gt;", PROMPT)

THEME_BOOT = ("<script>(function(){var d=document.documentElement,t=null;"
              "try{t=new URLSearchParams(location.search).get('theme')||localStorage.getItem('first-light-theme')}catch(e){}"
              "if(t==='dark'||t==='light')d.setAttribute('data-theme',t)})();</script>")

SUN_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 12a6 6 0 0 1 12 0zM0 13.500h16v1H0zM7.500 1h1v3h-1zM1.800 4.500l.7-.7 2.100 2.100-.7.7zM14.200 4.500l-.7-.7-2.100 2.100.7.7z"/></svg>'
MOON_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M9 1a7 7 0 1 0 6 10.500A6 6 0 0 1 9 1z"/></svg>'


def head(title, desc):
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>%s</title>
<meta name="description" content="%s">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#f3eee2" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0c2136" media="(prefers-color-scheme: dark)">
%s
<link rel="stylesheet" href="styles.css">
</head>
""" % (title, desc, THEME_BOOT)


def folio(current, extra_cls=""):
    items = [("index.html", "Front Page", ""), ("#", "The Wire", '<span class="folio__count">%d</span>' % ON_WIRE),
             ("#markets-at-close" if current == "Front Page" else "index.html#markets-at-close", "Markets", ""),
             ("#", "Weekend Review", ""),
             ("#claude-desk" if current == "Front Page" else "index.html#claude-desk", "Claude Desk", ""),
             ("#", "Clippings", ""), ("#", "Back Issues", "")]
    lis = "".join('<li><a class="folio__link" href="%s"%s>%s%s</a></li>' % (
        h, ' aria-current="page"' if n == current else "", n, c) for h, n, c in items)
    return """<header class="folio%s">
<div class="page folio__in">
<button class="folio__menu" type="button" data-sheet-open aria-haspopup="dialog" aria-controls="sheet"><i aria-hidden="true"></i>Index</button>
<nav class="folio__nav" aria-label="The paper"><ul class="folio__list">%s</ul></nav>
<span class="folio__date">%s · No. %d</span>%s
<form class="search" role="search" action="#" onsubmit="return false">
<label class="vh" for="q%s">Search the paper</label>
<input class="search__input" id="q%s" type="search" placeholder="Search the paper" autocomplete="off" data-search>
<kbd class="search__key" aria-hidden="true">/</kbd>
</form>
<button class="toggle" type="button" data-theme-toggle aria-label="Switch between the morning and night editions">
<span class="in-morning">%s</span><span class="at-night">%s</span>
<span class="toggle__text"><span class="in-morning">Night edition</span><span class="at-night">Morning edition</span></span>
</button>
</div>
</header>""" % (extra_cls, lis, DATE_SHORT, EDITION_NO,
                ('<span class="folio__progress" data-progress title="Dispatches that have crossed your screen">'
                 '<b data-progress-n>0</b> of %d seen</span>' % TOTAL) if current == "Front Page" and not extra_cls else "",
                extra_cls.strip() or "main", extra_cls.strip() or "main", MOON_ICON, SUN_ICON)


def desks_nav():
    links = "".join('<li><a class="desks__link" href="#%s">%s</a></li>' % (a, n) for _, n, a in DESKS)
    return ('<nav class="desks" aria-label="Desks"><ul class="desks__list"><li class="desks__label">The desks</li>%s'
            '</ul></nav>') % links


def tabbar(current="Front"):
    tabs = [("index.html", "Front", "No. %d" % EDITION_NO), ("#", "Wire", "%d new" % ON_WIRE),
            ("#markets-at-close", "Markets", "+0.45%"), ("#", "Clippings", "3 kept"), ("#index", "Index", "10 desks")]
    out = []
    for h, n, sub in tabs:
        attr = ' aria-current="page"' if n == current else ""
        if n == "Index":
            attr += " data-sheet-open"
        out.append('<a class="tabbar__tab" href="%s"%s>%s<small>%s</small></a>' % (h, attr, n, sub))
    return '<nav class="tabbar" aria-label="The paper, at thumb reach">%s</nav>' % "".join(out)


def sheet(static=False):
    main = [("Front Page", "No. %d" % EDITION_NO, True), ("The Wire", "%d new" % ON_WIRE, False),
            ("Markets", "at close", False), ("Weekend Review", "Saturday", False),
            ("Claude Desk", "1 to try", False), ("Clippings", "3 kept", False), ("Back Issues", "since No. 1", False)]
    lis = "".join('<li><a href="#"%s><span>%s</span><small>%s</small></a></li>' % (
        ' aria-current="page"' if cur else "", n, sub) for n, sub, cur in main)
    desks = "".join('<li><a href="#%s" data-sheet-close>%s</a></li>' % (a, n) for _, n, a in DESKS)
    attrs = 'class="sheet"' if static else 'class="sheet" id="sheet" role="dialog" aria-modal="true" aria-label="Index of the paper" data-open="false"'
    return """<div %s><div class="sheet__in">
<div class="sheet__top"><span class="sheet__title">Index</span><button class="sheet__close" type="button" data-sheet-close>Close</button></div>
<label class="vh" for="q-sheet%s">Search the paper</label>
<input class="sheet__search" id="q-sheet%s" type="search" placeholder="Search the paper">
<ul class="sheet__main">%s</ul>
<p class="sheet__label">The desks</p>
<ul class="sheet__desks">%s</ul>
</div></div>""" % (attrs, "-s" if static else "", "-s" if static else "", lis, desks)


def claude_desk(full=False):
    return """<section class="notice" id="claude-desk" aria-labelledby="cd-title%(x)s">
<p class="notice__label">Claude Desk <em>one technique to try at work today</em></p>
<div class="notice__grid">
<div>
<h%(h)s class="notice__title" id="cd-title%(x)s">Quotes first, then the answer</h%(h)s>
<p class="notice__when">Reach for it when you ask a question of a long document, such as a contract, an incident report or a design spec, and need an answer you can check.</p>
<p class="notice__how">Put the document at the top of the prompt. Have Claude copy out the passages that bear on the question before it answers, and cite them by number. The quotes show you at a glance whether the answer stands on the text.</p>
<p class="notice__how">Read the quotes before the answer. A claim with no quote behind it is a claim to check yourself.</p>
</div>
<div>
<div class="prompt">
<div class="prompt__bar"><span>The prompt</span><button class="prompt__copy" type="button" data-copy="#cd-prompt%(x)s"><span data-copy-label>Copy</span></button></div>
<pre class="prompt__text" id="cd-prompt%(x)s" tabindex="0">%(prompt)s</pre>
</div>
</div>
<div class="notice__side">
<fieldset class="adopt">
<legend>Your ledger for this technique</legend>
<label class="adopt__opt"><input type="radio" name="adopt%(x)s" value="not-tried" checked><span class="adopt__box" aria-hidden="true"></span><span class="adopt__text">Not tried</span></label>
<label class="adopt__opt"><input type="radio" name="adopt%(x)s" value="tried"><span class="adopt__box" aria-hidden="true"></span><span class="adopt__text">Tried</span></label>
<label class="adopt__opt"><input type="radio" name="adopt%(x)s" value="workflow"><span class="adopt__box" aria-hidden="true"></span><span class="adopt__text">In my workflow</span></label>
</fieldset>
<p class="notice__src">From Anthropic’s guide to long-context prompting. <a href="#">Earlier techniques</a></p>
</div>
</div>
</section>""" % {"prompt": PROMPT_HTML, "x": "-full" if full else "", "h": "3" if full else "2"}


FOOT_SCRIPT = '<script src="app.js" defer></script>\n</body>\n</html>\n'

# ---------------------------------------------------------------- index.html
num = WORDS[LEAD["sourceCount"]]
lead_html = """<article class="story lead" id="no-1">
<p class="lead__kicker"><span class="no">No. 1</span><span class="lozenge" aria-hidden="true"></span><a class="story__desk" href="#world">World</a></p>
<h3 class="lead__head"><a href="#">%(title)s</a></h3>
<div class="lead__dash" aria-hidden="true"></div>
<p class="lead__deck">%(deck)s</p>
<div class="lead__body">
<p class="lead__text"><span class="leadin">The people of the Falkland Islands</span>%(rest)s <a class="jump" href="#">Continued at %(src)s</a></p>
<aside class="gloss" aria-label="Why this story leads">
<p><span class="gloss__mark">†</span><b>Why it leads.</b> Carried by %(num)s outlets, the widest coverage in this edition. Filed at %(time)s, three hours before press.</p>
<p class="story__meta"><span class="cov">%(tally)s%(outlets)s</span></p>
</aside>
</div>
</article>""" % {
    "title": esc(LEAD["title"]), "deck": esc(LEAD["deck"]),
    "rest": esc(LEAD["sum"][len("The people of the Falkland Islands"):]),
    "src": esc(LEAD["source"]), "num": num, "time": filed(LEAD["ageHours"]),
    "tally": tally(LEAD["sourceCount"]), "outlets": outlets(LEAD["sourceCount"]),
}

WHY = {
    "Anthropic has its own": "Nine outlets, the most for any AI story since yesterday’s edition.",
    "Bajaj Finance": "Nine outlets, the widest coverage on Dalal Street.",
    "Tesla’s China": "Six outlets, and the day’s largest number: down 66 per cent.",
    "US House blocks": "Four outlets, filed one hour before press.",
}


def why_for(s):
    for k, v in WHY.items():
        if k in s["title"]:
            return v
    return None


SCALE = """<aside class="scale" aria-label="How to read this paper">
<p class="scale__title">Scale of headlines</p>
<dl class="scale__bar">
%s
</dl>
<p class="scale__note">Size is earned by coverage: one stroke, one outlet. An italic headline arrived without a summary.</p>
</aside>""" % "\n".join(
    '<div class="scale__step scale__step--%s"><dt aria-hidden="true">Aa</dt><dd>%s<span>%s</span><span class="vh"> outlets</span></dd></div>' % (t, tally(n), lab)
    for t, n, lab in [("a", 9, "8+"), ("b", 6, "5–7"), ("c", 4, "3–4"), ("d", 2, "1–2")])

briefs_html = "\n".join(
    '<li id="no-%d"><span class="brief__no">%d</span><span class="brief__lead">%s.</span> <a href="#">%s</a> '
    '<span class="brief__src">%s <time>%s</time></span></li>' % (
        s["no"], s["no"], DESK_NAME[s["section"]], esc(s["title"].rstrip(".")) + ".", esc(s["source"]), filed(s["ageHours"]))
    for s in BRIEFS)

index_rows = "".join(
    '<li class="index__row"><a href="#%s"><span>%s</span><span class="dots"></span><span class="nos">%d–%d</span></a></li>' % (
        a, n, RANGES[k][0], RANGES[k][1]) for k, n, a in DESKS)

front = """<section class="row row--front" aria-labelledby="front-title">
<h2 class="vh" id="front-title">The front page</h2>
<div class="cell cell--3 cell--left">
<div class="stack">
%(left)s
</div>
%(scale)s
</div>
<div class="cell cell--6 cell--lead">
%(lead)s
<hr class="rule">
<div class="split" style="padding-top: var(--s-4)">
<div>%(u1)s</div>
<div>%(u2)s</div>
</div>
<aside class="stop" aria-label="Stop press">
<span class="stop__label">Stop press</span>
This edition closed at 05:30 and will not change. %(wire)d further items have since reached <a href="#">The Wire</a>
</aside>
</div>
<div class="cell cell--3 cell--right">
<section aria-labelledby="brief-title">
<header class="desk__head"><h2 class="desk__title" id="brief-title">In brief</h2><span class="desk__nos">%(brief_nos)s</span></header>
<ol class="briefs">
%(briefs)s
</ol>
</section>
<nav class="index" id="index" aria-labelledby="index-title">
<h2 class="index__title" id="index-title">Inside this edition</h2>
<ol>
%(index)s
</ol>
<hr class="index__rule">
<ul>
<li class="index__row index__row--also"><a href="#markets-at-close"><span>Markets at close</span><span class="dots"></span><span class="nos">ledger</span></a></li>
<li class="index__row index__row--also"><a href="#claude-desk"><span>Claude Desk</span><span class="dots"></span><span class="nos">notice</span></a></li>
</ul>
</nav>
</div>
</section>""" % {
    "left": "\n".join(story(s, desk=True, why=why_for(s)) for s in FRONT_LEFT),
    "lead": lead_html,
    "u1": story(FRONT_UNDER[0], desk=True, why=why_for(FRONT_UNDER[0])),
    "u2": story(FRONT_UNDER[1], desk=True, why=why_for(FRONT_UNDER[1])),
    "brief_nos": "Nos. %d–%d" % (BRIEFS[0]["no"], BRIEFS[-1]["no"]),
    "briefs": briefs_html, "wire": ON_WIRE, "index": index_rows, "scale": SCALE,
}

masthead = """<div class="page masthead">
<div class="masthead__top">
<aside class="ear ear--left" aria-label="Markets at close">
<p class="ear__title">Markets at close <span>Tuesday</span></p>
<dl class="ear__rows">
%(ear)s
</dl>
</aside>
<div class="nameplate">
<h1 class="nameplate__title"><a href="index.html" aria-label="First Light, front page"><span>First</span>%(vignette)s<span>Light</span></a></h1>
<p class="nameplate__motto">One finite edition, set every morning.</p>
</div>
<aside class="ear ear--right" aria-label="This edition">
<p class="ear__title">This edition <span>No. %(no)d</span></p>
<p class="ear__note"><b>%(total)d stories</b>, about %(mins)d minutes.<br>Composed at 05:30 <span class="caps">ist</span> from %(items)d items.</p>
<p class="ear__stamp">build %(stamp)s</p>
</aside>
</div>
<hr class="rule rule--thick-thin">
<div class="dateline">
<span class="dateline__vol">Vol. I &nbsp;·&nbsp; No. %(no)d <a class="dateline__back" href="#">Yesterday’s, No. %(prev)d</a></span>
<span class="dateline__date"><b>%(date)s</b> <span>&nbsp;—&nbsp; <span class="in-morning">Morning Edition</span><span class="at-night">Night Edition</span></span></span>
<span class="dateline__almanac" title="Almanac for Mumbai"><span class="almanac__place">Mumbai <span class="sep">·</span></span> First light <time>06:22</time> <span class="sep">·</span> Sunrise <time>06:44</time><span class="almanac__late"> <span class="sep">·</span> Sunset <time>18:02</time></span></span>
</div>
%(desks)s
<hr class="rule rule--thin-thick">
</div>""" % {
    "ear": "\n".join([ear_row("Nifty 50", "26,412", 0.45), ear_row("Sensex", "86,204", 0.43),
                      ear_row("S&P 500", "7,318", 0.74), ear_row("Rupee", "93.69", -0.22)]),
    "vignette": vignette(), "no": EDITION_NO, "total": TOTAL, "mins": MINUTES, "items": len(STORIES),
    "stamp": BUILD_STAMP, "date": DATE_LONG, "prev": EDITION_NO - 1, "desks": desks_nav(),
}

row_world = '<section class="row row--pair">%s%s</section>' % (desk_tee("world", 6), desk_tee("india", 6))
row_quad = '<section class="row row--quad">%s</section>' % "".join(desk_stack(k, 3) for k in ("ai", "ml", "llm", "labs"))
row_money = '<section class="row row--pair">%s%s</section>' % (desk_tee("companies", 6), desk_tee("markets", 6))
row_dalal = '<div class="band-wrap">%s</div>' % desk_band("india-markets", (5, 4, 3))
row_science = '<div class="band-wrap">%s</div>' % desk_band("science", (5, 4, 3))
row_claude = '<div class="notice-wrap">%s</div>' % claude_desk()

ledger_block = """<section id="markets-at-close" aria-label="Markets at close">
<div class="banner"><h2 class="banner__title">Markets at close</h2><span class="banner__line"></span><span class="banner__note">Declines are ruled in the second ink and marked with a falling arrow.</span></div>
<div class="ledger-wrap">
<div>%s</div>
<div>%s</div>
<p class="ledger__foot">Prototype ledger: figures here and in the almanac line are illustrative, not quotations.</p>
</div>
</section>""" % (ledger("Dalal Street", "Mumbai, Tuesday’s close", LEDGER_IN),
                 ledger("Abroad", "New York and London, Tuesday’s close", LEDGER_OUT))

endmark = """<footer class="endmark">
%s
<p class="endmark__thirty">— 30 —</p>
<p class="endmark__line">That’s the edition. %d stories, about %d minutes.</p>
<p class="endmark__next"><a href="#">Open The Wire, %d waiting</a><a href="#">Yesterday’s edition</a><a href="#">Clippings</a></p>
</footer>""" % (ORNAMENT, TOTAL, MINUTES, ON_WIRE)

colophon = """<footer class="page">
<div class="colophon">
<section><h2>Colophon</h2>
<p>Composed by machine at 05:30 <span class="caps">ist</span> and then left alone. Headline size is earned: one tally stroke for each outlet that carried the story.</p>
<p>Set in EB Garamond and Old Standard, with figures in IBM Plex Mono. The nameplate is Jacques Francois Shadow.</p></section>
<section><h2>The paper</h2>
<p><a href="index.html">Front Page</a> &nbsp; <a href="#">The Wire</a> &nbsp; <a href="#markets-at-close">Markets</a> &nbsp; <a href="#">Weekend Review</a> &nbsp; <a href="#claude-desk">Claude Desk</a> &nbsp; <a href="#">Clippings</a> &nbsp; <a href="#">Back Issues</a> &nbsp; <a href="components.html">Specimen sheet</a></p></section>
<section><h2>At the keyboard</h2>
<dl class="keys">
<dt><kbd>j</kbd> <kbd>k</kbd></dt><dd>next and previous dispatch</dd>
<dt><kbd>o</kbd></dt><dd>open the dispatch at its source</dd>
<dt><kbd>/</kbd></dt><dd>search the paper</dd>
<dt><kbd>n</kbd></dt><dd>night edition, and back</dd>
</dl></section>
</div>
</footer>"""

index_html = (head("First Light — %s" % DATE_LONG,
                   "First Light, the morning edition for %s. %d stories, about %d minutes." % (DATE_LONG, TOTAL, MINUTES))
              + "<body>\n<a class=\"skip\" href=\"#edition\">Skip to the edition</a>\n"
              + folio("Front Page") + "\n" + masthead + "\n"
              + '<main class="page edition" id="edition">\n' + front
              + '\n<hr class="rule rule--thick-thin">\n' + row_world
              + '\n<hr class="rule rule--thick-thin">\n' + row_quad
              + '\n<hr class="rule rule--thick-thin">\n' + ledger_block
              + '\n<hr class="rule rule--thick-thin">\n' + row_money
              + '\n<hr class="rule rule--thick-thin">\n' + row_dalal
              + '\n<hr class="rule rule--thick-thin">\n' + row_science
              + '\n<hr class="rule rule--thick-thin">\n' + row_claude
              + '\n<hr class="rule">\n' + endmark + "\n</main>\n" + colophon + "\n"
              + tabbar() + "\n" + sheet() + "\n" + FOOT_SCRIPT)
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(index_html)


# ---------------------------------------------------------------- components.html
def wire_row(s, unread, selected=False):
    return ('<li class="wire__row" role="option" data-unread="%s" aria-selected="%s" tabindex="%s">'
            '<span class="wire__mark" aria-hidden="true"></span><span class="vh">%s</span>'
            '<time class="wire__time">%s</time><span class="wire__tag">%s</span>'
            '<a class="wire__head" href="#" tabindex="-1">%s</a>'
            '<span class="wire__cov"><b>%d<span class="vh"> outlets</span></b>%s</span>'
            '<span class="wire__src">%s</span></li>') % (
        "true" if unread else "false", "true" if selected else "false", "0" if selected else "-1",
        "Unread." if unread else "Read.", filed(s["ageHours"])[-5:], DESK_NAME[s["section"]],
        esc(smart(s["title"])), s["sourceCount"], tally(s["sourceCount"]), esc(s["source"]))


WIRE = [(find("US House blocks"), True, False), (find("Lucid CEO"), True, True),
        (find("Locating the source"), True, False), (find("Rupee touches"), False, False),
        (find("Claude Code is accidentally"), True, False), (find("ChatGPT Plus for veterans"), False, False),
        (find("Gemini 4 Carbon is now"), False, False), (find("Collision of two trains"), False, False)]
wire_html = """<div class="wire__keys"><span><kbd>j</kbd><kbd>k</kbd> move</span><span><kbd>o</kbd> open at the source</span><span><kbd>s</kbd> clip</span><span><kbd>m</kbd> mark read</span><span><kbd>/</kbd> search</span></div>
<div class="wire">
<p class="wire__day">Wednesday 11 November <span class="data">%d items</span></p>
<ol role="listbox" aria-label="The Wire" data-wire>
%s
</ol>
</div>""" % (len(STORIES), "\n".join(wire_row(*w) for w in WIRE))

papers_html = """<div class="papers">
<article class="paper">
<p class="paper__rank" aria-label="Rank 1">1</p>
<div>
<h3 class="paper__title"><a href="#">Attention Is All You Need</a></h3>
<p class="paper__authors">Vaswani, Shazeer, Parmar, Uszkoreit, Jones, Gomez, Kaiser, Polosukhin</p>
<p class="chips"><span class="chip">Linked by 3 of your feeds</span><span class="chip">Code released</span><span class="chip">Matches “attention”</span></p>
<ol class="digest">
<li>We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.</li>
<li>Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train.</li>
<li>Our model achieves 28.4 BLEU on the WMT 2014 English-to-German translation task, improving over the existing best results, including ensembles, by over 2 BLEU.</li>
</ol>
<p class="paper__foot"><span class="data">arXiv:1706.03762</span><a href="#">Read the abstract</a><a href="#">Clip</a></p>
</div>
</article>
<article class="paper">
<p class="paper__rank" aria-label="Rank 2">2</p>
<div>
<h3 class="paper__title"><a href="#">Deep Residual Learning for Image Recognition</a></h3>
<p class="paper__authors">He, Zhang, Ren, Sun</p>
<p class="chips"><span class="chip">Linked by 2 of your feeds</span><span class="chip">Matches “depth”</span></p>
<ol class="digest">
<li>We present a residual learning framework to ease the training of networks that are substantially deeper than those used previously.</li>
<li>We explicitly reformulate the layers as learning residual functions with reference to the layer inputs, instead of learning unreferenced functions.</li>
<li>An ensemble of these residual nets achieves 3.57% error on the ImageNet test set.</li>
</ol>
<p class="paper__foot"><span class="data">arXiv:1512.03385</span><a href="#">Read the abstract</a><a href="#">Clip</a></p>
</div>
</article>
</div>
<hr class="rule">"""

rupee, bond = find("Rupee touches"), find("India bonds slip")
search_html = """<div class="finder" role="search">
<div class="finder__field">
<label class="finder__label" for="finder">Search the paper</label>
<input class="finder__input" id="finder" type="search" value="rupee" autocomplete="off">
<kbd>esc</kbd>
</div>
<div class="finder__also" role="group" aria-label="Also searching">
<span class="finder__also-label">Also searching:</span>
<button class="chip" type="button" aria-pressed="true">INR</button>
<button class="chip" type="button" aria-pressed="true">USD/INR</button>
<button class="chip" type="button" aria-pressed="true">forex</button>
<button class="chip" type="button" aria-pressed="false">RBI</button>
</div>
<p class="finder__count">Two of the matches in this edition and on The Wire. Strike a chip to drop that term.</p>
<div class="hit"><span class="hit__where">Dalal Street</span><a href="#"><mark>Rupee</mark> touches strongest since April as foreign inflows offset firm dollar</a><span class="hit__src">%s, %s</span></div>
<div class="hit"><span class="hit__where">Dalal Street</span><a href="#">India bonds slip as Treasury rout offsets oil slide</a><span class="hit__src">%s, %s</span></div>
</div>""" % (rupee["source"], filed(rupee["ageHours"]), bond["source"], filed(bond["ageHours"]))

tier_samples = [("lead", LEAD), ("a", DESK_STORIES["ml"][0]), ("b", DESK_STORIES["ai"][0]),
                ("c", DESK_STORIES["ai"][1]), ("d", DESK_STORIES["markets"][2]), ("a", DESK_STORIES["science"][0])]
tiers_html = []
for t, s in tier_samples:
    if t == "lead":
        tiers_html.append('<article class="story"><p class="story__kicker"><span class="no">Lead</span><span class="story__desk">the widest coverage of the night</span></p>'
                          '<h3 class="lead__head" style="margin-bottom: var(--s-2)"><a href="#">%s</a></h3>%s</article>' % (esc(s["title"]), meta(s)))
    else:
        tiers_html.append(story(s))
tiers_html = '<div class="tiers">%s</div>' % "\n".join(tiers_html)

phone_front = """<div class="phone-wrap"><div class="phone" role="img" aria-label="Phone layout: top bar, edition, tab bar">
%s
<div class="phone__screen">
<p class="nameplate__title" style="font-size: 2.6rem; margin-top: var(--s-3)"><span>First</span>%s<span>Light</span></p>
<hr class="rule rule--thick-thin" style="margin-top: var(--s-3)">
<p class="dateline__date" style="padding: var(--s-2) 0; text-align:center"><b>%s</b></p>
<hr class="rule">
<div class="lead" style="padding-top: var(--s-3)">
<p class="lead__kicker"><span class="no">No. 1</span><span class="lozenge"></span><span class="story__desk">World</span></p>
<p class="lead__head" style="font-size: 1.75rem; line-height: 2rem">%s</p>
<div class="lead__dash"></div>
<p class="lead__deck" style="font-size: 1.0625rem; line-height: 1.375rem">%s</p>
</div>
</div>
%s
</div><p>Phone. The folio shrinks to Index, date and the edition switch. Five tabs sit at thumb reach, each printing its own live figure.</p></div>""" % (
    folio("Front Page", " folio--phone"), vignette(), DATE_LONG, esc(LEAD["title"]), esc(LEAD["deck"]), tabbar())
phone_sheet = """<div class="phone-wrap"><div class="phone" role="img" aria-label="Phone layout: the index sheet">
%s
</div><p>The Index sheet. Every destination on one leaf, the ten desks in two columns, search at the top.</p></div>""" % sheet(static=True)


def plate(no, title, notes, body, wide=False):
    return """<section class="plate%s" aria-labelledby="plate-%s">
<div class="plate__note"><p class="plate__no">Plate %s</p><h2 class="plate__title" id="plate-%s">%s</h2>%s</div>
<div class="plate__body">%s</div>
</section>
<hr class="rule rule--hair">""" % (" plate--wide" if wide else "", no, no, no, title, "".join("<p>%s</p>" % n for n in notes), body)


type_rows = [
    ("--fs-nameplate", '<span style="font-family:var(--font-nameplate);font-size:3.5rem;line-height:1">First Light</span>'),
    ("--fs-lead 52/56", '<span class="lead__head" style="display:block">Falkland Islanders face ‘devastating consequences’</span>'),
    ("--fs-a 31/36", '<span style="font-family:var(--font-head);font-weight:700;font-size:var(--fs-a);line-height:var(--lh-a)">Genie 4: A new generation of world simulation</span>'),
    ("--fs-b 25/28", '<span style="font-family:var(--font-head);font-weight:700;font-size:var(--fs-b);line-height:var(--lh-b)">Ukraine’s fiber-optic drones get squeezed by AI data center demand</span>'),
    ("--fs-c 21/24", '<span style="font-family:var(--font-head);font-weight:700;font-size:var(--fs-c);line-height:var(--lh-c)">Grok Build coding agent leaks oodles of confidential info</span>'),
    ("--fs-d 18/24", '<span style="font-family:var(--font-head);font-size:var(--fs-d);line-height:var(--lh-d)">Baird downgrades Nvidia on CEO Huang worries, AI uncertainty</span>'),
    ("--fs-deck 22/28", '<span class="lead__deck" style="display:block;margin:0;max-width:none">Countries clash over Sea Lion project as Hamburg tribunal risks deepening sovereignty dispute</span>'),
    ("--fs-text 18/24", 'Only 8,817 of the cars Tesla delivered from Giga Shanghai in October went to Chinese buyers. That’s down 66% from a year ago and Tesla’s worst month in China since July 2022. <i>Old-style figures in running text: 1234567890.</i>'),
    ("--fs-caps 17/20", '<span class="caps">The Guardian · Nine outlets · Dalal Street · Frontier Labs</span>'),
    ("--fs-data 13/20", '<span class="data">26,412.35 &nbsp; +118.20 &nbsp; +0.45% &nbsp; 02:30 &nbsp; build 2026.11.11-0530</span>'),
]
type_html = '<dl class="specimen-type">%s</dl>' % "".join("<dt>%s</dt><dd>%s</dd>" % r for r in type_rows)
swatches = "".join('<div class="swatch"><div class="swatch__chip" style="background:var(%s)"></div><div class="swatch__name">%s<br>%s</div></div>' % (v, v, n)
                   for v, n in [("--paper", "newsprint"), ("--paper-deep", "tint for boxes"), ("--paper-lift", "raised"),
                                ("--ink", "first ink"), ("--ink-soft", "summaries"), ("--ink-faint", "meta"),
                                ("--hair", "hairlines"), ("--rule", "rules"), ("--spot", "second ink")])
tallies = "".join('<span>%s%s</span>' % (tally(n), outlets(n)) for n in (1, 2, 3, 4, 5, 6, 9, 12))
ladder = "".join('<div><i style="height:var(--s-%d)"></i><span>s-%d</span></div>' % (i, i) for i in range(1, 10))
system_html = """<p class="plate__sub">Faces and sizes</p>%s
<p class="plate__sub">Two inks</p><div class="swatches">%s</div>
<p class="plate__sub">Coverage tally</p><p class="tallies">%s</p>
<p class="plate__sub">Rules and ornament</p>
<hr class="rule rule--thick-thin" style="margin: var(--s-3) 0"><hr class="rule" style="margin: var(--s-3) 0"><hr class="rule rule--hair" style="margin: var(--s-3) 0"><hr class="rule rule--thin-thick" style="margin: var(--s-3) 0 var(--s-4)">%s
<p class="plate__sub">Spacing ladder, a 24px line quartered</p><div class="ladder">%s</div>""" % (type_html, swatches, tallies, ORNAMENT, ladder)

ROOMS = [
    ("Front Page", "The morning edition, frozen at 05:30. %d stories, then — 30 —." % TOTAL, "Folio line", "Tab"),
    ("The Wire", "Everything since press, newest first. %d waiting." % ON_WIRE, "Folio line", "Tab"),
    ("The desks", "One section each, World to Science, every story ranked by coverage.", "Desks line; desk heads and feet", "Index sheet"),
    ("Markets", "The ledger at close, Dalal Street and abroad.", "Folio line; left ear", "Tab"),
    ("Weekend Review", "The week’s papers, ranked, on Saturday.", "Folio line", "Index sheet"),
    ("Claude Desk", "One technique a day, and your ledger of the ones tried.", "Folio line", "Index sheet"),
    ("Clippings", "What you kept.", "Folio line", "Tab"),
    ("Back Issues", "Every edition since No. 1.", "Folio line; dateline", "Index sheet"),
    ("Search", "The edition and The Wire together.", "<kbd>/</kbd> from anywhere", "Top of the Index sheet"),
]
rooms_html = ('<table class="rooms"><caption>The rooms of the paper <span>and the way into each</span></caption>'
              '<thead><tr><th scope="col">Room</th><th scope="col">Holds</th><th scope="col">Laptop</th><th scope="col">Phone</th></tr></thead><tbody>%s</tbody></table>'
              % "".join('<tr><th scope="row">%s</th><td>%s</td><td>%s</td><td>%s</td></tr>' % r for r in ROOMS))

nav_html = """<p class="plate__sub only-laptop">Laptop: the folio line and the desks line</p>
<div class="spec-nav only-laptop">%s<div style="padding: 0 var(--s-4)">%s</div></div>
<p class="plate__sub">Phone and tablet</p>
<div class="phones">%s%s<div class="rooms-wrap">%s</div></div>""" % (folio("Front Page", " folio--spec"), desks_nav(), phone_front, phone_sheet, rooms_html)

plates = [
    plate("I", "Navigation", [
        "The folio line holds the paper’s seven rooms and stays at the top of the window. The current room is underlined in the second ink.",
        "The desks line sits under the dateline, between rules, and jumps within the edition.",
        "Keys: <kbd>j</kbd> and <kbd>k</kbd> step through the dispatches, <kbd>/</kbd> searches, <kbd>n</kbd> switches to the night edition. Below 1024px the rooms move to a tab bar and the Index sheet."], nav_html, wide=True),
    plate("II", "Headline tiers", [
        "Size is earned by coverage. The lead is the widest-covered story; then 8 or more outlets, 5 to 7, 3 to 4, and 1 to 2.",
        "A story that arrives without a summary is set in italic and stands alone.",
        "Tokens <code>--fs-lead</code> to <code>--fs-d</code>."], tiers_html),
    plate("III", "The Wire", [
        "One line per item: unread mark, hour filed, desk, headline, tally with count, source. A long headline is cut at the line and opens in full under the cursor.",
        "Unread items carry a filled lozenge and a heavier headline. The keyboard cursor is a bar of the second ink.",
        "Try <kbd>j</kbd> and <kbd>k</kbd> here."], wire_html),
    plate("IV", "Markets ledger", [
        "Tabular lining figures in the data face. The margin line is ruled in the second ink, as in a cash book.",
        "Direction is given three ways: sign, arrow and a word for screen readers. Colour only confirms it.",
        "Figures are illustrative."],
          '<div class="ledger-wrap" style="padding-top:0">\n<div>%s</div>\n</div>' % (
              ledger("Dalal Street", "Mumbai, Tuesday’s close", LEDGER_IN + LEDGER_OUT[3:]))),
    plate("V", "Weekend Review", [
        "A ranked paper: numeral, title, authors, the reasons it surfaced, and three sentences lifted whole from the abstract.",
        "Specimen set with two classic papers. The chips are illustrative."], papers_html),
    plate("VI", "Claude Desk", [
        "A notice box in a double rule. The prompt is set in the data face, with the slots to fill in the second ink.",
        "The reader keeps a ledger for each technique: not tried, tried, in my workflow."], claude_desk(full=True)),
    plate("VII", "Search", [
        "The query is set large, in italic. Under it the paper says which other terms it is also searching; strike a chip to drop one.",
        "Matched words are underlined in the second ink, not highlighted."], search_html),
    plate("VIII", "Type, inks, rules", [
        "Every colour, size and gap is a custom property at the top of <code>styles.css</code>.",
        "Switch to the night edition: the same tokens are redrawn as a blueprint, with lamp amber as the second ink."], system_html),
]

components_html = (head("First Light — Specimen sheet", "The parts of First Light, set in the Gazette style.")
                   + "<body>\n<a class=\"skip\" href=\"#sheet-main\">Skip to the specimens</a>\n"
                   + folio("Specimen") + "\n"
                   + '<main class="page" id="sheet-main">\n<header class="sheet-head">'
                     '<p class="sheet-head__over">First Light &nbsp;·&nbsp; The Gazette</p>'
                     '<h1 class="sheet-head__title">Specimen Sheet</h1>'
                     '<p class="sheet-head__sub">The parts the other rooms of the paper are built from, shown with this morning’s stories.</p></header>\n'
                     '<hr class="rule rule--thick-thin">\n'
                   + "\n".join(plates) + "\n</main>\n" + colophon + "\n" + FOOT_SCRIPT)
open(os.path.join(HERE, "components.html"), "w", encoding="utf-8").write(components_html)

print("index.html: %d stories, %d words, about %d minutes, %d on the wire" % (TOTAL, WORDCOUNT, MINUTES, ON_WIRE))
