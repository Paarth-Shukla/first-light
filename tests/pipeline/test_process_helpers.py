"""Shared helpers for the process-stage tests (cluster, rank, threads, edition, process).

Not a test module itself: it loads the fixtures under tests/fixtures/process, builds
items and stories with sensible defaults, and sets up a stage context on a temporary
data directory with a frozen clock.
"""

import io
import json
import tempfile
from pathlib import Path
from unittest import mock

from pipeline import cluster, lexicon
from pipeline.core import config, jsonio, textutil, timeutil

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "process"
TZ = timeutil.zone("Asia/Kolkata")
NOW = "2026-11-11T14:30:00Z"  # 20:00 in Kolkata: after the edition hour, late enough for a full day
LIVE_DAYS = ["2026-11-09", "2026-11-10", "2026-11-11"]


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def real_items():
    """The real items snapshot: a list of Item objects as the fetch stage stores them."""
    return fixture("items.json")["items"]


def make_item(title, source_name="Reuters", published="2026-11-11T08:00:00Z", **fields):
    """A complete Item with a deterministic id; ``fields`` override any key."""
    item = {
        "title": title, "summary": "", "source": "test", "sourceName": source_name, "publishedAt": published,
        "firstSeenAt": published, "image": None, "section": "world", "topics": [], "feedRank": None,
        "publisher": None, "points": None, "comments": None, "alt": [],
    }
    item.update(fields)
    item.setdefault("id", textutil.stable_id("i", title, item["sourceName"], item["publisher"], published))
    item.setdefault("url", "https://example.org/%s" % item["id"])
    return item


def make_doc(item):
    """The clustering view of an item, classified the way the process stage does it."""
    title, summary = item["title"], item.get("summary") or ""
    text = "%s. %s" % (title, summary) if summary else title
    return cluster.Doc(item, lexicon.match_entities(title), lexicon.match_entities(text), TZ)


def cluster_items(items, days, state=None):
    """Cluster ``items`` and return the state (``{"items": ..., "stories": ...}``)."""
    state = cluster.empty_state() if state is None else state
    cluster.assign([make_doc(item) for item in items], state, days)
    return state


def make_story(story_id, title, score=50.0, section="world", sources=2, updated="2026-11-11T12:00:00Z", **fields):
    """A Story as the process stage publishes it; ``sources`` is a count or a list of outlet names."""
    names = sources if isinstance(sources, list) else ["Outlet %d" % index for index in range(1, sources + 1)]
    story = {
        "id": story_id, "title": title, "summary": "Summary of %s." % title,
        "url": "https://example.org/%s" % story_id, "image": None,
        "section": section, "sections": [section], "entities": [], "tickers": [],
        "publishedAt": updated, "updatedAt": updated, "day": timeutil.local_date(timeutil.parse_date(updated), TZ),
        "sources": [{"id": "test", "name": name, "tier": 2, "title": title,
                     "url": "https://example.org/%s/%d" % (story_id, index), "publishedAt": updated}
                    for index, name in enumerate(names)],
        "sourceCount": len(names), "score": score,
        "signals": {"breadth": 0.5, "tier": 0.6, "recency": 0.9, "velocity": 0.2, "attention": 0.0, "editorial": 0.0},
        "why": ["%d outlets" % len(names)] if len(names) > 1 else [], "thread": None,
    }
    story.update(fields)
    return story


def stage_context(owner, now=NOW, force_edition=False):
    """A stage context on a fresh temporary data dir with the clock frozen at ``now``.

    ``owner`` is a test (cleaned up when it finishes) or a test class (cleaned
    up after its last test, for an expensive run shared by many assertions).
    The stage's log lines are kept out of the test output and collected in
    ``owner.log_output`` (a StringIO) for tests that check a warning.
    """
    cleanup = owner.addClassCleanup if isinstance(owner, type) else owner.addCleanup
    directory = tempfile.TemporaryDirectory()
    cleanup(directory.cleanup)
    owner.log_output = io.StringIO()
    patcher = mock.patch("sys.stderr", new=owner.log_output)
    patcher.start()
    cleanup(patcher.stop)
    timeutil.set_now(now)
    cleanup(timeutil.set_now, None)
    ctx = config.context(data_dir=directory.name, force_edition=force_edition)
    ctx.paths.ensure()
    return ctx


def later_context(ctx, now, force_edition=False):
    """A later run on the same data directory (the clock stays frozen until the owner's cleanup)."""
    timeutil.set_now(now)
    return config.context(data_dir=str(ctx.paths.data), force_edition=force_edition)


def store_items(ctx, items):
    """Write items into state/items day files, filed by the local date of publishedAt."""
    days = {}
    for item in items:
        day = timeutil.local_date(timeutil.parse_date(item["publishedAt"]), ctx.tz)
        days.setdefault(day, {})[item["id"]] = item
    for day, entries in days.items():
        jsonio.write_json(ctx.paths.items_dir / ("%s.json" % day), {"date": day, "items": entries}, sort_keys=True)
