"""The morning edition: one frozen front page per day, ``public/editions/<date>.json``.

The first ``process`` run at or after ``site.json -> edition.hour`` (local
time) writes today's edition; it is never rewritten that day unless
``--force-edition`` asks. Freezing is the point: the reader gets a paper, not a
feed that reshuffles while they read.

Layout rules, in the order slots are filled:

* Only fresh stories are eligible: updated since the previous edition was
  printed, or within the last 24 hours. Promos, live-blog shells and recurring
  bulletins never make the paper.
* ``lead``: the highest score among stories carried by two or more outlets,
  passing over the routine market wrap when there is other news; without any
  multi-outlet story, the highest score.
* ``front``: the next four by score, at most two per section; the market wrap
  is kept for its desk unless the front would otherwise be short.
* ``sections``: per desk, in canonical order, its best remaining stories (a
  story appears once, under its primary desk); a desk with nothing fresh is
  left out.
* ``briefs``: the best of the rest that have short headlines, at most two per section.
* No story appears twice, no two stories come from one thread, and no two
  stories are instalments of one event even when clustering left them apart.

Around the stories: the markets strip from ``public/markets.json``, a Claude
card (the newest feature or release of the last 36 hours, else a playbook
feature of the day that rotates through every feature before repeating), a
pointer to the weekend digest on Saturday and Sunday, and reading statistics.
"""

import hashlib
import math
from datetime import date, timedelta

from . import cluster, rank, threads
from .core import jsonio, log, timeutil

DEFAULTS = {"hour": 6, "frontCount": 4, "briefCount": 10, "perSection": 3}
FRESH_HOURS = 24.0
REPRINT_MIN_NEW_OUTLETS = 3   # a story already printed returns only if it gained at least this many outlets
REPRINT_GROWTH = 1.5          # ... and has at least this many times the outlets it had
FRONT_PER_SECTION = 2
BRIEFS_PER_SECTION = 2
BRIEF_TITLE_CHARS = 90
# "Too alike to print side by side": looser than thread linking, because leaving out a
# second take on one event costs nothing while printing both wastes a slot.
SAME_EVENT = {"link": 0.28, "words_share": 0.1, "strict": 0.45}
STRIP_MAX = 8
CLAUDE_UPDATE_HOURS = 36.0
CLAUDE_UPDATE_KINDS = ("feature", "release")
WORDS_PER_MINUTE = 230.0
INDEX_FILE = "index.json"


def _setting(ctx, name):
    """An edition setting from site.json, or its default when missing or not a non-negative integer."""
    value = (ctx.site.get("edition") or {}).get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return DEFAULTS[name]
    return value


# ---------------------------------------------------------------- when

def is_due(ctx, path):
    """Whether this run should print today's edition."""
    if ctx.force_edition:
        return True
    local = ctx.now.astimezone(ctx.tz)
    return local.hour >= _setting(ctx, "hour") and not path.exists()


def _edition_dates(editions_dir):
    """Dates that have an edition file, oldest first."""
    dates = []
    for path in editions_dir.glob("*.json"):
        try:
            dates.append(date.fromisoformat(path.stem).isoformat())
        except ValueError:
            continue  # index.json and anything else that is not a date
    return sorted(dates)


def _previous_printed_at(editions_dir, today):
    """When the newest edition before today was generated, or None."""
    earlier = [day for day in _edition_dates(editions_dir) if day < today]
    if not earlier:
        return None
    stored = jsonio.read_json(editions_dir / ("%s.json" % earlier[-1]), default=None)
    return timeutil.parse_date(stored.get("generatedAt")) if isinstance(stored, dict) else None


def _number(editions_dir, today):
    """Today's edition number: its existing number when reprinting, else one more than the files so far."""
    existing = jsonio.read_json(editions_dir / ("%s.json" % today), default=None)
    if isinstance(existing, dict) and isinstance(existing.get("number"), int):
        return existing["number"]
    return len([day for day in _edition_dates(editions_dir) if day != today]) + 1


def _previously_printed(editions_dir, today):
    """{story id: outlet count} for every story in the newest edition before today."""
    earlier = [day for day in _edition_dates(editions_dir) if day < today]
    if not earlier:
        return {}
    stored = jsonio.read_json(editions_dir / ("%s.json" % earlier[-1]), default=None)
    if not isinstance(stored, dict):
        return {}
    printed = [stored.get("lead")] + list(stored.get("front") or []) + list(stored.get("briefs") or [])
    for section in stored.get("sections") or []:
        printed.extend(section.get("stories") or [])
    return {story["id"]: int(story.get("sourceCount") or 1)
            for story in printed if isinstance(story, dict) and story.get("id")}


def drop_reprints(stories, printed_before):
    """Leave out a story the last edition already carried, unless coverage of it has grown a lot since.

    A story that is still gaining outlets stays "fresh" for days; without this rule the same
    headline would lead two mornings running. A real new development arrives as a new story in
    the same thread, which is unaffected. "A lot" is half as many outlets again, and at least
    three more: the story has visibly become bigger news than it was when it was printed.
    """
    kept = []
    for story in stories:
        before = printed_before.get(story.get("id"))
        now_count = int(story.get("sourceCount") or 1)
        if before is not None and now_count < max(before + REPRINT_MIN_NEW_OUTLETS, before * REPRINT_GROWTH):
            continue
        kept.append(story)
    return kept


# ---------------------------------------------------------------- stories

def eligible(stories, now, previous_printed_at):
    """Fresh, printable stories, best first."""
    cutoff = now - timedelta(hours=FRESH_HOURS)
    if previous_printed_at is not None:
        cutoff = min(cutoff, previous_printed_at)
    fresh = []
    for story in stories:
        updated = timeutil.parse_date(story.get("updatedAt"))
        if updated is None or updated < cutoff:
            continue
        if rank.quality(story.get("title"), story.get("summary"))[0] < 1.0:
            continue
        fresh.append(story)
    return rank.by_score(fresh)


class Desk:
    """Hands out stories for slots while enforcing "once", "one per thread" and "one per event"."""

    def __init__(self, stories):
        self._stories = stories
        self._used = set()
        self._threads = set()
        self._placed = []
        profiles = [threads.Profile(story) for story in stories]
        self._profiles = {profile.id: profile for profile in profiles}
        self._weights = cluster.Weights(profiles)

    def _free(self, story):
        """True when the story, its thread and its event are all still unused."""
        if story["id"] in self._used:
            return False
        thread_id = (story.get("thread") or {}).get("id")
        if thread_id is not None and thread_id in self._threads:
            return False
        profile = self._profiles[story["id"]]
        return not any(threads.similarity(profile, placed, self._weights, **SAME_EVENT) > 0.0
                       for placed in self._placed)

    def take(self, story):
        """Mark a story as printed."""
        self._used.add(story["id"])
        thread_id = (story.get("thread") or {}).get("id")
        if thread_id is not None:
            self._threads.add(thread_id)
        self._placed.append(self._profiles[story["id"]])
        return story

    def pick(self, count, accept=lambda story: True, per_section=None, tally=None):
        """Up to ``count`` free stories in score order that ``accept`` allows.

        ``per_section`` caps how many picked stories may share a primary
        section; ``tally`` carries those per-section counts across calls.
        """
        picked = []
        tally = {} if tally is None else tally
        for story in self._stories:
            if len(picked) >= count:
                break
            if not accept(story) or not self._free(story):
                continue
            if per_section is not None and tally.get(story["section"], 0) >= per_section:
                continue
            tally[story["section"]] = tally.get(story["section"], 0) + 1
            picked.append(self.take(story))
        return picked

    def pick_front(self, count):
        """The front page under the lead: news first, the routine market wrap only to fill a gap.

        The day's "markets closed higher" is widely carried and so scores well,
        but it belongs on its desk and in the markets strip, not next to the lead.
        """
        tally = {}
        front = self.pick(count, lambda story: not rank.is_market_wrap(story), FRONT_PER_SECTION, tally)
        return front + self.pick(count - len(front), per_section=FRONT_PER_SECTION, tally=tally)

    def pick_lead(self):
        """The lead: multi-outlet and not a routine market wrap when possible (see the module docstring)."""
        for accept in (
                lambda story: story["sourceCount"] >= 2 and not rank.is_market_wrap(story),
                lambda story: story["sourceCount"] >= 2,
                lambda story: not rank.is_market_wrap(story),
                lambda story: True):
            found = self.pick(1, accept)
            if found:
                return found[0]
        return None


def lay_out(stories, ctx):
    """(lead, front, sections, briefs) from eligible stories in score order."""
    desk = Desk(stories)
    lead = desk.pick_lead()
    front = desk.pick_front(_setting(ctx, "frontCount"))
    sections = []
    for section in ctx.site.get("sections") or []:
        chosen = desk.pick(_setting(ctx, "perSection"), lambda story, wanted=section["id"]: story["section"] == wanted)
        if chosen:
            sections.append({"id": section["id"], "name": section["name"], "stories": chosen})
    briefs = desk.pick(_setting(ctx, "briefCount"), lambda story: len(story["title"]) <= BRIEF_TITLE_CHARS,
                       per_section=BRIEFS_PER_SECTION)
    return lead, front, sections, briefs


# ---------------------------------------------------------------- furniture

def markets_strip(public_dir):
    """The edition's markets strip: quotes for the "strip" symbols, or None without usable data."""
    markets = jsonio.read_json(public_dir / "markets.json", default=None)
    if not isinstance(markets, dict):
        return None
    quotes = {}
    for group in markets.get("groups") or []:
        for quote in (group or {}).get("quotes") or [] if isinstance(group, dict) else []:
            if isinstance(quote, dict) and quote.get("symbol"):
                quotes.setdefault(quote["symbol"], quote)
    strip = [quotes[symbol] for symbol in markets.get("strip") or [] if symbol in quotes][:STRIP_MAX]
    if not strip:
        return None
    stamps = [stamp for stamp in (timeutil.parse_date(quote.get("asOf")) for quote in strip) if stamp is not None]
    as_of = timeutil.iso(max(stamps)) if stamps else markets.get("generatedAt")
    return {"asOf": as_of, "quotes": strip}


def _newest_update(claude_dir, now, tz):
    """The newest Claude feature or release dated within the last 36 hours, or None.

    Updates carry a date only, read here as the start of that local day.
    """
    stored = jsonio.read_json(claude_dir / "updates.json", default=None)
    entries = stored.get("entries") if isinstance(stored, dict) else None
    best, best_date = None, None
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or entry.get("kind") not in CLAUDE_UPDATE_KINDS:
            continue
        dated = timeutil.parse_date(entry.get("date"), tz)
        if dated is None or not 0.0 <= timeutil.hours_between(dated, now) <= CLAUDE_UPDATE_HOURS:
            continue
        if best is None or dated > best_date:  # the file is newest first: keep the first of the newest date
            best, best_date = entry, dated
    return best


def feature_of_the_day(claude_dir, today):
    """A playbook feature id chosen by date, or None without a playbook.

    Features are put in a fixed pseudo-random order (by a hash of their id, so
    neighbours in the playbook are not shown on consecutive days) and the day
    number indexes into it: every feature comes up once before any repeats.
    """
    playbook = jsonio.read_json(claude_dir / "playbook.json", default=None)
    features = playbook.get("features") if isinstance(playbook, dict) else None
    ids = sorted({feature["id"] for feature in features if isinstance(feature, dict) and feature.get("id")}
                 if isinstance(features, list) else [],
                 key=lambda feature_id: hashlib.sha1(feature_id.encode("utf-8")).hexdigest())
    if not ids:
        return None
    return ids[date.fromisoformat(today).toordinal() % len(ids)]


def claude_card(claude_dir, now, tz):
    """The Claude card: a recent update when there is one, else the feature of the day, else None."""
    update = _newest_update(claude_dir, now, tz)
    if update is not None:
        features = update.get("features") or []
        return {"kind": "update", "update": update, "featureId": features[0] if features else None}
    feature_id = feature_of_the_day(claude_dir, timeutil.local_date(now, tz))
    if feature_id is None:
        return None
    return {"kind": "feature", "update": None, "featureId": feature_id}


def weekend_pointer(weekend_dir, now, tz):
    """On Saturday and Sunday, a pointer to this week's weekend digest when it has been built.

    The digest built on Saturday covers the week ending Friday and is named
    for that ISO week, which is also the ISO week of the weekend itself.
    """
    if now.astimezone(tz).weekday() < 5:
        return None
    iso_week = timeutil.iso_week(now, tz)
    issue = jsonio.read_json(weekend_dir / ("%s.json" % iso_week), default=None)
    if not isinstance(issue, dict):
        return None
    papers = issue.get("papers")
    lead_paper = papers[0] if isinstance(papers, list) and papers and isinstance(papers[0], dict) else {}
    return {"isoWeek": iso_week, "title": lead_paper.get("title") or "The Weekend Review"}


def stats(printed, considered, state_dir):
    """Reading statistics: stories considered, source health and minutes to read the page."""
    health = jsonio.read_json(state_dir / "source-health.json", default=None)
    records = [record for record in health.values() if isinstance(record, dict)] if isinstance(health, dict) else []
    words = sum(len(("%s %s" % (story.get("title") or "", story.get("summary") or "")).split()) for story in printed)
    return {
        "storiesConsidered": considered,
        "sourcesOk": sum(1 for record in records if record.get("ok")),
        "sourcesTotal": len(records),
        "readMinutes": max(1, int(math.ceil(words / WORDS_PER_MINUTE))),
    }


# ---------------------------------------------------------------- index

def update_index(editions_dir, entry):
    """Rewrite ``index.json``: every edition's date, number and headline, newest first.

    Entries for files that no longer exist are dropped; an edition missing from
    the index (a lost or damaged index) is read back from its file.
    """
    stored = jsonio.read_json(editions_dir / INDEX_FILE, default=None)
    listed = stored.get("editions") if isinstance(stored, dict) else None
    known = {item["date"]: item for item in listed if isinstance(item, dict) and item.get("date")} \
        if isinstance(listed, list) else {}
    known[entry["date"]] = entry
    entries = []
    for day in _edition_dates(editions_dir):
        item = known.get(day)
        if item is None:
            printed = jsonio.read_json(editions_dir / ("%s.json" % day), default=None)
            if not isinstance(printed, dict):
                continue
            item = {"date": day, "number": printed.get("number"), "headline": printed.get("headline")}
        entries.append(item)
    entries.sort(key=lambda item: item["date"], reverse=True)
    jsonio.write_json(editions_dir / INDEX_FILE, {"editions": entries})


# ---------------------------------------------------------------- the edition

def compose(ctx, stories):
    """Today's edition object from the run's stories, or None when there is nothing to print."""
    today = timeutil.local_date(ctx.now, ctx.tz)
    fresh = eligible(stories, ctx.now, _previous_printed_at(ctx.paths.editions_dir, today))
    fresh = drop_reprints(fresh, _previously_printed(ctx.paths.editions_dir, today))
    lead, front, sections, briefs = lay_out(fresh, ctx)
    if lead is None:
        return None
    printed = [lead] + front + briefs + [story for section in sections for story in section["stories"]]
    return {
        "date": today,
        "number": _number(ctx.paths.editions_dir, today),
        "generatedAt": timeutil.iso(ctx.now),
        "headline": lead["title"],
        "lead": lead,
        "front": front,
        "briefs": briefs,
        "sections": sections,
        "markets": markets_strip(ctx.paths.public),
        "claude": claude_card(ctx.paths.claude_dir, ctx.now, ctx.tz),
        "weekend": weekend_pointer(ctx.paths.weekend_dir, ctx.now, ctx.tz),
        "stats": stats(printed, len(fresh), ctx.paths.state),
    }


def build(ctx, stories):
    """Print today's edition if it is due; returns ``{"date", "number"}`` when written, else None."""
    today = timeutil.local_date(ctx.now, ctx.tz)
    path = ctx.paths.editions_dir / ("%s.json" % today)
    if not is_due(ctx, path):
        log.debug("edition %s not due (already printed, or before the edition hour)", today)
        return None
    printed = compose(ctx, stories)
    if printed is None:
        log.warn("no fresh stories: edition %s not printed; a later run will try again", today)
        return None
    jsonio.write_json(path, printed)
    update_index(ctx.paths.editions_dir, {"date": today, "number": printed["number"],
                                          "headline": printed["headline"]})
    log.info("edition %s no. %d printed: %s", today, printed["number"], printed["headline"])
    return {"date": today, "number": printed["number"]}
