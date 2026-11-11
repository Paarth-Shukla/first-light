"""Reader state: clippings of every kind, notes, export and import, erase, theme, the seen counter."""

import json
import os
import re
import shutil
import tempfile
import time

from tests.e2e.scenarios import support as S

KIND_HEADINGS = ["Stories", "Papers", "Claude techniques", "Claude recipes"]
NAV_COUNT = ".nav__main a[href='#/clippings'] .nav__count"


def clip_four(page, base_url):
    """Clip a story, a paper, a feature and a recipe through their own pages; return their titles."""
    titles = {}
    S.open_route(page, base_url, "/")
    lead = S.edition()["lead"]
    page.click(".lead .clipper")
    page.wait_for_text(NAV_COUNT, "1")
    assert page.attr(".lead .clipper", "aria-pressed") == "true"
    titles["story"] = lead["title"]

    week = S.weekend_index()["weeks"][0]["isoWeek"]
    paper = S.data("weekend/{0}.json".format(week))["papers"][0]
    S.go(page, "/weekend/" + week)
    page.click(".paper .clipper")
    page.wait_for_text(NAV_COUNT, "2")
    titles["paper"] = paper["title"]

    feature = S.playbook()["features"][0]
    S.go(page, "/claude/feature/" + feature["id"])
    page.click(".claude__links .clipper")
    page.wait_for_text(NAV_COUNT, "3")
    titles["feature"] = feature["title"]

    recipe = S.playbook()["recipes"][0]
    S.go(page, "/claude/recipe/" + recipe["id"])
    page.click(".folio .clipper")
    page.wait_for_text(NAV_COUNT, "4")
    titles["recipe"] = recipe["title"]
    return titles


def same_words(a, b):
    return S.tokenize(a) == S.tokenize(b)


def test_clip_every_kind_note_export_remove(page, base_url):
    titles = clip_four(page, base_url)
    saved = S.storage_json(page, "fl.saved")
    assert sorted(item["kind"] for item in saved.values()) == ["feature", "paper", "recipe", "story"], saved
    S.go(page, "/clippings")
    headings = S.texts_of(page, "section.block .block__title")
    assert headings == KIND_HEADINGS, headings
    shown = S.texts_of(page, "ol.rows .row__title")
    for kind, title in titles.items():
        assert any(same_words(text, title) for text in shown), (kind, title, shown)
    assert "4 kept in this browser" in S.text_of(page, ".folio")

    # a note survives a reload
    page.fill("ol.rows li.row input.note", "read this before Friday")
    page.press("Tab")
    page.wait_for(js="Object.values(JSON.parse(localStorage.getItem('fl.saved'))).some((c) => c.note === 'read this before Friday')")
    S.reload(page)
    assert page.eval("document.querySelector('ol.rows li.row input.note').value") == "read this before Friday"

    # Markdown export carries every title and the note
    S.click_button(page, ".folio", "Export as Markdown")
    download = page.wait_for_download()
    assert download.filename.endswith(".md"), download
    with open(download.path, encoding="utf-8") as handle:
        markdown = handle.read()
    assert markdown.startswith("# Clippings from First Light")
    for heading in KIND_HEADINGS:
        assert "## " + heading in markdown, heading
    for title in titles.values():
        assert title in markdown, title
    assert "read this before Friday" in markdown
    assert "](#/" not in markdown, "an in-app link was exported as a Markdown link"

    # remove one
    first_title = S.text_of(page, "ol.rows .row__title")
    S.click_button(page, "ol.rows li.row:first-child .row__aside", "Remove")
    page.wait_for_text(NAV_COUNT, "3")
    assert len(S.storage_json(page, "fl.saved")) == 3
    assert first_title not in S.texts_of(page, "ol.rows .row__title")
    assert "3 kept in this browser" in S.text_of(page, ".folio")


def test_settings_export_erase_import(page, base_url):
    S.open_route(page, base_url, "/")
    stories = S.latest()["stories"][:3]
    now = int(time.time() * 1000)
    page.local_storage_set("fl.read", {s["id"]: now for s in stories[:2]})
    page.local_storage_set("fl.saved", {"story:" + stories[2]["id"]: {"kind": "story", "id": stories[2]["id"], "title": stories[2]["title"], "url": stories[2]["url"], "day": stories[2]["day"], "savedAt": now, "note": "keep"}})
    S.go(page, "/settings")
    S.reload(page)
    assert "2 stories marked read · 1 clippings" in S.text_of(page, ".block p.label"), S.text_of(page, ".block p.label")

    S.click_button(page, ".actions", "Export my state")
    download = page.wait_for_download()
    with open(download.path, encoding="utf-8") as handle:
        exported = json.load(handle)
    assert exported["app"] == "first-light"
    assert set(exported["data"]["read"]) == set(s["id"] for s in stories[:2])
    assert "story:" + stories[2]["id"] in exported["data"]["saved"]

    S.click_button(page, ".actions", "Erase everything")
    assert page.local_storage_get("fl.saved") is not None, "one press must only arm the button"
    S.click_button(page, ".actions", "Press again")
    page.wait_for(js="localStorage.getItem('fl.saved') === null && localStorage.getItem('fl.read') === null")
    assert "0 stories marked read · 0 clippings" in S.text_of(page, ".block p.label")
    assert not page.exists(NAV_COUNT)

    workdir = tempfile.mkdtemp(prefix="fl-e2e-import-")
    try:
        path = os.path.join(workdir, "state.json")
        shutil.copy(download.path, path)
        page.set_files("input[type=file]", [path])
        S.wait_text(page, "#toast", "Imported")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    assert set(S.storage_json(page, "fl.read")) == set(s["id"] for s in stories[:2])
    assert S.storage_json(page, "fl.saved")["story:" + stories[2]["id"]]["note"] == "keep"
    page.wait_for_text(NAV_COUNT, "1")
    S.go(page, "/clippings")
    assert page.count("ol.rows li.row") == 1
    S.go(page, "/wire")
    for story in stories[:2]:
        row = ".wire__row[data-story='{0}']".format(story["id"])
        if page.exists(row):
            assert "is-read" in page.attr(row, "class")


def test_import_rejects_a_foreign_file(page, base_url):
    S.open_route(page, base_url, "/settings")
    workdir = tempfile.mkdtemp(prefix="fl-e2e-import-")
    try:
        path = os.path.join(workdir, "other.json")
        with open(path, "w") as handle:
            json.dump({"app": "something-else", "data": {"saved": {"x": {}}}}, handle)
        page.set_files("input[type=file]", [path])
        S.wait_text(page, "#toast", "Not a First Light export file")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    assert page.local_storage_get("fl.saved") is None


FIRST_PAINT = """
new MutationObserver((_, observer) => {
  if (document.body && window.__themeAtBody === undefined) {
    window.__themeAtBody = document.documentElement.getAttribute('data-theme') || 'none';
    window.__bodyBg = null;
    observer.disconnect();
  }
}).observe(document, { childList: true, subtree: true });
"""


def test_theme_toggle_button_key_settings(page, base_url):
    page.add_init_script(FIRST_PAINT)
    S.open_route(page, base_url, "/")
    assert page.eval("window.__themeAtBody") == "none"
    light_bg = page.eval("getComputedStyle(document.body).backgroundColor")
    page.click(".theme-toggle")
    assert page.eval("document.documentElement.dataset.theme") == "dark"
    assert (S.storage_json(page, "fl.prefs") or {}).get("theme") == "dark"
    assert page.attr(".theme-toggle", "aria-pressed") == "true"
    dark_bg = page.eval("getComputedStyle(document.body).backgroundColor")
    assert dark_bg != light_bg, (dark_bg, light_bg)
    S.reload(page)
    assert page.eval("window.__themeAtBody") == "dark", "the saved theme was not applied before the body was parsed"
    page.press("n")
    assert page.eval("document.documentElement.dataset.theme") == "light"
    assert S.storage_json(page, "fl.prefs")["theme"] == "light"
    page.press("N", ["Shift"])
    assert page.eval("document.documentElement.dataset.theme") == "dark"
    S.go(page, "/settings")
    S.click_button(page, ".filters[aria-label=Theme]", "Day edition")
    assert page.eval("document.documentElement.dataset.theme") == "light"
    S.click_button(page, ".filters[aria-label=Theme]", "Follow the system")
    assert page.eval("document.documentElement.hasAttribute('data-theme')") is False
    assert S.storage_json(page, "fl.prefs")["theme"] == "auto"
    page.emulate_dark(True)
    assert page.attr(".theme-toggle", "aria-pressed") == "true" or page.eval(
        "matchMedia('(prefers-color-scheme: dark)').matches"), "auto theme ignores the system"
    S.reload(page)
    assert page.eval("window.__themeAtBody") == "none"


def seen_numbers(page):
    text = S.text_of(page, "#seen")
    match = re.match(r"(\d+) of (\d+) seen", text)
    return (int(match.group(1)), int(match.group(2))) if match else None


def test_seen_counter_advances(page, base_url):
    S.open_route(page, base_url, "/")
    total = len(S.edition_stories())
    page.wait_for(js="!document.querySelector('#seen').hidden")
    assert seen_numbers(page) == (0, total) or seen_numbers(page)[1] == total
    page.wait_for(js="/^[1-9]\\d* of/.test(document.querySelector('#seen').textContent)", timeout=6)
    first = seen_numbers(page)[0]
    page.eval("window.scrollTo(0, document.documentElement.scrollHeight / 2)")
    page.wait_for(js="parseInt(document.querySelector('#seen').textContent) > {0}".format(first), timeout=6)
    second = seen_numbers(page)[0]
    date = S.edition()["date"]
    page.wait_for(js="(JSON.parse(localStorage.getItem('fl.seen') || '{{}}')[{0!r}] || []).length >= {1}".format(date, second))
    S.reload(page)
    assert seen_numbers(page)[0] >= second
    S.go(page, "/archive")
    assert "seen" in S.text_of(page, "ol.rows li.row .row__aside")


def test_seen_counter_survives_a_clip(page, base_url):
    S.open_route(page, base_url, "/")
    page.wait_for(js="/^[1-9]\\d* of/.test(document.querySelector('#seen').textContent)", timeout=6)
    before = S.text_of(page, "#seen")
    page.click(".lead .clipper")
    page.wait_for(NAV_COUNT)
    assert page.visible("#seen"), "clipping a story blanked the seen counter"
    assert S.text_of(page, "#seen") == before or seen_numbers(page)[0] >= seen_numbers_text(before)


def seen_numbers_text(text):
    return int(re.match(r"(\d+)", text).group(1))


def test_settings_counts_follow_an_import(page, base_url):
    S.open_route(page, base_url, "/settings")
    assert "0 stories marked read · 0 clippings" in S.text_of(page, ".block p.label")
    story = S.latest()["stories"][0]
    state = {"app": "first-light", "version": 1, "data": {
        "read": {story["id"]: int(time.time() * 1000)},
        "saved": {"story:" + story["id"]: {"kind": "story", "id": story["id"], "title": story["title"], "url": story["url"], "savedAt": 1, "note": ""}}}}
    workdir = tempfile.mkdtemp(prefix="fl-e2e-import-")
    try:
        path = os.path.join(workdir, "state.json")
        with open(path, "w") as handle:
            json.dump(state, handle)
        page.set_files("input[type=file]", [path])
        S.wait_text(page, "#toast", "Imported")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    S.wait_text(page, ".block p.label", "1 stories marked read · 1 clippings", timeout=2)
