"""The executable contract: every public JSON shape in docs/ARCHITECTURE.md, checked.

Each stage has its own unit tests; this module checks what crosses a stage
boundary or reaches the browser. The validators are plain functions that
append human-readable problems to a list, so one run reports every violation
at once. They run against:

- a small committed snapshot of a real run (``tests/fixtures/contracts/public``),
- deliberately broken copies of it, to prove each rule can fail,
- the live ``data/public`` directory when it exists (skipped otherwise, as in CI).

A shape may carry extra keys (stages document their additions); only the
contract's keys, types, enums, ranges and cross-references are enforced.
"""

import copy
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline.core import config

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "contracts" / "public"
LIVE = ROOT / "data" / "public"

SECTION_IDS = ("world", "india", "ai", "ml", "llm", "labs", "companies", "markets", "india-markets", "science")
SIGNALS = ("breadth", "tier", "recency", "velocity", "attention", "editorial")
QUOTE_KINDS = ("index", "stock", "fx", "commodity", "crypto")
MARKET_GROUPS = ("india", "us", "world", "watch-in", "watch-us", "fx", "commodities", "crypto")
UPDATE_SURFACES = ("apps", "code", "platform", "cowork", "models", "news", "learn")
UPDATE_KINDS = ("feature", "release", "article", "video")
FEATURE_SURFACES = ("apps", "code", "platform", "cowork", "integrations")
LEVELS = ("starter", "intermediate", "power")
PAPER_SIGNALS = ("hfUpvotes", "hnPoints", "citations", "githubStars", "mentions")
DIGEST_KEYS = ("gist", "problem", "method", "result")
SHARD_KINDS = ("story", "paper", "update")
STATIC_KINDS = ("feature", "recipe", "term")
DOC_KEYS = ("i", "k", "t", "s", "c", "e", "o", "n", "d", "u", "x")

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH = re.compile(r"^\d{4}-\d{2}$")
WEEK = re.compile(r"^\d{4}-W\d{2}$")
STORY_ID = re.compile(r"^s[0-9a-f]{10}$")
THREAD_ID = re.compile(r"^t[0-9a-f]{10}$")
ARXIV_ID = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
WEB_URL = re.compile(r"^https?://\S+$")
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")

EDITION_FRONT, EDITION_BRIEFS, EDITION_PER_SECTION, EDITION_STRIP = 4, 10, 3, 8


# ---- primitive checks -------------------------------------------------------------------------


def _is_num(value):
    """A JSON number (bool is an int in Python but not a number in the contract)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _keys(obj, keys, where, errors):
    """Require a dict holding ``keys``; returns False (after reporting) when it is not a dict."""
    if not isinstance(obj, dict):
        errors.append("%s: expected an object, got %s" % (where, type(obj).__name__))
        return False
    missing = [key for key in keys if key not in obj]
    if missing:
        errors.append("%s: missing %s" % (where, ", ".join(missing)))
    return True


def _check(ok, where, message, errors):
    if not ok:
        errors.append("%s: %s" % (where, message))


def _str(value, where, errors, empty=True, pattern=None, nullable=False):
    if value is None and nullable:
        return
    if not isinstance(value, str) or (not empty and not value.strip()):
        errors.append("%s: expected a%s string, got %r" % (where, "" if empty else " non-empty", value))
    elif pattern is not None and not pattern.match(value):
        errors.append("%s: %r does not match %s" % (where, value, pattern.pattern))


def _num(value, where, errors, low=None, high=None, nullable=False):
    if value is None and nullable:
        return
    if not _is_num(value):
        errors.append("%s: expected a number, got %r" % (where, value))
    elif (low is not None and value < low) or (high is not None and value > high):
        errors.append("%s: %r outside %s..%s" % (where, value, low, high))


def _str_list(value, where, errors, allowed=None):
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append("%s: expected a list of strings, got %r" % (where, value))
        return
    if allowed is not None:
        bad = [item for item in value if item not in allowed]
        _check(not bad, where, "unknown values %s" % bad, errors)


def _get(obj, key):
    return obj.get(key) if isinstance(obj, dict) else None


# ---- stories ----------------------------------------------------------------------------------


def validate_story(story, where, errors):
    """A Story (contract: Public: stories)."""
    keys = ("id", "title", "summary", "url", "image", "section", "sections", "entities", "tickers",
            "publishedAt", "updatedAt", "day", "sources", "sourceCount", "score", "signals", "why", "thread")
    if not _keys(story, keys, where, errors):
        return
    _str(story.get("id"), where + ".id", errors, pattern=STORY_ID)
    _str(story.get("title"), where + ".title", errors, empty=False)
    _str(story.get("summary"), where + ".summary", errors)
    _str(story.get("url"), where + ".url", errors, pattern=WEB_URL)
    _str(story.get("image"), where + ".image", errors, pattern=WEB_URL, nullable=True)
    _check(story.get("section") in SECTION_IDS, where, "section %r is not a section id" % story.get("section"), errors)
    _str_list(story.get("sections"), where + ".sections", errors, allowed=SECTION_IDS)
    if isinstance(story.get("sections"), list):
        _check(story.get("section") in story["sections"], where, "section not in sections", errors)
        _check(len(set(story["sections"])) == len(story["sections"]), where, "sections repeat", errors)
    _str_list(story.get("entities"), where + ".entities", errors)
    _str_list(story.get("tickers"), where + ".tickers", errors)
    _str(story.get("publishedAt"), where + ".publishedAt", errors, pattern=ISO)
    _str(story.get("updatedAt"), where + ".updatedAt", errors, pattern=ISO)
    if all(isinstance(story.get(key), str) for key in ("publishedAt", "updatedAt")):
        _check(story["publishedAt"] <= story["updatedAt"], where, "publishedAt after updatedAt", errors)
    _str(story.get("day"), where + ".day", errors, pattern=DATE)
    sources = story.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("%s.sources: expected a non-empty list" % where)
        sources = []
    for index, source in enumerate(sources):
        at = "%s.sources[%d]" % (where, index)
        if _keys(source, ("id", "name", "tier", "title", "url", "publishedAt"), at, errors):
            _str(source.get("id"), at + ".id", errors, empty=False)
            _str(source.get("name"), at + ".name", errors, empty=False)
            _check(source.get("tier") in (1, 2, 3), at, "tier %r not 1-3" % source.get("tier"), errors)
            _str(source.get("publishedAt"), at + ".publishedAt", errors, pattern=ISO)
    count = story.get("sourceCount")
    _check(_is_int(count) and count >= max(1, len(sources)), where,
           "sourceCount %r must be an int >= the %d listed sources" % (count, len(sources)), errors)
    _num(story.get("score"), where + ".score", errors, 0, 100)
    signals = story.get("signals")
    if _keys(signals, SIGNALS, where + ".signals", errors):
        for name in SIGNALS:
            _num(signals.get(name), "%s.signals.%s" % (where, name), errors, 0, 1)
    why = story.get("why")
    _str_list(why, where + ".why", errors)
    _check(not isinstance(why, list) or len(why) <= 3, where, "more than three reasons in why", errors)
    _validate_thread(story.get("thread"), where + ".thread", errors)


def _validate_thread(thread, where, errors):
    if thread is None:
        return
    if not _keys(thread, ("id", "day", "history"), where, errors):
        return
    _str(thread.get("id"), where + ".id", errors, pattern=THREAD_ID)
    _check(_is_int(thread.get("day")) and thread["day"] >= 1, where, "day %r is not a 1-based int" % thread.get("day"), errors)
    history = thread.get("history")
    if not isinstance(history, list) or len(history) > 6:
        errors.append("%s.history: expected a list of at most 6" % where)
        return
    for index, entry in enumerate(history):
        at = "%s.history[%d]" % (where, index)
        if _keys(entry, ("date", "id", "title"), at, errors):
            _str(entry.get("date"), at + ".date", errors, pattern=DATE)
            _str(entry.get("id"), at + ".id", errors, pattern=STORY_ID)
    dates = [_get(entry, "date") for entry in history]
    if all(isinstance(date, str) for date in dates):
        _check(dates == sorted(dates), where, "history is not oldest first", errors)


def validate_stories_day(doc, name, errors):
    """``public/stories/<date>.json``: the day's stories, filed under that day."""
    where = "stories/%s.json" % name
    if not _keys(doc, ("date", "generatedAt", "stories"), where, errors):
        return []
    _check(doc.get("date") == name, where, "date %r does not match the file name" % doc.get("date"), errors)
    _str(doc.get("generatedAt"), where + ".generatedAt", errors, pattern=ISO)
    stories = doc.get("stories") if isinstance(doc.get("stories"), list) else []
    for index, story in enumerate(stories):
        validate_story(story, "%s[%d]" % (where, index), errors)
        _check(_get(story, "day") == name, "%s[%d]" % (where, index), "day %r filed under %s" % (_get(story, "day"), name), errors)
    return stories


def validate_latest(doc, errors):
    """``public/latest.json``: the hot set, score-descending, plus trending and section counts."""
    where = "latest.json"
    if not _keys(doc, ("generatedAt", "stories", "trending", "sectionCounts"), where, errors):
        return
    _str(doc.get("generatedAt"), where + ".generatedAt", errors, pattern=ISO)
    stories = doc.get("stories") if isinstance(doc.get("stories"), list) else []
    _check(len(stories) <= 500, where, "more than 500 stories", errors)
    for index, story in enumerate(stories):
        validate_story(story, "%s.stories[%d]" % (where, index), errors)
    scores = [_get(story, "score") for story in stories]
    if all(_is_num(score) for score in scores):
        _check(scores == sorted(scores, reverse=True), where, "stories are not score-descending", errors)
    ids = [_get(story, "id") for story in stories]
    _check(len(ids) == len(set(ids)), where, "a story appears twice", errors)
    trending = doc.get("trending") if isinstance(doc.get("trending"), list) else []
    for index, row in enumerate(trending):
        at = "%s.trending[%d]" % (where, index)
        if _keys(row, ("entity", "name", "count", "baseline", "ratio"), at, errors):
            _str(row.get("entity"), at + ".entity", errors, empty=False)
            _num(row.get("count"), at + ".count", errors, 0)
            _num(row.get("baseline"), at + ".baseline", errors, 0)
            _num(row.get("ratio"), at + ".ratio", errors, 0)
    counts = doc.get("sectionCounts")
    if isinstance(counts, dict):
        bad = [key for key in counts if key not in SECTION_IDS]
        _check(not bad, where + ".sectionCounts", "unknown sections %s" % bad, errors)
        _check(all(_is_int(value) and value >= 0 for value in counts.values()), where + ".sectionCounts", "counts must be ints >= 0", errors)
    else:
        errors.append("%s.sectionCounts: expected an object" % where)


# ---- editions ---------------------------------------------------------------------------------


def validate_edition(doc, name, errors):
    """``public/editions/<date>.json``: the frozen paper and its placement rules."""
    where = "editions/%s.json" % name
    keys = ("date", "number", "generatedAt", "headline", "lead", "front", "briefs", "sections",
            "markets", "claude", "weekend", "stats")
    if not _keys(doc, keys, where, errors):
        return
    _check(doc.get("date") == name, where, "date %r does not match the file name" % doc.get("date"), errors)
    _check(_is_int(doc.get("number")) and doc["number"] >= 1, where, "number must be an int >= 1", errors)
    _str(doc.get("generatedAt"), where + ".generatedAt", errors, pattern=ISO)
    _str(doc.get("headline"), where + ".headline", errors, empty=False)
    placed = []
    validate_story(doc.get("lead"), where + ".lead", errors)
    placed.append(("lead", doc.get("lead")))
    front = doc.get("front") if isinstance(doc.get("front"), list) else []
    _check(len(front) <= EDITION_FRONT, where, "front has %d stories" % len(front), errors)
    briefs = doc.get("briefs") if isinstance(doc.get("briefs"), list) else []
    _check(len(briefs) <= EDITION_BRIEFS, where, "briefs has %d stories" % len(briefs), errors)
    for label, group in (("front", front), ("briefs", briefs)):
        for index, story in enumerate(group):
            validate_story(story, "%s.%s[%d]" % (where, label, index), errors)
            placed.append((label, story))
    per_section = {}
    for story in front:
        per_section[_get(story, "section")] = per_section.get(_get(story, "section"), 0) + 1
    crowded = [section for section, count in per_section.items() if count > 2]
    _check(not crowded, where + ".front", "more than two stories from %s" % crowded, errors)
    _validate_edition_sections(doc.get("sections"), where, errors, placed)
    _check_placed_once(placed, where, errors)
    _validate_edition_extras(doc, where, errors)


def _validate_edition_sections(sections, where, errors, placed):
    if not isinstance(sections, list):
        errors.append("%s.sections: expected a list" % where)
        return
    ids = [_get(section, "id") for section in sections]
    _check(all(section_id in SECTION_IDS for section_id in ids), where + ".sections", "unknown section ids in %s" % ids, errors)
    _check(len(ids) == len(set(ids)), where + ".sections", "a section repeats", errors)
    order = [SECTION_IDS.index(section_id) for section_id in ids if section_id in SECTION_IDS]
    _check(order == sorted(order), where + ".sections", "sections are not in canonical order", errors)
    for index, section in enumerate(sections):
        at = "%s.sections[%d]" % (where, index)
        if not _keys(section, ("id", "name", "stories"), at, errors):
            continue
        stories = section.get("stories") if isinstance(section.get("stories"), list) else []
        _check(len(stories) <= EDITION_PER_SECTION, at, "more than %d stories" % EDITION_PER_SECTION, errors)
        for number, story in enumerate(stories):
            validate_story(story, "%s.stories[%d]" % (at, number), errors)
            placed.append((section.get("id"), story))


def _check_placed_once(placed, where, errors):
    """No story twice, and no two stories from one thread, anywhere in the paper."""
    seen, threads = {}, {}
    for slot, story in placed:
        story_id = _get(story, "id")
        if story_id in seen:
            errors.append("%s: story %s placed in %s and %s" % (where, story_id, seen[story_id], slot))
        seen[story_id] = slot
        thread_id = _get(_get(story, "thread"), "id")
        if thread_id is not None:
            if thread_id in threads and threads[thread_id] != story_id:
                errors.append("%s: thread %s has two stories (%s, %s)" % (where, thread_id, threads[thread_id], story_id))
            threads[thread_id] = story_id


def _validate_edition_extras(doc, where, errors):
    markets = doc.get("markets")
    if markets is not None and _keys(markets, ("asOf", "quotes"), where + ".markets", errors):
        _str(markets.get("asOf"), where + ".markets.asOf", errors, pattern=ISO)
        quotes = markets.get("quotes") if isinstance(markets.get("quotes"), list) else []
        _check(len(quotes) <= EDITION_STRIP, where + ".markets", "more than %d quotes" % EDITION_STRIP, errors)
        for index, quote in enumerate(quotes):
            validate_quote(quote, "%s.markets.quotes[%d]" % (where, index), errors)
    claude = doc.get("claude")
    if claude is not None and _keys(claude, ("kind", "update", "featureId"), where + ".claude", errors):
        _check(claude.get("kind") in ("update", "feature"), where + ".claude", "kind %r" % claude.get("kind"), errors)
        if claude.get("kind") == "update":
            validate_update(claude.get("update"), where + ".claude.update", errors)
        else:
            _str(claude.get("featureId"), where + ".claude.featureId", errors, empty=False)
    weekend = doc.get("weekend")
    if weekend is not None and _keys(weekend, ("isoWeek", "title"), where + ".weekend", errors):
        _str(weekend.get("isoWeek"), where + ".weekend.isoWeek", errors, pattern=WEEK)
    stats = doc.get("stats")
    if _keys(stats, ("storiesConsidered", "sourcesOk", "sourcesTotal", "readMinutes"), where + ".stats", errors):
        for key in ("storiesConsidered", "sourcesOk", "sourcesTotal", "readMinutes"):
            _check(_is_int(stats.get(key)) and stats[key] >= 0, where + ".stats", "%s must be an int >= 0" % key, errors)
        if _is_int(stats.get("sourcesOk")) and _is_int(stats.get("sourcesTotal")):
            _check(stats["sourcesOk"] <= stats["sourcesTotal"], where + ".stats", "more sources ok than total", errors)


def validate_editions_index(doc, names, errors):
    """``public/editions/index.json`` lists exactly the edition files, newest first."""
    where = "editions/index.json"
    if not _keys(doc, ("editions",), where, errors):
        return
    rows = doc.get("editions") if isinstance(doc.get("editions"), list) else []
    dates = [_get(row, "date") for row in rows]
    _check(dates == sorted(names, reverse=True), where, "lists %s, files are %s" % (dates, sorted(names, reverse=True)), errors)
    for index, row in enumerate(rows):
        _check(_is_int(_get(row, "number")), "%s[%d]" % (where, index), "number must be an int", errors)


# ---- markets ----------------------------------------------------------------------------------


def validate_quote(quote, where, errors):
    """A Quote (contract: Public: markets)."""
    keys = ("symbol", "name", "short", "kind", "currency", "price", "change", "changePct", "spark",
            "asOf", "exchange", "entity", "high52", "low52", "stale")
    if not _keys(quote, keys, where, errors):
        return
    _str(quote.get("symbol"), where + ".symbol", errors, empty=False)
    _str(quote.get("name"), where + ".name", errors, empty=False)
    _check(quote.get("kind") in QUOTE_KINDS, where, "kind %r" % quote.get("kind"), errors)
    _num(quote.get("price"), where + ".price", errors, 0)
    _num(quote.get("change"), where + ".change", errors, nullable=True)
    _num(quote.get("changePct"), where + ".changePct", errors, -100, 1000, nullable=True)
    spark = quote.get("spark")
    _check(isinstance(spark, list) and len(spark) <= 32 and all(_is_num(v) for v in spark), where,
           "spark must be at most 32 numbers", errors)
    _str(quote.get("asOf"), where + ".asOf", errors, pattern=ISO)
    _str(quote.get("entity"), where + ".entity", errors, nullable=True)
    _num(quote.get("high52"), where + ".high52", errors, 0, nullable=True)
    _num(quote.get("low52"), where + ".low52", errors, 0, nullable=True)
    _check(isinstance(quote.get("stale"), bool), where, "stale must be a boolean", errors)


def validate_markets(doc, errors):
    """``public/markets.json``: groups of quotes, the strip and the movers."""
    where = "markets.json"
    if not _keys(doc, ("generatedAt", "stale", "groups", "strip", "movers"), where, errors):
        return
    _str(doc.get("generatedAt"), where + ".generatedAt", errors, pattern=ISO)
    _check(isinstance(doc.get("stale"), bool), where, "stale must be a boolean", errors)
    symbols = set()
    groups = doc.get("groups") if isinstance(doc.get("groups"), list) else []
    for index, group in enumerate(groups):
        at = "%s.groups[%d]" % (where, index)
        if not _keys(group, ("id", "name", "quotes"), at, errors):
            continue
        _check(group.get("id") in MARKET_GROUPS, at, "unknown group %r" % group.get("id"), errors)
        for number, quote in enumerate(group.get("quotes") or []):
            validate_quote(quote, "%s.quotes[%d]" % (at, number), errors)
            symbols.add(_get(quote, "symbol"))
    _str_list(doc.get("strip"), where + ".strip", errors, allowed=symbols)
    movers = doc.get("movers") if isinstance(doc.get("movers"), list) else []
    for index, mover in enumerate(movers):
        at = "%s.movers[%d]" % (where, index)
        if _keys(mover, ("symbol", "name", "changePct", "story"), at, errors):
            _check(mover.get("symbol") in symbols, at, "mover %r is not a published quote" % mover.get("symbol"), errors)
            _num(mover.get("changePct"), at + ".changePct", errors)
            story = mover.get("story")
            if story is not None and _keys(story, ("id", "title", "sourceCount"), at + ".story", errors):
                _str(story.get("id"), at + ".story.id", errors, pattern=STORY_ID)


# ---- weekend ----------------------------------------------------------------------------------


def validate_paper(paper, where, errors):
    """A Paper (contract: Public: weekend)."""
    keys = ("id", "title", "authors", "primary", "categories", "track", "published", "abstract",
            "digest", "signals", "score", "why", "links", "rank")
    if not _keys(paper, keys, where, errors):
        return
    _str(paper.get("id"), where + ".id", errors, pattern=ARXIV_ID)
    _str(paper.get("title"), where + ".title", errors, empty=False)
    _str_list(paper.get("authors"), where + ".authors", errors)
    _str(paper.get("primary"), where + ".primary", errors, empty=False)
    _str_list(paper.get("categories"), where + ".categories", errors)
    _check(paper.get("track") in ("cs", "electronics"), where, "track %r" % paper.get("track"), errors)
    _str(paper.get("published"), where + ".published", errors, pattern=ISO)
    _str(paper.get("abstract"), where + ".abstract", errors, empty=False)
    digest = paper.get("digest")
    if _keys(digest, DIGEST_KEYS, where + ".digest", errors):
        for key in DIGEST_KEYS:
            _str(digest.get(key), "%s.digest.%s" % (where, key), errors)
            text = digest.get(key)
            # Extractive: every digest line is lifted from the abstract, never invented.
            if isinstance(text, str) and text and isinstance(paper.get("abstract"), str):
                _check(_squash(text) in _squash(paper["abstract"]), where + ".digest." + key, "not a sentence of the abstract", errors)
    signals = paper.get("signals")
    if _keys(signals, PAPER_SIGNALS, where + ".signals", errors):
        _check(all(_is_num(value) and value >= 0 for value in signals.values()), where + ".signals", "signals must be numbers >= 0", errors)
    _num(paper.get("score"), where + ".score", errors, 0, 100)
    _str_list(paper.get("why"), where + ".why", errors)
    links = paper.get("links")
    if _keys(links, ("abs", "pdf", "code", "hf", "hn"), where + ".links", errors):
        _str(links.get("abs"), where + ".links.abs", errors, pattern=WEB_URL)
        _str(links.get("pdf"), where + ".links.pdf", errors, pattern=WEB_URL)
        for key in ("code", "hf", "hn"):
            _str(links.get(key), "%s.links.%s" % (where, key), errors, pattern=WEB_URL, nullable=True)
    _check(_is_int(paper.get("rank")) and paper["rank"] >= 1, where, "rank must be an int >= 1", errors)


def _squash(text):
    return " ".join(text.split())


def validate_weekend(doc, name, errors):
    """``public/weekend/<isoWeek>.json``: five papers (two or more electronics), runners-up, review."""
    where = "weekend/%s.json" % name
    keys = ("isoWeek", "from", "to", "generatedAt", "method", "papers", "runnersUp", "review")
    if not _keys(doc, keys, where, errors):
        return
    _check(doc.get("isoWeek") == name, where, "isoWeek %r does not match the file name" % doc.get("isoWeek"), errors)
    _str(doc.get("from"), where + ".from", errors, pattern=DATE)
    _str(doc.get("to"), where + ".to", errors, pattern=DATE)
    if isinstance(doc.get("from"), str) and isinstance(doc.get("to"), str):
        _check(doc["from"] <= doc["to"], where, "from is after to", errors)
    _str(doc.get("generatedAt"), where + ".generatedAt", errors, pattern=ISO)
    _str(doc.get("method"), where + ".method", errors, empty=False)
    papers = doc.get("papers") if isinstance(doc.get("papers"), list) else []
    runners = doc.get("runnersUp") if isinstance(doc.get("runnersUp"), list) else []
    _check(len(papers) == 5, where, "%d papers, expected 5" % len(papers), errors)
    _check(len(runners) <= 10, where, "%d runners-up, at most 10" % len(runners), errors)
    for label, group in (("papers", papers), ("runnersUp", runners)):
        for index, paper in enumerate(group):
            validate_paper(paper, "%s.%s[%d]" % (where, label, index), errors)
    electronics = sum(1 for paper in papers if _get(paper, "track") == "electronics")
    _check(electronics >= 2, where, "%d electronics papers, at least 2 required" % electronics, errors)
    _check([_get(paper, "rank") for paper in papers] == list(range(1, len(papers) + 1)), where, "papers are not ranked 1..n", errors)
    ids = [_get(paper, "id") for paper in papers + runners]
    _check(len(ids) == len(set(ids)), where, "a paper appears twice", errors)
    review = doc.get("review")
    if not isinstance(review, dict):
        errors.append("%s.review: expected an object" % where)
        return
    for index, story in enumerate(review.get("stories") or []):
        validate_story(story, "%s.review.stories[%d]" % (where, index), errors)
    _check(len(review.get("stories") or []) <= 7, where + ".review", "more than 7 stories", errors)
    for index, row in enumerate(review.get("markets") or []):
        at = "%s.review.markets[%d]" % (where, index)
        if _keys(row, ("symbol", "name", "weekPct"), at, errors):
            _num(row.get("weekPct"), at + ".weekPct", errors)
    _check(len(review.get("claude") or []) <= 6, where + ".review", "more than 6 Claude updates", errors)
    for index, update in enumerate(review.get("claude") or []):
        validate_update(update, "%s.review.claude[%d]" % (where, index), errors)


def validate_weekend_index(doc, names, errors):
    """``public/weekend/index.json`` lists exactly the weekend files, newest first."""
    where = "weekend/index.json"
    if not _keys(doc, ("weeks",), where, errors):
        return
    rows = doc.get("weeks") if isinstance(doc.get("weeks"), list) else []
    weeks = [_get(row, "isoWeek") for row in rows]
    _check(weeks == sorted(names, reverse=True), where, "lists %s, files are %s" % (weeks, sorted(names, reverse=True)), errors)
    for index, row in enumerate(rows):
        _keys(row, ("isoWeek", "from", "to", "title"), "%s[%d]" % (where, index), errors)


# ---- claude -----------------------------------------------------------------------------------


def validate_update(update, where, errors):
    """A ClaudeUpdate (contract: Public: claude)."""
    keys = ("id", "date", "surface", "kind", "title", "summary", "url", "source", "features")
    if not _keys(update, keys, where, errors):
        return
    _str(update.get("id"), where + ".id", errors, empty=False)
    _str(update.get("date"), where + ".date", errors, pattern=DATE)
    _check(update.get("surface") in UPDATE_SURFACES, where, "surface %r" % update.get("surface"), errors)
    _check(update.get("kind") in UPDATE_KINDS, where, "kind %r" % update.get("kind"), errors)
    _str(update.get("title"), where + ".title", errors, empty=False)
    _str(update.get("summary"), where + ".summary", errors)
    _str(update.get("url"), where + ".url", errors, pattern=WEB_URL)
    _str(update.get("source"), where + ".source", errors, empty=False)
    _str_list(update.get("features"), where + ".features", errors)


def validate_updates(doc, errors, feature_ids=None):
    """``public/claude/updates.json``: newest first, unique ids, links into the playbook."""
    where = "claude/updates.json"
    if not _keys(doc, ("generatedAt", "status", "entries"), where, errors):
        return
    _str(doc.get("generatedAt"), where + ".generatedAt", errors, pattern=ISO)
    status = doc.get("status")
    if status is not None:
        _keys(status, ("indicator", "description"), where + ".status", errors)
    entries = doc.get("entries") if isinstance(doc.get("entries"), list) else []
    for index, entry in enumerate(entries):
        validate_update(entry, "%s.entries[%d]" % (where, index), errors)
        if feature_ids is not None and isinstance(_get(entry, "features"), list):
            unknown = [fid for fid in entry["features"] if fid not in feature_ids]
            _check(not unknown, "%s.entries[%d]" % (where, index), "links unknown features %s" % unknown, errors)
    dates = [_get(entry, "date") for entry in entries]
    if all(isinstance(date, str) for date in dates):
        _check(dates == sorted(dates, reverse=True), where, "entries are not newest first", errors)
    ids = [_get(entry, "id") for entry in entries]
    _check(len(ids) == len(set(ids)), where, "an entry id repeats", errors)


def validate_playbook(doc, errors):
    """``public/claude/playbook.json``; returns the feature ids for cross-checks."""
    where = "claude/playbook.json"
    if not _keys(doc, ("generatedAt", "surfaces", "jobs", "features", "recipes"), where, errors):
        return set()
    jobs = {_get(job, "id") for job in doc.get("jobs") or []}
    surfaces = [_get(surface, "id") for surface in doc.get("surfaces") or []]
    _check(set(surfaces) <= set(FEATURE_SURFACES), where + ".surfaces", "unknown surfaces %s" % surfaces, errors)
    features = doc.get("features") if isinstance(doc.get("features"), list) else []
    for index, feature in enumerate(features):
        _validate_feature(feature, "%s.features[%d]" % (where, index), jobs, errors)
    feature_ids = {_get(feature, "id") for feature in features}
    recipes = doc.get("recipes") if isinstance(doc.get("recipes"), list) else []
    for index, recipe in enumerate(recipes):
        _validate_recipe(recipe, "%s.recipes[%d]" % (where, index), jobs, feature_ids, errors)
    ids = [_get(item, "id") for item in features + recipes]
    _check(len(ids) == len(set(ids)), where, "an id repeats across features and recipes", errors)
    return feature_ids


def _validate_docs_list(docs, where, errors):
    if not isinstance(docs, list) or not docs:
        errors.append("%s: expected a non-empty list of {title, url}" % where)
        return
    for index, link in enumerate(docs):
        if _keys(link, ("title", "url"), "%s[%d]" % (where, index), errors):
            _str(link.get("url"), "%s[%d].url" % (where, index), errors, pattern=re.compile(r"^https://\S+$"))


def _validate_feature(feature, where, jobs, errors):
    keys = ("id", "title", "surface", "group", "status", "since", "level", "payoff", "effort", "jobs", "tags",
            "summary", "when", "replaces", "example_kind", "docs", "verified", "html", "example")
    if not _keys(feature, keys, where, errors):
        return
    _check(feature.get("surface") in FEATURE_SURFACES, where, "surface %r" % feature.get("surface"), errors)
    _check(feature.get("status") in ("new", "stable", "beta"), where, "status %r" % feature.get("status"), errors)
    _str(feature.get("since"), where + ".since", errors, pattern=MONTH, nullable=True)
    _check(feature.get("level") in LEVELS, where, "level %r" % feature.get("level"), errors)
    for key in ("payoff", "effort"):
        _check(feature.get(key) in (1, 2, 3), where, "%s %r not 1-3" % (key, feature.get(key)), errors)
    _str_list(feature.get("jobs"), where + ".jobs", errors, allowed=jobs)
    _str_list(feature.get("tags"), where + ".tags", errors)
    for key in ("title", "summary", "when", "replaces", "html", "example"):
        _str(feature.get(key), "%s.%s" % (where, key), errors, empty=False)
    _check(feature.get("example_kind") in ("prompt", "command", "config"), where, "example_kind %r" % feature.get("example_kind"), errors)
    _validate_docs_list(feature.get("docs"), where + ".docs", errors)
    _str(feature.get("verified"), where + ".verified", errors, pattern=DATE)


def _validate_recipe(recipe, where, jobs, feature_ids, errors):
    keys = ("id", "title", "job", "level", "minutes_saved", "features", "prerequisites", "fields", "docs",
            "verified", "html", "template")
    if not _keys(recipe, keys, where, errors):
        return
    _check(recipe.get("job") in jobs, where, "job %r is not a playbook job" % recipe.get("job"), errors)
    _check(recipe.get("level") in LEVELS, where, "level %r" % recipe.get("level"), errors)
    _check(_is_int(recipe.get("minutes_saved")) and recipe["minutes_saved"] > 0, where, "minutes_saved must be a positive int", errors)
    _str_list(recipe.get("features"), where + ".features", errors, allowed=feature_ids)
    _str_list(recipe.get("prerequisites"), where + ".prerequisites", errors)
    names = set()
    for index, field in enumerate(recipe.get("fields") or []):
        if _keys(field, ("name", "label", "placeholder"), "%s.fields[%d]" % (where, index), errors):
            names.add(field.get("name"))
    template = recipe.get("template")
    _str(template, where + ".template", errors, empty=False)
    if isinstance(template, str):
        used = set(PLACEHOLDER.findall(template))
        _check(used == names, where, "template placeholders %s do not match fields %s" % (sorted(used), sorted(names)), errors)
    _validate_docs_list(recipe.get("docs"), where + ".docs", errors)
    _str(recipe.get("verified"), where + ".verified", errors, pattern=DATE)


# ---- search -----------------------------------------------------------------------------------


def validate_search_doc(doc, where, kinds, errors):
    """One compact search doc; ``c`` must be a section for stories, a surface for updates and features."""
    if not _keys(doc, DOC_KEYS, where, errors):
        return
    _str(doc.get("i"), where + ".i", errors, empty=False)
    _check(doc.get("k") in kinds, where, "kind %r not one of %s" % (doc.get("k"), kinds), errors)
    _str(doc.get("t"), where + ".t", errors, empty=False)
    _str(doc.get("s"), where + ".s", errors)
    _check(not isinstance(doc.get("s"), str) or len(doc["s"]) <= 220, where, "summary longer than 220", errors)
    _str_list(doc.get("e"), where + ".e", errors)
    _str(doc.get("d"), where + ".d", errors, pattern=ISO, nullable=doc.get("k") in STATIC_KINDS)
    _str(doc.get("u"), where + ".u", errors, empty=False)
    _num(doc.get("x"), where + ".x", errors, 0, 100, nullable=True)
    kind = doc.get("k")
    if kind == "story":
        _check(doc.get("c") in SECTION_IDS, where, "story c %r is not a section" % doc.get("c"), errors)
        _check(_is_int(doc.get("n")) and doc["n"] >= 1, where, "story n must be a sourceCount", errors)
        _str(doc.get("i"), where + ".i", errors, pattern=STORY_ID)
    elif kind == "update":
        _check(doc.get("c") in UPDATE_SURFACES, where, "update c %r is not a surface" % doc.get("c"), errors)
    elif kind == "feature":
        _check(doc.get("c") in FEATURE_SURFACES, where, "feature c %r is not a surface" % doc.get("c"), errors)


def validate_search(directory, errors):
    """``public/search``: the manifest names exactly its shards, counts match, ids are unique.

    Returns ``{kind: {doc ids}}`` for cross-checks, or None when there is no manifest.
    """
    manifest = _read(directory / "manifest.json", "search/manifest.json", errors)
    if not _keys(manifest, ("generatedAt", "shards", "static"), "search/manifest.json", errors):
        return None
    seen, by_kind, listed = {}, {}, set()
    for index, shard in enumerate(manifest.get("shards") or []):
        at = "search/manifest.json.shards[%d]" % index
        if not _keys(shard, ("month", "file", "count"), at, errors):
            continue
        _str(shard.get("month"), at + ".month", errors, pattern=MONTH)
        _check(shard.get("file") == "docs-%s.json" % shard.get("month"), at, "file %r does not match month" % shard.get("file"), errors)
        listed.add(shard.get("file"))
        docs = _read(directory / str(shard.get("file")), "search/%s" % shard.get("file"), errors)
        if not isinstance(docs, list):
            continue
        _check(len(docs) == shard.get("count"), at, "count %r but the file has %d docs" % (shard.get("count"), len(docs)), errors)
        for number, doc in enumerate(docs):
            where = "search/%s[%d]" % (shard.get("file"), number)
            validate_search_doc(doc, where, SHARD_KINDS, errors)
            _note_unique(seen, _get(doc, "i"), where, errors)
            by_kind.setdefault(_get(doc, "k"), set()).add(_get(doc, "i"))
    on_disk = {path.name for path in directory.glob("docs-*.json") if path.name != manifest.get("static")}
    _check(on_disk == listed, "search/manifest.json", "shards on disk %s, listed %s" % (sorted(on_disk), sorted(listed)), errors)
    static = _read(directory / str(manifest.get("static")), "search/%s" % manifest.get("static"), errors)
    for number, doc in enumerate(static if isinstance(static, list) else []):
        where = "search/%s[%d]" % (manifest.get("static"), number)
        validate_search_doc(doc, where, STATIC_KINDS, errors)
        _note_unique(seen, _get(doc, "i"), where, errors)
        by_kind.setdefault(_get(doc, "k"), set()).add(_get(doc, "i"))
    validate_search_lexicon(_read(directory / "lexicon.json", "search/lexicon.json", errors), errors)
    return by_kind


def _note_unique(seen, doc_id, where, errors):
    if doc_id in seen:
        errors.append("%s: id %r already in %s" % (where, doc_id, seen[doc_id]))
    seen[doc_id] = where


def validate_search_lexicon(doc, errors):
    """``public/search/lexicon.json``: aliases, entities, learned related terms, glossary."""
    where = "search/lexicon.json"
    if not _keys(doc, ("aliases", "entities", "related", "glossary"), where, errors):
        return
    for term, others in (doc.get("aliases") or {}).items():
        _str_list(others, "%s.aliases[%r]" % (where, term), errors)
    for entity_id, entity in (doc.get("entities") or {}).items():
        at = "%s.entities[%r]" % (where, entity_id)
        if _keys(entity, ("name", "type", "aliases", "related", "ticker"), at, errors):
            _str_list(entity.get("aliases"), at + ".aliases", errors)
            _str_list(entity.get("related"), at + ".related", errors)
            _str(entity.get("ticker"), at + ".ticker", errors, nullable=True)
    for term, neighbours in (doc.get("related") or {}).items():
        at = "%s.related[%r]" % (where, term)
        ok = isinstance(neighbours, list) and len(neighbours) <= 6 and all(
            isinstance(pair, list) and len(pair) == 2 and isinstance(pair[0], str) and _is_num(pair[1]) and 0 < pair[1] <= 1
            for pair in neighbours)
        _check(ok, at, "expected at most 6 [stem, weight 0..1] pairs", errors)
        if ok:
            weights = [pair[1] for pair in neighbours]
            _check(weights == sorted(weights, reverse=True), at, "neighbours are not strongest first", errors)
    _check(all(isinstance(k, str) and isinstance(v, str) and v for k, v in (doc.get("glossary") or {}).items()),
           where + ".glossary", "expected term -> definition strings", errors)


# ---- manifest and status ----------------------------------------------------------------------


def validate_manifest(doc, public, errors):
    """``public/manifest.json`` agrees with site.json and lists exactly the files on disk."""
    where = "manifest.json"
    keys = ("schema", "builtAt", "site", "sections", "edition", "editions", "days", "weekends", "counts", "nextBuild")
    if not _keys(doc, keys, where, errors):
        return
    _check(doc.get("schema") == 1, where, "schema %r" % doc.get("schema"), errors)
    _str(doc.get("builtAt"), where + ".builtAt", errors, pattern=ISO)
    _keys(doc.get("site"), ("name", "tagline", "timezone"), where + ".site", errors)
    _check([_get(s, "id") for s in doc.get("sections") or []] == list(SECTION_IDS), where, "sections are not the canonical ten in order", errors)
    expected = {
        "editions": _names(public / "editions", DATE),
        "days": _names(public / "stories", DATE),
        "weekends": _names(public / "weekend", WEEK),
    }
    for key, names in expected.items():
        _check(doc.get(key) == names, where, "%s lists %s, files on disk are %s" % (key, doc.get(key), names), errors)
    edition = doc.get("edition")
    if expected["editions"]:
        _check(_get(edition, "date") == expected["editions"][0], where, "edition %r is not the newest edition file" % edition, errors)
        _check(_is_int(_get(edition, "number")), where, "edition.number must be an int", errors)
    else:
        _check(edition is None, where, "edition set but there are no edition files", errors)
    counts = doc.get("counts")
    if _keys(counts, ("stories", "sources", "sourcesOk"), where + ".counts", errors):
        _check(all(_is_int(counts.get(key)) and counts[key] >= 0 for key in ("stories", "sources", "sourcesOk")), where + ".counts", "counts must be ints >= 0", errors)
        _check(not all(_is_int(counts.get(k)) for k in ("sources", "sourcesOk")) or counts["sourcesOk"] <= counts["sources"],
               where + ".counts", "more sources ok than sources", errors)
    _str(doc.get("nextBuild"), where + ".nextBuild", errors, pattern=ISO, nullable=True)


def _names(directory, pattern):
    """File stems in ``directory`` matching ``pattern``, newest first (index.json is excluded by the pattern)."""
    if not directory.is_dir():
        return []
    return sorted((p.stem for p in directory.glob("*.json") if pattern.match(p.stem)), reverse=True)


def validate_status(doc, errors):
    """``public/status.json``: stage records and per-source health rows."""
    where = "status.json"
    if not _keys(doc, ("generatedAt", "stages", "sources"), where, errors):
        return
    _str(doc.get("generatedAt"), where + ".generatedAt", errors, pattern=ISO)
    for index, stage in enumerate(doc.get("stages") or []):
        at = "%s.stages[%d]" % (where, index)
        if _keys(stage, ("stage", "ok", "startedAt", "durationSec", "error", "counts"), at, errors):
            _check(isinstance(stage.get("ok"), bool), at, "ok must be a boolean", errors)
            _str(stage.get("startedAt"), at + ".startedAt", errors, pattern=ISO)
            _num(stage.get("durationSec"), at + ".durationSec", errors, 0)
            _check(stage.get("ok") == (stage.get("error") is None), at, "ok and error disagree", errors)
            _check(isinstance(stage.get("counts"), dict), at, "counts must be an object", errors)
    names = [_get(stage, "stage") for stage in doc.get("stages") or []]
    _check(len(names) == len(set(names)), where, "a stage is listed twice", errors)
    for index, source in enumerate(doc.get("sources") or []):
        at = "%s.sources[%d]" % (where, index)
        if _keys(source, ("id", "name", "section", "ok", "items", "newItems", "ms", "error", "lastOkAt"), at, errors):
            _check(source.get("section") in SECTION_IDS, at, "section %r" % source.get("section"), errors)
            _check(isinstance(source.get("ok"), bool), at, "ok must be a boolean", errors)
            _str(source.get("lastOkAt"), at + ".lastOkAt", errors, pattern=ISO, nullable=True)
            _check(source.get("ok") or source.get("error"), at, "a failing source must say why", errors)


# ---- the whole directory ----------------------------------------------------------------------


def _read(path, where, errors):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append("%s: missing" % where)
    except ValueError as err:
        errors.append("%s: not valid JSON (%s)" % (where, err))
    return None


def validate_public(public):
    """Validate every published file under ``public`` and their cross-references; returns problems."""
    public = Path(public)
    errors = []
    story_ids = {}
    for name in _names(public / "stories", DATE):
        for story in validate_stories_day(_read(public / "stories" / (name + ".json"), "stories/%s.json" % name, errors), name, errors):
            _note_unique(story_ids, _get(story, "id"), "stories/%s.json" % name, errors)
    latest = _read(public / "latest.json", "latest.json", errors)
    validate_latest(latest, errors)
    missing = [_get(s, "id") for s in _get(latest, "stories") or [] if _get(s, "id") not in story_ids]
    _check(not missing, "latest.json", "stories not in any day file: %s" % missing[:5], errors)
    editions = _names(public / "editions", DATE)
    for name in editions:
        validate_edition(_read(public / "editions" / (name + ".json"), "editions/%s.json" % name, errors), name, errors)
    if editions:
        validate_editions_index(_read(public / "editions" / "index.json", "editions/index.json", errors), editions, errors)
    validate_markets(_read(public / "markets.json", "markets.json", errors), errors)
    weeks = _names(public / "weekend", WEEK)
    for name in weeks:
        validate_weekend(_read(public / "weekend" / (name + ".json"), "weekend/%s.json" % name, errors), name, errors)
    if weeks:
        validate_weekend_index(_read(public / "weekend" / "index.json", "weekend/index.json", errors), weeks, errors)
    feature_ids = validate_playbook(_read(public / "claude" / "playbook.json", "claude/playbook.json", errors), errors)
    updates = _read(public / "claude" / "updates.json", "claude/updates.json", errors)
    validate_updates(updates, errors, feature_ids)
    indexed = validate_search(public / "search", errors)
    manifest = _read(public / "manifest.json", "manifest.json", errors)
    validate_manifest(manifest, public, errors)
    status = _read(public / "status.json", "status.json", errors)
    validate_status(status, errors)
    _cross_check(public, {
        "stories": story_ids, "editions": editions, "weeks": weeks, "features": feature_ids,
        "updates": {_get(e, "id") for e in _get(updates, "entries") or []}, "indexed": indexed,
        "manifest": manifest, "status": status,
    }, errors)
    return errors


def _cross_check(public, known, errors):
    """References between files: every id one file names must exist in the file that owns it."""
    markets = _read(public / "markets.json", "markets.json", []) or {}
    for mover in markets.get("movers") or []:
        story_id = _get(_get(mover, "story"), "id")
        _check(story_id is None or story_id in known["stories"], "markets.json", "mover story %s is not on file" % story_id, errors)
    for name in known["editions"]:
        edition = _read(public / "editions" / (name + ".json"), "", []) or {}
        claude = edition.get("claude") or {}
        if claude.get("kind") == "feature":
            _check(claude.get("featureId") in known["features"], "editions/%s.json" % name,
                   "featureId %r is not in the playbook" % claude.get("featureId"), errors)
        week = _get(edition.get("weekend"), "isoWeek")
        _check(week is None or week in known["weeks"], "editions/%s.json" % name, "weekend %s has no file" % week, errors)
    if known["indexed"] is not None:
        kinds = known["indexed"]
        _check(kinds.get("story", set()) == set(known["stories"]), "search", "story docs %d differ from the %d stories on file (%s)"
               % (len(kinds.get("story", set())), len(known["stories"]),
                  sorted(kinds.get("story", set()) ^ set(known["stories"]))[:5]), errors)
        _check(kinds.get("update", set()) == known["updates"], "search", "update docs differ from claude/updates.json", errors)
        _check(kinds.get("feature", set()) == {"feature:%s" % f for f in known["features"]}, "search", "feature docs differ from the playbook", errors)
    manifest, status = known["manifest"] or {}, known["status"] or {}
    counts = manifest.get("counts") or {}
    _check(counts.get("stories") == len(known["stories"]), "manifest.json", "counts.stories %r, %d stories on file"
           % (counts.get("stories"), len(known["stories"])), errors)
    sources = status.get("sources") or []
    _check(counts.get("sources") == len(sources) and counts.get("sourcesOk") == sum(1 for s in sources if _get(s, "ok")),
           "manifest.json", "source counts disagree with status.json", errors)


def _report(errors, limit=40):
    shown = "\n".join(errors[:limit])
    more = "\n… and %d more" % (len(errors) - limit) if len(errors) > limit else ""
    return "%d contract violation(s):\n%s%s" % (len(errors), shown, more)


# ---- tests ------------------------------------------------------------------------------------


class SiteConfigMatchesContract(unittest.TestCase):
    def test_sections_are_the_canonical_ten(self):
        site = config.load("site")
        self.assertEqual([s["id"] for s in site["sections"]], list(SECTION_IDS))

    def test_edition_limits_match_site_config(self):
        edition = config.load("site")["edition"]
        self.assertEqual((edition["frontCount"], edition["briefCount"], edition["perSection"]),
                         (EDITION_FRONT, EDITION_BRIEFS, EDITION_PER_SECTION))


class FixtureSnapshot(unittest.TestCase):
    """The committed snapshot of a real run satisfies the whole contract."""

    def test_snapshot_is_valid(self):
        errors = validate_public(FIXTURE)
        self.assertEqual(errors, [], _report(errors))


class BrokenSnapshot(unittest.TestCase):
    """Each rule can fail: break a copy of the snapshot one way and expect that exact complaint."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="contracts-"))
        self.public = self.tmp / "public"
        shutil.copytree(FIXTURE, self.public)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def edit(self, relative, change):
        path = self.public / relative
        doc = json.loads(path.read_text(encoding="utf-8"))
        change(doc)
        path.write_text(json.dumps(doc), encoding="utf-8")

    def assertViolation(self, fragment):
        errors = validate_public(self.public)
        self.assertTrue(any(fragment in error for error in errors), "no %r in:\n%s" % (fragment, "\n".join(errors) or "(no errors)"))

    def edition_path(self):
        return "editions/%s.json" % _names(self.public / "editions", DATE)[0]

    def test_story_in_edition_twice(self):
        self.edit(self.edition_path(), lambda doc: doc["briefs"].append(copy.deepcopy(doc["lead"])))
        self.assertViolation("placed in lead and briefs")

    def test_two_stories_from_one_thread(self):
        def share_thread(doc):
            for story in (doc["front"][0], doc["front"][1]):
                story["thread"] = {"id": "t0123456789", "day": 2, "history": []}
        self.edit(self.edition_path(), share_thread)
        self.assertViolation("thread t0123456789 has two stories")

    def test_front_crowded_by_one_section(self):
        def crowd(doc):
            for story in doc["front"]:
                story["section"] = "world"
                story["sections"] = ["world"]
        self.edit(self.edition_path(), crowd)
        self.assertViolation("more than two stories from ['world']")

    def test_unknown_section_id(self):
        def rename(doc):
            doc["stories"][0]["section"] = "sport"
        self.edit("stories/%s.json" % _names(self.public / "stories", DATE)[0], rename)
        self.assertViolation("section 'sport' is not a section id")

    def test_signal_out_of_range(self):
        def inflate(doc):
            doc["stories"][0]["signals"]["breadth"] = 1.4
        self.edit("latest.json", inflate)
        self.assertViolation("signals.breadth: 1.4 outside 0..1")

    def test_weekend_needs_two_electronics_papers(self):
        def all_cs(doc):
            for paper in doc["papers"]:
                paper["track"] = "cs"
        self.edit("weekend/%s.json" % _names(self.public / "weekend", WEEK)[0], all_cs)
        self.assertViolation("0 electronics papers, at least 2 required")

    def test_digest_must_be_extractive(self):
        def invent(doc):
            doc["papers"][0]["digest"]["gist"] = "This paper changes everything."
        self.edit("weekend/%s.json" % _names(self.public / "weekend", WEEK)[0], invent)
        self.assertViolation("not a sentence of the abstract")

    def test_duplicate_search_doc(self):
        shard = json.loads((self.public / "search" / "manifest.json").read_text())["shards"][0]
        def duplicate(docs):
            docs.append(copy.deepcopy(docs[0]))
        self.edit("search/" + shard["file"], duplicate)
        self.assertViolation("already in search/")
        self.assertViolation("but the file has")

    def test_manifest_lists_missing_day(self):
        self.edit("manifest.json", lambda doc: doc["days"].insert(0, "2099-01-01"))
        self.assertViolation("days lists")

    def test_manifest_misses_a_file_on_disk(self):
        name = _names(self.public / "stories", DATE)[0]
        shutil.copy(self.public / "stories" / (name + ".json"), self.public / "stories" / "2001-01-01.json")
        self.assertViolation("days lists")

    def test_update_with_unknown_surface(self):
        def bad(doc):
            doc["entries"][0]["surface"] = "mobile"
        self.edit("claude/updates.json", bad)
        self.assertViolation("surface 'mobile'")

    def test_update_links_unknown_feature(self):
        def bad(doc):
            doc["entries"][0]["features"] = ["no-such-feature"]
        self.edit("claude/updates.json", bad)
        self.assertViolation("links unknown features ['no-such-feature']")

    def test_recipe_placeholder_without_field(self):
        def bad(doc):
            doc["recipes"][0]["template"] += "\n{{undeclared}}"
        self.edit("claude/playbook.json", bad)
        self.assertViolation("template placeholders")

    def test_strip_symbol_without_quote(self):
        self.edit("markets.json", lambda doc: doc["strip"].append("^NOPE"))
        self.assertViolation("unknown values ['^NOPE']")

    def test_quote_kind_enum(self):
        def bad(doc):
            doc["groups"][0]["quotes"][0]["kind"] = "bond"
        self.edit("markets.json", bad)
        self.assertViolation("kind 'bond'")

    def test_failing_source_must_say_why(self):
        def bad(doc):
            doc["sources"][0].update({"ok": False, "error": None})
        self.edit("status.json", bad)
        self.assertViolation("a failing source must say why")

    def test_latest_story_must_be_on_file(self):
        def stray(doc):
            doc["stories"][0]["id"] = "s0000000000"
        self.edit("latest.json", stray)
        self.assertViolation("stories not in any day file")


class LiveOutput(unittest.TestCase):
    """The real ``data/public`` satisfies the contract (skipped where no run has happened, as in CI)."""

    def test_live_public_directory(self):
        if not (LIVE / "manifest.json").is_file():
            self.skipTest("no built data/public on this machine")
        errors = validate_public(LIVE)
        self.assertEqual(errors, [], _report(errors))


if __name__ == "__main__":
    unittest.main()
