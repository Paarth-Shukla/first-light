"""Every route renders, with a sensible title, one h1 and no console error."""

from tests.e2e.run import allow_errors
from tests.e2e.scenarios import support as S

BROKEN_WORDS = ("undefined", "NaN", "[object Object]", "Invalid Date")


def check_page(page, title_part, selector=None, h1_text=None):
    title = page.title()
    assert title_part in title, "title {0!r} does not contain {1!r}".format(title, title_part)
    assert "First Light" in title, title
    for word in BROKEN_WORDS:
        assert word not in title, title
    if selector:
        page.wait_for(selector)
    text = page.eval("document.body.textContent")
    for word in BROKEN_WORDS:
        assert word not in text, "{0!r} printed on {1}: ...{2}...".format(
            word, page.url, text[max(0, text.find(word) - 80) : text.find(word) + 40]
        )
    assert page.count("h1") == 1, "expected one h1, found {0}".format(page.count("h1"))
    if h1_text is not None:
        assert h1_text.lower() in page.text("h1").lower(), (page.text("h1"), h1_text)


def test_front_page(page, base_url):
    S.open_route(page, base_url, "/")
    number = S.edition()["number"]
    check_page(page, "No. {0}".format(number), ".lead", h1_text="First Light")


def test_edition_by_date(page, base_url):
    date = S.manifest()["editions"][0]
    S.open_route(page, base_url, "/edition/" + date)
    check_page(page, "No. ", ".lead")
    assert page.exists(".flap"), "the edition plate is missing"


def test_wire(page, base_url):
    S.open_route(page, base_url, "/wire")
    check_page(page, "The Wire", ".wire__row[data-story]", h1_text="The Wire")


def test_every_desk(page, base_url):
    S.open_route(page, base_url, "/")
    for section in S.manifest()["sections"]:
        S.go(page, "/s/" + section["id"])
        check_page(page, section["name"], h1_text=section["name"])
        has_rows = page.count(".wire__row[data-story]") > 0
        has_notice = page.exists(".notice")
        assert has_rows or has_notice, "desk {0} shows neither stories nor a notice".format(section["id"])
        current = page.eval("document.querySelector('nav.desks a[aria-current=page]')?.getAttribute('href')")
        assert current == "#/s/" + section["id"], current


def test_story_page(page, base_url):
    story = S.latest()["stories"][0]
    S.open_route(page, base_url, "/story/{0}?d={1}".format(story["id"], story["day"]))
    # the tab title names the story, so history and bookmarks can tell stories apart; the page head stays generic
    check_page(page, story["title"][:30], ".detail", h1_text="Who carried it")
    assert page.count(".detail ol.rows li.row") >= len(story.get("sources") or []) > 0
    assert page.text(".cov-xl__n") == str(story["sourceCount"])


def test_story_from_an_older_day(page, base_url):
    days = S.manifest()["days"]
    hot = set(s["id"] for s in S.latest()["stories"])
    for day in reversed(days):
        older = [s for s in S.data("stories/{0}.json".format(day))["stories"] if s["id"] not in hot]
        if older:
            break
    else:
        page.note("every story on file is in the hot set; nothing older to open")
        return
    S.open_route(page, base_url, "/story/{0}?d={1}".format(older[0]["id"], day))
    check_page(page, "First Light", ".detail", h1_text="Who carried it")


def test_markets(page, base_url):
    S.open_route(page, base_url, "/markets")
    check_page(page, "Markets", "table.mkt", h1_text="Markets")


def test_weekend_latest_and_by_week(page, base_url):
    weeks = S.weekend_index()["weeks"]
    S.open_route(page, base_url, "/weekend")
    check_page(page, "Weekend Review", ".paper")
    S.go(page, "/weekend/" + weeks[0]["isoWeek"])
    check_page(page, "Weekend Review", ".paper")
    assert weeks[0]["isoWeek"] in page.text(".folio")


def test_claude_pages(page, base_url):
    book = S.playbook()
    feature, recipe = book["features"][0], book["recipes"][0]
    S.open_route(page, base_url, "/claude")
    check_page(page, "Claude Desk", "#drill-h", h1_text="Claude Desk")
    for route, title in (
        ("/claude/updates", "What’s new in Claude"),
        ("/claude/playbook", "The Playbook"),
        ("/claude/feature/" + feature["id"], feature["title"]),
        ("/claude/recipes", "Recipes"),
        ("/claude/recipe/" + recipe["id"], recipe["title"]),
    ):
        S.go(page, route)
        check_page(page, title, ".subnav")
        assert page.exists(".subnav a[aria-current=page]"), "no Claude Desk tab is marked current on " + route


def test_search_with_query(page, base_url):
    S.open_route(page, base_url, "/search?q=nvidia")
    check_page(page, "Search", "#q2", h1_text="Search")
    S.wait_text(page, "#find-count", "result")


def test_reader_pages(page, base_url):
    S.open_route(page, base_url, "/clippings")
    check_page(page, "Clippings", ".notice", h1_text="Clippings")
    for route, title, selector in (
        ("/archive", "Back Issues", "ol.rows a[href^='#/edition/']"),
        ("/settings", "Settings", ".readon--danger"),
    ):
        S.go(page, route)
        check_page(page, title, selector, h1_text=title)


def test_colophon(page, base_url):
    S.open_route(page, base_url, "/colophon")
    check_page(page, "Colophon", ".detail", h1_text="Colophon")
    if not S.has_data("status.json"):
        S.forgive_missing(page, "status.json")
        page.note("this build has no status.json; the source table shows its empty state")


def test_unknown_route(page, base_url):
    S.open_route(page, base_url, "/no/such/page")
    check_page(page, "No such page", ".notice")
    assert "no page at this address" in page.text(".notice").lower()


def test_unknown_story(page, base_url):
    S.open_route(page, base_url, "/story/s0000000000?d=" + S.manifest()["days"][0])
    check_page(page, "Story not on file", ".notice")


def test_unknown_section(page, base_url):
    S.open_route(page, base_url, "/s/astrology")
    check_page(page, "No such desk", ".notice")


def test_unknown_feature_and_recipe(page, base_url):
    S.open_route(page, base_url, "/claude/feature/no-such-feature")
    check_page(page, "Not in the playbook", ".notice")
    S.go(page, "/claude/recipe/no-such-recipe")
    check_page(page, "No such recipe", ".notice")


@allow_errors("editions/1999-01-01.json")
def test_edition_with_no_file(page, base_url):
    S.open_route(page, base_url, "/edition/1999-01-01")
    check_page(page, "Front Page", ".notice")
    assert "There is no edition for" in page.text(".notice"), page.text(".notice")
    assert page.exists(".notice a[href='#/archive']")


def test_unknown_weekend_week(page, base_url):
    S.open_route(page, base_url, "/weekend/1999-W01")
    S.forgive_missing(page, "weekend/1999-W01.json")
    check_page(page, "Weekend Review", ".notice")
    assert "1999-W01" in page.text(".notice")


def test_desk_top_of_the_desk(page, base_url):
    hot = S.latest()["stories"]
    section = max(S.manifest()["sections"], key=lambda s: len([x for x in hot if x["section"] == s["id"]]))
    S.open_route(page, base_url, "/s/" + section["id"])
    top = sorted([x for x in hot if x["section"] == section["id"]], key=lambda x: -x["score"])[:3]
    shown = page.eval("[...document.querySelectorAll('section.desk--12 [data-story]')].map((e) => e.dataset.story)")
    assert shown == [x["id"] for x in top], (shown, [x["id"] for x in top])


def test_archive_and_colophon_figures(page, base_url):
    index = S.data("editions/index.json")["editions"]
    S.open_route(page, base_url, "/archive")
    rows = page.eval("[...document.querySelectorAll('ol.rows a[href^=\"#/edition/\"]')].map((a) => a.getAttribute('href'))")
    assert rows == ["#/edition/" + e["date"] for e in index], rows
    page.click("ol.rows a[href^='#/edition/']")
    S.wait_route(page, "#/edition/")
    assert page.exists(".lead")
    S.go(page, "/colophon")
    if not S.has_data("status.json"):
        S.forgive_missing(page, "status.json")
    m = S.manifest()
    figures = dict(zip(S.texts_of(page, ".detail__side table:first-of-type th"), S.texts_of(page, ".detail__side table:first-of-type td")))
    assert figures.get("Editions") == str(len(m["editions"])), figures
    assert figures.get("Days on the wire") == str(len(m["days"])), figures
    assert figures.get("Sources answering") == "{0} of {1}".format(m["counts"]["sourcesOk"], m["counts"]["sources"]), figures
