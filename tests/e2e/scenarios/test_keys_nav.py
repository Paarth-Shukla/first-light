"""Single-key navigation, the search key, the Cmd/Ctrl+K palette, history and scroll."""

from tests.e2e.scenarios import support as S

PAGES = [("w", "#/wire", "The Wire"), ("m", "#/markets", "Markets"), ("r", "#/weekend", "Weekend Review"),
         ("c", "#/claude", "Claude Desk"), ("l", "#/clippings", "Clippings"), ("f", "#/", "No. ")]


def test_letter_keys_go_to_their_pages(page, base_url):
    S.open_route(page, base_url, "/settings")
    for key, route, title in PAGES:
        page.eval("document.activeElement && document.activeElement.blur()")
        page.press(key)
        page.wait_for(js="location.hash === {0!r} || (location.hash === '' && {0!r} === '#/')".format(route))
        S.wait_ready(page)
        assert title in page.title(), (key, page.title())
        current = page.eval("document.querySelector('.nav__main a[aria-current=page]')?.getAttribute('href')")
        assert current == route, (key, current)
    page.press("b")
    S.wait_route(page, "#/archive")
    page.press("?", ["Shift"])
    S.wait_route(page, "#/colophon")
    if not S.has_data("status.json"):
        S.forgive_missing(page, "status.json")


def test_slash_focuses_search(page, base_url):
    S.open_route(page, base_url, "/wire")
    page.press("/")
    assert page.eval("document.activeElement.id") == "q"
    S.go(page, "/claude/playbook")
    page.eval("document.activeElement.blur()")
    page.press("/")
    assert page.eval("document.activeElement.matches('.quickfind')"), "on the playbook / should focus its own filter"


def test_keys_do_nothing_while_typing(page, base_url):
    S.open_route(page, base_url, "/wire")
    page.click("#q")
    page.type("wmrclfnjx")
    assert page.eval("location.hash") == "#/wire"
    assert page.eval("document.querySelector('#q').value") == "wmrclfnjx"
    assert not page.eval("document.documentElement.hasAttribute('data-theme')"), "N toggled the theme while typing"
    assert page.local_storage_get("fl.read") in (None, "{}")
    page.press("Escape")
    assert page.eval("document.activeElement.id") != "q", "Escape should leave the field"
    page.press("w")
    S.wait_route(page, "#/wire")
    S.go(page, "/claude/recipe/" + S.playbook()["recipes"][0]["id"])
    if page.exists(".builder textarea"):
        page.click(".builder textarea")
        page.type("fl")
        assert page.eval("location.hash").startswith("#/claude/recipe/")


def test_palette_open_filter_enter(page, base_url):
    S.open_route(page, base_url, "/wire")
    page.press("j")
    focused = page.eval("document.activeElement.closest('[data-story]').dataset.story")
    page.press("k", ["Meta"])
    page.wait_for("#palette:not([hidden])")
    assert page.eval("document.activeElement.matches('.palette__input')")
    total = page.count(".palette__list li")
    page.type("markets")
    labels = S.texts_of(page, ".palette__list li span")
    assert 0 < len(labels) < total, labels
    assert all("markets" in label.lower() for label in labels), labels
    assert labels[0] == "Markets", labels
    page.press("Enter")
    S.wait_route(page, "#/markets")
    assert page.eval("document.querySelector('#palette').hidden")
    # Ctrl works too; Escape closes and puts focus back
    S.go(page, "/wire")
    page.press("j")
    focused = page.eval("document.activeElement.closest('[data-story]').dataset.story")
    page.press("k", ["Control"])
    page.wait_for("#palette:not([hidden])")
    page.press("Escape")
    assert page.eval("document.querySelector('#palette').hidden")
    assert page.eval("document.activeElement.closest('[data-story]')?.dataset.story") == focused, "focus was not restored"
    assert page.eval("location.hash") == "#/wire"


def test_palette_arrows_and_search_fallback(page, base_url):
    S.open_route(page, base_url, "/")
    page.press("k", ["Meta"])
    page.wait_for("#palette:not([hidden])")
    page.type("desk")
    page.press("ArrowDown")
    selected = S.text_of(page, ".palette__list [aria-selected=true] span")
    assert selected == S.texts_of(page, ".palette__list li span")[1], selected
    page.press("Backspace")
    page.press("Backspace")
    page.press("Backspace")
    page.press("Backspace")
    page.type("zzqv")
    labels = S.texts_of(page, ".palette__list li span")
    assert labels == ["Search every edition for “zzqv”"], labels
    page.press("Enter")
    S.wait_route(page, "#/search")
    assert S.query_of(page)["q"] == "zzqv"


def test_palette_desk_commands(page, base_url):
    S.open_route(page, base_url, "/")
    section = S.manifest()["sections"][2]
    page.press("k", ["Meta"])
    page.wait_for("#palette:not([hidden])")
    page.type(section["name"])
    page.wait_for(js="[...document.querySelectorAll('.palette__list li span')].some((s) => s.textContent.endsWith({0!r}))".format(section["name"]))
    page.eval("(n) => [...document.querySelectorAll('.palette__list li')].find((li) => li.querySelector('span').textContent.endsWith(n)).setAttribute('data-pick', 1)", section["name"])
    page.click(".palette__list li[data-pick]")
    S.wait_route(page, "#/s/" + section["id"])


def test_back_and_forward(page, base_url):
    S.open_route(page, base_url, "/")
    S.go(page, "/wire")
    S.go(page, "/markets")
    page.eval("history.back()")
    S.wait_route(page, "#/wire")
    assert "The Wire" in page.title()
    page.eval("history.back()")
    page.wait_for(js="location.hash === '#/' || location.hash === ''")
    S.wait_ready(page)
    assert page.exists(".lead")
    page.eval("history.forward()")
    S.wait_route(page, "#/wire")
    page.wait_for(".wire__row")


def test_navigation_scrolls_to_top(page, base_url):
    S.open_route(page, base_url, "/")
    page.eval("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for(js="window.scrollY > 500")
    page.click("footer.end a[href='#/wire']")
    S.wait_route(page, "#/wire")
    page.wait_for(js="window.scrollY === 0", timeout=3)
    page.eval("window.scrollTo(0, 2000)")
    page.press("m")
    S.wait_route(page, "#/markets")
    page.wait_for(js="window.scrollY === 0", timeout=3)


def test_focus_moves_to_the_view_after_navigation(page, base_url):
    S.open_route(page, base_url, "/")
    page.click(".nav__main a[href='#/markets']")
    S.wait_route(page, "#/markets")
    page.wait_for(js="document.activeElement.id === 'view' || document.activeElement.closest('#mast')")
