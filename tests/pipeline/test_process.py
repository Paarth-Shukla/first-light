"""pipeline.process end to end on the real-item fixture, plus its building blocks.

A whole run goes into a temporary data dir: story files, the hot set, state and the
edition are checked against docs/ARCHITECTURE.md; a second and an incremental run check
that ids, files and the frozen edition hold still.
"""

import copy
import unittest
from datetime import datetime, timedelta, timezone

from pipeline import __main__ as cli
from pipeline import cluster, process, rank
from pipeline.core import jsonio, textutil, timeutil
from tests.pipeline.test_process_helpers import (LIVE_DAYS, NOW, TZ, later_context, make_item, make_story,
                                                 real_items, stage_context, store_items)

SECTION_IDS = ["world", "india", "ai", "ml", "llm", "labs", "companies", "markets", "india-markets", "science"]
STORY_KEYS = {"id", "title", "summary", "url", "image", "section", "sections", "entities", "tickers",
              "publishedAt", "updatedAt", "day", "sources", "sourceCount", "score", "signals", "why", "thread"}
SIGNALS = {"breadth", "tier", "recency", "velocity", "attention", "editorial"}


def read_days(ctx):
    return {day: jsonio.read_json(ctx.paths.stories_dir / ("%s.json" % day)) for day in LIVE_DAYS}


def all_stories(ctx):
    return [story for stored in read_days(ctx).values() for story in stored["stories"]]


def source(source_id="test", name="Test Outlet", tier=2, mode="firehose", section="world"):
    return {"id": source_id, "name": name, "tier": tier, "mode": mode, "section": section}


def member(title, name="Test Outlet", tier=2, mode="firehose", section="world", **fields):
    """A classified Member from a hand-built item and source."""
    item = make_item(title, name, section=section, **fields)
    return process.Member(item, source(name=name, tier=tier, mode=mode, section=section),
                          {"bbc news": 1, "reuters": 1, "ndtv": 2}, TZ)


class FullRunTests(unittest.TestCase):
    """One run over the real snapshot, inspected from every side."""

    @classmethod
    def setUpClass(cls):
        cls.ctx = stage_context(cls)
        store_items(cls.ctx, real_items())
        cls.counts = process.run(cls.ctx)
        cls.days = read_days(cls.ctx)
        cls.stories = all_stories(cls.ctx)
        cls.by_title = {story["title"]: story for story in cls.stories}

    def find(self, *words):
        """The best-scored story whose headlines (any outlet's) contain every word."""
        hits = [story for story in self.stories
                if all(any(word.lower() in source["title"].lower() for source in story["sources"]) for word in words)]
        self.assertTrue(hits, words)
        return max(hits, key=lambda story: story["score"])

    def test_counts(self):
        self.assertEqual(self.counts["items"], len(real_items()))
        self.assertEqual(self.counts["skippedItems"], 0)
        self.assertEqual(self.counts["stories"], len(self.stories))
        self.assertEqual(self.counts["newStories"], len(self.stories))
        self.assertGreater(self.counts["multiSource"], 40)
        self.assertEqual(self.counts["edition"], "2026-11-11")
        self.assertLess(len(self.stories), len(real_items()))

    def test_outputs_exist(self):
        paths = self.ctx.paths
        for path in [paths.stories_dir / ("%s.json" % day) for day in LIVE_DAYS] + [
                paths.public / "latest.json", paths.state / "clusters.json", paths.state / "threads.json",
                paths.editions_dir / "2026-11-11.json", paths.editions_dir / "index.json"]:
            self.assertTrue(path.is_file(), path)

    def test_day_files_have_the_contract_shape(self):
        for day, stored in self.days.items():
            self.assertEqual(set(stored), {"date", "generatedAt", "stories"})
            self.assertEqual(stored["date"], day)
            self.assertEqual(stored["generatedAt"], NOW)
            self.assertTrue(all(story["day"] == day for story in stored["stories"]))
            scores = [story["score"] for story in stored["stories"]]
            self.assertEqual(scores, sorted(scores, reverse=True))

    def test_every_story_has_the_contract_shape(self):
        for story in self.stories:
            with self.subTest(story["id"]):
                self.assertEqual(set(story), STORY_KEYS)
                self.assertRegex(story["id"], r"^s[0-9a-f]{10}$")
                self.assertTrue(story["title"].strip())
                self.assertIsInstance(story["summary"], str)
                self.assertTrue(story["url"].startswith("http"))
                self.assertTrue(story["image"] is None or story["image"].startswith("http"))
                self.assertIn(story["section"], SECTION_IDS)
                self.assertEqual(story["sections"][0], story["section"])
                self.assertTrue(set(story["sections"]) <= set(SECTION_IDS))
                self.assertEqual(len(story["sections"]), len(set(story["sections"])))
                self.assertEqual(len(story["entities"]), len(set(story["entities"])))
                self.assertLessEqual(len(story["entities"]), process.MAX_ENTITIES)
                self.assertLessEqual(story["publishedAt"], story["updatedAt"])
                self.assertLessEqual(story["updatedAt"], NOW)
                self.assertEqual(set(story["signals"]), SIGNALS)
                self.assertTrue(all(0.0 <= value <= 1.0 for value in story["signals"].values()))
                self.assertTrue(0.0 <= story["score"] <= 100.0)
                self.assertLessEqual(len(story["why"]), 3)
                self.assertTrue(all(isinstance(reason, str) and reason for reason in story["why"]))
                self.assertGreaterEqual(story["sourceCount"], len(story["sources"]))
                self.assertGreaterEqual(len(story["sources"]), 1)

    def test_story_ids_are_unique_and_derive_from_a_member(self):
        ids = [story["id"] for story in self.stories]
        self.assertEqual(len(ids), len(set(ids)))
        state = jsonio.read_json(self.ctx.paths.state / "clusters.json")
        members = {}
        for item_id, story_id in state["items"].items():
            members.setdefault(story_id, []).append(item_id)
        self.assertEqual(set(members), set(ids))
        for story_id, item_ids in members.items():
            self.assertIn(story_id, {textutil.stable_id("s", item_id) for item_id in item_ids})

    def test_sources_list_each_outlet_once_with_the_contract_fields(self):
        for story in self.stories:
            keys = [cluster.outlet_key(entry["name"]) for entry in story["sources"]]
            self.assertEqual(len(keys), len(set(keys)), story["title"])
            for entry in story["sources"]:
                self.assertEqual(set(entry), {"id", "name", "tier", "title", "url", "publishedAt"})
                self.assertIn(entry["tier"], (1, 2, 3))
        self.assertTrue(all(story["title"] == story["sources"][0]["title"] for story in self.stories))
        self.assertTrue(all(story["url"] == story["sources"][0]["url"] for story in self.stories))

    def test_published_and_updated_span_the_members(self):
        for story in self.stories:
            times = [entry["publishedAt"] for entry in story["sources"]]
            self.assertLessEqual(story["publishedAt"], min(times))
            self.assertGreaterEqual(story["updatedAt"], max(times))

    def test_the_days_biggest_story_is_found_whole_and_ranked_first(self):
        italy = self.find("Italy", "schools", "bomb")
        self.assertGreaterEqual(italy["sourceCount"], 10)
        self.assertEqual(italy["section"], "world")
        self.assertEqual(italy["id"], max(self.stories, key=lambda story: story["score"])["id"])
        self.assertIn("%d outlets" % italy["sourceCount"], italy["why"])
        self.assertTrue(italy["summary"])
        self.assertFalse(italy["url"].startswith("https://news.google.com/"))

    def test_a_labs_own_announcement_leads_its_story_on_the_labs_desk(self):
        gemini = self.find("Gemini 4 Carbon")
        self.assertEqual(gemini["section"], "labs")
        self.assertEqual(gemini["sources"][0]["name"], "Google")
        self.assertEqual(gemini["sources"][0]["tier"], 1)
        self.assertIn("first-party source", gemini["why"])
        self.assertGreaterEqual(gemini["sourceCount"], 5)
        self.assertIn("gemini", gemini["entities"])

    def test_stories_about_a_lab_go_to_the_labs_desk(self):
        ipo = self.find("Anthropic", "IPO", "valuation")
        self.assertEqual(ipo["section"], "labs")
        self.assertIn("anthropic", ipo["entities"])

    def test_company_story_is_on_the_companies_desk_with_its_ticker(self):
        nvidia = self.find("Nvidia", "spy", "affair")
        self.assertEqual(nvidia["section"], "companies")
        self.assertIn("nvidia", nvidia["entities"])
        self.assertIn("NVDA", nvidia["tickers"])
        self.assertGreaterEqual(nvidia["sourceCount"], 8)

    def test_market_close_is_on_dalal_street_and_wall_street_news_is_not(self):
        close = self.find("Sensex", "Nifty", "end higher")
        self.assertEqual(close["section"], "india-markets")
        self.assertTrue({"^BSESN", "^NSEI"} & set(close["tickers"]))
        dalal = [story for story in self.stories if story["section"] == "india-markets"]
        offenders = [story["title"] for story in dalal
                     if any(word in story["title"] for word in ("Nasdaq", "Wall Street", "Sterling", "CoreWeave"))
                     and not any(word in story["title"] for word in ("Sensex", "Nifty", "India", "Rs", "₹"))]
        self.assertEqual(offenders, [])

    def test_multi_source_stories_carry_their_reason(self):
        for story in self.stories:
            if story["sourceCount"] >= 2:
                self.assertIn("%d outlets" % story["sourceCount"], story["why"], story["title"])

    def test_latest_is_the_hot_set(self):
        latest = jsonio.read_json(self.ctx.paths.public / "latest.json")
        self.assertEqual(set(latest), {"generatedAt", "stories", "trending", "sectionCounts"})
        self.assertEqual(latest["generatedAt"], NOW)
        hot = latest["stories"]
        self.assertLessEqual(len(hot), 500)
        self.assertEqual(self.counts["latest"], len(hot))
        scores = [story["score"] for story in hot]
        self.assertEqual(scores, sorted(scores, reverse=True))
        cutoff = timeutil.iso(timeutil.parse_date(NOW) - timedelta(hours=48))
        self.assertTrue(all(story["updatedAt"] >= cutoff for story in hot))
        expected = sorted(story["id"] for story in self.stories if story["updatedAt"] >= cutoff)
        self.assertEqual(sorted(story["id"] for story in hot), expected)
        self.assertEqual(sum(latest["sectionCounts"].values()), len(hot))
        self.assertEqual(list(latest["sectionCounts"]),
                         [section for section in SECTION_IDS if section in latest["sectionCounts"]])
        self.assertEqual(self.by_title[hot[0]["title"]], hot[0])

    def test_trending_entries_have_the_contract_shape(self):
        latest = jsonio.read_json(self.ctx.paths.public / "latest.json")
        self.assertLessEqual(len(latest["trending"]), 12)
        for trend in latest["trending"]:
            self.assertEqual(set(trend), {"entity", "name", "count", "baseline", "ratio"})
            self.assertGreaterEqual(trend["count"], 3)
            self.assertGreaterEqual(trend["ratio"], 2.0)

    def test_edition_is_built_from_this_runs_stories(self):
        printed = jsonio.read_json(self.ctx.paths.editions_dir / "2026-11-11.json")
        self.assertEqual(printed["number"], 1)
        self.assertEqual(printed["lead"], self.find("Italy", "schools", "bomb"))
        self.assertEqual(printed["headline"], printed["lead"]["title"])
        self.assertEqual(len(printed["front"]), 4)
        ids = [printed["lead"]["id"]] + [story["id"] for story in printed["front"] + printed["briefs"]]
        ids += [story["id"] for section in printed["sections"] for story in section["stories"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(printed["stats"]["storiesConsidered"], 150)
        self.assertGreaterEqual(printed["stats"]["readMinutes"], 2)

    def test_a_second_run_changes_nothing(self):
        before = {path.name: path.read_bytes() for path in sorted(self.ctx.paths.stories_dir.iterdir())}
        state = (self.ctx.paths.state / "clusters.json").read_bytes()
        edition_bytes = (self.ctx.paths.editions_dir / "2026-11-11.json").read_bytes()
        counts = process.run(self.ctx)
        self.assertEqual(counts["newStories"], 0)
        self.assertIsNone(counts["edition"])  # already printed today
        self.assertEqual({path.name: path.read_bytes() for path in sorted(self.ctx.paths.stories_dir.iterdir())},
                         before)
        self.assertEqual((self.ctx.paths.state / "clusters.json").read_bytes(), state)
        self.assertEqual((self.ctx.paths.editions_dir / "2026-11-11.json").read_bytes(), edition_bytes)


class IncrementalRunTests(unittest.TestCase):
    """A morning run, then an afternoon run with the rest of the day's items."""

    MORNING = "2026-11-11T05:00:00Z"

    @classmethod
    def setUpClass(cls):
        items = real_items()
        early = [item for item in items if item["publishedAt"] <= cls.MORNING]
        cls.ctx = stage_context(cls, cls.MORNING)
        store_items(cls.ctx, early)
        cls.first_counts = process.run(cls.ctx)
        cls.first = {story["id"]: story for story in all_stories(cls.ctx)}
        cls.first_edition = (cls.ctx.paths.editions_dir / "2026-11-11.json").read_bytes()
        cls.first_threads = jsonio.read_json(cls.ctx.paths.state / "threads.json")
        store_items(cls.ctx, items)
        cls.second_counts = process.run(later_context(cls.ctx, NOW))
        cls.second = {story["id"]: story for story in all_stories(cls.ctx)}
        cls.early_count, cls.total = len(early), len(items)

    def test_the_runs_saw_different_amounts(self):
        self.assertEqual(self.first_counts["items"], self.early_count)
        self.assertEqual(self.second_counts["items"], self.total)
        self.assertGreater(self.second_counts["newStories"], 50)
        self.assertEqual(len(self.second), len(self.first) + self.second_counts["newStories"])

    def test_every_story_keeps_its_id_and_day(self):
        self.assertTrue(set(self.first) <= set(self.second))
        for story_id, story in self.first.items():
            self.assertEqual(self.second[story_id]["day"], story["day"])
            self.assertEqual(self.second[story_id]["publishedAt"] <= story["publishedAt"], True)

    def test_stories_only_gain_outlets(self):
        grew = 0
        for story_id, story in self.first.items():
            later = self.second[story_id]
            self.assertGreaterEqual(later["sourceCount"], story["sourceCount"])
            self.assertGreaterEqual(later["updatedAt"], story["updatedAt"])
            grew += later["sourceCount"] > story["sourceCount"]
        self.assertGreater(grew, 5)

    def test_the_morning_edition_stays_frozen(self):
        self.assertEqual(self.first_counts["edition"], "2026-11-11")
        self.assertIsNone(self.second_counts["edition"])
        self.assertEqual((self.ctx.paths.editions_dir / "2026-11-11.json").read_bytes(), self.first_edition)

    def test_thread_assignments_survive(self):
        later = jsonio.read_json(self.ctx.paths.state / "threads.json")
        for story_id, thread_id in self.first_threads["stories"].items():
            self.assertEqual(later["stories"][story_id], thread_id)

    def test_tomorrow_the_oldest_day_is_frozen_and_ids_still_hold(self):
        frozen_day = LIVE_DAYS[0]
        frozen_before = (self.ctx.paths.stories_dir / ("%s.json" % frozen_day)).read_bytes()
        kept = {day: jsonio.read_json(self.ctx.paths.stories_dir / ("%s.json" % day)) for day in LIVE_DAYS[1:]}
        late = make_item("Ferry capsizes off Zanzibar with more than 200 aboard, dozens missing", "AP News",
                         "2026-11-12T03:00:00Z")
        store_items(self.ctx, real_items() + [late])
        counts = process.run(later_context(self.ctx, "2026-11-12T04:00:00Z"))
        self.assertEqual(counts["newStories"], 1)
        self.assertEqual(counts["edition"], "2026-11-12")
        self.assertEqual((self.ctx.paths.stories_dir / ("%s.json" % frozen_day)).read_bytes(), frozen_before)
        for day, stored in kept.items():
            now = jsonio.read_json(self.ctx.paths.stories_dir / ("%s.json" % day))
            self.assertEqual({story["id"] for story in now["stories"]}, {story["id"] for story in stored["stories"]})
        today = jsonio.read_json(self.ctx.paths.stories_dir / "2026-11-12.json")
        self.assertEqual([story["title"] for story in today["stories"]], [late["title"]])
        index = jsonio.read_json(self.ctx.paths.editions_dir / "index.json")
        self.assertEqual([(entry["date"], entry["number"]) for entry in index["editions"]],
                         [("2026-11-12", 2), ("2026-11-11", 1)])
        second_edition = jsonio.read_json(self.ctx.paths.editions_dir / "2026-11-12.json")
        printed = [second_edition["lead"]] + second_edition["front"] + second_edition["briefs"]
        printed += [story for section in second_edition["sections"] for story in section["stories"]]
        # Fresh means updated since the first edition (05:00) or within 24 hours (04:00), whichever is earlier.
        self.assertTrue(all(story["updatedAt"] >= "2026-11-11T04:00:00Z" for story in printed))
        self.assertGreater(len(printed), 20)


class RobustnessTests(unittest.TestCase):

    def test_empty_store_writes_empty_outputs_and_no_edition(self):
        ctx = stage_context(self)
        counts = process.run(ctx)
        self.assertEqual((counts["items"], counts["stories"], counts["edition"]), (0, 0, None))
        self.assertEqual(jsonio.read_json(ctx.paths.public / "latest.json"),
                         {"generatedAt": NOW, "stories": [], "trending": [], "sectionCounts": {}})
        for day in LIVE_DAYS:
            self.assertEqual(jsonio.read_json(ctx.paths.stories_dir / ("%s.json" % day))["stories"], [])
        self.assertFalse((ctx.paths.editions_dir / "2026-11-11.json").exists())
        self.assertIn("no fresh stories", self.log_output.getvalue())

    def test_malformed_items_are_skipped_and_counted(self):
        ctx = stage_context(self)
        good = make_item("Ferry capsizes off Zanzibar with more than 200 aboard", "AP News", "2026-11-11T08:00:00Z")
        entries = {
            good["id"]: good,
            "no-title": dict(make_item("x", published="2026-11-11T08:00:00Z"), title="  "),
            "no-date": dict(make_item("A headline without a date", published="2026-11-11T08:00:00Z"),
                            publishedAt="yesterday-ish"),
            "no-url": dict(make_item("A headline without a link", published="2026-11-11T08:00:00Z"), url=""),
            "not-an-object": "nonsense",
        }
        jsonio.write_json(ctx.paths.items_dir / "2026-11-11.json", {"date": "2026-11-11", "items": entries})
        jsonio.write_json(ctx.paths.items_dir / "2026-11-10.json", ["not", "an", "items", "file"])
        (ctx.paths.items_dir / "2026-11-09.json").write_text("{ truncated", encoding="utf-8")
        counts = process.run(ctx)
        self.assertEqual((counts["items"], counts["skippedItems"], counts["stories"]), (1, 4, 1))
        self.assertIn("not an items file", self.log_output.getvalue())

    def test_item_from_an_unknown_desk_is_skipped_with_a_warning(self):
        ctx = stage_context(self)
        store_items(ctx, [make_item("Ferry capsizes off Zanzibar with more than 200 aboard", "AP News",
                                    "2026-11-11T08:00:00Z", section="gardening"),
                          make_item("Parliament passes the annual budget after marathon debate", "Reuters",
                                    "2026-11-11T09:00:00Z")])
        counts = process.run(ctx)
        self.assertEqual((counts["items"], counts["skippedItems"], counts["stories"]), (1, 1, 1))
        self.assertIn("gardening", self.log_output.getvalue())

    def test_junk_scores_below_news_of_the_same_standing(self):
        ctx = stage_context(self)
        when = "2026-11-11T12:00:00Z"
        store_items(ctx, [
            make_item("Regulator fines cement makers for price fixing", "Mint", when, summary="Details."),
            make_item("Stocks to watch: Reliance, TCS, Infosys, HDFC Bank", "Mint", when, summary="Details."),
            make_item("Best Black Friday deals on laptops and headphones", "Mint", when, summary="Details."),
            make_item("Budget session: Live updates", "Mint", when, summary="Details."),
        ])
        process.run(ctx)
        scores = {story["title"].split()[0]: story["score"] for story in all_stories(ctx)}
        self.assertEqual(len(scores), 4)
        self.assertTrue(all(scores["Regulator"] > scores[junk] for junk in ("Stocks", "Best", "Budget")), scores)

    def test_item_from_an_unconfigured_source_still_becomes_a_story(self):
        ctx = stage_context(self)
        store_items(ctx, [make_item("Ferry capsizes off Zanzibar with more than 200 aboard", "Some Blog",
                                    "2026-11-11T08:00:00Z", source="retired-source")])
        process.run(ctx)
        story = all_stories(ctx)[0]
        self.assertEqual(story["sources"][0], {
            "id": "retired-source", "name": "Some Blog", "tier": 3, "title": story["title"], "url": story["url"],
            "publishedAt": "2026-11-11T08:00:00Z"})

    def test_future_dated_item_does_not_run_ahead_of_the_clock(self):
        ctx = stage_context(self)
        store_items(ctx, [make_item("Ferry capsizes off Zanzibar with more than 200 aboard", "AP News",
                                    "2026-11-11T18:00:00Z")])
        process.run(ctx)
        story = all_stories(ctx)[0]
        self.assertEqual((story["publishedAt"], story["updatedAt"]), (NOW, NOW))
        self.assertEqual(story["signals"]["recency"], 1.0)

    def test_corrupt_state_files_are_replaced(self):
        ctx = stage_context(self)
        store_items(ctx, real_items()[:40])
        (ctx.paths.state / "clusters.json").write_text("[1, 2", encoding="utf-8")
        jsonio.write_json(ctx.paths.state / "threads.json", {"stories": []})
        counts = process.run(ctx)
        self.assertGreater(counts["stories"], 0)
        self.assertEqual(set(jsonio.read_json(ctx.paths.state / "clusters.json")), {"items", "stories"})
        self.assertEqual(set(jsonio.read_json(ctx.paths.state / "threads.json")), {"stories", "threads"})

    def test_story_files_past_retention_are_pruned_and_frozen_ones_left_alone(self):
        ctx = stage_context(self)
        marker = {"date": "x", "generatedAt": "x", "stories": []}
        for day in ("2026-07-01", "2026-08-12", "2026-08-13", "2026-11-08"):
            jsonio.write_json(ctx.paths.stories_dir / ("%s.json" % day), marker)
        (ctx.paths.stories_dir / "notes.txt").write_text("keep me", encoding="utf-8")
        counts = process.run(ctx)
        self.assertEqual(counts["prunedFiles"], 2)  # retentionDays is 90: 2026-08-13 is the oldest day kept
        names = sorted(path.name for path in ctx.paths.stories_dir.iterdir())
        self.assertEqual(names, ["2026-08-13.json", "2026-11-08.json", "2026-11-09.json", "2026-11-10.json",
                                 "2026-11-11.json", "notes.txt"])
        self.assertEqual(jsonio.read_json(ctx.paths.stories_dir / "2026-11-08.json"), marker)

    def test_cluster_state_forgets_stories_long_frozen(self):
        ctx = stage_context(self)
        jsonio.write_json(ctx.paths.state / "clusters.json",
                          {"items": {"i-old": "s-old", "i-recent": "s-recent"},
                           "stories": {"s-old": {"day": "2026-10-20"}, "s-recent": {"day": "2026-11-05"}}})
        process.run(ctx)
        state = jsonio.read_json(ctx.paths.state / "clusters.json")
        self.assertEqual(state, {"items": {"i-recent": "s-recent"}, "stories": {"s-recent": {"day": "2026-11-05"}}})

    def test_cli_runs_the_stage_and_records_it(self):
        ctx = stage_context(self)
        store_items(ctx, real_items()[:60])
        status = cli.main(["process", "--data", str(ctx.paths.data), "--now", NOW])
        self.assertEqual(status, 0)
        record = jsonio.read_json(ctx.paths.state / "run.json")[-1]
        self.assertEqual((record["stage"], record["ok"], record["error"]), ("process", True, None))
        self.assertEqual(record["counts"]["items"], 60)
        self.assertEqual(record["counts"]["edition"], "2026-11-11")

    def test_cli_force_edition_reprints(self):
        ctx = stage_context(self)
        store_items(ctx, real_items()[:60])
        self.assertEqual(cli.main(["process", "--data", str(ctx.paths.data), "--now", NOW]), 0)
        self.assertEqual(cli.main(["process", "--data", str(ctx.paths.data), "--now", "2026-11-11T15:00:00Z"]), 0)
        self.assertEqual(jsonio.read_json(ctx.paths.editions_dir / "2026-11-11.json")["generatedAt"], NOW)
        self.assertEqual(cli.main(["process", "--data", str(ctx.paths.data), "--now", "2026-11-11T16:00:00Z",
                                   "--force-edition"]), 0)
        printed = jsonio.read_json(ctx.paths.editions_dir / "2026-11-11.json")
        self.assertEqual((printed["generatedAt"], printed["number"]), ("2026-11-11T16:00:00Z", 1))


class LiveDayTests(unittest.TestCase):

    def test_three_local_days_ending_today(self):
        now = datetime(2026, 11, 11, 14, 30, tzinfo=timezone.utc)
        self.assertEqual(process.live_days(now, TZ), LIVE_DAYS)

    def test_local_midnight_decides_not_utc(self):
        late = datetime(2026, 11, 11, 19, 0, tzinfo=timezone.utc)  # 00:30 on the 12th in Kolkata
        self.assertEqual(process.live_days(late, TZ), ["2026-11-10", "2026-11-11", "2026-11-12"])

    def test_month_boundary(self):
        self.assertEqual(process.live_days(datetime(2026, 3, 1, 6, 0, tzinfo=timezone.utc), TZ),
                         ["2026-02-27", "2026-02-28", "2026-03-01"])


class DeskTests(unittest.TestCase):

    def test_indian_markets_feed_keeps_indian_stories(self):
        for title in ("Sensex, Nifty close higher as banks rally",
                      "Bajaj Finance launches QIP with floor price at ₹992.25 per share",
                      "Cabinet decisions today: Rs 62,370 crore fertiliser subsidy cleared",
                      "Moody's raises India's growth forecast to 7%"):
            with self.subTest(title):
                self.assertEqual(member(title, section="india-markets").primary, "india-markets")

    def test_indian_markets_feed_passes_on_foreign_business_news(self):
        for title in ("Sterling drops against firmer dollar as markets price in a hawkish Fed",
                      "Nvidia Stock Sell-Off Deepens: Spy scandal puts AI giant under pressure",
                      "AI whiplash poses major test for Wall Street's dip-buying habit"):
            with self.subTest(title):
                found = member(title, section="india-markets")
                self.assertNotEqual(found.primary, "india-markets")
                self.assertNotIn("india-markets", found.sections)
                self.assertEqual(found.sections[0], found.primary)

    def test_unclassifiable_foreign_item_falls_back_to_markets(self):
        self.assertEqual(member("Why some bets pay off and others never do", section="india-markets").primary,
                         "markets")

    def test_other_desks_follow_the_lexicon(self):
        self.assertEqual(member("Why some bets pay off and others never do", section="llm").primary, "llm")
        self.assertEqual(member("Nvidia unveils Rubin Ultra chips", section="world").primary, "companies")


class MemberTests(unittest.TestCase):

    def test_outlet_through_an_aggregator_keeps_its_own_standing(self):
        relayed = member("Ferry capsizes off Zanzibar", "Google News", tier=3, publisher="BBC")
        self.assertTrue(relayed.relayed)
        self.assertEqual((relayed.name, relayed.outlet, relayed.tier, relayed.feed_tier), ("BBC", "bbc news", 1, 3))
        unknown = member("Ferry capsizes off Zanzibar", "Google News", tier=3, publisher="Coastal Gazette")
        self.assertEqual((unknown.tier, unknown.relayed), (3, True))

    def test_single_publisher_search_feed_is_not_a_relay(self):
        wire = member("Ferry capsizes off Zanzibar", "Reuters", tier=1, publisher="Reuters")
        self.assertFalse(wire.relayed)
        self.assertEqual(wire.tier, 1)

    def test_google_news_link_is_not_a_direct_link(self):
        self.assertFalse(member("A headline", url="https://news.google.com/rss/articles/CBMi?oc=5").direct_link)
        self.assertTrue(member("A headline", url="https://www.bbc.co.uk/news/articles/c1").direct_link)

    def test_lab_subject_is_the_first_name_in_the_headline(self):
        self.assertTrue(member("Anthropic targets $1.4 trillion IPO").lab_subject)
        self.assertFalse(member("Australia considers penalties for rogue AI in wake of OpenAI hack").lab_subject)
        self.assertFalse(member("Ferry capsizes off Zanzibar").lab_subject)


class BestMemberTests(unittest.TestCase):

    def order(self, *members):
        newest = max(found.time for found in members)
        return [found.item["title"] for found in process.best_first(list(members), newest)]

    def test_higher_tier_first(self):
        self.assertEqual(self.order(member("Blog take", tier=3), member("Paper of record", tier=1),
                                    member("Trade press", tier=2)), ["Paper of record", "Trade press", "Blog take"])

    def test_first_party_then_curated_then_firehose_within_a_tier(self):
        self.assertEqual(self.order(member("Firehose", tier=1), member("Curated", tier=1, mode="curated"),
                                    member("Official", tier=1, mode="official")),
                         ["Official", "Curated", "Firehose"])

    def test_longest_summary_breaks_the_tie(self):
        self.assertEqual(self.order(member("Short", summary="Brief."), member("Long", summary="A much longer one.")),
                         ["Long", "Short"])

    def test_direct_link_beats_a_google_news_redirect_even_from_a_better_outlet(self):
        google = member("Wire via Google", "Reuters", tier=1, publisher="Reuters",
                        url="https://news.google.com/rss/articles/CBMi?oc=5")
        direct = member("Trade press direct", tier=2, summary="With a summary.")
        self.assertEqual(self.order(google, direct), ["Trade press direct", "Wire via Google"])

    def test_real_headline_beats_a_live_blog_or_promo(self):
        live = member("Budget session: Live updates", tier=1, mode="curated")
        news = member("Finance minister cuts income tax in budget", tier=2)
        self.assertEqual(self.order(live, news)[0], news.item["title"])

    def test_todays_headline_beats_yesterdays(self):
        old = member("Probe opens", tier=1, published="2026-11-10T02:00:00Z")
        new = member("Probe widens", tier=2, published="2026-11-11T08:00:00Z")
        self.assertEqual(self.order(old, new), ["Probe widens", "Probe opens"])
        close = member("Probe opens", tier=1, published="2026-11-11T02:00:00Z")
        self.assertEqual(self.order(close, new), ["Probe opens", "Probe widens"])


class BuildStoryTests(unittest.TestCase):

    TIERS = {"bbc news": 1, "reuters": 1, "ndtv": 2}

    def build(self, members, tickers=None):
        return process.build_story("s-test", "2026-11-11", members, self.TIERS, SECTION_IDS, tickers or {},
                                   timeutil.parse_date(NOW))

    def test_story_takes_title_and_link_from_the_best_member_and_fills_gaps_from_the_next(self):
        best = member("Volcano erupts near Arequipa", "BBC News", tier=1, published="2026-11-11T09:00:00Z")
        second = member("Peru volcano: thousands evacuated", "NDTV", tier=2, published="2026-11-11T07:00:00Z",
                        summary="Ash fell on villages.", image="https://example.org/ash.jpg")
        story, facts = self.build([second, best])
        self.assertEqual((story["title"], story["url"]), (best.item["title"], best.item["url"]))
        self.assertEqual((story["summary"], story["image"]), ("Ash fell on villages.", "https://example.org/ash.jpg"))
        self.assertEqual((story["publishedAt"], story["updatedAt"]), ("2026-11-11T07:00:00Z", "2026-11-11T09:00:00Z"))
        self.assertEqual([entry["name"] for entry in story["sources"]], ["BBC News", "NDTV"])
        self.assertEqual((story["sourceCount"], facts["bestTier"], facts["firstParty"]), (2, 1, False))

    def test_same_outlet_twice_counts_once(self):
        story, facts = self.build([member("Volcano erupts near Arequipa", "BBC News", tier=1),
                                   member("Volcano: what we know", "BBC News", tier=1,
                                          published="2026-11-11T09:00:00Z")])
        self.assertEqual((story["sourceCount"], len(story["sources"]), len(facts["outlets"])), (1, 1, 1))
        self.assertEqual(rank.breadth(facts["outlets"]), 0.0)

    def test_outlets_an_aggregator_lists_are_counted_but_not_linked(self):
        item_alts = [{"title": "Other take", "publisher": "Reuters"}, {"title": "Third take", "publisher": "BBC"},
                     {"title": "Fourth", "publisher": "Coastal Gazette"}]
        google = member("Volcano erupts near Arequipa", "Google News", tier=3, publisher="NDTV", alt=item_alts)
        bbc = member("Volcano erupts in Peru", "BBC News", tier=1)
        story, facts = self.build([google, bbc])
        self.assertEqual(story["sourceCount"], 4)
        self.assertEqual([entry["name"] for entry in story["sources"]], ["BBC News", "NDTV"])
        via = sorted((outlet["tier"], outlet["via"]) for outlet in facts["outlets"])
        self.assertEqual(via, [(1, "direct"), (1, "listed"), (2, "relayed"), (3, "listed")])

    def test_curated_slots_become_placements_one_per_curator(self):
        top = member("Volcano erupts near Arequipa", "BBC News", tier=1, mode="curated", feedRank=1)
        again = member("Volcano: what we know", "BBC News", tier=1, mode="curated", feedRank=7,
                       published="2026-11-11T09:00:00Z")
        google = member("Peru volcano erupts", "Google News", tier=3, mode="curated", feedRank=0, publisher="NDTV")
        firehose = member("Volcano latest", "Reuters", tier=1, feedRank=0)
        _story, facts = self.build([top, again, google, firehose])
        self.assertEqual(sorted(facts["placements"]), [(1, 1), (3, 0)])
        self.assertEqual(facts["topSlots"], ["BBC News"])

    def test_hacker_news_points_come_from_any_member(self):
        _story, facts = self.build([member("Volcano erupts", "BBC News", tier=1),
                                    member("Volcano erupts in Peru", "Hacker News", tier=3, points=412, comments=200)])
        self.assertEqual((facts["points"], facts["comments"]), (412, 200))

    def test_labs_desk_takes_a_labs_own_post_and_stories_led_by_a_lab(self):
        official = member("Introducing a smaller, faster model", "OpenAI", tier=1, mode="official", section="labs")
        press = [member("New small model undercuts rivals on price", "Outlet %d" % index, section="ai")
                 for index in range(3)]
        self.assertEqual(self.build([official] + press)[0]["section"], "labs")
        about = [member("Anthropic targets $1.4 trillion IPO", "Outlet A", section="markets"),
                 member("Anthropic sets IPO price range", "Outlet B", section="ai"),
                 member("IPO market braces for biggest listing ever", "Outlet C", section="markets")]
        self.assertEqual(self.build(about)[0]["section"], "labs")
        mention = [member("Australia weighs AI law after OpenAI hack", "Outlet A", section="world"),
                   member("Canberra considers criminal penalties for rogue AI", "Outlet B", section="world"),
                   member("Rogue AI could bring jail terms in Australia", "Outlet C", section="ai")]
        self.assertNotEqual(self.build(mention)[0]["section"], "labs")

    def test_outlets_vote_for_the_primary_desk(self):
        members = [member("Volcano erupts near Arequipa", "Outlet A", section="world"),
                   member("Peru volcano erupts, thousands flee", "Outlet B", section="world"),
                   member("Volcano ash grounds flights", "Outlet C", section="science")]
        story, _facts = self.build(members)
        self.assertEqual(story["section"], "world")
        self.assertEqual(story["sections"][0], "world")

    def test_entities_need_support_and_tickers_follow_entities(self):
        members = [member("Nvidia hires law firm over affair inquiry", "Outlet A", section="companies"),
                   member("Nvidia board opens inquiry", "Outlet B", section="companies"),
                   member("Nvidia inquiry: what Tesla's board did differently", "Outlet C", section="companies"),
                   member("Chipmaker inquiry widens", "Outlet D", section="companies"),
                   member("Inquiry into chipmaker chief", "Outlet E", section="companies"),
                   member("Board hires law firm", "Outlet F", section="companies"),
                   member("Law firm to lead inquiry", "Outlet G", section="companies"),
                   member("Inquiry to take months", "Outlet H", section="companies"),
                   member("Nvidia inquiry begins", "Outlet I", section="companies")]
        story, _facts = self.build(members, {"nvidia": "NVDA", "tesla": "TSLA"})
        self.assertIn("nvidia", story["entities"])
        self.assertNotIn("tesla", story["entities"])  # one mention in nine
        self.assertEqual(story["tickers"], ["NVDA"])


class TrendingTests(unittest.TestCase):

    NOW = timeutil.parse_date(NOW)

    def story(self, index, hours_ago, entities):
        updated = timeutil.iso(self.NOW - timedelta(hours=hours_ago))
        return make_story("s%d-%s" % (index, hours_ago), "Story %d" % index, updated=updated, entities=entities)

    def windows(self, today, *earlier):
        """Stories mentioning the given entities: ``today`` and each earlier day map entity -> count."""
        made, serial = [], 0
        for days_back, counts in enumerate((today,) + earlier):
            for entity, count in counts.items():
                for _ in range(count):
                    serial += 1
                    made.append(self.story(serial, 24 * days_back + 2, [entity]))
        return process.day_windows(made, self.NOW)

    def test_day_windows_bucket_by_age(self):
        stories = [self.story(1, 1, []), self.story(2, 23.9, []), self.story(3, 24.1, []),
                   self.story(4, 24 * 7 + 5, []), self.story(5, 24 * 8 + 1, [])]
        windows = process.day_windows(stories, self.NOW)
        self.assertEqual([len(window) for window in windows], [2, 1, 0, 0, 0, 0, 0, 1])

    def test_entity_well_above_its_usual_level_trends(self):
        trends = process.trending(self.windows({"nvidia": 9, "openai": 4}, {"nvidia": 2, "openai": 4},
                                               {"nvidia": 2, "openai": 4}))
        self.assertEqual(trends, [{"entity": "nvidia", "name": "Nvidia", "count": 9, "baseline": 2.0, "ratio": 4.5}])

    def test_needs_three_stories_today(self):
        self.assertEqual(process.trending(self.windows({"nvidia": 2}, {"openai": 1})), [])

    def test_needs_twice_the_baseline(self):
        self.assertEqual(process.trending(self.windows({"nvidia": 5}, {"nvidia": 3}, {"nvidia": 3})), [])
        self.assertEqual(len(process.trending(self.windows({"nvidia": 6}, {"nvidia": 3}, {"nvidia": 3}))), 1)

    def test_baseline_is_the_mean_over_days_with_data(self):
        trends = process.trending(self.windows({"nvidia": 8}, {"nvidia": 4}, {}, {"openai": 5}))
        self.assertEqual((trends[0]["baseline"], trends[0]["ratio"]), (2.0, 4.0))

    def test_rare_entity_is_measured_against_once_a_day(self):
        trends = process.trending(self.windows({"nvidia": 3}, {"openai": 5}))
        self.assertEqual((trends[0]["baseline"], trends[0]["ratio"]), (0.0, 3.0))

    def test_no_history_no_trends(self):
        self.assertEqual(process.trending(self.windows({"nvidia": 20})), [])

    def test_places_never_trend(self):
        self.assertEqual(process.trending(self.windows({"india": 30, "united-states": 12}, {"india": 1})), [])

    def test_at_most_twelve_strongest_first(self):
        ids = ["nvidia", "openai", "anthropic", "tesla", "spacex", "apple", "microsoft", "google", "meta", "amazon",
               "tsmc", "amd", "intel", "reliance"]
        today = {entity: 3 + index for index, entity in enumerate(ids)}
        trends = process.trending(self.windows(today, {"sensex": 1}))
        self.assertEqual(len(trends), 12)
        self.assertEqual([trend["entity"] for trend in trends[:2]], ["reliance", "intel"])
        ratios = [trend["ratio"] for trend in trends]
        self.assertEqual(ratios, sorted(ratios, reverse=True))


class HelperTests(unittest.TestCase):

    def test_outlet_tiers_keep_the_best_tier_per_newsroom(self):
        sources = {"a": {"id": "a", "name": "The Guardian", "tier": 2}, "b": {"id": "b", "name": "Guardian", "tier": 1},
                   "c": {"id": "c", "name": "Odd", "tier": 9}}
        self.assertEqual(process.outlet_tiers(sources), {"guardian": 1})

    def test_shipped_sources_load(self):
        sources = process.load_sources()
        self.assertGreater(len(sources), 100)
        self.assertEqual(process.outlet_tiers(sources)["bbc news"], 1)

    def test_days_running(self):
        story = make_story("s1", "A story", updated="2026-11-11T08:00:00Z", day="2026-11-09")
        self.assertEqual(process._days_running(story, TZ), 3)
        self.assertEqual(process._days_running(dict(story, day="2026-11-11"), TZ), 1)

    def test_reasons_include_the_day_of_a_long_running_story(self):
        ctx = stage_context(self)
        story = make_story("s1", "A story", updated="2026-11-11T08:00:00Z", day="2026-11-09", sources=3)
        facts = {"sourceCount": 3, "firstAt": timeutil.parse_date("2026-11-09T08:00:00Z"), "points": 0,
                 "firstParty": False, "topSlots": []}
        process.add_reasons([(story, facts)], ctx)
        self.assertEqual(story["why"], ["3 outlets", "day 3"])
        self.assertIsNone(story["thread"])

    def test_thread_day_counts_the_days_the_story_itself_has_run(self):
        ctx = stage_context(self)
        facts = {"sourceCount": 3, "firstAt": timeutil.parse_date("2026-11-09T08:00:00Z"), "points": 0,
                 "firstParty": False, "topSlots": []}
        # Filed on the 9th as day 5 of its thread, still gaining items on the 11th: day 7.
        running = make_story("s1", "A story", updated="2026-11-11T08:00:00Z", day="2026-11-09", sources=3,
                             thread={"id": "t1", "day": 5, "history": []})
        process.add_reasons([(running, copy.deepcopy(facts))], ctx)
        self.assertEqual(running["thread"]["day"], 7)
        self.assertIn("day 7", running["why"])
        # Filed and last updated on the same day: the thread's own count stands.
        fresh = make_story("s2", "A story", updated="2026-11-11T08:00:00Z", sources=3,
                           thread={"id": "t1", "day": 5, "history": []})
        process.add_reasons([(fresh, copy.deepcopy(facts))], ctx)
        self.assertEqual(fresh["thread"]["day"], 5)
        # The root of a thread on its first day is day 1 and says nothing about it.
        root = make_story("s3", "A story", updated="2026-11-11T08:00:00Z", sources=3,
                          thread={"id": "t1", "day": 1, "history": []})
        process.add_reasons([(root, copy.deepcopy(facts))], ctx)
        self.assertEqual((root["thread"]["day"], root["why"]), (1, ["3 outlets"]))


if __name__ == "__main__":
    unittest.main()
