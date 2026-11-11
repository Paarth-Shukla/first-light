"""pipeline.__main__: the command line wrapper around stage modules (stages are faked here)."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import pipeline.__main__ as cli
from pipeline.core import log, net, timeutil

REPO = Path(__file__).resolve().parents[2]
RECORD_KEYS = ["stage", "ok", "startedAt", "durationSec", "error", "counts"]


class CliTestCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name) / "data"
        self.calls = []
        self.contexts = []
        self.fake_names = []
        self.addCleanup(self.remove_fakes)
        self.addCleanup(timeutil.set_now, None)
        self.addCleanup(net.set_offline, False)
        self.addCleanup(log.set_verbose, False)
        self.addCleanup(log.set_stage, "pipeline")

    def remove_fakes(self):
        for name in self.fake_names:
            sys.modules.pop(name, None)

    def fake_stage(self, label, behaviour=None):
        """Register a module whose run(ctx) records the call, then returns or raises ``behaviour``."""
        name = "pipeline._fake_%s_%d" % (label, len(self.fake_names))
        module = types.ModuleType(name)

        def run(ctx):
            self.calls.append(label)
            self.contexts.append(ctx)
            if isinstance(behaviour, BaseException):
                raise behaviour
            if callable(behaviour):
                return behaviour(ctx)
            return behaviour

        module.run = run
        sys.modules[name] = module
        self.fake_names.append(name)
        return name

    def run_cli(self, argv, stages):
        """Run main() with STAGES replaced; returns (exit code, stderr text)."""
        with mock.patch.dict(cli.STAGES, stages, clear=True), \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = cli.main(list(argv) + ["--data", str(self.data)])
        return code, stderr.getvalue()

    def run_log(self):
        return json.loads((self.data / "state" / "run.json").read_text(encoding="utf-8"))

    def all_stages(self, **overrides):
        """A full stage table of fakes; overrides map stage name -> behaviour or a module name."""
        table = {}
        for name in cli.ALL_ORDER:
            behaviour = overrides.get(name, {"n": 1})
            if isinstance(behaviour, str):
                table[name] = behaviour
            else:
                table[name] = self.fake_stage(name, behaviour)
        return table


class SingleStage(CliTestCase):
    def test_successful_stage(self):
        stages = {"fetch": self.fake_stage("fetch", {"sources": 150, "items": 412})}
        code, err = self.run_cli(["fetch", "--now", "2026-11-11T00:45:00Z"], stages)
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, ["fetch"])
        (record,) = self.run_log()
        self.assertEqual(list(record), RECORD_KEYS)
        self.assertEqual(record["stage"], "fetch")
        self.assertIs(record["ok"], True)
        self.assertEqual(record["startedAt"], "2026-11-11T00:45:00Z")
        self.assertIsNone(record["error"])
        self.assertEqual(record["counts"], {"sources": 150, "items": 412})
        self.assertIsInstance(record["durationSec"], float)
        self.assertGreaterEqual(record["durationSec"], 0)
        self.assertRegex(err, r"\[fetch\] info: done in ")

    def test_started_at_uses_the_real_clock_without_now(self):
        code, _ = self.run_cli(["fetch"], {"fetch": self.fake_stage("fetch")})
        self.assertEqual(code, 0)
        started = timeutil.parse_date(self.run_log()[0]["startedAt"])
        self.assertLess(abs(timeutil.hours_between(started, timeutil.now_utc())), 0.01)

    def test_failing_stage_is_recorded_and_exits_one(self):
        stages = {"process": self.fake_stage("process", ValueError("cluster table is  empty\nsecond line"))}
        code, err = self.run_cli(["process"], stages)
        self.assertEqual(code, 1)
        (record,) = self.run_log()
        self.assertIs(record["ok"], False)
        self.assertEqual(record["error"], "ValueError: cluster table is empty second line")
        self.assertEqual(record["counts"], {})
        self.assertIn("Traceback (most recent call last)", err)
        self.assertIn("[process] error: stage failed: ValueError", err)

    def test_long_error_messages_are_capped(self):
        code, _ = self.run_cli(["fetch"], {"fetch": self.fake_stage("fetch", RuntimeError("x" * 5000))})
        self.assertEqual(code, 1)
        self.assertEqual(len(self.run_log()[0]["error"]), 300)

    def test_missing_stage_module_exits_three(self):
        code, err = self.run_cli(["papers"], {"papers": "pipeline._not_written_yet"})
        self.assertEqual(code, 3)
        self.assertIn("stage not implemented", err)
        (record,) = self.run_log()
        self.assertEqual((record["stage"], record["ok"], record["error"]), ("papers", False, "stage not implemented"))

    def test_real_stage_table_points_at_the_contract_modules(self):
        self.assertEqual(cli.STAGES, {
            "fetch": "pipeline.fetch", "markets": "pipeline.markets", "process": "pipeline.process",
            "papers": "pipeline.papers", "claude": "pipeline.claude_updates",
            "search": "pipeline.searchindex", "build": "pipeline.build"})
        # process runs after claude and papers so the frozen edition can embed their output.
        self.assertEqual(cli.ALL_ORDER, ("fetch", "markets", "claude", "papers", "process", "search", "build"))

    def test_broken_import_inside_a_stage_is_a_failure_not_missing(self):
        name = "pipeline._fake_broken_import"
        loader = mock.patch.object(cli.importlib, "import_module",
                                   side_effect=ModuleNotFoundError("No module named 'pipeline.feeds'",
                                                                   name="pipeline.feeds"))
        with loader:
            code, err = self.run_cli(["fetch"], {"fetch": name})
        self.assertEqual(code, 1)
        self.assertIn("ModuleNotFoundError", self.run_log()[0]["error"])
        self.assertNotIn("stage not implemented", err)

    def test_stage_without_run_is_a_failure(self):
        name = "pipeline._fake_no_run"
        sys.modules[name] = types.ModuleType(name)
        self.fake_names.append(name)
        code, _ = self.run_cli(["fetch"], {"fetch": name})
        self.assertEqual(code, 1)
        self.assertIn("AttributeError", self.run_log()[0]["error"])

    def test_stage_calling_sys_exit(self):
        code, _ = self.run_cli(["fetch"], {"fetch": self.fake_stage("fetch", SystemExit(4))})
        self.assertEqual(code, 1)
        self.assertEqual(self.run_log()[0]["error"], "exited with status 4")
        code, _ = self.run_cli(["fetch"], {"fetch": self.fake_stage("fetch", SystemExit(0))})
        self.assertEqual(code, 0)
        self.assertIs(self.run_log()[1]["ok"], True)

    def test_none_result_means_empty_counts(self):
        code, _ = self.run_cli(["fetch"], {"fetch": self.fake_stage("fetch", None)})
        self.assertEqual(code, 0)
        self.assertEqual(self.run_log()[0]["counts"], {})

    def test_non_dict_result_is_noted_not_fatal(self):
        code, err = self.run_cli(["fetch"], {"fetch": self.fake_stage("fetch", lambda ctx: [1, 2, 3])})
        self.assertEqual(code, 0)
        self.assertEqual(self.run_log()[0]["counts"], {})
        self.assertIn("instead of a dict", err)

    def test_unserialisable_counts_do_not_lose_the_record(self):
        code, err = self.run_cli(["fetch"], {"fetch": self.fake_stage("fetch", lambda ctx: {"bad": object()})})
        self.assertEqual(code, 0)
        (record,) = self.run_log()
        self.assertEqual((record["ok"], record["counts"]), (True, {}))
        self.assertIn("cannot be stored as JSON", err)

    def test_keyboard_interrupt_is_recorded_and_stops_the_run(self):
        stages = self.all_stages(markets=KeyboardInterrupt())
        code, err = self.run_cli(["all"], stages)
        self.assertEqual(code, 130)
        self.assertEqual(self.calls, ["fetch", "markets"])
        self.assertEqual([(r["stage"], r["error"]) for r in self.run_log()],
                         [("fetch", None), ("markets", "interrupted")])
        self.assertIn("interrupted", err)


class Context(CliTestCase):
    def test_context_fields(self):
        stages = {"fetch": self.fake_stage("fetch")}
        argv = ["fetch", "--now", "2026-11-11T06:00:00+05:30", "--offline", "--force", "--force-edition", "-v"]
        code, _ = self.run_cli(argv, stages)
        self.assertEqual(code, 0)
        (ctx,) = self.contexts
        self.assertEqual(ctx.paths.data, self.data.resolve())
        self.assertEqual(ctx.paths.state, self.data.resolve() / "state")
        self.assertEqual(timeutil.iso(ctx.now), "2026-11-11T00:30:00Z")
        self.assertIs(ctx.offline, True)
        self.assertIs(ctx.force, True)
        self.assertIs(ctx.force_edition, True)
        self.assertIs(ctx.verbose, True)
        self.assertEqual(ctx.args.stage, "fetch")
        self.assertEqual(ctx.tz, ZoneInfo("Asia/Kolkata"))
        self.assertEqual(ctx.site["name"], "First Light")

    def test_defaults(self):
        code, _ = self.run_cli(["fetch"], {"fetch": self.fake_stage("fetch")})
        (ctx,) = self.contexts
        self.assertEqual((ctx.offline, ctx.force, ctx.force_edition, ctx.verbose), (False, False, False, False))
        self.assertEqual(ctx.paths.dist, REPO / "dist")

    def test_dist_flag(self):
        target = self.data.parent / "site-out"
        code, _ = self.run_cli(["build", "--dist", str(target)], {"build": self.fake_stage("build")})
        self.assertEqual(self.contexts[0].paths.dist, target.resolve())

    def test_flags_reach_the_shared_helpers_while_the_stage_runs(self):
        seen = {}

        def probe(ctx):
            seen["now"] = timeutil.iso(timeutil.now_utc())
            seen["offline"] = net.is_offline()
            seen["verbose"] = log.is_verbose()
            seen["dirs"] = ctx.paths.items_dir.is_dir() and ctx.paths.search_dir.is_dir()
            return {}

        argv = ["fetch", "--now", "2026-11-11T00:45:00Z", "--offline", "-v"]
        self.run_cli(argv, {"fetch": self.fake_stage("fetch", probe)})
        self.assertEqual(seen, {"now": "2026-11-11T00:45:00Z", "offline": True, "verbose": True, "dirs": True})

    def test_each_run_resets_the_flags(self):
        self.run_cli(["fetch", "--offline", "--now", "2026-11-11T00:45:00Z"], {"fetch": self.fake_stage("fetch")})
        self.run_cli(["fetch"], {"fetch": self.fake_stage("fetch")})
        self.assertFalse(net.is_offline())
        self.assertFalse(self.contexts[1].offline)
        self.assertNotEqual(timeutil.iso(self.contexts[1].now), "2026-11-11T00:45:00Z")

    def test_bad_now_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()) as stderr, self.assertRaises(SystemExit) as caught:
            cli.main(["fetch", "--now", "next tuesday", "--data", str(self.data)])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("not a date/time", stderr.getvalue())

    def test_unknown_stage_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            cli.main(["publish"])
        self.assertEqual(caught.exception.code, 2)

    def test_broken_site_config_exits_two_without_running(self):
        from pipeline.core import config
        stages = {"fetch": self.fake_stage("fetch")}
        with mock.patch.object(config, "load", side_effect=config.ConfigError("config/site.json is not valid JSON")):
            code, err = self.run_cli(["fetch"], stages)
        self.assertEqual(code, 2)
        self.assertEqual(self.calls, [])
        self.assertIn("site.json is not valid JSON", err)


class RunAll(CliTestCase):
    def test_runs_every_stage_in_order_with_one_context(self):
        code, err = self.run_cli(["all"], self.all_stages())
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, ["fetch", "markets", "claude", "papers", "process", "search", "build"])
        self.assertEqual([record["stage"] for record in self.run_log()], self.calls)
        self.assertTrue(all(record["ok"] for record in self.run_log()))
        self.assertEqual(len({id(ctx) for ctx in self.contexts}), 1)
        self.assertIn("[all] info: build", err)

    def test_continues_after_a_failed_stage_and_exits_zero_when_build_succeeds(self):
        stages = self.all_stages(markets=RuntimeError("yahoo is down"), papers="pipeline._missing_papers")
        code, err = self.run_cli(["all"], stages)
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, ["fetch", "markets", "claude", "process", "search", "build"])
        outcome = {record["stage"]: (record["ok"], record["error"]) for record in self.run_log()}
        self.assertEqual(outcome["markets"], (False, "RuntimeError: yahoo is down"))
        self.assertEqual(outcome["papers"], (False, "stage not implemented"))
        self.assertEqual(outcome["build"], (True, None))
        self.assertRegex(err, r"\[all\] info: markets +FAILED")

    def test_exits_one_when_build_fails(self):
        code, _ = self.run_cli(["all"], self.all_stages(build=OSError("disk full")))
        self.assertEqual(code, 1)
        self.assertEqual(len(self.run_log()), 7)

    def test_exits_one_when_build_is_missing(self):
        code, _ = self.run_cli(["all"], self.all_stages(build="pipeline._missing_build"))
        self.assertEqual(code, 1)


class RunLog(CliTestCase):
    def test_keeps_only_the_last_sixty_records(self):
        stages = {"fetch": self.fake_stage("fetch", lambda ctx: {"call": len(self.calls)})}
        for _ in range(65):
            self.run_cli(["fetch"], stages)
        history = self.run_log()
        self.assertEqual(len(history), 60)
        self.assertEqual(history[0]["counts"], {"call": 6})
        self.assertEqual(history[-1]["counts"], {"call": 65})

    def test_corrupt_run_log_is_replaced(self):
        (self.data / "state").mkdir(parents=True)
        (self.data / "state" / "run.json").write_text("{broken", encoding="utf-8")
        code, err = self.run_cli(["fetch"], {"fetch": self.fake_stage("fetch")})
        self.assertEqual(code, 0)
        self.assertEqual(len(self.run_log()), 1)
        self.assertIn("corrupt JSON", err)

    def test_run_log_of_the_wrong_shape_is_replaced(self):
        (self.data / "state").mkdir(parents=True)
        (self.data / "state" / "run.json").write_text('{"runs": []}', encoding="utf-8")
        code, err = self.run_cli(["fetch"], {"fetch": self.fake_stage("fetch")})
        self.assertEqual(code, 0)
        self.assertEqual(len(self.run_log()), 1)
        self.assertIn("was not a list", err)

    def test_unwritable_run_log_does_not_change_the_outcome(self):
        with mock.patch.object(cli.jsonio, "write_json", side_effect=OSError("read-only file system")):
            code, err = self.run_cli(["fetch"], {"fetch": self.fake_stage("fetch")})
        self.assertEqual(code, 0)
        self.assertIn("could not record the run", err)


class Subprocess(unittest.TestCase):
    """The module really runs as ``python3 -m pipeline`` (no stage is executed here)."""

    def run_module(self, *argv):
        return subprocess.run([sys.executable, "-m", "pipeline"] + list(argv), cwd=str(REPO),
                              capture_output=True, text=True, timeout=60)

    def test_help(self):
        result = self.run_module("--help")
        self.assertEqual(result.returncode, 0)
        for word in ("fetch", "markets", "process", "papers", "claude", "search", "build", "all",
                     "--data", "--now", "--offline", "--force", "--force-edition", "-v"):
            self.assertIn(word, result.stdout)

    def test_no_stage_is_a_usage_error(self):
        result = self.run_module()
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)


if __name__ == "__main__":
    unittest.main()
