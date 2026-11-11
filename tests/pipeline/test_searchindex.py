"""pipeline.searchindex: compact docs, monthly shards, the manifest and the stage's handling of bad inputs.

Inputs are the small, real-shaped files in tests/fixtures/search/data (trimmed
from live pipeline output) plus the mini lexicon copied to
tests/fixtures/search/lexicon.json. The learned "related" map has its own
tests in test_searchindex_related.py.
"""

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from pipeline import __main__ as cli
from pipeline import lexicon, searchindex
from pipeline.core import config, net, timeutil

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "search"
SECTIONS = ["world", "india", "ai", "ml", "llm", "labs", "companies", "markets", "india-markets", "science"]
NOW = datetime(2026, 11, 11, 6, 0, tzinfo=timezone.utc)
TZ = "Asia/Kolkata"
SOURCE_NAMES = {"claude-code": "Claude Code changelog"}


def quiet(test):
    """Keep the stage's expected warnings (corrupt fixture file, skipped docs) out of the test output."""
    patcher = mock.patch("sys.stderr")
    patcher.start()
    test.addCleanup(patcher.stop)


def mini_lexicon():
    with open(FIXTURES / "lexicon.json", encoding="utf-8") as handle:
        return lexicon.Lexicon(json.load(handle), SECTIONS)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class TempData(unittest.TestCase):
    """Each test gets a fresh copy of the fixture data directory."""

    def setUp(self):
        quiet(self)
        self.tmp = Path(tempfile.mkdtemp(prefix="fl-search-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.data = self.tmp / "data"
        shutil.copytree(FIXTURES / "data", self.data)
        self.paths = config.paths(self.data).ensure()
        self.search = self.paths.search_dir

    def build(self, lex="mini", now=NOW):
        lex = mini_lexicon() if lex == "mini" else lex
        return searchindex.build(self.paths, TZ, now, 90, lex, SOURCE_NAMES)

    def docs(self):
        """Every doc in every shard the manifest lists, by id."""
        manifest = read(self.search / "manifest.json")
        out = {}
        for entry in manifest["shards"]:
            for doc in read(self.search / entry["file"]):
                self.assertNotIn(doc["i"], out, "doc %s appears in two shards" % doc["i"])
                out[doc["i"]] = doc
        return out


class Docs(TempData):
    def test_story_doc_fields(self):
        self.build()
        doc = self.docs()["s0000000001"]
        self.assertEqual(doc["k"], "story")
        self.assertEqual(doc["t"], "Nifty ends at record high as banks rally")
        self.assertEqual(doc["c"], "india-markets")
        self.assertEqual(doc["e"], ["nifty-50"])
        self.assertEqual(doc["o"], "Moneycontrol")  # best (first) source
        self.assertEqual(doc["n"], 2)
        self.assertEqual(doc["d"], "2026-10-31T18:00:00Z")
        self.assertEqual(doc["u"], "https://example.com/s0000000001")
        self.assertEqual(doc["x"], 71.2)

    def test_every_doc_has_the_same_keys(self):
        self.build()
        static = read(self.search / "docs-static.json")
        for doc in list(self.docs().values()) + static:
            self.assertEqual(sorted(doc), sorted("ikstceondux"), doc["i"])

    def test_summary_truncated_to_220_at_a_word(self):
        self.build()
        summary = self.docs()["s0000000001"]["s"]
        self.assertLessEqual(len(summary), 220)
        self.assertTrue(summary.endswith("…"))
        self.assertTrue(summary.startswith("The Nifty 50 closed at a record high"))
        for doc in read(self.search / "docs-static.json"):
            self.assertLessEqual(len(doc["s"]), 220)

    def test_papers_use_gist_then_abstract(self):
        self.build()
        docs = self.docs()
        paper = docs["2611.08449"]
        self.assertEqual(paper["k"], "paper")
        self.assertEqual(paper["c"], "weekend")
        self.assertEqual(paper["o"], "cs.RO")
        self.assertEqual(paper["u"], "https://arxiv.org/abs/2611.08449")
        self.assertEqual(paper["s"], "We introduce VFlash, a method for fast, accurate visual planning through "
                                     "Flash Primitive Decoding.")
        runner = docs["2611.08264"]  # runners-up are searchable too; no gist, so the abstract
        self.assertTrue(runner["s"].startswith("We identify a key limitation of existing feed-forward 3DGS"))
        self.assertLessEqual(len(runner["s"]), 220)

    def test_newest_weekend_issue_wins_and_undated_papers_are_skipped(self):
        counts = self.build()
        docs = self.docs()
        self.assertEqual(docs["2611.08449"]["t"], "VFlash: Fast, Accurate Visual Planning via Flash Primitive Decoding")
        self.assertEqual(counts["papers"], 2)
        self.assertGreaterEqual(counts["invalidDocs"], 1)

    def test_update_docs(self):
        self.build()
        docs = self.docs()
        update = docs["uc487d5abf0"]
        self.assertEqual((update["k"], update["c"]), ("update", "code"))
        self.assertEqual(update["o"], "Claude Code changelog")
        self.assertEqual(update["d"], "2026-11-09T18:30:00Z")  # midnight in Kolkata on 2026-11-10
        self.assertEqual(docs["ue539ef5a34"]["o"], "claude-cowork")  # unknown source: its id
        self.assertNotIn("ubad", docs)

    def test_static_docs(self):
        self.build()
        static = {doc["i"]: doc for doc in read(self.search / "docs-static.json")}
        feature = static["feature:projects"]
        self.assertEqual((feature["k"], feature["c"], feature["u"]), ("feature", "apps", "#/claude/feature/projects"))
        self.assertTrue(feature["s"].startswith("A project is a self-contained workspace"))
        self.assertIn("Reach for a project", feature["s"])  # summary + when
        recipe = static["recipe:analyse-a-spreadsheet"]
        self.assertEqual((recipe["k"], recipe["c"]), ("recipe", "analysis"))
        self.assertEqual(recipe["u"], "#/claude/recipe/analyse-a-spreadsheet")
        self.assertEqual(recipe["s"], "Profiling the file first puts the cleaning decisions in front of you.")
        term = static["term:repo rate"]
        self.assertEqual((term["k"], term["t"], term["u"]), ("term", "repo rate", "#/search?q=repo%20rate"))
        self.assertEqual(term["s"], "The rate at which the central bank lends to banks overnight.")


class Sharding(TempData):
    def test_month_boundary_in_site_timezone(self):
        self.build()
        oct_ids = {doc["i"] for doc in read(self.search / "docs-2026-10.json")}
        nov_ids = {doc["i"] for doc in read(self.search / "docs-2026-11.json")}
        self.assertIn("s0000000001", oct_ids)   # 18:00Z = 23:30 IST on 31 Oct
        self.assertIn("s0000000003", nov_ids)   # 19:00Z = 00:30 IST on 1 Nov, though UTC says October
        self.assertNotIn("s0000000003", oct_ids)

    def test_shard_function_directly(self):
        docs = [{"i": "a", "d": "2026-10-31T18:29:59Z"}, {"i": "b", "d": "2026-10-31T18:30:00Z"},
                {"i": "c", "d": "2026-11-05T00:00:00Z"}]
        months = searchindex.shard(docs, timeutil.zone(TZ))
        self.assertEqual([d["i"] for d in months["2026-10"]], ["a"])
        self.assertEqual([d["i"] for d in months["2026-11"]], ["c", "b"])  # newest first

    def test_story_ids_are_unique_and_newest_copy_wins(self):
        counts = self.build()
        docs = self.docs()
        self.assertEqual(docs["s0000000002"]["t"], "Bank Nifty recovers after early slide")
        self.assertEqual(counts["stories"], 2 + 0 + 1)  # s1, s2 (once), s3

    def test_window_ignores_future_and_expired_day_files(self):
        self.build()
        docs = self.docs()
        self.assertNotIn("s0000000004", docs)   # 2026-11-20 is after --now
        self.assertNotIn("s0000000005", docs)   # 2026-07-01 is older than 90 days

    def test_corrupt_files_and_bad_stories_are_reported(self):
        counts = self.build()
        self.assertEqual(counts["skippedFiles"], ["2026-10-30.json"])
        # titleless story, undated paper, duplicate update, undated update
        self.assertEqual(counts["invalidDocs"], 4)
        self.assertEqual(counts["dayFiles"], 2)

    def test_manifest_counts_and_sizes(self):
        self.build()
        manifest = read(self.search / "manifest.json")
        self.assertEqual(manifest["generatedAt"], "2026-11-11T06:00:00Z")
        self.assertEqual([entry["month"] for entry in manifest["shards"]], ["2026-11", "2026-10"])
        for entry in manifest["shards"]:
            path = self.search / entry["file"]
            self.assertEqual(entry["count"], len(read(path)))
            self.assertEqual(entry["bytes"], path.stat().st_size)
        self.assertEqual(manifest["static"], "docs-static.json")
        self.assertEqual(manifest["staticCount"], len(read(self.search / "docs-static.json")))
        self.assertEqual(manifest["staticBytes"], (self.search / "docs-static.json").stat().st_size)
        self.assertEqual(manifest["lexiconBytes"], (self.search / "lexicon.json").stat().st_size)

    def test_stale_shards_are_removed(self):
        (self.search / "docs-2025-01.json").write_text("[]\n", encoding="utf-8")
        (self.search / "keep-me.json").write_text("{}\n", encoding="utf-8")
        counts = self.build()
        self.assertEqual(counts["staleShardsRemoved"], 1)
        self.assertFalse((self.search / "docs-2025-01.json").exists())
        self.assertTrue((self.search / "keep-me.json").exists())


class LexiconFile(TempData):
    def test_lexicon_parts(self):
        self.build()
        data = read(self.search / "lexicon.json")
        self.assertEqual(sorted(data), ["aliases", "entities", "glossary", "related", "words"])
        self.assertIn("llm", data["aliases"])
        self.assertEqual(data["entities"]["bank-nifty"]["name"], "Bank Nifty")
        self.assertIn("repo rate", data["glossary"])
        self.assertEqual(data["related"], {})  # three stories teach nothing

    def test_broken_lexicon_writes_docs_keeps_old_lexicon_and_fails(self):
        (self.search / "lexicon.json").write_text('{"old": true}\n', encoding="utf-8")
        timeutil.set_now(NOW)
        self.addCleanup(timeutil.set_now, None)
        ctx = config.context(data_dir=self.data)
        with mock.patch.object(lexicon, "load", side_effect=config.ConfigError("bad lexicon")):
            with self.assertRaisesRegex(RuntimeError, "lexicon unavailable.*bad lexicon"):
                searchindex.run(ctx)
        self.assertEqual(read(self.search / "lexicon.json"), {"old": True})
        self.assertIn("s0000000001", self.docs())
        self.assertEqual(self.docs()["2611.08449"]["e"], [])  # no matcher without a lexicon


class MissingInputs(unittest.TestCase):
    def setUp(self):
        quiet(self)

    def test_empty_data_directory(self):
        tmp = Path(tempfile.mkdtemp(prefix="fl-search-empty-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        paths = config.paths(tmp).ensure()
        counts = searchindex.build(paths, TZ, NOW, 90, mini_lexicon(), {})
        manifest = read(paths.search_dir / "manifest.json")
        self.assertEqual(manifest["shards"], [])
        static = read(paths.search_dir / "docs-static.json")
        self.assertEqual({doc["k"] for doc in static}, {"term"})  # glossary still searchable
        self.assertEqual(counts["stories"] + counts["papers"] + counts["updates"], 0)
        self.assertEqual(counts["skippedFiles"], [])

    def test_missing_directories_entirely(self):
        tmp = Path(tempfile.mkdtemp(prefix="fl-search-bare-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        paths = config.paths(tmp)  # not ensure()d: no stories/weekend/claude directories at all
        paths.search_dir.mkdir(parents=True)
        counts = searchindex.build(paths, TZ, NOW, 90, mini_lexicon(), {})
        self.assertEqual(counts["dayFiles"], 0)
        self.assertTrue((paths.search_dir / "manifest.json").exists())


class Malformed(TempData):
    def test_bad_entries_are_counted_not_fatal(self):
        playbook = read(self.paths.claude_dir / "playbook.json")
        playbook["features"] += ["not a dict", {"id": "no-title"}, {"id": 7, "title": "numeric id"}]
        (self.paths.claude_dir / "playbook.json").write_text(json.dumps(playbook), encoding="utf-8")
        day = read(self.paths.stories_dir / "2026-11-01.json")
        day["stories"] += [None, {"id": "s-bad-title", "title": ["list"], "updatedAt": "2026-11-01T00:00:00Z"},
                           {"id": "s-no-date", "title": "Undated", "updatedAt": "yesterday-ish"}]
        (self.paths.stories_dir / "2026-11-01.json").write_text(json.dumps(day), encoding="utf-8")
        self.assertEqual(self.build()["invalidDocs"], 4 + 3 + 3)  # the fixture's own 4, three features, three stories
        static_ids = {doc["i"] for doc in read(self.search / "docs-static.json")}
        self.assertIn("feature:projects", static_ids)
        self.assertNotIn("s-no-date", self.docs())

    def test_wrong_top_level_shape_skips_the_file(self):
        (self.paths.claude_dir / "updates.json").write_text('{"entries": {"not": "a list"}}', encoding="utf-8")
        counts = self.build()
        self.assertIn("updates.json", counts["skippedFiles"])
        self.assertEqual(counts["updates"], 0)


class Determinism(unittest.TestCase):
    """Two runs of the real CLI over the same input and --now give byte-identical files."""

    def run_cli(self):
        tmp = Path(tempfile.mkdtemp(prefix="fl-search-cli-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(FIXTURES / "data", tmp / "data")
        code = cli.main(["search", "--data", str(tmp / "data"), "--now", "2026-11-11T06:00:00Z"])
        self.assertEqual(code, 0)
        search = tmp / "data" / "public" / "search"
        return {path.name: path.read_bytes() for path in sorted(search.iterdir())}

    def test_byte_identical(self):
        quiet(self)
        self.addCleanup(timeutil.set_now, None)
        self.addCleanup(net.set_offline, False)
        first, second = self.run_cli(), self.run_cli()
        self.assertEqual(sorted(first), ["docs-2026-10.json", "docs-2026-11.json", "docs-static.json",
                                         "lexicon.json", "manifest.json"])
        for name in first:
            self.assertEqual(first[name], second[name], name)


if __name__ == "__main__":
    unittest.main()
