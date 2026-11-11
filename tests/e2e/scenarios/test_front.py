"""Front Page integrity: the page shows exactly the edition file, set by coverage."""

import re

from tests.e2e.scenarios import support as S

STORY_FACTS = (
    "[...document.querySelectorAll('#view [data-story]')].map((el) => {"
    " const hl = el.querySelector('[class*=\"hl-\"]');"
    " const step = hl ? [...hl.classList].find((c) => /^hl-\\d$/.test(c)) : null;"
    " const ctx = el.closest('.seconds__row') ? (el.closest('.seconds__row') === document.querySelector('.seconds__row') && el.closest('.seconds__wide') ? 'first' : 'seconds')"
    "   : el.closest('.desk__first') ? 'wide' : el.closest('.desk__stack') ? 'stack' : el.closest('.desk--12') ? 'rail'"
    "   : el.closest('.desk--3') ? 'narrow' : el.closest('.lead') || el.matches('.lead') ? 'lead' : el.closest('.briefs') ? 'brief' : 'other';"
    " return {id: el.dataset.story, outlets: el.dataset.outlets || null, step, ctx}; })"
)


def test_story_count_and_uniqueness(page, base_url):
    S.open_route(page, base_url, "/")
    expected = S.edition_stories()
    facts = page.eval(STORY_FACTS)
    ids = [fact["id"] for fact in facts]
    assert len(ids) == len(expected), "page shows {0} stories, the edition has {1}".format(len(ids), len(expected))
    duplicates = sorted(set(i for i in ids if ids.count(i) > 1))
    assert not duplicates, "stories set twice: {0}".format(duplicates)
    assert set(ids) == set(s["id"] for s in expected), "page and edition list different stories"
    page.note("{0} stories, all distinct".format(len(ids)))


def test_lead_numeral_and_why(page, base_url):
    S.open_route(page, base_url, "/")
    lead = S.edition()["lead"]
    assert page.attr(".lead", "data-story") == lead["id"]
    assert S.text_of(page, ".lead .cov-xl__n") == str(lead["sourceCount"])
    shown = S.tokenize(S.text_of(page, ".lead .lead__hl"))
    assert shown == S.tokenize(lead["title"]), (shown, lead["title"])
    assert page.eval("document.querySelector('.lead__hl a').href") == page.eval("(u) => new URL(u).href", lead["url"])
    if lead.get("why"):
        why = S.text_of(page, ".lead__why")
        for reason in lead["why"]:
            assert reason in why, (reason, why)


def test_headline_links_leave_safely(page, base_url):
    S.open_route(page, base_url, "/")
    links = page.eval(
        "[...document.querySelectorAll('#view [data-hl], #view a.readon[target]')].map((a) => ({href: a.getAttribute('href'), target: a.target, rel: a.rel}))"
    )
    assert len(links) >= len(S.edition_stories()), len(links)
    for link in links:
        assert link["href"].startswith(("https://", "http://")), link
        assert link["target"] == "_blank", link
        rel = link["rel"].split()
        assert "noopener" in rel and "noreferrer" in rel, link


def test_headline_sizes_follow_coverage(page, base_url):
    S.open_route(page, base_url, "/")
    by_id = {s["id"]: s for s in S.edition_stories()}
    expected_step = {"seconds": S.FRONT_STEP, "narrow": S.DESK_STEP, "stack": S.DESK_STEP, "wide": S.WIDE_STEP, "rail": S.RAIL_STEP}
    checked = 0
    for fact in page.eval(STORY_FACTS):
        story = by_id[fact["id"]]
        if fact["outlets"] is not None:
            assert fact["outlets"] == str(story["sourceCount"]), fact
        if fact["ctx"] == "first":
            assert fact["step"] == "hl-6", fact
        elif fact["ctx"] in expected_step:
            want = expected_step[fact["ctx"]][S.tier(story["sourceCount"])]
            assert fact["step"] == want, "{0} story with {1} outlets set at {2}, expected {3}".format(
                fact["ctx"], story["sourceCount"], fact["step"], want)
            checked += 1
    assert checked >= 10, "only {0} desk/seconds stories checked".format(checked)
    # within one kind of slot, more outlets never means a smaller headline
    facts = [f for f in page.eval(STORY_FACTS) if f["ctx"] in expected_step]
    for a in facts:
        for b in facts:
            if a["ctx"] == b["ctx"] and by_id[a["id"]]["sourceCount"] > by_id[b["id"]]["sourceCount"]:
                assert int(a["step"][3:]) >= int(b["step"][3:]), (a, b)


def test_end_mark_and_masthead_agree(page, base_url):
    S.open_route(page, base_url, "/")
    ed = S.edition()
    count = len(S.edition_stories())
    assert S.text_of(page, ".end__mark") == "— 30 —"
    end = S.text_of(page, ".end__line")
    assert "{0} stories".format(count) in end, end
    folio = S.text_of(page, ".folio")
    assert "No. {0} · {1} stories".format(ed["number"], count) in folio, folio
    assert page.attr(".flap", "aria-label") == str(ed["number"])
    assert S.text_of(page, ".flap") == str(ed["number"])
    assert "{0} stories".format(count) in S.text_of(page, ".edition__facts").lower()
    assert "No. {0}".format(ed["number"]) in page.title()
    assert page.eval("document.querySelector('#mast h1')?.textContent.trim()") == "First Light"


def test_briefs_and_desks_match_the_file(page, base_url):
    S.open_route(page, base_url, "/")
    ed = S.edition()
    briefs = page.eval("[...document.querySelectorAll('.briefs [data-story]')].map((e) => e.dataset.story)")
    assert sorted(briefs) == sorted(s["id"] for s in ed.get("briefs") or []), briefs
    assert S.text_of(page, ".briefs__head .label") == "{0} {1}".format(len(briefs), "line" if len(briefs) == 1 else "lines")
    desks = page.eval("[...document.querySelectorAll('section.desk .desk__name')].map((e) => e.textContent.trim())")
    names = {s["id"]: s["name"] for s in S.manifest()["sections"]}
    want = [names.get(s["id"], s["id"]) for s in ed["sections"] if s.get("stories")]
    assert desks == want, (desks, want)
    for section in ed["sections"]:
        if section.get("stories"):
            assert page.exists("section.desk a[href='#/s/{0}']".format(section["id"])), section["id"]


def test_markets_tape_and_claude_block(page, base_url):
    S.open_route(page, base_url, "/")
    ed = S.edition()
    if ed.get("markets") and ed["markets"].get("quotes"):
        quotes = page.count(".tape .quote")
        assert quotes == min(6, len(ed["markets"]["quotes"])), quotes
        for change in S.texts_of(page, ".tape .quote__chg"):
            assert re.search(r"[+−]\d|^\d", change) or change.startswith("–"), change
    card = ed.get("claude") or {}
    if card.get("kind") == "feature":
        book = S.playbook()
        feature = next((f for f in book["features"] if f["id"] == card.get("featureId")), book["features"][0])
        assert page.attr(".claude__title a", "href") == "#/claude/feature/" + feature["id"]
    elif card.get("kind") == "update" and card.get("update"):
        assert card["update"]["title"][:15] in S.text_of(page, ".claude__title").replace("’", "'")


def test_story_without_summary_looks_intended(page, base_url):
    S.open_route(page, base_url, "/")
    bare = page.eval("[...document.querySelectorAll('article.story--bare')].map((e) => !!e.querySelector('.story__src'))")
    assert all(bare), "a story without a summary has no source line"
    page.note("{0} bare stories on this edition".format(len(bare)))


def test_clicking_a_headline_marks_it_read(page, base_url):
    S.open_route(page, base_url, "/")
    page.eval("window.open = () => null")
    story_id = page.eval("document.querySelector('.seconds article.story').dataset.story")
    # a modified click target: suppress the new tab, keep the app's own click handler
    page.eval("document.querySelector('.seconds article.story [data-hl]').addEventListener('click', (e) => e.preventDefault())")
    page.click(".seconds article.story [data-hl]")
    page.wait_for(js="(JSON.parse(localStorage.getItem('fl.read') || '{{}}'))[{0!r}] > 0".format(story_id))
    assert "is-read" in page.attr(".seconds article.story", "class")
    S.reload(page)
    assert "is-read" in page.attr("article.story[data-story='{0}']".format(story_id), "class")


def test_wire_new_counts_on_a_first_visit(page, base_url):
    import calendar
    import time as _time

    def ms(value):
        return calendar.timegm(_time.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")) * 1000

    ed = S.edition()
    since = ms(ed["generatedAt"])
    fresh = len([s for s in S.latest()["stories"] if ms(s.get("updatedAt") or s["publishedAt"]) > since])
    S.open_route(page, base_url, "/")
    link = S.text_of(page, ".briefs__wire a")
    if fresh:
        assert "The Wire · {0} new".format(fresh) in link, (link, fresh)
        page.wait_for(".nav__main a[href='#/wire'] .nav__count")
        assert S.text_of(page, ".nav__main a[href='#/wire'] .nav__count") == "{0} new".format(min(999, fresh))
    else:
        assert link == "The Wire", link


def test_x_and_s_work_on_the_front_page(page, base_url):
    S.open_route(page, base_url, "/")
    page.press("j")
    story = page.eval("document.activeElement.closest('[data-story]').dataset.story")
    page.press("x")
    assert story in (S.storage_json(page, "fl.read") or {})
    page.press("s")
    page.wait_for(".nav__main a[href='#/clippings'] .nav__count")
    assert "story:" + story in S.storage_json(page, "fl.saved")
