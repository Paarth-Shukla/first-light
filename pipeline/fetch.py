"""Fetch stage: config/sources.json -> state/items/<local date>.json and state/source-health.json.

Every enabled source is fetched through its adapter (``pipeline.adapters``),
concurrently but politely: a pool of 8 workers, at least 0.5 s between two
requests to one host, and Google News and Reddit each fetched strictly one
source at a time with a pause in between, because those two throttle.
Conditional requests (ETag / Last-Modified) make an unchanged feed cost a 304.

Items are de-duplicated within the run (same canonical URL, then the same
normalised headline from the same publisher; the higher-tier source wins and
absorbs the other's points and topics) and merged into the day files of their
``publishedAt`` local date. An item already stored is never re-filed and keeps
its ``firstSeenAt`` and ``publishedAt``; only what legitimately moves is
refreshed (points, comments, feedRank, and a summary/image that was missing).
Day files older than ``site.json -> retentionDays`` are deleted.

A failing source never fails the stage: its error lands in source health
(``{ok, items, newItems, ms, error, lastOkAt, consecutiveFailures}``) and its
previous items stay in place.
"""

import json
import re
import time
import traceback
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta

from . import feeds
from .adapters import ADAPTERS
from .core import config, jsonio, log, net, textutil, timeutil

WORKERS = 8
HOST_INTERVAL_S = 0.5
SEQUENTIAL_PAUSE_S = 1.0
DEFAULT_RETENTION_DAYS = 90
HEALTH_FILE = "source-health.json"
CACHE_FILE = "http-cache.json"

MODES = ("curated", "firehose", "official")
REQUIRED = ("id", "name", "url", "kind", "section", "tier", "mode", "maxItems", "maxAgeHours")
_DAY_FILE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MIN_TITLE_WORDS = 4  # shorter headlines ("Live updates", "Markets wrap") recur across stories


# ---------------------------------------------------------------- sources

def _problem(source, sections, seen):
    """Why a source entry cannot be used, or None. Config is hand-edited; say exactly what is wrong."""
    missing = [key for key in REQUIRED if key not in source]
    if missing:
        return "missing %s" % ", ".join(missing)
    if source["id"] in seen:
        return "duplicate id"
    if source["kind"] not in ADAPTERS:
        return "unknown kind %r" % source["kind"]
    if source["section"] not in sections:
        return "unknown section %r" % source["section"]
    if source["tier"] not in (1, 2, 3) or source["mode"] not in MODES:
        return "tier must be 1-3 and mode one of %s" % "/".join(MODES)
    for key in ("maxItems", "maxAgeHours"):
        if isinstance(source[key], bool) or not isinstance(source[key], (int, float)) or source[key] <= 0:
            return "%s must be a positive number" % key
    if source.get("urlPattern"):
        try:
            re.compile(source["urlPattern"])
        except re.error as err:
            return "bad urlPattern: %s" % err
    return None


def load_sources(site):
    """Enabled, valid sources in config order, plus ``{id: problem}`` for broken entries.

    A broken entry is reported in source health instead of failing the run;
    a missing or unreadable sources.json is a real failure and raises.
    """
    entries = config.load("sources").get("sources")
    if not isinstance(entries, list):
        raise config.ConfigError("config/sources.json must hold a \"sources\" list")
    sections = {section["id"] for section in site.get("sections", [])}
    sources, problems, seen = [], {}, set()
    for index, source in enumerate(entries):
        if not isinstance(source, dict):
            problems["sources[%d]" % index] = "entry is not an object"
            continue
        if source.get("enabled", True) is False:
            continue
        problem = _problem(source, sections, seen)
        key = str(source.get("id") or "sources[%d]" % index)
        if problem:
            problems[key if key not in seen else "%s#%d" % (key, index)] = problem
            continue
        seen.add(source["id"])
        sources.append(source)
    return sources, problems


# ---------------------------------------------------------------- fetching

class SourceContext:
    """What an adapter may use: the run's clock and a polite, cached GET."""

    def __init__(self, now, cache, force):
        self.now = now
        self._cache = cache
        self._conditional = None if force else cache
        self._fetched = []
        self.requests = 0
        self.unchanged = 0

    def get(self, url, headers=None):
        """Body bytes, or None when the server says the cached copy is current (304)."""
        net.polite(url, HOST_INTERVAL_S)
        response = net.fetch(url, headers=headers, cache=self._conditional)
        self._fetched.append(url)
        self.requests += 1
        if response.not_modified:
            self.unchanged += 1
            return None
        return response.body

    def json(self, url):
        """Decoded JSON, or None on 304. An error page with status 200 is a FeedError."""
        body = self.get(url, headers={"Accept": "application/json, */*;q=0.8"})
        if body is None:
            return None
        try:
            return json.loads(body.decode("utf-8-sig", errors="replace"))
        except ValueError as err:
            raise feeds.FeedError("response is not valid JSON") from err

    def forget(self):
        """Drop validators for this source's URLs, so a body we could not use is fetched again."""
        if self._cache is not None:
            for url in self._fetched:
                self._cache.forget(url)


@dataclass
class Result:
    """The outcome of fetching one source."""

    source: dict
    items: list
    error: object = None   # str when the source failed
    ms: int = 0
    unchanged: bool = False


def fetch_one(source, now, cache, force=False):
    """Fetch and parse one source. Never raises (except KeyboardInterrupt): failures become ``error``."""
    ctx = SourceContext(now, cache, force)
    started = time.monotonic()
    items, error = [], None
    try:
        items = ADAPTERS[source["kind"]](source, ctx)
    except (net.NetError, feeds.FeedError) as err:
        error = str(err)
    except Exception as err:  # an adapter bug must cost one source, not the run
        error = " ".join(("%s: %s" % (type(err).__name__, err)).split())[:300]
        log.error("%s: adapter crashed\n%s", source["id"], traceback.format_exc().rstrip())
    if error is not None:
        ctx.forget()
    ms = int((time.monotonic() - started) * 1000)
    unchanged = error is None and ctx.requests > 0 and ctx.unchanged == ctx.requests
    if error is not None:
        log.warn("%-28s FAILED %s", source["id"], error)
    else:
        log.debug("%-28s %3d items %6d ms%s", source["id"], len(items), ms, " (not modified)" if unchanged else "")
    return Result(source, items, error, ms, unchanged)


def _lane(source):
    """Sources sharing a lane are fetched one after another: hosts that throttle hard."""
    if source["kind"] == "google-news":
        return "google-news"
    host = (urllib.parse.urlsplit(source["url"]).hostname or "").lower()
    if host == "reddit.com" or host.endswith(".reddit.com"):
        return "reddit"
    return None


def _fetch_lane(sources, now, cache, force):
    """Fetch a lane's sources in order with a pause between them."""
    results = []
    for position, source in enumerate(sources):
        if position:
            time.sleep(SEQUENTIAL_PAUSE_S)
        results.append(fetch_one(source, now, cache, force))
    return results


def fetch_all(sources, now, cache, force=False):
    """Fetch every source (lanes sequential, the rest concurrent); results in config order."""
    lanes, singles = {}, []
    for source in sources:
        lane = _lane(source)
        if lane:
            lanes.setdefault(lane, []).append(source)
        else:
            singles.append(source)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(_fetch_lane, lane, now, cache, force) for lane in lanes.values()]
        futures += [pool.submit(_fetch_lane, [source], now, cache, force) for source in singles]
        results = [result for future in futures for result in future.result()]
    order = {id(source): index for index, source in enumerate(sources)}
    return sorted(results, key=lambda result: order[id(result.source)])


# ---------------------------------------------------------------- de-duplication

def title_key(item):
    """Same headline from the same outlet: a duplicate even when the URLs differ."""
    norm = textutil.norm_title(item["title"])
    if len(norm.split()) < _MIN_TITLE_WORDS:
        return None
    return (item.get("publisher") or item["sourceName"]).strip().lower() + "|" + norm


def absorb(kept, other):
    """Fold a duplicate's extra signal into the item we keep; returns True if anything changed."""
    before = json.dumps(kept, sort_keys=True)
    for key in ("points", "comments"):
        values = [value for value in (kept.get(key), other.get(key)) if value is not None]
        kept[key] = max(values) if values else None
    kept["topics"] = list(dict.fromkeys((kept.get("topics") or []) + (other.get("topics") or [])))
    if not kept.get("image") and other.get("image"):
        kept["image"] = other["image"]
    if not kept.get("summary") and other.get("summary"):
        kept["summary"] = other["summary"]
    seen = {(alt["title"], alt["publisher"]) for alt in kept.get("alt") or []}
    for alt in other.get("alt") or []:
        if (alt["title"], alt["publisher"]) not in seen:
            kept.setdefault("alt", []).append(alt)
    return json.dumps(kept, sort_keys=True) != before


def dedupe(results):
    """One item per URL and per (publisher, headline); the best-tier source keeps it."""
    order = {id(result): index for index, result in enumerate(results)}
    ranked = sorted((r for r in results if r.items), key=lambda r: (r.source["tier"], order[id(r)]))
    by_id, by_title, kept = {}, {}, []
    for result in ranked:
        for item in result.items:
            key = title_key(item)
            existing = by_id.get(item["id"]) or (by_title.get(key) if key else None)
            if existing is not None:
                absorb(existing, item)
                continue
            by_id[item["id"]] = item
            if key:
                by_title[key] = item
            kept.append(item)
    return kept


# ---------------------------------------------------------------- storage

def _refresh(stored, fresh):
    """Update the fields that legitimately change between runs; True if the stored item changed."""
    changed = False
    same_source = stored.get("source") == fresh["source"]
    for key in ("points", "comments") + (("feedRank",) if same_source else ()):
        if fresh.get(key) is not None and stored.get(key) != fresh[key]:
            stored[key] = fresh[key]
            changed = True
    if same_source and fresh.get("alt") and stored.get("alt") != fresh["alt"]:
        stored["alt"] = fresh["alt"]
        changed = True
    return absorb(stored, {"topics": fresh.get("topics"), "image": fresh.get("image"),
                           "summary": fresh.get("summary")}) or changed


class ItemStore:
    """The day files an item of this run could belong to, indexed by id and by title key."""

    def __init__(self, items_dir, tz, now, window_hours):
        self.dir = items_dir
        self.tz = tz
        self.days = {}
        self.dirty = set()
        self.by_id = {}
        self.by_title = {}
        day = now - timedelta(hours=window_hours)
        while day < now:
            self._day(timeutil.local_date(day, tz))
            day += timedelta(days=1)
        self._day(timeutil.local_date(now, tz))

    def _day(self, date):
        """Load (once) and index one day file; a missing or malformed file starts empty."""
        if date in self.days:
            return self.days[date]
        path = self.dir / (date + ".json")
        data = jsonio.read_json(path, default=None)
        if data is not None and not (isinstance(data, dict) and isinstance(data.get("items"), dict)):
            log.warn("%s is not an items file; starting it afresh", path)
            data = None
        data = data or {"date": date, "items": {}}
        data["date"] = date
        items = {key: item for key, item in data["items"].items() if isinstance(item, dict) and item.get("title")}
        if len(items) != len(data["items"]):
            log.warn("%s: dropped %d malformed items", path, len(data["items"]) - len(items))
            data["items"] = items
            self.dirty.add(date)
        self.days[date] = data
        for item_id, item in items.items():
            self.by_id[item_id] = date
            key = title_key(item)
            if key:
                self.by_title.setdefault(key, item_id)
        return data

    def find(self, item):
        """The stored copy of this item (same id, or same outlet and headline), or None."""
        item_id = item["id"] if item["id"] in self.by_id else None
        if item_id is None:
            key = title_key(item)
            item_id = self.by_title.get(key) if key else None
        if item_id is None:
            return None
        date = self.by_id[item_id]
        return self.days[date]["items"][item_id], date

    def merge(self, items, now):
        """Add new items and refresh known ones; returns new-item counts per source id."""
        new = Counter()
        for item in items:
            found = self.find(item)
            if found is not None:
                stored, date = found
                if _refresh(stored, item):
                    self.dirty.add(date)
                continue
            item["firstSeenAt"] = timeutil.iso(now)
            date = timeutil.local_date(timeutil.parse_date(item["publishedAt"]), self.tz)
            self._day(date)["items"][item["id"]] = item
            self.by_id[item["id"]] = date
            key = title_key(item)
            if key:
                self.by_title.setdefault(key, item["id"])
            self.dirty.add(date)
            new[item["source"]] += 1
        return new

    def save(self):
        """Write every changed day file (sorted ids keep the data branch's diffs small)."""
        for date in sorted(self.dirty):
            jsonio.write_json(self.dir / (date + ".json"), self.days[date], sort_keys=True)
        written = len(self.dirty)
        self.dirty = set()
        return written


def prune(items_dir, tz, now, retention_days):
    """Delete day files older than the retention window; returns how many went."""
    cutoff = timeutil.local_date(now - timedelta(days=retention_days), tz)
    removed = 0
    for path in sorted(items_dir.glob("*.json")):
        if not _DAY_FILE.match(path.stem) or path.stem >= cutoff:
            continue
        try:
            path.unlink()
            removed += 1
        except OSError as err:
            log.warn("could not delete expired %s (%s)", path, err)
    return removed


# ---------------------------------------------------------------- health

def health(previous, results, problems, new_counts, now):
    """The new source-health map. Sources no longer configured drop out."""
    stamp = timeutil.iso(now)
    records = {}

    def failure(source_id, error, ms):
        old = previous.get(source_id) if isinstance(previous.get(source_id), dict) else {}
        return {"ok": False, "items": 0, "newItems": 0, "ms": ms, "error": error,
                "lastOkAt": old.get("lastOkAt"),
                "consecutiveFailures": int(old.get("consecutiveFailures") or 0) + 1}

    for result in results:
        source_id = result.source["id"]
        if result.error is not None:
            records[source_id] = failure(source_id, result.error, result.ms)
            continue
        old = previous.get(source_id) if isinstance(previous.get(source_id), dict) else {}
        count = int(old.get("items") or 0) if result.unchanged else len(result.items)
        records[source_id] = {"ok": True, "items": count, "newItems": new_counts.get(source_id, 0),
                              "ms": result.ms, "error": None, "lastOkAt": stamp,
                              "consecutiveFailures": 0}
    for source_id, problem in problems.items():
        records[source_id] = failure(source_id, "invalid source config: " + problem, 0)
    return records


# ---------------------------------------------------------------- stage

def _window_hours(sources):
    """How far back an item of this run can be dated, plus a day of slack for time zones."""
    return max([float(source["maxAgeHours"]) for source in sources] or [48.0]) + 24.0


def _offline_counts(ctx, sources):
    """--offline: touch nothing, report what is already stored."""
    files = sorted(ctx.paths.items_dir.glob("*.json")) if ctx.paths.items_dir.is_dir() else []
    store = ItemStore(ctx.paths.items_dir, ctx.tz, ctx.now, _window_hours(sources))
    recent = sum(len(day["items"]) for day in store.days.values())
    log.info("offline: %d day files, %d items in the last %d h", len(files), recent,
             _window_hours(sources))
    return {"offline": True, "files": len(files), "recentItems": recent, "sources": len(sources)}


def run(ctx):
    """Fetch every enabled source, merge into state/items, write source health. Returns counts."""
    sources, problems = load_sources(ctx.site)
    if ctx.offline:
        return _offline_counts(ctx, sources)
    state = ctx.paths.state
    ctx.paths.items_dir.mkdir(parents=True, exist_ok=True)
    cache = net.HttpCache(state / CACHE_FILE)
    for source_id, problem in problems.items():
        log.warn("%s: invalid source config: %s", source_id, problem)

    results = fetch_all(sources, ctx.now, cache, ctx.force)
    items = dedupe(results)
    store = ItemStore(ctx.paths.items_dir, ctx.tz, ctx.now, _window_hours(sources))
    new_counts = store.merge(items, ctx.now)
    written = store.save()
    retention = int(ctx.site.get("retentionDays") or DEFAULT_RETENTION_DAYS)
    pruned = prune(ctx.paths.items_dir, ctx.tz, ctx.now, retention)

    health_path = state / HEALTH_FILE
    previous = jsonio.read_json(health_path, default={})
    records = health(previous if isinstance(previous, dict) else {}, results, problems, new_counts, ctx.now)
    jsonio.write_json(health_path, records, sort_keys=True)
    cache.save()  # only after the items are safely stored (see HttpCache)

    failed = sum(1 for record in records.values() if not record["ok"])
    counts = {
        "sources": len(records),
        "ok": len(records) - failed,
        "failed": failed,
        "unchanged": sum(1 for result in results if result.unchanged),
        "items": len(items),
        "newItems": sum(new_counts.values()),
        "filesWritten": written,
        "pruned": pruned,
    }
    log.info("%d/%d sources ok, %d items, %d new", counts["ok"], counts["sources"], counts["items"],
             counts["newItems"])
    return counts
