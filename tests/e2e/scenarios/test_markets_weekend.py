"""Markets ledger and movers; the Weekend Review's papers."""

import re

from tests.e2e.scenarios import support as S

ROW_FACTS = (
    "[...document.querySelectorAll('table.mkt:not(.mkt--week) tbody tr')].map((tr) => ({"
    " name: tr.querySelector('.mkt__name b')?.textContent,"
    " last: tr.querySelector('.mkt__last')?.textContent,"
    " chg: tr.querySelector('.chg')?.textContent.replace(/\\s+/g, ' ').trim(),"
    " cls: tr.querySelector('.chg')?.className,"
    " arrow: tr.querySelector('.chg use')?.getAttribute('href'),"
    " points: (tr.querySelector('.spark polyline')?.getAttribute('points') || '').trim().split(/\\s+/).filter(Boolean).length,"
    " label: tr.querySelector('.spark')?.getAttribute('aria-label') }))"
)


def test_every_quote_row(page, base_url):
    m = S.markets()
    quotes = [q for g in m["groups"] for q in g.get("quotes") or []]
    S.open_route(page, base_url, "/markets")
    rows = page.eval(ROW_FACTS)
    assert len(rows) == len(quotes), (len(rows), len(quotes))
    groups = S.texts_of(page, "section.block .block__title")
    for group in m["groups"]:
        if group.get("quotes"):
            assert group["name"] in groups, (group["name"], groups)
    for row, q in zip(rows, quotes):
        assert row["name"] == (q.get("short") or q["name"]), (row, q["symbol"])
        assert re.fullmatch(r"[\d,]+\.\d{2,4}", row["last"] or ""), row
        pct = q.get("changePct")
        if pct is None:
            assert row["arrow"] == "#a-flat", row
        elif pct > 0:
            assert row["arrow"] == "#a-up" and row["chg"].startswith("+") and "up" in row["chg"], row
        elif pct < 0:
            assert row["arrow"] == "#a-down" and row["chg"].startswith("−") and "down" in row["chg"], row
        else:
            assert row["arrow"] == "#a-flat", row
        if pct is not None:
            assert "{0:.2f}%".format(abs(pct)) in row["chg"], (row, pct)
        good = [v for v in q.get("spark") or [] if isinstance(v, (int, float))]
        if len(good) >= 2:
            assert row["points"] == len(good), (row, len(good))
        assert row["label"] and q["name"] in row["label"], row


def test_movers(page, base_url):
    movers = S.markets().get("movers") or []
    S.open_route(page, base_url, "/markets")
    if not movers:
        assert not page.exists("#movers-h")
        return
    rows = page.eval("[...document.querySelector('#movers-h').closest('section').querySelectorAll('li.row')].map((li) => ({"
                     "symbol: li.querySelector('.row__aside b').textContent, link: li.querySelector('.row__sum a')?.getAttribute('href') || null,"
                     "arrow: li.querySelector('.chg use').getAttribute('href')}))")
    assert len(rows) == len(movers)
    for row, mover in zip(rows, movers):
        assert row["symbol"] == mover["symbol"]
        assert row["arrow"] == ("#a-up" if mover["changePct"] > 0 else "#a-down" if mover["changePct"] < 0 else "#a-flat")
        if mover.get("story"):
            assert row["link"] == "#/story/" + mover["story"]["id"], row
    linked = next((r for r in rows if r["link"]), None)
    if linked:
        page.click("a[href='{0}']".format(linked["link"]))
        S.wait_route(page, linked["link"])
        page.wait_for(".detail")
        assert page.eval("document.querySelector('h1').textContent") == "Who carried it"


def test_front_page_strip_matches_markets(page, base_url):
    S.open_route(page, base_url, "/")
    ed = S.edition()
    quotes = (ed.get("markets") or {}).get("quotes") or []
    if not quotes:
        page.note("this edition has no markets strip")
        return
    names = S.texts_of(page, ".ear--markets th")
    assert names == [q.get("short") or q["name"] for q in quotes[:5]], names


def test_weekend_papers_in_rank_order(page, base_url):
    week = S.weekend_index()["weeks"][0]["isoWeek"]
    issue = S.data("weekend/{0}.json".format(week))
    papers = issue["papers"]
    S.open_route(page, base_url, "/weekend")
    shown = page.eval("[...document.querySelectorAll('.papers .paper')].map((p) => ({rank: p.querySelector('.paper__rank').textContent,"
                      " href: p.querySelector('.paper__title a').getAttribute('href'), target: p.querySelector('.paper__title a').target,"
                      " title: p.querySelector('.paper__title').textContent, track: p.querySelector('.chip--solid').textContent}))")
    assert len(shown) == len(papers), (len(shown), len(papers))
    ranks = [int(p["rank"]) for p in shown]
    assert ranks == sorted(ranks) == [p["rank"] for p in papers], ranks
    for card, paper in zip(shown, papers):
        assert card["href"].startswith("https://arxiv.org/"), card
        assert card["target"] == "_blank"
        assert S.tokenize(card["title"]) == S.tokenize(paper["title"]), (card["title"], paper["title"])
    electronics = [p for p in papers if p["track"] == "electronics"]
    shown_electronics = [c for c in shown if c["track"].startswith("Electronics")]
    assert len(shown_electronics) == len(electronics)
    if len(papers) >= 5:
        assert len(electronics) >= 2, "the issue has fewer than two electronics papers: {0}".format([p["track"] for p in papers])
    for link in page.eval("[...document.querySelectorAll('.paper__foot a')].map((a) => a.getAttribute('href'))"):
        assert link.startswith("https://"), link
    runners = issue.get("runnersUp") or []
    if runners:
        assert page.count(".block li.row .row__title a[href*='arxiv.org']") >= len(runners)


def test_weekend_digest_lines_are_from_the_abstract(page, base_url):
    week = S.weekend_index()["weeks"][0]["isoWeek"]
    papers = S.data("weekend/{0}.json".format(week))["papers"]
    S.open_route(page, base_url, "/weekend/" + week)
    digests = page.eval("[...document.querySelectorAll('.paper')].map((p) => [...p.querySelectorAll('.paper__digest li')].map((li) => li.textContent))")
    for lines, paper in zip(digests, papers):
        abstract = " ".join(S.tokenize(paper.get("abstract") or ""))
        assert lines, "paper {0} has no digest".format(paper["id"])
        for line in lines:
            assert " ".join(S.tokenize(line)) in abstract, "digest line not lifted from the abstract: " + line
