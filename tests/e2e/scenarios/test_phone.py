"""Phone (390x844, touch): no sideways scroll, the tab bar, the desk sheet, tap targets, gutters."""

from tests.e2e.scenarios import support as S


def phone(page):
    page.set_viewport(390, 844, mobile=True, scale=1)


def main_routes():
    book = S.playbook()
    story = S.latest()["stories"][0]
    routes = ["/", "/wire", "/story/{0}?d={1}".format(story["id"], story["day"]), "/markets", "/weekend",
              "/claude", "/claude/updates", "/claude/playbook", "/claude/recipes",
              "/claude/feature/" + book["features"][0]["id"], "/claude/recipe/" + book["recipes"][0]["id"],
              "/search?q=" + S.lexicon()["entities"][next(iter(S.lexicon()["entities"]))]["name"].replace(" ", "%20"),
              "/search", "/clippings", "/archive", "/settings", "/colophon", "/no/such/page"]
    routes += ["/s/" + s["id"] for s in S.manifest()["sections"]]
    return routes


def test_no_horizontal_scroll_anywhere(page, base_url):
    phone(page)
    S.open_route(page, base_url, "/")
    wide = []
    for route in main_routes():
        S.go(page, route)
        if not S.no_horizontal_scroll(page):
            culprit = page.eval(
                "(() => { const w = document.documentElement.clientWidth; const out = [];"
                " for (const el of document.querySelectorAll('#view *, #mast *')) { const r = el.getBoundingClientRect();"
                " if (r.right > w + 1 && getComputedStyle(el).position !== 'fixed' && !el.closest('.filters, .tablewrap')) out.push(el.tagName + '.' + el.className + ' ' + Math.round(r.right)); }"
                " return out.slice(0, 3); })()")
            wide.append((route, page.eval("document.documentElement.scrollWidth"), culprit))
    if not S.has_data("status.json"):
        S.forgive_missing(page, "status.json")
    assert not wide, "pages scroll sideways at 390px: {0}".format(wide)


def test_tab_bar_is_there_and_navigates(page, base_url):
    phone(page)
    S.open_route(page, base_url, "/")
    assert page.visible("#tabbar")
    names = page.eval("[...document.querySelectorAll('#tabbar > a')].map((a) => a.firstChild.textContent)")
    assert names == ["Front", "Wire", "Desks", "Markets", "More"], names
    heights = page.eval("[...document.querySelectorAll('#tabbar > a')].map((a) => a.getBoundingClientRect().height)")
    assert min(heights) >= 40, heights
    widths = page.eval("[...document.querySelectorAll('#tabbar > a')].map((a) => a.getBoundingClientRect().width)")
    assert min(widths) >= 40, widths
    bottom = page.eval("document.querySelector('#tabbar').getBoundingClientRect().bottom")
    assert abs(bottom - 844) <= 1, bottom
    for href, title in (("#/wire", "The Wire"), ("#/markets", "Markets"), ("#/", "No. ")):
        page.click("#tabbar a[href='{0}']".format(href))
        page.wait_for(js="location.hash === {0!r}".format(href))
        S.wait_ready(page)
        assert title in page.title()
        assert page.attr("#tabbar a[href='{0}']".format(href), "aria-current") == "page"
    # the last story on a long page is not hidden behind the bar
    S.go(page, "/wire")
    page.eval("window.scrollTo(0, document.documentElement.scrollHeight)")
    covered = page.eval("(() => { const bar = document.querySelector('#tabbar').getBoundingClientRect();"
                        " const end = document.querySelector('#colophon').getBoundingClientRect(); return end.bottom > bar.top + 1; })()")
    assert not covered, "the end of the page sits behind the tab bar"


def test_desks_sheet(page, base_url):
    phone(page)
    S.open_route(page, base_url, "/")
    desks = page.eval("document.querySelector('#tabbar [data-sheet=true]')")
    assert desks is not None
    page.click("#tabbar [data-sheet=true]")
    page.wait_for("#desk-index.is-open", visible=True)
    assert page.attr("#tabbar [data-sheet=true]", "aria-expanded") == "true"
    assert page.eval("document.activeElement.matches('.sheet__close')")
    links = page.count("#desk-index .sheet__list a")
    assert links == len(S.manifest()["sections"])
    heights = page.eval("[...document.querySelectorAll('#desk-index .sheet__list a, #desk-index .sheet__close')].map((a) => a.getBoundingClientRect().height)")
    assert min(heights) >= 40, heights
    target = S.manifest()["sections"][1]
    page.click("#desk-index .sheet__list a[href='#/s/{0}']".format(target["id"]))
    S.wait_route(page, "#/s/" + target["id"])
    page.wait_for(js="!document.querySelector('#desk-index').classList.contains('is-open')")
    assert target["name"] in page.title()
    assert not page.eval("document.body.classList.contains('sheet-open')")
    # Escape closes it
    page.click("#tabbar [data-sheet=true]")
    page.wait_for("#desk-index.is-open", visible=True)
    page.press("Escape")
    page.wait_for(js="!document.querySelector('#desk-index').classList.contains('is-open')")
    assert page.attr("#tabbar [data-sheet=true]", "aria-expanded") == "false"
    # so does Close, and tapping Desks again
    page.click("#tabbar [data-sheet=true]")
    page.wait_for("#desk-index.is-open", visible=True)
    page.click("#desk-index .sheet__close")
    page.wait_for(js="!document.querySelector('#desk-index').classList.contains('is-open')")
    page.click("#tabbar [data-sheet=true]")
    page.wait_for("#desk-index.is-open", visible=True)
    page.click("#tabbar [data-sheet=true]")
    page.wait_for(js="!document.querySelector('#desk-index').classList.contains('is-open')")


def test_more_sheet_focuses_search(page, base_url):
    phone(page)
    S.open_route(page, base_url, "/")
    page.click("#tabbar [data-sheet=more]")
    page.wait_for("#desk-index.is-open", visible=True)
    assert page.eval("document.activeElement.matches('.sheet__search input')"), page.eval("document.activeElement.outerHTML")
    page.type("markets")
    page.press("Enter")
    S.wait_route(page, "#/search")
    assert S.query_of(page)["q"] == "markets"
    assert not page.eval("document.querySelector('#desk-index').classList.contains('is-open')")
    # the other links in the sheet
    page.click("#tabbar [data-sheet=more]")
    page.wait_for("#desk-index.is-open", visible=True)
    page.click("#desk-index .sheet__more a[href='#/clippings']")
    S.wait_route(page, "#/clippings")
    page.wait_for(js="!document.querySelector('#desk-index').classList.contains('is-open')")


def test_filter_rows_keep_the_gutter(page, base_url):
    phone(page)
    S.open_route(page, base_url, "/wire")
    for route in ("/wire", "/claude/playbook", "/search?q=markets", "/claude/updates"):
        S.go(page, route)
        lefts = page.eval("[...document.querySelectorAll('#view .filters')].map((f) => { f.scrollLeft = 0; return Math.round(f.firstElementChild.getBoundingClientRect().left); })")
        assert lefts, route
        assert min(lefts) >= 15, "{0}: a filter row starts at x={1}, outside the 16px gutter".format(route, lefts)


def test_phone_tap_targets_on_the_wire(page, base_url):
    phone(page)
    S.open_route(page, base_url, "/wire")
    small = page.eval("[...document.querySelectorAll('#view .filters button, #view .wire__toggles > button')].filter((b) => b.getBoundingClientRect().height < 40).map((b) => b.textContent)")
    assert not small, "filter buttons under the 40px touch target on a phone: {0}".format(small)


def test_closing_the_sheet_returns_focus_to_its_tab(page, base_url):
    phone(page)
    S.open_route(page, base_url, "/")
    page.eval("document.querySelector('#tabbar [data-sheet=true]').focus()")
    page.press("Enter")
    page.wait_for("#desk-index.is-open", visible=True)
    page.press("Escape")
    page.wait_for(js="!document.querySelector('#desk-index').classList.contains('is-open')")
    assert page.eval("document.activeElement.matches('#tabbar [data-sheet=true]')"), \
        "after Escape focus is lost: " + page.eval("document.activeElement.tagName + ' ' + document.activeElement.className")
    page.press("Enter")
    page.wait_for("#desk-index.is-open", visible=True)
    page.press("Enter")  # focus starts on Close
    page.wait_for(js="!document.querySelector('#desk-index').classList.contains('is-open')")
    assert page.eval("document.activeElement.matches('#tabbar [data-sheet=true]')"), "after Close focus is lost"
