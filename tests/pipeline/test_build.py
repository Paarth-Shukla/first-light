"""Tests for the build stage: status.json, manifest.json and the dist/ swap.

Each test builds into a temporary data directory and a temporary dist/, with
its own site/ where the test needs to control it, so nothing touches the real
data/, dist/ or site/.
"""

import dataclasses
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import build
from pipeline.core import config, jsonio, timeutil
from tests.pipeline import test_contracts as contracts

ROOT = Path(__file__).resolve().parents[2]
NOW = "2026-11-11T00:35:00Z"
SOURCES = {"sources": [
    {"id": "bbc-world", "name": "BBC News", "section": "world", "enabled": True},
    {"id": "et-markets", "name": "The Economic Times", "section": "india-markets", "enabled": True},
    {"id": "never-run", "name": "Quiet Wire", "section": "science", "enabled": True},
    {"id": "switched-off", "name": "Blocked Feed", "section": "ai", "enabled": False},
]}
HEALTH = {
    "bbc-world": {"ok": True, "items": 20, "newItems": 3, "ms": 190, "error": None,
                  "lastOkAt": "2026-11-11T00:30:00Z", "consecutiveFailures": 0},
    "et-markets": {"ok": False, "items": 0, "newItems": 0, "ms": 20012, "error": "timed out after 20 s",
                   "lastOkAt": "2026-11-10T21:30:00Z", "consecutiveFailures": 2},
    "removed-source": {"ok": True, "items": 5, "newItems": 0, "ms": 10, "error": None, "lastOkAt": NOW},
}


def record(stage, ok=True, at=NOW, counts=None, error=None):
    return {"stage": stage, "ok": ok, "startedAt": at, "durationSec": 1.5, "error": error, "counts": counts or {}}


class BuildTestCase(unittest.TestCase):
    """A fresh data dir, dist dir and site dir per test, with the clock frozen at NOW."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="build-test-"))
        self.addCleanup(shutil.rmtree, self.tmp)
        timeutil.set_now(NOW)
        self.addCleanup(timeutil.set_now, None)
        ctx = config.context(data_dir=self.tmp / "data", dist_dir=self.tmp / "dist")
        ctx.paths = dataclasses.replace(ctx.paths, site=self.tmp / "site")
        ctx.paths.ensure()
        self.ctx = ctx
        self.write_site({"index.html": "<!doctype html><title>First Light</title>", "js/app.js": "export {};"})
        loader = mock.patch.object(build.config, "load", side_effect=self.fake_config)
        loader.start()
        self.addCleanup(loader.stop)
        self.sources = SOURCES

    def fake_config(self, name):
        if name == "sources":
            return self.sources
        return config.load(name)

    def write_site(self, files):
        for relative, text in files.items():
            path = self.ctx.paths.site / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def write(self, relative, obj):
        jsonio.write_json(self.ctx.paths.data / relative, obj)

    def public(self, relative):
        return json.loads((self.ctx.paths.public / relative).read_text(encoding="utf-8"))

    def run_build(self):
        return build.run(self.ctx)


class StatusTest(BuildTestCase):
    def test_latest_record_of_each_stage_in_the_order_they_last_ran(self):
        self.write("state/run.json", [
            record("fetch", counts={"run": 1}), record("markets"), record("build"),
            record("fetch", ok=False, error="ValueError: boom", counts={"run": 2}),
            dict(record("search"), extra="not in the contract"),
        ])
        self.run_build()
        stages = self.public("status.json")["stages"]
        self.assertEqual([stage["stage"] for stage in stages], ["markets", "fetch", "search"])
        fetch = stages[1]
        self.assertEqual((fetch["ok"], fetch["error"], fetch["counts"]), (False, "ValueError: boom", {"run": 2}))
        self.assertEqual(set(stages[2]), {"stage", "ok", "startedAt", "durationSec", "error", "counts"})

    def test_run_log_that_is_not_a_list_gives_no_stages(self):
        self.write("state/run.json", {"stage": "fetch"})
        self.run_build()
        self.assertEqual(self.public("status.json")["stages"], [])

    def test_sources_are_enabled_config_entries_joined_with_health(self):
        self.write("state/source-health.json", HEALTH)
        counts = self.run_build()
        rows = {row["id"]: row for row in self.public("status.json")["sources"]}
        self.assertEqual(list(rows), ["bbc-world", "et-markets", "never-run"])
        self.assertEqual(rows["bbc-world"], {
            "id": "bbc-world", "name": "BBC News", "section": "world", "ok": True, "items": 20, "newItems": 3,
            "ms": 190, "error": None, "lastOkAt": "2026-11-11T00:30:00Z"})
        self.assertEqual((rows["et-markets"]["ok"], rows["et-markets"]["error"]), (False, "timed out after 20 s"))
        self.assertEqual((rows["never-run"]["ok"], rows["never-run"]["error"]), (False, build.NOT_FETCHED))
        self.assertEqual((counts["sources"], counts["sourcesOk"]), (3, 1))

    def test_unreadable_sources_config_falls_back_to_reported_sources(self):
        def broken(name):
            raise config.ConfigError("config/sources.json is not valid JSON at line 3 column 1")
        self.write("state/source-health.json", HEALTH)
        with mock.patch.object(build.config, "load", side_effect=broken):
            counts = self.run_build()
        rows = self.public("status.json")["sources"]
        self.assertEqual([row["id"] for row in rows], ["bbc-world", "et-markets", "removed-source"])
        self.assertTrue(any("sources.json unreadable" in problem for problem in counts["problems"]))

    def test_status_satisfies_the_contract(self):
        self.write("state/run.json", [record("fetch"), record("process", ok=False, error="KeyError: 'x'")])
        self.write("state/source-health.json", HEALTH)
        self.run_build()
        errors = []
        contracts.validate_status(self.public("status.json"), errors)
        self.assertEqual(errors, [])


class ManifestTest(BuildTestCase):
    def test_lists_readable_files_newest_first(self):
        for day in ("2026-11-09", "2026-11-11", "2026-11-10"):
            self.write("public/stories/%s.json" % day, {"date": day, "generatedAt": NOW, "stories": [{"id": "a"}, {"id": "b"}]})
        self.write("public/editions/2026-11-10.json", {"date": "2026-11-10", "number": 1})
        self.write("public/editions/2026-11-11.json", {"date": "2026-11-11", "number": 2})
        self.write("public/editions/index.json", {"editions": []})
        self.write("public/weekend/2026-W45.json", {"isoWeek": "2026-W45"})
        self.write("public/weekend/2026-W46.json", {"isoWeek": "2026-W46"})
        self.write("public/weekend/index.json", {"weeks": []})
        (self.ctx.paths.stories_dir / "notes.txt").write_text("not a day file")
        self.run_build()
        manifest = self.public("manifest.json")
        self.assertEqual(manifest["days"], ["2026-11-11", "2026-11-10", "2026-11-09"])
        self.assertEqual(manifest["editions"], ["2026-11-11", "2026-11-10"])
        self.assertEqual(manifest["weekends"], ["2026-W46", "2026-W45"])
        self.assertEqual(manifest["edition"], {"date": "2026-11-11", "number": 2})
        self.assertEqual(manifest["counts"]["stories"], 6)
        self.assertEqual(manifest["builtAt"], NOW)
        self.assertEqual(manifest["schema"], 1)
        self.assertEqual(manifest["site"]["timezone"], "Asia/Kolkata")
        self.assertEqual(manifest["site"]["editionHour"], 6)
        self.assertEqual([s["id"] for s in manifest["sections"]], list(contracts.SECTION_IDS))

    def test_corrupt_files_are_left_out_and_reported(self):
        self.write("public/stories/2026-11-11.json", {"date": "2026-11-11", "generatedAt": NOW, "stories": []})
        (self.ctx.paths.stories_dir / "2026-11-10.json").write_text('{"date": "2026-11-10", "stor')
        (self.ctx.paths.editions_dir / "2026-11-11.json").write_text("[]")
        counts = self.run_build()
        manifest = self.public("manifest.json")
        self.assertEqual(manifest["days"], ["2026-11-11"])
        self.assertEqual((manifest["editions"], manifest["edition"]), ([], None))
        self.assertEqual(len([p for p in counts["problems"] if "unreadable" in p]), 2)

    def test_empty_data_dir_still_builds(self):
        counts = self.run_build()
        manifest = self.public("manifest.json")
        self.assertEqual((manifest["edition"], manifest["days"], manifest["counts"]["stories"]), (None, [], 0))
        self.assertEqual(counts["problems"], [])

    def test_manifest_satisfies_the_contract(self):
        self.write("public/stories/2026-11-11.json", {"date": "2026-11-11", "generatedAt": NOW, "stories": []})
        self.write("public/editions/2026-11-11.json", {"date": "2026-11-11", "number": 1})
        self.write("state/source-health.json", HEALTH)
        self.run_build()
        errors = []
        contracts.validate_manifest(self.public("manifest.json"), self.ctx.paths.public, errors)
        self.assertEqual(errors, [])


IST = timeutil.zone("Asia/Kolkata")


def at(text):
    return timeutil.parse_date(text)


class NextBuildTest(unittest.TestCase):
    def test_no_schedule_means_no_promise(self):
        problems = []
        self.assertIsNone(build.next_build(at("2026-11-11T00:00:00Z"), IST, None, problems))
        self.assertEqual(problems, [])

    def test_next_local_hour_today(self):
        # 05:00 IST -> 06:00 IST is 00:30 UTC.
        self.assertEqual(build.next_build(at("2026-11-10T23:30:00Z"), IST, [12, 6, 9], []), "2026-11-11T00:30:00Z")

    def test_a_slot_that_is_now_is_not_next(self):
        self.assertEqual(build.next_build(at("2026-11-11T00:30:00Z"), IST, [6, 9], []), "2026-11-11T03:30:00Z")

    def test_after_the_last_slot_rolls_to_tomorrow(self):
        # 23:00 IST on the 11th -> 06:00 IST on the 12th.
        self.assertEqual(build.next_build(at("2026-11-11T17:30:00Z"), IST, [6, 21], []), "2026-11-12T00:30:00Z")

    def test_zone_with_daylight_saving(self):
        london = timeutil.zone("Europe/London")
        # The clocks went back on 2026-10-25: 06:00 is 06:00 UTC on the 26th, 05:00 UTC on the 24th.
        self.assertEqual(build.next_build(at("2026-10-26T03:00:00Z"), london, [6], []), "2026-10-26T06:00:00Z")
        self.assertEqual(build.next_build(at("2026-10-24T03:00:00Z"), london, [6], []), "2026-10-24T05:00:00Z")

    def test_bad_schedules_are_reported_not_guessed(self):
        for schedule in ([], [24], ["06:00"], [True], {"hours": [6]}):
            problems = []
            self.assertIsNone(build.next_build(at("2026-11-11T00:00:00Z"), IST, schedule, problems), schedule)
            self.assertEqual(len(problems), 1, schedule)

    def test_manifest_uses_site_schedule(self):
        with tempfile.TemporaryDirectory() as folder:
            timeutil.set_now("2026-11-10T23:30:00Z")
            self.addCleanup(timeutil.set_now, None)
            ctx = config.context(data_dir=Path(folder) / "data", dist_dir=Path(folder) / "dist")
            ctx.site = dict(ctx.site, schedule=[6, 9])
            ctx.paths = dataclasses.replace(ctx.paths, site=Path(folder) / "no-site")
            ctx.paths.ensure()
            build.run(ctx)
            manifest = json.loads((ctx.paths.public / "manifest.json").read_text())
        self.assertEqual(manifest["nextBuild"], "2026-11-11T00:30:00Z")


class DistTest(BuildTestCase):
    def dist_files(self):
        root = self.ctx.paths.dist
        return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())

    def test_site_and_public_data_are_published_state_is_not(self):
        self.write("public/latest.json", {"stories": []})
        self.write("state/items/2026-11-11.json", {"items": {}})
        self.write("state/http-cache.json", {})
        counts = self.run_build()
        files = self.dist_files()
        self.assertEqual(files, [".nojekyll", "data/latest.json", "data/manifest.json", "data/status.json",
                                 "index.html", "js/app.js"])
        self.assertEqual((counts["siteFiles"], counts["dataFiles"]), (2, 3))
        self.assertEqual(counts["distBytes"], sum(os.path.getsize(self.ctx.paths.dist / f) for f in files))

    def test_hidden_files_and_half_written_temp_files_are_skipped(self):
        self.write_site({".DS_Store": "x"})
        (self.ctx.paths.public / ".latest.json.abc123.tmp").write_text("{")
        self.run_build()
        self.assertFalse(any(Path(f).name.startswith(".") and f != ".nojekyll" for f in self.dist_files()))

    def test_previous_build_is_replaced_whole(self):
        self.ctx.paths.dist.mkdir()
        (self.ctx.paths.dist / "stale.js").write_text("old")
        self.run_build()
        self.assertNotIn("stale.js", self.dist_files())
        self.assertFalse(self.ctx.paths.dist.with_name("dist.old").exists())

    def test_leftovers_of_an_interrupted_build_are_cleared(self):
        for leftover in ("dist.tmp", "dist.old"):
            folder = self.ctx.paths.dist.with_name(leftover)
            folder.mkdir()
            (folder / "junk.txt").write_text("junk")
        self.run_build()
        self.assertNotIn("junk.txt", self.dist_files())
        self.assertFalse(self.ctx.paths.dist.with_name("dist.tmp").exists())
        self.assertFalse(self.ctx.paths.dist.with_name("dist.old").exists())

    def test_missing_site_still_publishes_the_data(self):
        shutil.rmtree(self.ctx.paths.site)
        counts = self.run_build()
        self.assertEqual(self.dist_files(), [".nojekyll", "data/manifest.json", "data/status.json"])
        self.assertTrue(any("no site/" in problem for problem in counts["problems"]))

    def test_site_data_folder_is_replaced_by_public_data(self):
        self.write_site({"data/manifest.json": '{"fake": true}'})
        counts = self.run_build()
        published = json.loads((self.ctx.paths.dist / "data" / "manifest.json").read_text())
        self.assertEqual(published["schema"], 1)
        self.assertTrue(any("site/data" in problem for problem in counts["problems"]))

    def test_failed_swap_restores_the_previous_build(self):
        self.ctx.paths.dist.mkdir()
        (self.ctx.paths.dist / "index.html").write_text("previous")
        real_rename = os.rename
        calls = []

        def flaky(src, dst):
            calls.append(Path(src).name)
            if Path(src).name == "dist.tmp":
                raise OSError("device busy")
            return real_rename(src, dst)

        with mock.patch.object(build.os, "rename", side_effect=flaky):
            with self.assertRaises(OSError):
                self.run_build()
        self.assertEqual((self.ctx.paths.dist / "index.html").read_text(), "previous")
        self.assertEqual(calls, ["dist", "dist.tmp", "dist.old"])


class CommandLineTest(unittest.TestCase):
    def test_build_stage_runs_as_a_process_and_is_logged(self):
        with tempfile.TemporaryDirectory() as folder:
            data, dist = Path(folder) / "data", Path(folder) / "dist"
            result = subprocess.run(
                [sys.executable, "-m", "pipeline", "build", "--data", str(data), "--dist", str(dist), "--now", NOW],
                cwd=str(ROOT), capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            (entry,) = json.loads((data / "state" / "run.json").read_text())
            self.assertEqual((entry["stage"], entry["ok"], entry["startedAt"]), ("build", True, NOW))
            self.assertTrue((dist / "index.html").is_file())
            self.assertTrue((dist / "data" / "manifest.json").is_file())
            self.assertFalse((dist / "data" / "state").exists())


if __name__ == "__main__":
    unittest.main()
