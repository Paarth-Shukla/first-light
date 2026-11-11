"""Command line entry point: ``python3 -m pipeline <stage> [options]``.

The CLI owns everything a stage should not have to think about: parsing flags,
freezing the clock, switching the network off, building the context, timing
the run, catching whatever the stage raises and recording the outcome in
``state/run.json`` (which ``build`` folds into ``status.json``). A stage is
just a module with ``run(ctx) -> dict of counts``.

``all`` runs every stage in order with one shared context, carries on past a
failed stage, and succeeds if the site was built. Stages that only do work on
some days (``papers``) decide that themselves from ``ctx.now`` and ``ctx.force``.

Exit status: 0 success, 1 the stage (or, for ``all``, the build) failed,
2 bad arguments or config, 3 the stage is not implemented, 130 interrupted.
"""

import argparse
import importlib
import sys
import time
import traceback

from .core import config, jsonio, log, net, timeutil

# Stage name -> module exposing run(ctx). Imported lazily so one broken or
# missing stage cannot stop the others from running.
STAGES = {
    "fetch": "pipeline.fetch",
    "markets": "pipeline.markets",
    "process": "pipeline.process",
    "papers": "pipeline.papers",
    "claude": "pipeline.claude_updates",
    "search": "pipeline.searchindex",
    "build": "pipeline.build",
}
# process freezes the morning edition, which embeds the market strip, the Claude
# card and (at weekends) the Weekend Review pointer, so every stage it reads from
# runs before it. markets reads latest.json for movers, so it sees the previous
# run's stories: one run behind there is harmless, a frozen edition missing the
# Saturday review is not.
ALL_ORDER = ("fetch", "markets", "claude", "papers", "process", "search", "build")

RUN_LOG_KEEP = 60
NOT_IMPLEMENTED = "stage not implemented"

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_NOT_IMPLEMENTED = 3
EXIT_INTERRUPTED = 130


def _datetime_arg(text):
    """argparse type for --now: any date ``timeutil.parse_date`` understands."""
    parsed = timeutil.parse_date(text)
    if parsed is None:
        raise argparse.ArgumentTypeError("not a date/time: %r (try 2026-11-11T06:00:00Z)" % text)
    return parsed


def _parser():
    parser = argparse.ArgumentParser(
        prog="python3 -m pipeline",
        description="First Light pipeline: fetch headlines and build the static site's data.",
    )
    parser.add_argument("stage", choices=list(STAGES) + ["all"],
                        help="one stage, or 'all' to run %s" % ", ".join(ALL_ORDER))
    parser.add_argument("--data", metavar="DIR", help="data directory (default: <repo>/data)")
    parser.add_argument("--dist", metavar="DIR", help="build output directory (default: <repo>/dist)")
    parser.add_argument("--now", metavar="ISO", type=_datetime_arg,
                        help="pretend this is the current time (tests, backfills)")
    parser.add_argument("--offline", action="store_true", help="no network; reuse existing state")
    parser.add_argument("--force", action="store_true", help="run work that is not due yet")
    parser.add_argument("--force-edition", action="store_true",
                        help="rewrite today's frozen edition (development)")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug output")
    return parser


def _load_stage(name):
    """Import a stage's module, or return None when that stage has not been written yet.

    Only the stage module itself being absent counts as "not implemented"; a
    missing import inside an existing stage is a real failure and propagates.
    """
    module_name = STAGES[name]
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as err:
        if err.name == module_name:
            return None
        raise


def _describe(err):
    """One short line for run.json; the traceback goes to the log."""
    text = "%s: %s" % (type(err).__name__, err)
    return " ".join(text.split())[:300]


def _counts(result):
    """A stage should return a dict of counts; anything else is noted, not fatal."""
    if result is None:
        return {}
    if not isinstance(result, dict):
        log.warn("run() returned %s instead of a dict of counts", type(result).__name__)
        return {}
    try:
        jsonio.dumps(result)
    except (TypeError, ValueError) as err:
        log.warn("run() returned counts that cannot be stored as JSON (%s)", err)
        return {}
    return result


def _append_run(paths, record):
    """Append to state/run.json, keeping the newest RUN_LOG_KEEP records (a JSON array, oldest first)."""
    path = paths.state / "run.json"
    history = jsonio.read_json(path, default=[])
    if not isinstance(history, list):
        log.warn("%s was not a list; starting a new run log", path)
        history = []
    history.append(record)
    try:
        jsonio.write_json(path, history[-RUN_LOG_KEEP:])
    except (OSError, TypeError, ValueError) as err:
        log.error("could not record the run in %s: %s", path, err)


def _execute(name, ctx):
    """Run one stage; returns (counts, error). KeyboardInterrupt is left to the caller."""
    try:
        module = _load_stage(name)
        if module is None:
            log.error("%s: %s", NOT_IMPLEMENTED, name)
            return {}, NOT_IMPLEMENTED
        ctx.paths.ensure()
        return _counts(module.run(ctx)), None
    except SystemExit as err:
        if err.code in (None, 0):
            return {}, None
        log.error("stage exited with status %r", err.code)
        return {}, "exited with status %r" % (err.code,)
    except Exception as err:  # a stage may raise anything; the run must go on
        log.error("stage failed: %s\n%s", _describe(err), traceback.format_exc().rstrip())
        return {}, _describe(err)


def run_stage(name, ctx):
    """Run a stage, time it, and record ``{stage, ok, startedAt, durationSec, error, counts}``."""
    log.set_stage(name)
    started_at = timeutil.iso(timeutil.now_utc())
    clock = time.monotonic()
    interrupted = False
    try:
        counts, error = _execute(name, ctx)
    except KeyboardInterrupt:
        counts, error, interrupted = {}, "interrupted", True
    record = {
        "stage": name,
        "ok": error is None,
        "startedAt": started_at,
        "durationSec": round(time.monotonic() - clock, 2),
        "error": error,
        "counts": counts,
    }
    _append_run(ctx.paths, record)
    if interrupted:
        raise KeyboardInterrupt
    if record["ok"]:
        log.info("done in %.1f s %s", record["durationSec"], jsonio.dumps(counts) if counts else "")
    return record


def _exit_code(stage, records):
    """Single stage: its own outcome. 'all': success means the site got built."""
    if stage == "all":
        log.set_stage("all")
        for record in records:
            log.info("%-8s %-6s %6.1f s  %s", record["stage"], "ok" if record["ok"] else "FAILED",
                     record["durationSec"], record["error"] or "")
        return EXIT_OK if records[-1]["ok"] else EXIT_FAILED
    record = records[0]
    if record["ok"]:
        return EXIT_OK
    return EXIT_NOT_IMPLEMENTED if record["error"] == NOT_IMPLEMENTED else EXIT_FAILED


def main(argv=None):
    """Parse arguments, run the requested stage(s) and return the process exit status."""
    args = _parser().parse_args(argv)
    log.set_stage("pipeline")
    log.set_verbose(args.verbose)
    timeutil.set_now(args.now)
    net.set_offline(args.offline)
    try:
        ctx = config.context(data_dir=args.data, dist_dir=args.dist, force=args.force,
                             force_edition=args.force_edition, verbose=args.verbose, args=args)
    except config.ConfigError as err:
        log.error("%s", err)
        return EXIT_USAGE
    names = ALL_ORDER if args.stage == "all" else (args.stage,)
    records = []
    try:
        for name in names:
            records.append(run_stage(name, ctx))
    except KeyboardInterrupt:
        log.error("interrupted")
        return EXIT_INTERRUPTED
    return _exit_code(args.stage, records)


if __name__ == "__main__":
    sys.exit(main())
