"""The Wire: filters, order, keys, read marks, clipping and "new since your last look"."""

import calendar
import re
import time

from tests.e2e.scenarios import support as S

PAGE = 150
ROW = ".wire__row[data-story]"


def parse_time(value):
    return calendar.timegm(time.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")) * 1000


def stamp(story):
    return parse_time(story.get("updatedAt") or story["publishedAt"])


def filtered(desk="all", cov=1, unread_except=(), ranked=False):
    rows = list({s["id"]: s for s in S.latest()["stories"]}.values())
    if desk != "all":
        rows = [s for s in rows if s["section"] == desk or desk in (s.get("sections") or [])]
    if cov > 1:
        rows = [s for s in rows if (s.get("sourceCount") or 1) >= cov]
    if unread_except:
        rows = [s for s in rows if s["id"] not in unread_except]
    if ranked:
        rows.sort(key=lambda s: (-s["score"], -stamp(s)))
    else:
        rows.sort(key=lambda s: -stamp(s))
    return rows


def shown_ids(page):
    return page.eval("[...document.querySelectorAll('.wire__row[data-story]')].map((e) => e.dataset.story)")


def live_count(page):
    text = S.text_of(page, ".wire__bar .live")
    match = re.match(r"(\d+) stor", text)
    assert match, text
    return int(match.group(1))


def assert_list(page, rows):
    assert live_count(page) == len(rows), (live_count(page), len(rows))
    ids = shown_ids(page)
    assert len(ids) == min(PAGE, len(rows)), (len(ids), len(rows))
    assert set(ids) <= set(s["id"] for s in rows)


def pressed(page, group):
    return page.eval(
        "(g) => [...document.querySelectorAll('.filters[aria-label=\"' + g + '\"] button[aria-pressed=true]')].map((b) => b.textContent.trim())",
        group,
    )


def busiest_desk(min_rows=2):
    counts = {}
    for section in S.SECTIONS:
        counts[section] = len(filtered(desk=section))
    return max(counts, key=counts.get)


def test_count_matches_data(page, base_url):
    S.open_route(page, base_url, "/wire")
    rows = filtered()
    assert_list(page, rows)
    # Latest: newest first
    first = shown_ids(page)[:5]
    assert first == [s["id"] for s in rows[:5]], first
    if len(rows) > PAGE:
        S.click_button(page, ".wire__more", "Show")
        page.wait_for(js="document.querySelectorAll('.wire__row[data-story]').length > {0}".format(PAGE))
        assert len(shown_ids(page)) == min(2 * PAGE, len(rows))


def test_desk_filter_url_and_reload(page, base_url):
    desk = busiest_desk()
    d = next(x for x in S.manifest()["sections"] if x["id"] == desk)
    no = "{0:02d}".format(S.manifest()["sections"].index(d) + 1)
    S.open_route(page, base_url, "/wire")
    S.click_button(page, ".filters[aria-label=Desk]", "{0} {1}".format(no, d["name"]))
    page.wait_for(js="location.hash.includes('desk={0}')".format(desk))
    rows = filtered(desk=desk)
    assert_list(page, rows)
    assert pressed(page, "Desk") == ["{0} {1}".format(no, d["name"])], pressed(page, "Desk")
    S.reload(page)
    assert S.query_of(page).get("desk") == desk
    assert_list(page, rows)
    assert pressed(page, "Desk") == ["{0} {1}".format(no, d["name"])]
    S.click_button(page, ".filters[aria-label=Desk]", "All desks")
    page.wait_for(js="!location.hash.includes('desk=')")
    assert_list(page, filtered())


def test_coverage_filter(page, base_url):
    S.open_route(page, base_url, "/wire")
    S.click_button(page, ".filters[aria-label=Coverage]", "3+ outlets")
    page.wait_for(js="location.hash.includes('cov=3')")
    rows = filtered(cov=3)
    assert_list(page, rows)
    outlets = page.eval("[...document.querySelectorAll('.wire__row[data-story] .cov b')].map((b) => +b.textContent)")
    assert outlets and min(outlets) >= 3, outlets
    S.reload(page)
    assert_list(page, rows)
    S.click_button(page, ".filters[aria-label=Coverage]", "6+ outlets")
    page.wait_for(js="location.hash.includes('cov=6')")
    assert_list(page, filtered(cov=6))


def test_ranked_order(page, base_url):
    S.open_route(page, base_url, "/wire")
    S.click_button(page, ".filters[aria-label=Order]", "Ranked")
    page.wait_for(js="location.hash.includes('sort=ranked')")
    rows = filtered(ranked=True)
    assert shown_ids(page)[:10] == [s["id"] for s in rows[:10]]
    assert not page.exists(".wire__day"), "day dividers belong to the Latest order"
    S.reload(page)
    assert shown_ids(page)[:10] == [s["id"] for s in rows[:10]]
    S.click_button(page, ".filters[aria-label=Order]", "Latest")
    page.wait_for(js="!location.hash.includes('sort=')")
    assert shown_ids(page)[:10] == [s["id"] for s in filtered()[:10]]


def test_unread_only(page, base_url):
    rows = filtered()
    read = [s["id"] for s in rows[:3]]
    seed = "{" + ",".join('"{0}":{1}'.format(i, int(time.time() * 1000)) for i in read) + "}"
    page.add_init_script("localStorage.setItem('fl.read', '{0}')".format(seed))
    S.open_route(page, base_url, "/wire")
    for story_id in read:
        assert "is-read" in page.attr(ROW + "[data-story='{0}']".format(story_id), "class")
    page.click(".wire__toggles > button.chip")
    page.wait_for(js="location.hash.includes('unread=1')")
    assert_list(page, filtered(unread_except=set(read)))
    for story_id in read:
        assert not page.exists(ROW + "[data-story='{0}']".format(story_id))
    S.reload(page)
    assert_list(page, filtered(unread_except=set(read)))
    page.press("u")
    page.wait_for(js="!location.hash.includes('unread')")
    assert_list(page, rows)


def test_combined_filters_in_url(page, base_url):
    desk = busiest_desk()
    S.open_route(page, base_url, "/wire?desk={0}&cov=3&sort=ranked".format(desk))
    rows = filtered(desk=desk, cov=3, ranked=True)
    assert live_count(page) == len(rows)
    assert shown_ids(page)[:5] == [s["id"] for s in rows[:5]]


def test_j_k_move_the_cursor(page, base_url):
    S.open_route(page, base_url, "/wire")
    ids = shown_ids(page)
    active = "document.activeElement.closest('[data-story]')?.dataset.story"
    page.press("j")
    assert page.eval(active) == ids[0]
    assert "is-cursor" in page.attr(ROW, "class")
    page.press("j")
    page.press("j")
    assert page.eval(active) == ids[2]
    page.press("k")
    assert page.eval(active) == ids[1]
    assert page.eval("document.activeElement.matches('[data-hl]')")


def test_x_marks_read_and_it_persists(page, base_url):
    S.open_route(page, base_url, "/wire")
    ids = shown_ids(page)
    page.press("j")
    page.press("j")
    page.press("x")
    target = ROW + "[data-story='{0}']".format(ids[1])
    assert "is-read" in page.attr(target, "class")
    assert ids[1] in (S.storage_json(page, "fl.read") or {})
    S.reload(page)
    assert "is-read" in page.attr(target, "class")
    assert "is-read" not in page.attr(ROW + "[data-story='{0}']".format(ids[0]), "class")
    # x again un-marks it
    page.eval("(s) => document.querySelector(s + ' [data-hl]').focus()", target)
    page.press("x")
    assert "is-read" not in page.attr(target, "class")
    assert ids[1] not in (S.storage_json(page, "fl.read") or {})


def test_s_clips_and_nav_count_updates(page, base_url):
    S.open_route(page, base_url, "/wire")
    assert not page.exists(".nav__main a[href='#/clippings'] .nav__count")
    ids = shown_ids(page)
    page.press("j")
    page.press("s")
    page.wait_for(".nav__main a[href='#/clippings'] .nav__count")
    assert S.text_of(page, ".nav__main a[href='#/clippings'] .nav__count") == "1"
    assert "story:" + ids[0] in S.storage_json(page, "fl.saved")
    assert page.attr(ROW + " .clipper", "aria-pressed") == "true"
    page.press("j")
    page.press("s")
    page.wait_for_text(".nav__main a[href='#/clippings'] .nav__count", "2")
    S.go(page, "/clippings")
    assert page.count("ol.rows li.row") == 2


def test_number_keys_filter_desks(page, base_url):
    S.open_route(page, base_url, "/wire")
    sections = S.manifest()["sections"]
    page.press("2")
    page.wait_for(js="location.hash.includes('desk={0}')".format(sections[1]["id"]))
    assert_list(page, filtered(desk=sections[1]["id"]))
    if len(sections) >= 10:
        page.press("0")
        page.wait_for(js="location.hash.includes('desk={0}')".format(sections[9]["id"]))
        assert_list(page, filtered(desk=sections[9]["id"]))
        page.press("0")
        page.wait_for(js="!location.hash.includes('desk=')")
    page.press("2")
    page.press("a")
    page.wait_for(js="!location.hash.includes('desk=')")
    assert_list(page, filtered())


def test_new_since_last_look_divider(page, base_url):
    rows = filtered()
    assert len(rows) > 12
    seen_at = (stamp(rows[9]) + stamp(rows[12])) // 2
    fresh = len([s for s in rows if stamp(s) > seen_at])
    page.add_init_script("localStorage.setItem('fl.visit', JSON.stringify({{wireSeenAt: {0}}}))".format(seen_at))
    S.open_route(page, base_url, "/wire")
    assert "{0} new since your last look".format(fresh) in S.text_of(page, ".wire__bar .live"), S.text_of(page, ".wire__bar .live")
    page.wait_for(".wire__mark")
    before = page.eval("[...document.querySelector('.wire ol').children].findIndex((li) => li.matches('.wire__mark'))")
    rows_before = page.eval(
        "(n) => [...document.querySelector('.wire ol').children].slice(0, n).filter((li) => li.matches('[data-story]')).length", before)
    assert rows_before == fresh, (rows_before, fresh)


def test_leaving_the_wire_records_the_visit(page, base_url):
    S.open_route(page, base_url, "/wire")
    assert not page.exists(".wire__mark"), "a first visit has nothing to divide"
    started = page.eval("Date.now()")
    S.go(page, "/")
    visit = S.storage_json(page, "fl.visit") or {}
    assert visit.get("wireSeenAt", 0) >= started, visit
    S.go(page, "/wire")
    assert "new since your last look" not in S.text_of(page, ".wire__bar .live")


def test_closing_the_tab_on_the_wire_records_the_visit(page, base_url):
    S.open_route(page, base_url, "/wire")
    started = page.eval("Date.now()")
    S.reload(page)  # the reader closes the tab or reloads, never leaving the route
    visit = S.storage_json(page, "fl.visit") or {}
    assert visit.get("wireSeenAt", 0) >= started, "a look at the Wire that ends by closing the tab is forgotten: {0}".format(visit)


def test_desk_page_entity_chips(page, base_url):
    desk = busiest_desk()
    S.open_route(page, base_url, "/s/" + desk)
    stories = filtered(desk=desk)
    assert live_count(page) == len(stories)
    if not page.exists(".filters[aria-label='Filter by name'] button:nth-child(2)"):
        page.note("no name appears twice on this desk")
        return
    name = page.eval("document.querySelector(\".filters[aria-label='Filter by name'] button:nth-child(2)\").firstChild.textContent")
    count = int(S.text_of(page, ".filters[aria-label='Filter by name'] button:nth-child(2) .chip__n"))
    page.click(".filters[aria-label='Filter by name'] button:nth-child(2)")
    page.wait_for(js="document.querySelector(\".filters[aria-label='Filter by name'] button:nth-child(2)\").getAttribute('aria-pressed') === 'true'")
    assert live_count(page) == count, (name, live_count(page), count)


def test_pressed_filter_is_visibly_different(page, base_url):
    S.open_route(page, base_url, "/wire")
    colours = page.eval(
        "[...document.querySelectorAll('.filters[aria-label=Coverage] button')].map((b) => ({pressed: b.getAttribute('aria-pressed'), bg: getComputedStyle(b).backgroundColor}))"
    )
    on = [c["bg"] for c in colours if c["pressed"] == "true"]
    off = [c["bg"] for c in colours if c["pressed"] == "false"]
    assert on and off
    assert on[0] not in off, "the pressed filter looks the same as the others: {0}".format(colours)


def test_load_an_older_day(page, base_url):
    hot_days = set(s["day"] for s in S.latest()["stories"])
    oldest = min(hot_days)
    older = [d for d in S.manifest()["days"] if d < oldest]
    S.open_route(page, base_url, "/wire")
    if not older:
        assert not page.eval("[...document.querySelectorAll('.wire__more button')].some((b) => b.textContent.startsWith('Load'))")
        page.note("no day older than the hot set on file")
        return
    day = max(older)
    before = live_count(page)
    extra = [s for s in S.data("stories/{0}.json".format(day))["stories"] if s["id"] not in set(x["id"] for x in S.latest()["stories"])]
    S.click_button(page, ".wire__more", "Load")
    page.wait_for(js="parseInt(document.querySelector('.wire__bar .live').textContent) !== {0}".format(before))
    assert live_count(page) == before + len(extra), (live_count(page), before, len(extra))
