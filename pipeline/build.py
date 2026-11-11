"""Build stage: write the site manifest and status report, then assemble ``dist/``.

Every other stage writes JSON into ``data/public``; this one turns that into a
deployable site. It runs last so ``status.json`` can report on every stage of
the run, and it is the only stage that touches ``dist/``.

``dist/`` is assembled in a sibling ``dist.tmp`` and swapped in with two
renames, so a server reading ``dist/`` sees either the previous build or the
new one, never a tree that is still being copied. ``data/state`` is never
copied: it holds working state that is not meant to be published.
"""

import os
import re
import shutil
from datetime import datetime, timedelta

from .core import config, jsonio, log, timeutil

SCHEMA = 1
DATE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WEEK_NAME = re.compile(r"^\d{4}-W\d{2}$")
NOT_FETCHED = "no report yet"


def run(ctx):
    """Write ``public/status.json`` and ``public/manifest.json``, then publish ``dist/``.

    Missing inputs (no edition yet, no source report, no ``site/``) degrade the
    output and are listed in ``counts["problems"]``; only a failure to write the
    outputs themselves raises, because then there is nothing to publish.
    """
    paths, problems = ctx.paths, []
    sources = _source_rows(paths, problems)
    status = {
        "generatedAt": timeutil.iso(ctx.now),
        "stages": _stage_rows(paths),
        "sources": sources,
    }
    listing = _listing(paths, problems)
    manifest = _manifest(ctx, listing, sources, problems)
    jsonio.write_json(paths.public / "status.json", status)
    jsonio.write_json(paths.public / "manifest.json", manifest)
    site_files, data_files, dist_bytes = _publish(paths, problems)
    for problem in problems:
        log.warn("%s", problem)
    return {
        "editions": len(listing["editions"]),
        "days": len(listing["days"]),
        "weekends": len(listing["weekends"]),
        "stories": listing["stories"],
        "sources": len(sources),
        "sourcesOk": sum(1 for row in sources if row["ok"]),
        "stages": len(status["stages"]),
        "siteFiles": site_files,
        "dataFiles": data_files,
        "distBytes": dist_bytes,
        "problems": problems[:12],
    }


# ---- status ---------------------------------------------------------------------------------


def _stage_rows(paths):
    """The newest ``state/run.json`` record of each stage, in the order they last ran.

    The build's own record is left out: it is written after this file, and a
    build that failed never publishes a status file to report itself in.
    """
    history = jsonio.read_json(paths.state / "run.json", default=[])
    if not isinstance(history, list):
        log.warn("state/run.json is not a list; status.json will list no stages")
        return []
    latest = {}
    for record in history:
        if isinstance(record, dict) and isinstance(record.get("stage"), str) and record["stage"] != "build":
            latest.pop(record["stage"], None)  # re-insert so dict order follows the newest run
            latest[record["stage"]] = record
    return [_stage_row(record) for record in latest.values()]


def _stage_row(record):
    """Exactly the contract's keys, so a stray field in run.json never reaches the site."""
    counts = record.get("counts")
    return {
        "stage": record["stage"],
        "ok": bool(record.get("ok")),
        "startedAt": record.get("startedAt"),
        "durationSec": record.get("durationSec"),
        "error": record.get("error"),
        "counts": counts if isinstance(counts, dict) else {},
    }


def _source_rows(paths, problems):
    """One row per enabled source in ``config/sources.json``, joined with its last health report.

    Config is the list of record (a removed source's old health entry is not
    shown); an enabled source with no report yet is shown as not ok, since
    nothing has been read from it.
    """
    health = jsonio.read_json(paths.state / "source-health.json", default={})
    if not isinstance(health, dict):
        problems.append("state/source-health.json is not an object; sources shown without health")
        health = {}
    try:
        configured = config.load("sources").get("sources")
    except config.ConfigError as err:
        problems.append("sources.json unreadable, status lists reported sources only: %s" % err)
        configured = [{"id": source_id} for source_id in sorted(health)]
    if not isinstance(configured, list):
        problems.append("sources.json has no 'sources' list; status lists no sources")
        configured = []
    rows = []
    for source in configured:
        if isinstance(source, dict) and isinstance(source.get("id"), str) and source.get("enabled", True):
            report = health.get(source["id"])
            rows.append(_source_row(source, report if isinstance(report, dict) else None))
    return rows


def _source_row(source, report):
    """Merge a source's config identity with its health report into the contract's row."""
    report = report or {"ok": False, "error": NOT_FETCHED}
    return {
        "id": source["id"],
        "name": source.get("name") or source["id"],
        "section": source.get("section"),
        "ok": bool(report.get("ok")),
        "items": report.get("items", 0),
        "newItems": report.get("newItems", 0),
        "ms": report.get("ms"),
        "error": report.get("error"),
        "lastOkAt": report.get("lastOkAt"),
    }


# ---- manifest -------------------------------------------------------------------------------


def _listing(paths, problems):
    """What is on disk and readable: edition, story-day and weekend files, newest first.

    A file is listed only if it parses as a JSON object, so the site is never
    sent to a file it cannot read. Day files are read in full anyway to count
    stories, and edition files to find the current edition's number.
    """
    editions = _readable(paths.editions_dir, DATE_NAME, problems)
    days = _readable(paths.stories_dir, DATE_NAME, problems)
    weekends = _readable(paths.weekend_dir, WEEK_NAME, problems)
    stories = 0
    for name, doc in days:
        if isinstance(doc.get("stories"), list):
            stories += len(doc["stories"])
        else:
            problems.append("stories/%s.json has no stories list" % name)
    current = None
    if editions:
        name, doc = editions[0]
        current = {"date": name, "number": doc.get("number")}
    return {
        "editions": [name for name, _ in editions],
        "days": [name for name, _ in days],
        "weekends": [name for name, _ in weekends],
        "stories": stories,
        "edition": current,
    }


def _readable(directory, pattern, problems):
    """``[(name, document)]`` for ``<name>.json`` files matching ``pattern``, newest name first."""
    try:
        names = sorted((entry.name[:-5] for entry in os.scandir(directory)
                        if entry.is_file() and entry.name.endswith(".json")
                        and pattern.match(entry.name[:-5])), reverse=True)
    except FileNotFoundError:
        return []
    found = []
    for name in names:
        doc = jsonio.read_json(directory / (name + ".json"))
        if isinstance(doc, dict):
            found.append((name, doc))
        else:
            problems.append("%s/%s.json is unreadable; left out of the manifest" % (directory.name, name))
    return found


def _manifest(ctx, listing, sources, problems):
    """The site's table of contents (contract: Public: manifest and status).

    ``site.editionHour`` is an addition the frontend reads to say when the
    next edition is due.
    """
    site = ctx.site
    return {
        "schema": SCHEMA,
        "builtAt": timeutil.iso(ctx.now),
        "site": {
            "name": site.get("name"),
            "tagline": site.get("tagline"),
            "timezone": site.get("timezone"),
            "editionHour": (site.get("edition") or {}).get("hour", 6),
        },
        "sections": [{"id": s.get("id"), "name": s.get("name")} for s in site.get("sections", [])],
        "edition": listing["edition"],
        "editions": listing["editions"],
        "days": listing["days"],
        "weekends": listing["weekends"],
        "counts": {
            "stories": listing["stories"],
            "sources": len(sources),
            "sourcesOk": sum(1 for row in sources if row["ok"]),
        },
        "nextBuild": next_build(ctx.now, ctx.tz, site.get("schedule"), problems),
    }


def next_build(now, tz, schedule, problems):
    """The next scheduled run after ``now`` as an ISO UTC string, or None when no schedule is set.

    ``schedule`` is site.json's optional list of local hours (0-23) at which
    the pipeline runs. Without one the site cannot promise a time, so it says
    nothing rather than guess.
    """
    if schedule is None:
        return None
    if (not isinstance(schedule, list) or not schedule
            or not all(isinstance(h, int) and not isinstance(h, bool) and 0 <= h <= 23 for h in schedule)):
        problems.append("site.json schedule must be a list of hours 0-23; nextBuild left null")
        return None
    local = now.astimezone(tz)
    days = (local.date(), local.date() + timedelta(days=1))
    # Tomorrow's slots are always later than now, so there is always a candidate.
    candidates = [datetime(day.year, day.month, day.day, hour, tzinfo=tz) for day in days for hour in schedule]
    return timeutil.iso(min(slot for slot in candidates if slot > local))


# ---- dist -----------------------------------------------------------------------------------


def _skip_hidden(_directory, names):
    """copytree ignore hook: dotfiles are editor litter or half-written atomic temp files."""
    return [name for name in names if name.startswith(".")]


def _publish(paths, problems):
    """Assemble the site in ``dist.tmp`` and swap it in; returns (site files, data files, bytes)."""
    dist = paths.dist
    staging = dist.with_name(dist.name + ".tmp")
    _remove_tree(staging)  # leftover from an interrupted build
    if paths.site.is_dir():
        shutil.copytree(paths.site, staging, ignore=_skip_hidden)
    else:
        problems.append("no site/ directory; dist/ holds the data only")
        staging.mkdir(parents=True)
    site_files = _count_files(staging)
    if (staging / "data").exists():
        problems.append("site/data exists and was replaced by data/public")
        _remove_tree(staging / "data")
        site_files = _count_files(staging)
    shutil.copytree(paths.public, staging / "data", ignore=_skip_hidden)
    (staging / ".nojekyll").write_bytes(b"")
    data_files = _count_files(staging / "data")
    total = _tree_bytes(staging)
    _swap(staging, dist)
    return site_files, data_files, total


def _swap(staging, dist):
    """Replace ``dist`` with ``staging`` using renames; the old tree is restored if the second fails."""
    retired = dist.with_name(dist.name + ".old")
    _remove_tree(retired)
    had_previous = os.path.lexists(dist)
    if had_previous:
        os.rename(dist, retired)
    try:
        os.rename(staging, dist)
    except OSError:
        if had_previous:
            os.rename(retired, dist)
        raise
    _remove_tree(retired)


def _remove_tree(path):
    """Delete a directory tree (or a stray file or link) if it exists."""
    if os.path.islink(path) or os.path.isfile(path):
        os.unlink(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


def _count_files(root):
    """Number of regular files under ``root``."""
    return sum(len(files) for _, _, files in os.walk(root))


def _tree_bytes(root):
    """Total size of the files under ``root``, for the run log."""
    return sum(os.path.getsize(os.path.join(base, name)) for base, _, files in os.walk(root) for name in files)
