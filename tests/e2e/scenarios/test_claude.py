"""Claude Desk: today's technique, adoption state, the playbook filters, recipes, updates."""

import re

from tests.e2e.scenarios import support as S


def feature_rows(page):
    return page.eval("[...document.querySelectorAll('.rows li.row[data-story^=\"feature:\"]')].map((e) => e.dataset.story.slice(8))")


def matches(f, surface="all", job="all", text=""):
    return (surface == "all" or f["surface"] == surface) and (job == "all" or job in (f.get("jobs") or [])) and (
        not text or text.lower() in "{0} {1} {2}".format(f["title"], f.get("summary"), " ".join(f.get("tags") or [])).lower())


def tally(page):
    text = S.text_of(page, "#map-h + p")
    match = re.search(r"(\d+) in my workflow · (\d+) tried · (\d+) not tried", text)
    assert match, text
    return tuple(int(n) for n in match.groups())


def test_todays_technique_copies_its_prompt(page, base_url):
    S.open_route(page, base_url, "/claude")
    S.grant_clipboard(page, base_url)
    feature_id = page.eval("document.querySelector('#drill-h').closest('section').querySelector('.claude__title a').getAttribute('href').split('/').pop()")
    feature = next(f for f in S.playbook()["features"] if f["id"] == feature_id)
    section = "section.claude:has(#drill-h)"
    if not feature.get("example"):
        page.note("today's technique has no example to copy")
        return
    assert S.text_of(page, section + " pre") == re.sub(r"\s+", " ", feature["example"]).strip()
    assert S.text_of(page, section + " .copy") == "Copy"
    page.click(section + " .copy")
    S.wait_text(page, section + " .copy", "Copied")
    assert page.eval("document.querySelector('{0} .copy').hasAttribute('data-done')".format(section))
    assert S.read_clipboard(page) == feature["example"]


def test_adoption_persists_and_updates_the_map(page, base_url):
    S.open_route(page, base_url, "/claude")
    book = S.playbook()
    section = "section.claude:has(#drill-h)"
    feature_id = page.eval("document.querySelector('{0} .claude__title a').getAttribute('href').split('/').pop()".format(section))
    assert tally(page) == (0, 0, len(book["features"]))
    cell = ".fmap__cell[href='#/claude/feature/{0}']".format(feature_id)
    assert page.attr(cell, "data-state") == "none"
    S.click_button(page, section + " .seg", "Tried", tag="label")
    page.wait_for(js="(JSON.parse(localStorage.getItem('fl.claude') || '{{}}'))[{0!r}]?.state === 'tried'".format(feature_id))
    S.wait_text(page, "#toast", "come back in 1 day")
    page.wait_for(js="document.querySelector(\"{0}\").dataset.state === 'tried'".format(cell))
    assert tally(page) == (0, 1, len(book["features"]) - 1), tally(page)
    S.reload(page)
    # a tried technique leaves the drill (the next untried one comes up); its state is kept
    assert page.attr(cell, "data-state") == "tried"
    S.go(page, "/claude/feature/" + feature_id)
    assert page.eval("document.querySelector('.adopt input[value=tried]').checked")
    S.go(page, "/claude")
    assert page.attr(cell, "data-state") == "tried"
    assert tally(page) == (0, 1, len(book["features"]) - 1)
    # another feature, on its own page
    other = next(f for f in book["features"] if f["id"] != feature_id)
    S.go(page, "/claude/feature/" + other["id"])
    S.click_button(page, ".adopt .seg", "In my workflow", tag="label")
    page.wait_for(js="(JSON.parse(localStorage.getItem('fl.claude'))[{0!r}] || {{}}).state === 'habit'".format(other["id"]))
    S.go(page, "/claude")
    assert tally(page) == (1, 1, len(book["features"]) - 2), tally(page)
    assert page.attr(".fmap__cell[href='#/claude/feature/{0}']".format(other["id"]), "data-state") == "habit"
    # back to "not tried" removes it
    S.go(page, "/claude/feature/" + other["id"])
    S.click_button(page, ".adopt .seg", "Not tried", tag="label")
    page.wait_for(js="!(JSON.parse(localStorage.getItem('fl.claude'))[{0!r}])".format(other["id"]))


def test_playbook_filters_alone_and_combined(page, base_url):
    book = S.playbook()
    features = book["features"]
    S.open_route(page, base_url, "/claude/playbook")
    assert sorted(feature_rows(page)) == sorted(f["id"] for f in features)
    surface = max(book["surfaces"], key=lambda s: len([f for f in features if f["surface"] == s["id"]]))
    S.click_button(page, ".filters[aria-label=Product]", surface["name"])
    page.wait_for(js="location.hash.includes('surface={0}')".format(surface["id"]))
    assert sorted(feature_rows(page)) == sorted(f["id"] for f in features if matches(f, surface=surface["id"]))
    jobs = [j for j in book["jobs"] if any(matches(f, surface=surface["id"], job=j["id"]) for f in features)]
    job = max(jobs, key=lambda j: len([f for f in features if matches(f, surface=surface["id"], job=j["id"])]))
    S.click_button(page, ".filters[aria-label=Job]", job["name"])
    page.wait_for(js="location.hash.includes('job={0}')".format(job["id"]))
    combined = sorted(f["id"] for f in features if matches(f, surface=surface["id"], job=job["id"]))
    assert sorted(feature_rows(page)) == combined
    S.reload(page)
    assert sorted(feature_rows(page)) == combined, "the filters did not survive a reload"
    # text, on top
    word = next(t for f in features if matches(f, surface=surface["id"], job=job["id"]) for t in S.tokenize(f["title"]) if len(t) >= 4)
    page.fill(".quickfind", word)
    page.wait_for(js="location.hash.includes('q={0}')".format(word))
    assert sorted(feature_rows(page)) == sorted(f["id"] for f in features if matches(f, surface["id"], job["id"], word))
    # state: mark one tried, filter by "Tried"
    target = feature_rows(page)[0]
    page.local_storage_set("fl.claude", {target: {"state": "tried", "at": 1, "box": 0, "due": 9e15}})
    S.reload(page)
    S.click_button(page, ".filters[aria-label='Where you are with it']", "Tried")
    page.wait_for(js="location.hash.includes('state=tried')")
    assert feature_rows(page) == [target]
    # every filter at once, then nothing matches -> Clear
    page.fill(".quickfind", "zzzzqx")
    page.wait_for(".notice")
    S.click_button(page, ".notice", "Clear the filters")
    page.wait_for(js="!location.hash.includes('?')")
    assert sorted(feature_rows(page)) == sorted(f["id"] for f in features)


def test_playbook_text_filter_alone(page, base_url):
    features = S.playbook()["features"]
    tag = features[0]["tags"][0] if features[0].get("tags") else S.tokenize(features[0]["title"])[0]
    S.open_route(page, base_url, "/claude/playbook?q=" + tag)
    assert page.eval("document.querySelector('.quickfind').value") == tag
    assert sorted(feature_rows(page)) == sorted(f["id"] for f in features if matches(f, text=tag))


def test_recipe_fields_fill_the_prompt(page, base_url):
    recipe = next(r for r in S.playbook()["recipes"] if r.get("fields") and r.get("template"))
    S.open_route(page, base_url, "/claude/recipe/" + recipe["id"])
    S.grant_clipboard(page, base_url)
    first, *rest = recipe["fields"]
    assert page.count(".builder textarea") == len(recipe["fields"])
    assert "{{" + first["name"] + "}}" in S.text_of(page, ".prompt pre")
    value = "the quarterly <b>numbers</b> & more"
    page.fill(".builder label:nth-child(1) textarea", value)
    page.wait_for(js="document.querySelector('.prompt pre').textContent.includes({0!r})".format(value))
    assert "{{" + first["name"] + "}}" not in S.text_of(page, ".prompt pre")
    assert not page.exists(".prompt pre b"), "a typed tag became markup"
    if rest:
        assert "{{" + rest[0]["name"] + "}}" in S.text_of(page, ".prompt pre"), "an unfilled slot vanished"
    page.click(".prompt .copy")
    S.wait_text(page, ".prompt .copy", "Copied")
    expected = re.sub(r"\{\{\s*" + re.escape(first["name"]) + r"\s*\}\}", lambda m: value, recipe["template"])
    assert S.read_clipboard(page) == expected


def test_update_rows_link_out_safely(page, base_url):
    entries = S.updates()["entries"]
    S.open_route(page, base_url, "/claude/updates")
    links = page.eval("[...document.querySelectorAll('ol.rows .row__title a')].map((a) => ({href: a.getAttribute('href'), target: a.target, rel: a.rel}))")
    assert len(links) == min(250, len(entries)), (len(links), len(entries))
    for link in links:
        assert link["href"].startswith("https://"), link
        assert link["target"] == "_blank" and {"noopener", "noreferrer"} <= set(link["rel"].split()), link
    surfaces = sorted(set(e["surface"] for e in entries))
    surface = max(surfaces, key=lambda s: len([e for e in entries if e["surface"] == s]))
    button = page.eval("(s) => [...document.querySelectorAll('.filters[aria-label=\"Filter by product\"] button')].findIndex((b) => b.querySelector('.chip__n') && +b.querySelector('.chip__n').textContent === s)",
                       len([e for e in entries if e["surface"] == surface]))
    assert button > 0
    page.click(".filters[aria-label='Filter by product'] button:nth-child({0})".format(button + 1))
    page.wait_for(js="location.hash.includes('surface=')")
    assert page.count("ol.rows li.row") == len([e for e in entries if e["surface"] == surface][:250])


def test_feature_page_docs_are_https(page, base_url):
    book = S.playbook()
    feature = max(book["features"], key=lambda f: len(f.get("docs") or []))
    S.open_route(page, base_url, "/claude/feature/" + feature["id"])
    docs = page.eval("[...document.querySelector('.detail__side .linklist').querySelectorAll('a')].map((a) => ({href: a.getAttribute('href'), text: a.textContent.trim(), rel: a.rel}))")
    assert len(docs) == len(feature["docs"]), (docs, feature["docs"])
    for link, doc in zip(docs, feature["docs"]):
        assert link["href"].startswith("https://"), link
        assert "noopener" in link["rel"]
    for href in page.eval("[...document.querySelectorAll('#view a[href]')].map((a) => a.getAttribute('href'))"):
        assert href.startswith(("https://", "#/")), "unexpected link on the feature page: " + href
    assert page.exists(".prose h2"), "the feature body did not render"
    if feature.get("example"):
        assert page.exists(".claude__work .prompt pre")
