"""pipeline.core.config and pipeline.core.log, plus the shape of config/site.json."""

import contextlib
import dataclasses
import io
import re
import tempfile
import threading
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from pipeline.core import config, log, net, timeutil

REPO = Path(__file__).resolve().parents[2]


class Load(unittest.TestCase):
    def fake_root(self, files):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        (root / "config").mkdir()
        for name, content in files.items():
            (root / "config" / name).write_text(content, encoding="utf-8")
        patcher = mock.patch.object(config, "ROOT", root)
        patcher.start()
        self.addCleanup(patcher.stop)
        return root

    def test_root_is_the_repository(self):
        self.assertEqual(config.ROOT, REPO)
        self.assertTrue((config.ROOT / "docs" / "ARCHITECTURE.md").is_file())

    def test_loads_by_name_with_or_without_extension(self):
        self.assertEqual(config.load("site")["name"], "First Light")
        self.assertEqual(config.load("site.json"), config.load("site"))

    def test_missing_file_names_the_path(self):
        with self.assertRaises(config.ConfigError) as caught:
            config.load("no-such-config")
        self.assertIn("no-such-config.json", str(caught.exception))
        self.assertIsInstance(caught.exception, ValueError)

    def test_bad_json_reports_file_line_and_column(self):
        self.fake_root({"broken.json": '{\n  "a": 1,\n  "b": oops\n}\n'})
        with self.assertRaises(config.ConfigError) as caught:
            config.load("broken")
        message = str(caught.exception)
        self.assertIn("broken.json", message)
        self.assertIn("line 3 column 8", message)

    def test_top_level_must_be_an_object(self):
        self.fake_root({"list.json": "[1, 2, 3]"})
        with self.assertRaises(config.ConfigError) as caught:
            config.load("list")
        self.assertIn("JSON object", str(caught.exception))

    def test_bom_and_unicode(self):
        self.fake_root({"bom.json": "﻿{\"name\": \"Café\"}"})
        self.assertEqual(config.load("bom"), {"name": "Café"})


class SiteJson(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = config.load("site")

    def test_identity(self):
        self.assertEqual(self.site["name"], "First Light")
        self.assertEqual(self.site["tagline"], "The morning edition")
        self.assertEqual(self.site["timezone"], "Asia/Kolkata")
        self.assertEqual(ZoneInfo(self.site["timezone"]).utcoffset(timeutil.now_utc()), timedelta(hours=5, minutes=30))
        self.assertEqual(self.site["retentionDays"], 90)

    def test_edition_and_weekend(self):
        self.assertEqual(self.site["edition"], {"hour": 6, "frontCount": 4, "briefCount": 10, "perSection": 3})
        self.assertEqual(self.site["weekend"], {"weekday": 5})

    def test_ranking_weights_match_the_story_signals_and_sum_to_one(self):
        weights = self.site["ranking"]["weights"]
        self.assertEqual(weights, {"breadth": 0.34, "tier": 0.18, "recency": 0.16, "velocity": 0.10,
                                   "attention": 0.10, "editorial": 0.12})
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=9)
        self.assertEqual(self.site["ranking"]["recencyHalfLifeHours"], 18)

    def test_sections_are_the_ten_from_the_contract_in_canonical_order(self):
        self.assertEqual(self.site["sections"], [
            {"id": "world", "name": "World"},
            {"id": "india", "name": "India"},
            {"id": "ai", "name": "AI"},
            {"id": "ml", "name": "Machine Learning"},
            {"id": "llm", "name": "LLMs"},
            {"id": "labs", "name": "Frontier Labs"},
            {"id": "companies", "name": "Companies"},
            {"id": "markets", "name": "Markets"},
            {"id": "india-markets", "name": "Dalal Street"},
            {"id": "science", "name": "Science"},
        ])

    def test_sections_match_the_architecture_table(self):
        document = (REPO / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        table = document.split("\n## Sections\n", 1)[1].split("\n## ", 1)[0]
        rows = re.findall(r"^\| `([a-z-]+)` \| ([^|]+) \|", table, re.M)
        self.assertEqual([{"id": ident, "name": name.strip()} for ident, name in rows], self.site["sections"])


class PathsTest(unittest.TestCase):
    def test_default_layout(self):
        paths = config.paths()
        self.assertEqual(paths.root, REPO)
        self.assertEqual(paths.data, REPO / "data")
        self.assertEqual(paths.state, REPO / "data" / "state")
        self.assertEqual(paths.public, REPO / "data" / "public")
        self.assertEqual(paths.items_dir, REPO / "data" / "state" / "items")
        self.assertEqual(paths.stories_dir, REPO / "data" / "public" / "stories")
        self.assertEqual(paths.editions_dir, REPO / "data" / "public" / "editions")
        self.assertEqual(paths.weekend_dir, REPO / "data" / "public" / "weekend")
        self.assertEqual(paths.claude_dir, REPO / "data" / "public" / "claude")
        self.assertEqual(paths.search_dir, REPO / "data" / "public" / "search")
        self.assertEqual(paths.dist, REPO / "dist")
        self.assertEqual(paths.site, REPO / "site")

    def test_every_path_is_absolute(self):
        for field in dataclasses.fields(config.paths("relative/data")):
            self.assertTrue(getattr(config.paths("relative/data"), field.name).is_absolute(), field.name)

    def test_custom_data_and_dist_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = config.paths(folder, dist_dir=Path(folder) / "out")
            self.assertEqual(paths.data, Path(folder).resolve())
            self.assertEqual(paths.state, Path(folder).resolve() / "state")
            self.assertEqual(paths.dist, Path(folder).resolve() / "out")
            self.assertEqual(paths.root, REPO)
            self.assertEqual(paths.site, REPO / "site")

    def test_nothing_is_created_until_ensure(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder) / "data"
            paths = config.paths(data, dist_dir=Path(folder) / "dist")
            self.assertFalse(data.exists())
            self.assertIs(paths.ensure(), paths)
            for name in ("state", "public", "items_dir", "stories_dir", "editions_dir", "weekend_dir",
                         "claude_dir", "search_dir"):
                self.assertTrue(getattr(paths, name).is_dir(), name)
            self.assertFalse(paths.dist.exists())
            paths.ensure()

    def test_paths_are_immutable(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            config.paths().data = Path("/elsewhere")


class ContextTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(timeutil.set_now, None)
        self.addCleanup(net.set_offline, False)

    def test_fields(self):
        timeutil.set_now("2026-11-11T00:45:00Z")
        net.set_offline(True)
        with tempfile.TemporaryDirectory() as folder:
            ctx = config.context(folder, force=True, verbose=True, args="namespace")
            self.assertEqual(ctx.paths.data, Path(folder).resolve())
            self.assertEqual(timeutil.iso(ctx.now), "2026-11-11T00:45:00Z")
            self.assertIs(ctx.offline, True)
            self.assertIs(ctx.force, True)
            self.assertIs(ctx.force_edition, False)
            self.assertIs(ctx.verbose, True)
            self.assertEqual(ctx.args, "namespace")
            self.assertEqual(ctx.tz, ZoneInfo("Asia/Kolkata"))
            self.assertEqual(ctx.site["name"], "First Light")
            self.assertEqual(timeutil.local_date(ctx.now, ctx.tz), "2026-11-11")

    def test_defaults_follow_the_real_clock_and_network_switch(self):
        ctx = config.context()
        self.assertFalse(ctx.offline)
        self.assertFalse(ctx.force)
        self.assertIsNone(ctx.args)
        self.assertLess(abs(timeutil.hours_between(ctx.now, timeutil.now_utc())), 0.01)
        self.assertEqual(ctx.now.utcoffset(), timedelta(0))

    def test_bad_timezone_in_site_json_is_a_config_error(self):
        with mock.patch.object(config, "load", return_value={"timezone": "Nowhere/Land"}):
            with self.assertRaises(config.ConfigError):
                config.context()


class Log(unittest.TestCase):
    def setUp(self):
        self.addCleanup(log.set_stage, "pipeline")
        self.addCleanup(log.set_verbose, False)
        log.set_stage("fetch")
        log.set_verbose(False)

    def capture(self, action):
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            action()
        return stderr.getvalue()

    def test_line_format(self):
        out = self.capture(lambda: log.info("fetched %d of %d sources", 140, 150))
        self.assertRegex(out, r"^\d{2}:\d{2}:\d{2} \[fetch\] info: fetched 140 of 150 sources\n$")

    def test_levels(self):
        self.assertIn("[fetch] warn: careful", self.capture(lambda: log.warn("careful")))
        self.assertIn("[fetch] error: broken", self.capture(lambda: log.error("broken")))

    def test_debug_only_when_verbose(self):
        self.assertEqual(self.capture(lambda: log.debug("detail")), "")
        self.assertFalse(log.is_verbose())
        log.set_verbose(True)
        self.assertTrue(log.is_verbose())
        self.assertIn("[fetch] debug: detail", self.capture(lambda: log.debug("detail")))

    def test_stage_prefix_changes(self):
        log.set_stage("markets")
        self.assertIn("[markets] info: hi", self.capture(lambda: log.info("hi")))

    def test_writes_to_stderr_not_stdout(self):
        with contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()):
            log.info("quiet on stdout")
        self.assertEqual(stdout.getvalue(), "")

    def test_percent_signs_without_arguments_are_literal(self):
        self.assertIn("up 3.5% today", self.capture(lambda: log.info("up 3.5% today")))

    def test_bad_format_arguments_do_not_raise(self):
        out = self.capture(lambda: log.info("only %d here", "text", "extra"))
        self.assertIn("only %d here", out)
        self.assertIn("'text'", out)

    def test_non_string_messages(self):
        self.assertIn("info: 42", self.capture(lambda: log.info(42)))
        self.assertIn("boom", self.capture(lambda: log.error(ValueError("boom"))))

    def test_closed_stderr_does_not_raise(self):
        closed = io.StringIO()
        closed.close()
        with contextlib.redirect_stderr(closed):
            log.info("nobody is listening")

    def test_threads_do_not_interleave_lines(self):
        def worker(index):
            for _ in range(200):
                log.info("thread %d says %s", index, "x" * 50)

        def run():
            threads = [threading.Thread(target=worker, args=(index,)) for index in range(6)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        lines = self.capture(run).splitlines()
        self.assertEqual(len(lines), 1200)
        shape = re.compile(r"^\d{2}:\d{2}:\d{2} \[fetch\] info: thread \d says x{50}$")
        self.assertTrue(all(shape.match(line) for line in lines))


if __name__ == "__main__":
    unittest.main()
