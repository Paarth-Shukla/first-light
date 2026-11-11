"""Robustness: missing files, empty fields, hostile remote text, and the PWA files."""

import copy
import json

from tests.e2e.run import allow_errors
from tests.e2e.scenarios import support as S

PWNED = "window.__pwned"


def open_variant(page, site, route):
    S.hook(page)
    page.goto("{0}/#{1}".format(site.url, route))
    S.wait_ready(page)


def visit(page, route):
    S.go(page, route)
    return S.text_of(page, "#view")


@allow_errors("manifest.json", "data/latest.json")
def test_no_manifest_shows_nothing_built(page, base_url):
    with S.SiteVariant(remove=["data"], page=page) as site:
        page.goto(site.url + "/#/")
        page.wait_for_text("#view .notice", "There is no edition to show.")
        assert "Nothing has been built yet" in page.title()
        assert "python3 -m pipeline all" in S.text_of(page, ".notice__body")
        assert page.exists("#mast .nameplate"), "the masthead is missing"
        page.press("w")
        page.press("k", ["Meta"])
        page.wait_for("#palette:not([hidden])")
        page.press("Escape")
        page.sync()
        assert page.errors == [], page.errors


@allow_errors("markets.json")
def test_markets_missing(page, base_url):
    with S.SiteVariant(remove=["data/markets.json"], page=page) as site:
        open_variant(page, site, "/markets")
        assert "No market figures yet." in S.text_of(page, ".notice")
        assert "Markets" in page.title()
        visit(page, "/")
        assert page.count("#view [data-story]") == len(S.edition_stories())
        story = S.latest()["stories"][0]
        visit(page, "/story/{0}?d={1}".format(story["id"], story["day"]))
        page.wait_for(".detail")
        visit(page, "/wire")
        assert page.count(".wire__row[data-story]") > 0
        page.sync()
        assert page.errors == []


@allow_errors("claude/")
def test_claude_files_missing(page, base_url):
    with S.SiteVariant(remove=["data/claude/playbook.json", "data/claude/updates.json"], page=page) as site:
        open_variant(page, site, "/claude")
        assert "has not been built yet" in S.text_of(page, ".notice")
        assert "not been compiled" in visit(page, "/claude/playbook")
        assert "No updates fetched yet." in visit(page, "/claude/updates")
        assert "No recipes have been compiled yet." in visit(page, "/claude/recipes")
        assert "not in the playbook" in visit(page, "/claude/feature/" + S.playbook()["features"][0]["id"])
        visit(page, "/")
        assert page.count("#view [data-story]") == len(S.edition_stories())
        assert page.exists("footer.end")
        page.sync()
        assert page.errors == []


@allow_errors("weekend/")
def test_weekend_missing(page, base_url):
    with S.SiteVariant(remove=["data/weekend"], page=page) as site:
        open_variant(page, site, "/weekend")
        assert "has not been set yet" in S.text_of(page, ".notice")
        assert "There is no Weekend Review for 2026-W01" in visit(page, "/weekend/2026-W01")
        visit(page, "/archive")
        assert page.count("ol.rows a[href^='#/edition/']") == len(S.data("editions/index.json")["editions"])
        visit(page, "/")
        assert page.exists(".lead")
        page.sync()
        assert page.errors == []


@allow_errors("search/")
def test_search_index_missing(page, base_url):
    with S.SiteVariant(remove=["data/search"], page=page) as site:
        open_variant(page, site, "/search?q=markets")
        page.wait_for(".hits__foot .notice")
        text = S.text_of(page, ".hits__foot .notice")
        assert "Search could not start" in text, "a missing index is reported as an empty result: " + text
        # the rest of the site does not need the index
        desk = S.manifest()["sections"][0]
        visit(page, "/s/" + desk["id"])
        assert desk["name"] in page.title()
        story = S.latest()["stories"][0]
        visit(page, "/story/{0}?d={1}".format(story["id"], story["day"]))
        page.wait_for(".detail")
        visit(page, "/wire")
        assert page.count(".wire__row[data-story]") > 0
        page.sync()
        assert page.errors == []


@allow_errors("latest.json")
def test_latest_missing(page, base_url):
    with S.SiteVariant(remove=["data/latest.json"], page=page) as site:
        open_variant(page, site, "/wire")
        assert "The wire is silent." in S.text_of(page, ".notice")
        visit(page, "/")
        assert page.count("#view [data-story]") == len(S.edition_stories())
        page.sync()
        assert page.errors == []


def hostile_edition():
    ed = copy.deepcopy(S.edition())
    lead = ed["lead"]
    lead["title"] = '<img src=x onerror="{0}=1">Lead &amp; <b>bold</b> <script>{0}=2</script>'.format(PWNED)
    lead["summary"] = 'Tom &lt;Jr&gt; said "<a href=javascript:{0}=3>click</a>". Second sentence here.'.format(PWNED)
    lead["url"] = "javascript:{0}=4".format(PWNED)
    lead["sources"][0]["name"] = '<i onmouseover="{0}=5">Outlet</i>'.format(PWNED)
    bare = ed["front"][0]
    bare["summary"] = ""
    bare["image"] = None
    ed["briefs"][0]["url"] = " JaVaScRiPt:{0}=6".format(PWNED)
    return ed


def test_hostile_text_is_text(page, base_url):
    ed = hostile_edition()
    path = "data/editions/{0}.json".format(ed["date"])
    with S.SiteVariant(replace={path: ed}, page=page) as site:
        open_variant(page, site, "/")
        assert page.eval("typeof " + PWNED) == "undefined"
        assert page.count(".lead__hl img, .lead__hl b, .lead__hl script, .lead i, .lead a[href^='javascript'] ") == 0
        title = S.text_of(page, ".lead__hl")
        assert "<img src=x" in title and "<script>" in title and "&amp;" in title, title
        assert "<a href=javascript" in S.text_of(page, ".lead") or "click" not in S.text_of(page, ".lead")
        hrefs = page.eval("[...document.querySelectorAll('a[href]')].map((a) => a.getAttribute('href'))")
        bad = [h for h in hrefs if h.strip().lower().startswith("javascript")]
        assert not bad, bad
        assert page.attr(".lead__hl a", "href") == "#/"
        assert page.attr(".briefs li:first-child a[data-hl]", "href") in ("#/",) or \
            page.eval("[...document.querySelectorAll('.briefs a[data-hl]')].every((a) => /^https?:/.test(a.getAttribute('href')) || a.getAttribute('href') === '#/')")
        page.hover(".lead__kicker")
        page.click(".lead__hl a")
        page.sync()
        assert page.eval("typeof " + PWNED) == "undefined"
        # the story without summary or image still looks intended
        bare = ".seconds article.story[data-story='{0}']".format(ed["front"][0]["id"])
        assert "story--bare" in page.attr(bare, "class")
        assert page.exists(bare + " .story__src")
        assert page.count(bare + " img") == 0


def test_hostile_story_page_and_search(page, base_url):
    hot = copy.deepcopy(S.latest())
    story = hot["stories"][0]
    story["title"] = "<svg onload={0}=7>Story</svg> &lt;tag&gt;".format(PWNED)
    story["url"] = "javascript:{0}=8".format(PWNED)
    story["summary"] = ""
    story["image"] = ""
    for source in story["sources"]:
        source["url"] = "javascript:{0}=9".format(PWNED)
        source["title"] = "<b>{0}</b>".format(source.get("title") or "x")
    static = list(S.data("search/" + S.data("search/manifest.json")["static"]))
    static.append({"i": "term:zzxss", "k": "term", "t": "Zzxss <img src=x onerror={0}=10>".format(PWNED), "s": "<b>held</b> &amp; kept",
                   "c": "glossary", "e": [], "o": None, "n": None, "d": None, "u": "javascript:{0}=11".format(PWNED), "x": None})
    replace = {"data/latest.json": hot, "data/search/" + S.data("search/manifest.json")["static"]: static}
    with S.SiteVariant(replace=replace, page=page) as site:
        open_variant(page, site, "/story/{0}?d={1}".format(story["id"], story["day"]))
        page.wait_for(".detail")
        assert "<svg onload" in S.text_of(page, ".detail h2")
        assert page.count(".detail svg[onload], .detail h2 b, .detail .row__title b") == 0
        assert "<b>" in S.text_of(page, ".detail .row__title")
        hrefs = page.eval("[...document.querySelectorAll('#view a[href]')].map((a) => a.getAttribute('href'))")
        assert not [h for h in hrefs if h.lower().startswith("javascript")], hrefs
        visit(page, "/wire")
        assert page.eval("[...document.querySelectorAll('.wire a[href]')].every((a) => !/^javascript/i.test(a.getAttribute('href')))")
        visit(page, "/search?q=zzxss")
        page.wait_for("ol.hits li.hit")
        assert "<img src=x" in S.text_of(page, "ol.hits")
        assert page.count("ol.hits img") == 0
        assert page.attr("ol.hits li.hit .story__hl", "href") == "#/"
        page.sync()
        assert page.eval("typeof " + PWNED) == "undefined"


def test_story_with_empty_fields_renders(page, base_url):
    hot = copy.deepcopy(S.latest())
    story = hot["stories"][0]
    story.update({"summary": "", "image": None, "why": [], "entities": [], "tickers": [], "thread": None, "signals": {}, "sources": []})
    with S.SiteVariant(replace={"data/latest.json": hot}, page=page) as site:
        open_variant(page, site, "/story/{0}?d={1}".format(story["id"], story["day"]))
        page.wait_for(".detail")
        assert page.eval("document.querySelector('h1').textContent") == "Who carried it"
        assert page.count(".signals tr") == 6
        visit(page, "/wire")
        assert page.exists(".wire__row[data-story='{0}']".format(story["id"]))
        page.sync()
        assert page.errors == []


def test_service_worker_and_web_manifest_are_served(page, base_url):
    S.open_route(page, base_url, "/")
    sw = S.fetch_text(page, "sw.js")
    assert sw["status"] == 200 and "javascript" in (sw["type"] or ""), sw["type"]
    assert page.eval("(t) => { try { new Function(t); return true; } catch (e) { return String(e); } }", sw["text"]) is True
    assert "addEventListener('fetch'" in sw["text"]
    manifest = S.fetch_text(page, "manifest.webmanifest")
    assert manifest["status"] == 200
    parsed = json.loads(manifest["text"])
    assert parsed["name"] == "First Light" and parsed["start_url"] and parsed["icons"], parsed
    for icon in parsed["icons"]:
        served = S.fetch_text(page, icon["src"])
        assert served["status"] == 200 and "svg" in served["type"], (icon, served["type"])
    assert page.attr("link[rel=manifest]", "href") == "manifest.webmanifest"
    # the service worker only registers on https; on this http test server it must not
    assert page.eval("navigator.serviceWorker ? navigator.serviceWorker.getRegistrations().then((r) => r.length) : 0") == 0
