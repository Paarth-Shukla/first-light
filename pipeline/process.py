"""Process stage: state/items -> public/stories, public/latest.json and the morning edition.

This is the paper's editor. Each run it

1. loads the items of the three live local days (older day files are frozen);
2. classifies every item with the lexicon: entities, sections, tickers;
3. clusters items into stories (``cluster.py``; assignments persist in
   ``state/clusters.json`` so story ids never change);
4. builds one Story per cluster from its best member, scores it (``rank.py``)
   and links it to earlier instalments of the same event (``threads.py``);
5. rewrites the three live ``public/stories/<date>.json`` files and
   ``public/latest.json`` (the last 48 hours plus trending entities), prunes
   story files past retention, and hands the stories to ``edition.py``.

Nothing here touches the network. A malformed item is skipped and counted,
never fatal; a missing optional input just leaves its part of the output empty.
"""

import re
from collections import Counter, defaultdict
from datetime import date, timedelta

from . import cluster, edition, lexicon, rank, threads
from .core import config, jsonio, log, timeutil

LIVE_DAYS = 3
LATEST_HOURS = 48.0
LATEST_MAX = 500
TREND_DAYS = 7
TREND_MIN_COUNT = 3
TREND_MIN_RATIO = 2.0
TREND_MAX = 12
MAX_ENTITIES = 10
DEFAULT_RETENTION_DAYS = 90
DEFAULT_HALF_LIFE_HOURS = 18.0
CLUSTER_KEEP_DAYS = 10
# A member this much older than the story's newest item no longer speaks for the story.
STALE_HOURS = 18.0
# A curated slot at or above this position is worth naming in "why".
TOP_SLOT = 2
LOCAL_MARKETS, LOCAL_DESK, GLOBAL_MARKETS, GENERAL_DESK = "india-markets", "india", "markets", "world"
LABS_DESK = "labs"
CLUSTERS_FILE = "clusters.json"
THREADS_FILE = "threads.json"
_MODE_RANK = {"official": 0, "curated": 1, "firehose": 2}
_GOOGLE_NEWS = "https://news.google.com/"
_DAY_FILE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")
# Unmistakably Indian money talk, which the lexicon's section rules do not list.
_INDIAN = re.compile(r"₹|\bRs\.? ?\d|\bcrores?\b|\blakhs?\b|\bIndia(?:n|['’]s)?\b|\brupees?\b")


# ---------------------------------------------------------------- inputs

def live_days(now, tz):
    """The local dates whose story files are rewritten this run, oldest first."""
    today = date.fromisoformat(timeutil.local_date(now, tz))
    return [(today - timedelta(days=back)).isoformat() for back in range(LIVE_DAYS - 1, -1, -1)]


def load_sources():
    """{source id: source config} for every configured source (a disabled one still explains old items)."""
    listed = config.load("sources").get("sources")
    if not isinstance(listed, list):
        raise config.ConfigError("config/sources.json has no \"sources\" list")
    return {source["id"]: source for source in listed if isinstance(source, dict) and source.get("id")}


def outlet_tiers(sources):
    """{outlet key: best tier}: lets an outlet seen through an aggregator keep its standing."""
    tiers = {}
    for source in sources.values():
        if source.get("tier") in (1, 2, 3):
            key = cluster.outlet_key(source.get("name"))
            tiers[key] = min(tiers.get(key, 3), source["tier"])
    return tiers


def load_items(items_dir, days):
    """Every well-formed item in the day files for ``days``; returns (items, number skipped)."""
    items, skipped = [], 0
    for day in days:
        stored = jsonio.read_json(items_dir / ("%s.json" % day), default=None)
        if stored is None:
            continue
        entries = stored.get("items") if isinstance(stored, dict) else None
        if not isinstance(entries, dict):
            log.warn("%s.json is not an items file; ignoring it", day)
            continue
        for item in entries.values():
            if (isinstance(item, dict) and item.get("id") and str(item.get("title") or "").strip()
                    and item.get("url") and timeutil.parse_date(item.get("publishedAt")) is not None):
                items.append(item)
            else:
                skipped += 1
    return items, skipped


def load_state(path, empty):
    """A state file with the same top-level keys as ``empty`` (all dicts), or ``empty`` itself."""
    stored = jsonio.read_json(path, default=None)
    if stored is None:
        return empty
    if not isinstance(stored, dict) or any(not isinstance(stored.get(key), dict) for key in empty):
        log.warn("%s has an unexpected shape; starting it afresh", path)
        return empty
    return stored


def load_story_file(stories_dir, day):
    """The stories of one published day file; [] when it is missing or malformed."""
    stored = jsonio.read_json(stories_dir / ("%s.json" % day), default=None)
    listed = stored.get("stories") if isinstance(stored, dict) else None
    if not isinstance(listed, list):
        return []
    return [story for story in listed if isinstance(story, dict) and story.get("id") and story.get("day")]


# ---------------------------------------------------------------- classification

def desks(text, home, entities):
    """(primary, sections) for an item: the lexicon's answer, with one correction for Dalal Street.

    Indian business feeds also carry Wall Street and world business news. The
    lexicon keeps a specific home desk whatever the text says, which would put
    "Sterling drops against firmer dollar" under Dalal Street; when the text
    gives no evidence of India at all (no Indian desk phrase or entity, no
    rupee amounts), the item is filed as if it came from a general feed,
    falling back to Markets.
    """
    primary, sections = lexicon.sections_for(text, home, entities)
    if home != LOCAL_MARKETS or _INDIAN.search(text):
        return primary, sections
    elsewhere, evidence = lexicon.sections_for(text, GENERAL_DESK, entities)
    if LOCAL_MARKETS in evidence or LOCAL_DESK in evidence:
        return primary, sections
    primary = GLOBAL_MARKETS if elsewhere == GENERAL_DESK else elsewhere
    others = [section for section in evidence if section not in (GENERAL_DESK, primary)]
    return primary, [primary] + others


class Member:
    """One item with everything derived from it: its outlet, standing, entities and sections."""

    __slots__ = ("item", "doc", "time", "outlet", "name", "curator", "tier", "feed_tier", "mode", "relayed",
                 "entities", "primary", "sections", "template", "lab_subject")

    def __init__(self, item, source, tiers, tz):
        source = source or {}
        self.item = item
        self.time = timeutil.parse_date(item["publishedAt"])
        self.curator = item.get("sourceName") or source.get("name") or item.get("source") or ""
        self.name = cluster.outlet_label(item.get("publisher") or self.curator)
        self.outlet = cluster.outlet_key(self.name)
        self.feed_tier = source.get("tier", 3)
        # Through a mixed aggregator ("Google News": publisher "BBC") the outlet keeps its own standing.
        self.relayed = bool(item.get("publisher")) and self.outlet != cluster.outlet_key(self.curator)
        self.tier = tiers.get(self.outlet, 3) if self.relayed else self.feed_tier
        self.mode = source.get("mode", "firehose")
        title, summary = item["title"], item.get("summary") or ""
        text = "%s. %s" % (title, summary) if summary else title
        self.entities = lexicon.match_entities(text)
        home = item.get("section") or source.get("section")
        self.primary, self.sections = desks(text, home, self.entities)
        self.template = rank.template(title)
        named = lexicon.match_entities(title)
        # The first name in a headline is usually its subject: "Anthropic targets ..." is about a lab,
        # "Australia weighs AI law after OpenAI hack" is not.
        self.lab_subject = bool(named) and LABS_DESK in (lexicon.entity(named[0]) or {}).get("sections", ())
        self.doc = cluster.Doc(item, named, self.entities, tz)

    @property
    def direct_link(self):
        """False for a Google News redirect, which is an opaque link to someone else's page."""
        return not str(self.item.get("url") or "").startswith(_GOOGLE_NEWS)


def classify(items, sources, tz):
    """Members for every item that can be classified; returns (members, number skipped).

    An item whose home section the lexicon does not know (config drift) is
    skipped with a warning instead of failing the run.
    """
    tiers = outlet_tiers(sources)
    members, skipped = [], 0
    for item in items:
        try:
            members.append(Member(item, sources.get(item.get("source")), tiers, tz))
        except ValueError as err:
            skipped += 1
            log.warn("skipping item %s (%s): %s", item.get("id"), item.get("source"), err)
    return members, skipped


# ---------------------------------------------------------------- stories

def best_first(members, newest):
    """Members ordered by how well each speaks for the story.

    Real headlines before promos and live-blog shells; recent before stale (a
    story lives up to three days and should carry today's headline); a direct
    link before a Google News redirect; then tier, first-party and curated
    before firehose, and the longest summary.
    """
    def key(member):
        stale = timeutil.hours_between(member.time, newest) > STALE_HOURS
        return (member.template in rank.QUALITY, stale, not member.direct_link, member.tier,
                _MODE_RANK.get(member.mode, 2), -len(member.item.get("summary") or ""),
                -member.time.timestamp(), member.item["id"])
    return sorted(members, key=key)


def _supported(counter, total, always):
    """Values backed by the lead member or by a fair share of members (a quarter, at least two)."""
    need = max(2, -(-total // 4))
    return [value for value, count in counter.most_common() if value in always or count >= need]


def _sections(ordered, section_ids):
    """(primary, sections) for a story.

    The Frontier Labs desk takes any story a lab published itself, or whose
    headlines mostly lead with a lab: the outlets' own desks would scatter
    "Anthropic IPO" across AI, Markets and Companies. Otherwise each outlet
    votes once for its item's primary desk and the lead member breaks ties.
    """
    votes, seen = Counter(), set()
    for member in ordered:
        if member.outlet not in seen:
            seen.add(member.outlet)
            votes[member.primary] += 1
    lead = ordered[0]
    primary = max(votes, key=lambda section: (votes[section], section == lead.primary, -section_ids.index(section)))
    about_labs = sum(1 for member in ordered if member.lab_subject)
    by_a_lab = any(member.mode == "official" and member.primary == LABS_DESK for member in ordered)
    if LABS_DESK in section_ids and (by_a_lab or 2 * about_labs > len(ordered)):
        primary = LABS_DESK
    mentioned = Counter(section for member in ordered for section in member.sections)
    kept = set(_supported(mentioned, len(ordered), set(lead.sections)))
    return primary, [primary] + [section for section in section_ids if section in kept and section != primary]


def _source_entries(ordered):
    """``sources``: one entry per outlet, best first."""
    entries, seen = [], set()
    for member in ordered:
        if member.outlet in seen:
            continue
        seen.add(member.outlet)
        entries.append({"id": member.item.get("source"), "name": member.name, "tier": member.tier,
                        "title": member.item["title"], "url": member.item["url"],
                        "publishedAt": timeutil.iso(member.time)})
    return entries


_VIA_ORDER = ("direct", "relayed", "listed")


def _outlets(members, tiers):
    """{outlet key: {"tier", "via", "first"}} for members and for outlets an aggregator lists.

    ``via`` is the best way we know the outlet covers the story: "direct" from
    its own feed, "relayed" as the publisher of an aggregator's item, "listed"
    in an aggregator's list of other coverage.
    """
    outlets = {}

    def note(key, tier, via, when):
        known = outlets.get(key)
        if known is None:
            outlets[key] = {"tier": tier, "via": via, "first": when}
        else:
            known["tier"] = min(known["tier"], tier)
            known["via"] = min(known["via"], via, key=_VIA_ORDER.index)
            known["first"] = min(known["first"], when)

    for member in members:
        note(member.outlet, member.tier, "relayed" if member.relayed else "direct", member.time)
        for alt in member.item.get("alt") or []:
            key = cluster.outlet_key(alt.get("publisher"))
            if key:
                note(key, tiers.get(key, 3), "listed", member.time)
    return outlets


def _placements(members):
    """Each curator's best slot for the story: [(feed tier, feedRank, curator name)], best first."""
    best = {}
    for member in members:
        feed_rank = member.item.get("feedRank")
        if member.mode != "curated" or isinstance(feed_rank, bool) or not isinstance(feed_rank, int) or feed_rank < 0:
            continue
        worth = rank.editorial([(member.feed_tier, feed_rank)])
        key = cluster.outlet_key(member.curator)
        if key not in best or worth > best[key][0]:
            best[key] = (worth, member.feed_tier, feed_rank, cluster.outlet_label(member.curator))
    return [entry[1:] for entry in sorted(best.values(), key=lambda entry: -entry[0])]


def _short_name(name):
    """"The New York Times" -> "New York Times": reasons are short."""
    return name[4:] if name.startswith("The ") else name


def build_story(story_id, day, members, tiers, section_ids, tickers, now):
    """(Story without score, signals, why and thread; ranking facts) for one cluster.

    Times are clamped to ``now``: a feed that dates an item in the future must
    not make a story look newer than the run that found it.
    """
    newest = min(max(member.time for member in members), now)
    ordered = best_first(members, newest)
    lead = ordered[0]
    primary, sections = _sections(ordered, section_ids)
    mentions = Counter(entity for member in ordered for entity in set(member.entities))
    entities = _supported(mentions, len(ordered), set(lead.entities))[:MAX_ENTITIES]
    outlets = _outlets(ordered, tiers)
    placements = _placements(ordered)
    first = min(min(member.time for member in members), newest)
    story = {
        "id": story_id,
        "title": lead.item["title"],
        "summary": next((m.item["summary"] for m in ordered if m.item.get("summary")), ""),
        "url": lead.item["url"],
        "image": next((m.item["image"] for m in ordered if m.item.get("image")), None),
        "section": primary,
        "sections": sections,
        "entities": entities,
        "tickers": [tickers[entity] for entity in entities if entity in tickers],
        "publishedAt": timeutil.iso(first),
        "updatedAt": timeutil.iso(newest),
        "day": day,
        "sources": _source_entries(ordered),
        "sourceCount": len(outlets),
    }
    facts = {
        "outlets": list(outlets.values()),
        "bestTier": min(member.tier for member in members),
        "updatedAt": newest,
        "firstAt": first,
        "arrivals": [outlet["first"] for outlet in outlets.values()],
        "points": max((m.item.get("points") or 0 for m in members), default=0),
        "comments": max((m.item.get("comments") or 0 for m in members), default=0),
        "placements": [(tier, slot) for tier, slot, _name in placements],
        "topSlots": [_short_name(name) for tier, slot, name in placements if slot <= TOP_SLOT and tier <= 2],
        "firstParty": any(member.mode == "official" for member in members),
        "sourceCount": len(outlets),
    }
    return story, facts


def _days_running(story, tz):
    """How many local days a story spans, counting the day it was filed as 1."""
    updated = timeutil.local_date(timeutil.parse_date(story["updatedAt"]), tz)
    return (date.fromisoformat(updated) - date.fromisoformat(story["day"])).days + 1


def build_stories(members, state, days, ctx, sources):
    """Stories for every cluster filed on a live day, scored; returns [(story, facts)]."""
    ranking = ctx.site.get("ranking") or {}
    weights = ranking.get("weights") or {}
    half_life = float(ranking.get("recencyHalfLifeHours") or DEFAULT_HALF_LIFE_HOURS)
    section_ids = [section["id"] for section in ctx.site.get("sections") or []]
    tickers = {entity: symbol for symbol, entity in lexicon.ticker_map().items()}
    tiers = outlet_tiers(sources)
    grouped = defaultdict(list)
    for member in members:
        story_id = state["items"].get(member.item["id"])
        if story_id is not None and state["stories"].get(story_id, {}).get("day") in days:
            grouped[story_id].append(member)
    built = []
    for story_id in sorted(grouped):
        story, facts = build_story(story_id, state["stories"][story_id]["day"], grouped[story_id], tiers,
                                   section_ids, tickers, ctx.now)
        story["signals"] = rank.signals(facts, ctx.now, half_life)
        factor, _reason = rank.quality(story["title"], story["summary"])
        story["score"] = rank.score(story["signals"], weights, factor)
        built.append((story, facts))
    return built


def add_reasons(built, ctx):
    """Set ``why`` on every story, now that threads are known.

    A story can itself run for up to three days, so the day number of its
    thread is advanced to the story's newest item: an event that began on
    Monday and whose story was last updated on Wednesday is on day 3 whether
    Wednesday's news joined Monday's story or started a new one.
    """
    for story, facts in built:
        running = _days_running(story, ctx.tz)
        if story.get("thread"):
            story["thread"]["day"] += running - 1
            facts["threadDay"] = story["thread"]["day"]
        else:
            facts["threadDay"] = running
        story["why"] = rank.why(facts, story["signals"], ctx.now)


# ---------------------------------------------------------------- latest and trending

def _entity_counts(stories):
    """How many stories mention each entity."""
    return Counter(entity for story in stories for entity in set(story.get("entities") or []))


def day_windows(stories, now):
    """Stories bucketed by how many whole days ago they were last updated: [last 24 h, the 24 h before, ...].

    Rolling windows instead of calendar days keep "today" comparable with
    earlier days at any hour; at 06:00 a calendar day has barely begun.
    """
    windows = [[] for _ in range(TREND_DAYS + 1)]
    for story in stories:
        updated = timeutil.parse_date(story.get("updatedAt"))
        if updated is None:
            continue
        age = timeutil.hours_between(updated, now)
        if 0.0 <= age < 24.0 * len(windows):
            windows[int(age // 24.0)].append(story)
    return windows


def trending(windows):
    """Entities in the news in the last 24 hours well above their usual level.

    ``windows`` comes from ``day_windows``. An entity trends when at least
    three stories of the last 24 hours mention it and that is at least twice
    its mean count over the earlier windows that have any stories; with no
    history at all nothing can be called a trend. Places are never trends:
    "India" is always in the news.
    """
    history = [_entity_counts(window) for window in windows[1:] if window]
    if not history:
        return []
    found = []
    for entity_id, count in _entity_counts(windows[0]).items():
        if count < TREND_MIN_COUNT:
            continue
        baseline = sum(counts.get(entity_id, 0) for counts in history) / float(len(history))
        # An entity normally seen less than once a day is measured against once a day.
        ratio = count / max(baseline, 1.0)
        entity = lexicon.entity(entity_id)
        if ratio < TREND_MIN_RATIO or entity is None or entity["type"] == "place":
            continue
        found.append({"entity": entity_id, "name": entity["name"], "count": count,
                      "baseline": round(baseline, 2), "ratio": round(ratio, 2)})
    found.sort(key=lambda trend: (-trend["ratio"], -trend["count"], trend["entity"]))
    return found[:TREND_MAX]


def build_latest(stories, older, ctx):
    """``public/latest.json``: the last 48 hours by score, trending entities and counts per desk.

    ``older`` are stories from frozen day files, needed only as trend history.
    """
    cutoff = ctx.now - timedelta(hours=LATEST_HOURS)
    hot = rank.by_score([story for story in stories if timeutil.parse_date(story["updatedAt"]) >= cutoff])[:LATEST_MAX]
    per_section = Counter(story["section"] for story in hot)
    return {
        "generatedAt": timeutil.iso(ctx.now),
        "stories": hot,
        "trending": trending(day_windows(stories + older, ctx.now)),
        "sectionCounts": {section["id"]: per_section[section["id"]] for section in ctx.site.get("sections") or []
                          if per_section[section["id"]]},
    }


# ---------------------------------------------------------------- outputs

def write_day_files(stories, days, ctx):
    """Rewrite the live ``public/stories/<date>.json`` files, each sorted by score."""
    for day in days:
        jsonio.write_json(ctx.paths.stories_dir / ("%s.json" % day), {
            "date": day,
            "generatedAt": timeutil.iso(ctx.now),
            "stories": rank.by_score([story for story in stories if story["day"] == day]),
        })


def prune_story_files(stories_dir, today, retention_days):
    """Delete story files older than the retention window; returns how many went."""
    cutoff = (date.fromisoformat(today) - timedelta(days=retention_days)).isoformat()
    removed = 0
    for path in sorted(stories_dir.glob("*.json")):
        match = _DAY_FILE.match(path.name)
        if match and match.group(1) < cutoff:
            try:
                path.unlink()
                removed += 1
            except OSError as err:
                log.warn("could not delete %s: %s", path, err)
    return removed


def _archive(days, ctx):
    """Stories from the frozen day files a live story may still link back to."""
    first = date.fromisoformat(days[0])
    stories = []
    for back in range(1, threads.WINDOW_DAYS + 1):
        stories.extend(load_story_file(ctx.paths.stories_dir, (first - timedelta(days=back)).isoformat()))
    return stories


def run(ctx):
    """Build stories, the hot set and (when due) the edition from the item store. Returns counts."""
    days = live_days(ctx.now, ctx.tz)
    sources = load_sources()
    items, malformed = load_items(ctx.paths.items_dir, days)
    members, unclassified = classify(items, sources, ctx.tz)

    cluster_path = ctx.paths.state / CLUSTERS_FILE
    state = load_state(cluster_path, cluster.empty_state())
    new_stories = cluster.assign([member.doc for member in members], state, days)
    cluster.prune(state, (date.fromisoformat(days[-1]) - timedelta(days=CLUSTER_KEEP_DAYS)).isoformat())

    built = build_stories(members, state, days, ctx, sources)
    stories = [story for story, _facts in built]
    thread_path = ctx.paths.state / THREADS_FILE
    thread_state = load_state(thread_path, threads.empty_state())
    archive = _archive(days, ctx)
    threaded = threads.link(stories, archive, thread_state)
    threads.prune(thread_state, days[-1])
    add_reasons(built, ctx)

    write_day_files(stories, days, ctx)
    latest = build_latest(stories, archive, ctx)
    jsonio.write_json(ctx.paths.public / "latest.json", latest)
    # State is saved only after the stories it describes are published.
    jsonio.write_json(cluster_path, state, sort_keys=True)
    jsonio.write_json(thread_path, thread_state, sort_keys=True)
    retention = int(ctx.site.get("retentionDays") or DEFAULT_RETENTION_DAYS)
    pruned = prune_story_files(ctx.paths.stories_dir, days[-1], retention)

    built_edition = edition.build(ctx, stories)
    counts = {
        "items": len(members),
        "skippedItems": malformed + unclassified,
        "stories": len(stories),
        "newStories": new_stories,
        "multiSource": sum(1 for story in stories if story["sourceCount"] >= 2),
        "threaded": threaded,
        "latest": len(latest["stories"]),
        "trending": len(latest["trending"]),
        "prunedFiles": pruned,
        "edition": built_edition["date"] if built_edition else None,
    }
    log.info("%d items -> %d stories (%d new, %d multi-source, %d in threads); edition: %s",
             counts["items"], counts["stories"], new_stories, counts["multiSource"], threaded,
             "%s no. %d" % (built_edition["date"], built_edition["number"]) if built_edition else "not due")
    return counts
