"""Search: widening chips, operators, spelling, highlighting, tabs, sort, URL state."""

import collections
import functools
import re
import time
from urllib.parse import quote

from tests.e2e.run import run_js_tests
from tests.e2e.scenarios import support as S

HITS = "ol.hits li.hit"


# -- what the data says ------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def docs():
    seen = collections.OrderedDict()
    for doc in S.search_docs():
        if doc and doc["i"] not in seen:
            seen[doc["i"]] = doc
    return seen


@functools.lru_cache(maxsize=1)
def busy_entity():
    """A one-word lexicon entity whose widening (aliases, related names) adds docs that the
    name alone would not find, so dropping a chip has something to remove."""
    lex = S.lexicon()["entities"]
    counts = collections.Counter(e for d in docs().values() for e in (d.get("e") or []))
    texts = {i: set(S.tokenize("{0} {1} {2}".format(d["t"], d.get("s") or "", d.get("o") or ""))) for i, d in docs().items()}
    for entity_id, _ in counts.most_common(60):
        entity = lex.get(entity_id)
        if not entity or len(S.tokenize(entity["name"])) != 1:
            continue
        word = S.tokenize(entity["name"])[0]
        direct = set(i for i, d in docs().items() if word in texts[i] or entity_id in (d.get("e") or []))
        extra = set()
        for i, d in docs().items():
            if i in direct:
                continue
            if set(entity.get("related") or []) & set(d.get("e") or []):
                extra.add(i)
            for alias in entity.get("aliases") or []:
                tokens = S.tokenize(alias)
                if tokens and tokens != [word] and set(tokens) <= texts[i]:
                    extra.add(i)
        if len(extra) >= 3:
            return entity_id, entity["name"]
    raise AssertionError("no widening entity in the lexicon")


def click_until(page, container, text, done_js, tries=3):
    """Click a control on the search page until `done_js` holds. A background repaint (an older
    month of the archive arriving) can replace the control between mouse press and release."""
    for _ in range(tries):
        repainted(page, lambda: S.click_button(page, container, text))
        try:
            page.wait_for(js=done_js, timeout=2)
            settle(page)
            return
        except Exception:
            continue
    raise AssertionError("clicking {0!r} in {1} never led to {2}".format(text, container, done_js))


def repainted(page, action):
    """Run `action` and wait until the search page has painted a new result."""
    page.eval("document.querySelector('#find-count').append(Object.assign(document.createElement('i'), {className: 'e2e-stale'}))")
    action()
    page.wait_for(js="!document.querySelector('#find-count .e2e-stale')", timeout=10)


def docs_where(predicate):
    return [d for d in docs().values() if predicate(d)]


# -- driving the page ---------------------------------------------------------------


def settle(page):
    """Wait until every month of the archive is in the index and the count is painted."""
    page.wait_for(js="(() => { const c = document.querySelector('#find-count'); return c && /items on file/i.test(c.textContent); })()"
                     " || !!document.querySelector('.hits__foot .notice')", timeout=15)


def total(page):
    settle(page)
    text = S.text_of(page, "#find-count b")
    match = re.match(r"([\d,]+) result", text)
    return int(match.group(1).replace(",", "")) if match else 0


def search(page, base_url, q, extra="", fresh=False):
    route = "/search?q=" + quote(q) + extra
    if fresh or not page.eval("location.href.startsWith({0!r})".format(base_url)):
        S.open_route(page, base_url, route)
    else:
        S.go(page, route)
    return total(page)


def hit_ids(page):
    return page.eval("[...document.querySelectorAll('ol.hits li.hit')].map((e) => e.dataset.story)")


def hit_docs(page):
    return [docs()[i] for i in hit_ids(page)]


def dropped(page):
    return page.eval("[...document.querySelectorAll('.also button.more')].some((b) => /restore/i.test(b.textContent))")


# -- tests --------------------------------------------------------------------------


def test_typing_shows_results_and_url(page, base_url):
    _, name = busy_entity()
    S.open_route(page, base_url, "/search")
    assert page.eval("document.activeElement.id") == "q2", "the search field is not focused on an empty search page"
    page.type(name.lower())
    page.wait_for(js="location.hash.includes('q={0}')".format(quote(name.lower())))
    page.wait_for(HITS, timeout=10)
    count = total(page)
    assert count > 0
    S.reload(page)
    assert page.eval("document.querySelector('#q2').value") == name.lower()
    assert total(page) == count
    assert page.count(HITS) == min(40, count)


def test_entity_widening_chip_can_be_dropped(page, base_url):
    entity_id, name = busy_entity()
    wide = search(page, base_url, name)
    assert wide > 0
    assert "also searching" in S.text_of(page, ".also").lower()
    chips = page.count(".also button.chip")
    assert chips > 0, "no widening chips for " + name
    assert S.text_of(page, ".defcard__term").lower() == name.lower(), "no name card for " + name
    changed = None
    labels = [l.lower() for l in page.eval("[...document.querySelectorAll('.also button.chip')].map((b) => b.firstChild.textContent)")]
    assert len(labels) == len(set(labels)), "the same widening is offered twice: {0}".format(labels)
    for index in range(chips):
        label = page.eval("(i) => document.querySelectorAll('.also button.chip')[i].getAttribute('aria-label')", index)
        page.eval("(i) => document.querySelectorAll('.also button.chip')[i].setAttribute('data-pick', '1')", index)
        repainted(page, lambda: page.click(".also button.chip[data-pick='1']"))
        page.wait_for(js="[...document.querySelectorAll('.also button.more')].some((b) => /restore 1 dropped/i.test(b.textContent))")
        assert not page.eval("(l) => [...document.querySelectorAll('.also button.chip')].some((b) => b.getAttribute('aria-label') === l)", label), \
            "the dropped chip is still offered: " + label
        now = total(page)
        if now != wide:
            changed = (label, wide, now)
            break
        click_until(page, ".also", "Restore 1 dropped", "![...document.querySelectorAll('.also button.more')].some((b) => /restore/i.test(b.textContent))")
    assert changed, "dropping a widening chip never changed the results for {0!r}".format(name)
    assert changed[2] < changed[1], changed
    page.note("{0}: {1} -> {2} results".format(*changed))


def test_exact_words_only_narrows(page, base_url):
    _, name = busy_entity()
    wide = search(page, base_url, name)
    click_until(page, ".also", "Exact words only", "!!document.querySelector('.also button.more[aria-pressed=true]')")
    narrow = total(page)
    assert narrow <= wide, (narrow, wide)
    assert page.count(".also button.chip") == 0, "chips are still shown in exact mode"
    word = S.tokenize(name)[0]
    for doc in hit_docs(page):
        text = " ".join(S.tokenize("{0} {1} {2}".format(doc["t"], doc.get("s") or "", doc.get("o") or "")))
        names = " ".join(S.lexicon()["entities"].get(e, {}).get("name", "") for e in doc.get("e") or []).lower()
        assert word[:5] in text or word[:5] in names, (word, doc["t"])
    page.note("{0}: {1} widened, {2} exact".format(name, wide, narrow))


@functools.lru_cache(maxsize=1)
def phrase_case():
    """Two adjacent words that also occur apart: the quoted phrase must find fewer docs."""
    together = collections.Counter()
    for doc in docs().values():
        tokens = S.tokenize("{0} . {1}".format(doc["t"], doc.get("s") or ""))
        pairs = set(zip(tokens, tokens[1:]))
        for a, b in pairs:
            if a.isalpha() and b.isalpha() and len(a) >= 4 and len(b) >= 4 and a not in S.STOPWORDS and b not in S.STOPWORDS:
                together[(a, b)] += 1
    for (a, b), n in together.most_common(200):
        both = len(docs_where(lambda d: {a, b} <= set(S.tokenize("{0} {1}".format(d["t"], d.get("s") or "")))))
        if n >= 2 and both > n:
            return a, b
    raise AssertionError("no phrase to test with")


def test_quoted_phrase(page, base_url):
    a, b = phrase_case()
    loose = search(page, base_url, "{0} {1}".format(a, b))
    exact = search(page, base_url, '"{0} {1}"'.format(a, b))
    assert 0 < exact < loose, (a, b, exact, loose)
    for doc in hit_docs(page):
        joined = " ".join(S.tokenize("{0} . {1}".format(doc["t"], doc.get("s") or "")))
        assert "{0} {1}".format(a, b) in joined, doc["t"]


def test_minus_term(page, base_url):
    _, name = busy_entity()
    base = search(page, base_url, name)
    first = hit_docs(page)[0]
    word = next(t for t in S.tokenize(first["t"]) if t.isalpha() and len(t) >= 4 and t not in S.STOPWORDS and t != name.lower())
    fewer = search(page, base_url, "{0} -{1}".format(name, word))
    assert fewer < base, (name, word, fewer, base)
    assert first["i"] not in hit_ids(page)
    for doc in hit_docs(page):
        assert word not in S.tokenize("{0} {1}".format(doc["t"], doc.get("s") or "")), (word, doc["t"])


def test_desk_filter(page, base_url):
    count = search(page, base_url, "desk:ai")
    want = docs_where(lambda d: str(d.get("c") or "").startswith("ai"))
    assert count == len(want), (count, len(want))
    for label in S.texts_of(page, HITS + " > span.label:first-child"):
        assert label.endswith("· AI"), label


def test_in_papers_and_in_claude(page, base_url):
    papers = docs_where(lambda d: d["k"] == "paper")
    claude = docs_where(lambda d: d["k"] in ("update", "feature", "recipe"))
    count = search(page, base_url, "in:papers")
    assert count == len(papers), (count, len(papers))
    assert all(d["k"] == "paper" for d in hit_docs(page))
    count = search(page, base_url, "in:claude")
    assert count == len(claude), (count, len(claude))
    assert all(d["k"] in ("update", "feature", "recipe") for d in hit_docs(page))


def test_source_filter(page, base_url):
    sources = collections.Counter(d["o"] for d in docs().values() if d["k"] == "story" and d.get("o") and " " not in d["o"])
    source = sources.most_common(1)[0][0]
    count = search(page, base_url, "source:" + source.lower())
    want = docs_where(lambda d: source.lower() in str(d.get("o") or "").lower())
    assert count == len(want), (source, count, len(want))
    for doc in hit_docs(page):
        assert source.lower() in doc["o"].lower(), doc


def local_day(stamp):
    """The calendar day of an ISO timestamp in the site's timezone."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    zone = ZoneInfo(S.manifest()["site"]["timezone"])
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(zone).strftime("%Y-%m-%d")


def test_after_filter(page, base_url):
    # dates are typed in the paper's calendar, so the filter compares the day in the paper's timezone
    days = sorted(set(local_day(d["d"]) for d in docs().values() if d.get("d")))
    day = days[len(days) // 2]
    count = search(page, base_url, "after:" + day)
    want = docs_where(lambda d: d.get("d") and local_day(d["d"]) >= day)
    assert count == len(want), (day, count, len(want))
    assert all(local_day(d["d"]) >= day for d in hit_docs(page))
    # filters only: newest first
    stamps = [d["d"] for d in hit_docs(page)]
    assert stamps == sorted(stamps, reverse=True)


def test_is_saved(page, base_url):
    story = next(d for d in docs().values() if d["k"] == "story")
    feature = next(d for d in docs().values() if d["k"] == "feature")
    feature_id = feature["i"].split(":", 1)[1]
    saved = {
        "story:" + story["i"]: {"kind": "story", "id": story["i"], "title": story["t"], "url": story["u"], "savedAt": 1, "note": ""},
        "feature:" + feature_id: {"kind": "feature", "id": feature_id, "title": feature["t"], "url": feature["u"], "savedAt": 2, "note": ""},
    }
    S.open_route(page, base_url, "/")
    page.local_storage_set("fl.saved", saved)
    count = search(page, base_url, "is:saved", fresh=True)
    assert set(hit_ids(page)) == {story["i"], feature["i"]}, "is:saved found {0} (expected the clipped story and technique)".format(hit_ids(page))
    assert count == 2


def test_is_unread(page, base_url):
    _, name = busy_entity()
    base = search(page, base_url, name)
    read = [d["i"] for d in hit_docs(page) if d["k"] == "story"][:2]
    page.local_storage_set("fl.read", {i: int(time.time() * 1000) for i in read})
    count = search(page, base_url, name + " is:unread", fresh=True)
    assert count == base - len(read), (count, base, read)
    assert not set(read) & set(hit_ids(page))


def test_misspelling_still_finds(page, base_url):
    counts = collections.Counter(t for d in docs().values() if d["k"] == "story" for t in set(S.tokenize(d["t"])))
    word = next(w for w, n in counts.most_common() if w.isalpha() and 6 <= len(w) <= 8 and w not in S.STOPWORDS and n >= 3)
    typo = word[0] + word[2] + word[1] + word[3:]
    if typo in counts:
        typo = word[:-1]
    count = search(page, base_url, typo)
    did = S.text_of(page, ".didyou")
    assert count > 0 or did, "{0!r} (for {1!r}) finds nothing and offers nothing".format(typo, word)
    if did:
        repainted(page, lambda: page.click(".didyou button"))
        page.wait_for(js="document.querySelector('#q2').value !== {0!r}".format(typo))
    page.note("{0!r} -> {1} results{2}".format(typo, count, "; " + did if did else ""))


def test_highlighting_marks_query_words(page, base_url):
    counts = collections.Counter(t for d in docs().values() if d["k"] == "story" for t in set(S.tokenize(d["t"])))
    word = next(w for w, n in counts.most_common() if w.isalpha() and len(w) >= 5 and w not in S.STOPWORDS and 3 <= n <= 30)
    search(page, base_url, word)
    if page.exists(".also button.more"):
        click_until(page, ".also", "Exact words only", "!!document.querySelector('.also button.more[aria-pressed=true]')")
    marks = page.eval("[...document.querySelectorAll('ol.hits mark')].map((m) => m.textContent.toLowerCase())")
    assert marks, "no highlighting for " + word
    assert any(word in m for m in marks), (word, marks[:10])
    first_titles = page.eval("[...document.querySelectorAll('ol.hits li.hit .story__hl')].slice(0, 5).map((a) => a.querySelectorAll('mark').length)")
    assert all(first_titles), "a top hit's title has no highlighted word: {0}".format(first_titles)


def test_kind_tabs_and_sort(page, base_url):
    _, name = busy_entity()
    search(page, base_url, name)
    click_until(page, ".findbar .filters[aria-label=Kind]", "Stories",
                "location.hash.includes('in=story') && document.querySelector('.filters[aria-label=Kind] button[aria-pressed=true]').textContent.trim() === 'Stories'")
    assert all(d["k"] == "story" for d in hit_docs(page))
    click_until(page, ".findbar .filters[aria-label=Order]", "Newest",
                "location.hash.includes('sort=newest') && document.querySelector('.filters[aria-label=Order] button[aria-pressed=true]').textContent.trim() === 'Newest'")
    stamps = [d["d"] for d in hit_docs(page)]
    assert stamps == sorted(stamps, reverse=True), stamps[:10]
    S.reload(page)
    assert S.query_of(page) == {"q": name, "in": "story", "sort": "newest"}, S.query_of(page)
    stamps_after = [d["d"] for d in hit_docs(page)]
    assert stamps_after == stamps
    click_until(page, ".findbar .filters[aria-label=Kind]", "Glossary",
                "location.hash.includes('in=term') && document.querySelector('.filters[aria-label=Kind] button[aria-pressed=true]').textContent.trim() === 'Glossary'")
    assert all(d["k"] == "term" for d in hit_docs(page))


def test_enter_in_masthead_search(page, base_url):
    _, name = busy_entity()
    S.open_route(page, base_url, "/wire")
    page.fill("#q", name)
    page.press("Enter")
    S.wait_route(page, "#/search")
    page.wait_for("#q2")
    assert S.query_of(page).get("q") == name
    assert page.eval("document.querySelector('#q2').value") == name
    assert total(page) > 0


def test_empty_result_state(page, base_url):
    count = search(page, base_url, "zqxjvkw")
    assert count == 0
    assert "Nothing on file for" in S.text_of(page, ".hits__foot .notice")
    assert page.count(HITS) == 0


def test_glossary_term_card(page, base_url):
    glossary = S.lexicon().get("glossary") or {}
    entities = set(" ".join(S.tokenize(e["name"])) for e in S.lexicon()["entities"].values())
    term = next(t for t in glossary if " ".join(S.tokenize(t)) not in entities and len(S.tokenize(t)) >= 2)
    search(page, base_url, term)
    page.wait_for(".defcard")
    assert S.text_of(page, ".defcard__term") == term
    assert glossary[term][:30].replace("'", "’") in S.text_of(page, ".defcard").replace("'", "’")


def test_claude_feature_by_name(page, base_url):
    book = S.playbook()
    titles = collections.Counter(f["title"].lower() for f in book["features"])
    feature = next(f for f in book["features"] if len(S.tokenize(f["title"])) >= 2 and titles[f["title"].lower()] == 1)
    search(page, base_url, feature["title"])
    link = "ol.hits a[href='#/claude/feature/{0}']".format(feature["id"])
    page.wait_for(link)
    page.click(link)
    S.wait_route(page, "#/claude/feature/" + feature["id"])
    assert feature["title"] in page.title()


def test_slash_focuses_the_page_search_field(page, base_url):
    search(page, base_url, "markets")
    page.eval("document.activeElement.blur()")
    page.press("/")
    assert page.eval("document.activeElement.id") == "q2"


def test_browser_unit_tests(page, base_url):
    results = run_js_tests(page, base_url + "/__repo__/tests/js/index.html")
    page.note("{0} browser unit tests passed".format(len(results)))
    assert len(results) > 0


def test_desk_filter_is_exact_for_a_full_desk_id(page, base_url):
    sections = [s["id"] for s in S.manifest()["sections"]]
    prefixed = [(a, b) for a in sections for b in sections if a != b and b.startswith(a)]
    if not prefixed:
        page.note("no desk id is a prefix of another")
        return
    desk = prefixed[0][0]
    count = search(page, base_url, "desk:" + desk)
    want = docs_where(lambda d: d.get("c") == desk)
    assert count == len(want), "desk:{0} found {1}, the {0} desk has {2} (it also matched {3})".format(desk, count, len(want), prefixed[0][1])
    name = next(s["name"] for s in S.manifest()["sections"] if s["id"] == desk)
    for label in S.texts_of(page, HITS + " > span.label:first-child"):
        assert label.endswith("· " + name), label


def test_show_more_and_recent_searches(page, base_url):
    _, name = busy_entity()
    count = search(page, base_url, name)
    if count > 40:
        click_until(page, ".hits__foot", "Show", "document.querySelectorAll('ol.hits li.hit').length > 40")
        assert page.count(HITS) == min(80, count)
    S.go(page, "/wire")
    S.go(page, "/search")
    S.wait_text(page, ".hits__foot", "recent searches")
    assert name in S.texts_of(page, ".hits__foot .taglist button.chip"), S.texts_of(page, ".hits__foot .taglist button.chip")
    assert name in (S.storage_json(page, "fl.search") or {}).get("recent", [])
    page.eval("(n) => [...document.querySelectorAll('.hits__foot .taglist button.chip')].find((b) => b.textContent === n).setAttribute('data-pick', 1)", name)
    page.click(".hits__foot button[data-pick]")
    page.wait_for(js="location.hash.includes('q=')")
    assert total(page) == count
