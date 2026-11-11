"""pipeline.edition: every rule of the frozen morning paper.

When it is printed (hour, freeze, force), which stories are eligible, how the lead, front,
sections and briefs are filled, the no-duplicate and one-per-thread rules, and the furniture
around the stories (markets strip, Claude card, weekend pointer, stats, index).
"""

import json
import unittest
from datetime import date, timedelta

from pipeline import edition
from pipeline.core import jsonio
from tests.pipeline.test_process_helpers import later_context, make_story, stage_context

MORNING = "2026-11-11T01:00:00Z"   # 06:30 in Kolkata
BEFORE = "2026-11-10T23:00:00Z"    # 04:30 in Kolkata, still the 11th locally
SECTIONS = ["world", "india", "ai", "ml", "llm", "labs", "companies", "markets", "india-markets", "science"]

# Distinct, unrelated headlines so the same-event rule never interferes unless a test wants it to.
HEADLINES = [
    "Ferry capsizes off Zanzibar with hundreds aboard", "Parliament passes the annual budget after marathon debate",
    "Volcano erupts near Arequipa, thousands evacuated", "Court strikes down telecom spectrum auction rules",
    "New malaria vaccine cuts child deaths by half in trial", "Airline pilots call off strike after pay deal",
    "Drought forces water rationing in Cape Town", "Museum recovers stolen Renaissance painting",
    "Bridge collapse closes key Himalayan highway", "Regulator fines cement makers for price fixing",
    "Astronomers find rocky planet in nearby habitable zone", "Port workers end blockade in Rotterdam",
    "Chess prodigy becomes youngest grandmaster", "Cyclone warning issued for Odisha coast",
    "Steel tariffs trigger dispute at trade body", "Library digitises medieval manuscripts archive",
    "Wildfire smoke shuts schools across Alberta", "Rail operator orders hydrogen trains for branch lines",
    "Fishermen rescued after week adrift near Sri Lanka", "Glacier lake outburst damages hydropower dam",
    "Opera house reopens after decade of restoration", "Antitrust probe targets grocery delivery apps",
    "Coral bleaching spreads on Great Barrier Reef", "Metro line extension opens in Pune",
    "Vintage aircraft makes emergency landing on beach", "Coffee prices hit record on Brazilian frost",
    "University scraps entrance exam after paper leak", "Submarine cable cut slows internet in East Africa",
    "Tiger census counts rise in central India reserves", "Bank union calls two-day nationwide stoppage",
    "Satellite images show new island after eruption", "Heatwave buckles rail tracks in northern Spain",
    "Election commission redraws assembly boundaries", "Chipmaker breaks ground on Gujarat fabrication plant",
    "Orchestra tours with instruments made from scrap", "Avalanche buries mountain road in Kashmir valley",
    "Pharma recall widens over contaminated cough syrup", "Startup demonstrates sodium battery scooter",
    "Archaeologists unearth Bronze Age harbour", "Dairy cooperative raises milk procurement price",
]


def stories(count, top=90.0, **common):
    """``count`` unrelated stories scored ``top`` downwards, cycling through the sections."""
    return [make_story("s%03d" % index, HEADLINES[index], score=top - index,
                       section=SECTIONS[index % len(SECTIONS)], **common)
            for index in range(count)]


def printed_ids(printed):
    """Every story id in an edition, in reading order."""
    ids = [printed["lead"]["id"]] + [story["id"] for story in printed["front"]]
    ids += [story["id"] for section in printed["sections"] for story in section["stories"]]
    return ids + [story["id"] for story in printed["briefs"]]


class EditionCase(unittest.TestCase):

    def context(self, now=MORNING, force_edition=False):
        return stage_context(self, now, force_edition)

    def read(self, ctx, day="2026-11-11"):
        return jsonio.read_json(ctx.paths.editions_dir / ("%s.json" % day))


class TimingTests(EditionCase):

    def test_not_printed_before_the_edition_hour(self):
        ctx = self.context(BEFORE)
        self.assertIsNone(edition.build(ctx, stories(20)))
        self.assertEqual(list(ctx.paths.editions_dir.iterdir()), [])

    def test_printed_by_the_first_run_at_or_after_the_hour(self):
        ctx = self.context("2026-11-11T00:30:00Z")  # 06:00 sharp in Kolkata
        self.assertEqual(edition.build(ctx, stories(20)), {"date": "2026-11-11", "number": 1})
        printed = self.read(ctx)
        self.assertEqual(printed["date"], "2026-11-11")
        self.assertEqual(printed["generatedAt"], "2026-11-11T00:30:00Z")

    def test_frozen_for_the_rest_of_the_day(self):
        ctx = self.context()
        edition.build(ctx, stories(20))
        before = (ctx.paths.editions_dir / "2026-11-11.json").read_bytes()
        later_ctx = later_context(ctx, "2026-11-11T09:00:00Z")
        fresh = [make_story("s-new", "Entirely new and much bigger story breaks", score=99.0, sources=9,
                            updated="2026-11-11T08:50:00Z")]
        self.assertIsNone(edition.build(later_ctx, fresh + stories(20)))
        self.assertEqual((ctx.paths.editions_dir / "2026-11-11.json").read_bytes(), before)

    def test_force_reprints_and_keeps_the_number(self):
        ctx = self.context()
        edition.build(ctx, stories(20))
        forced = later_context(ctx, "2026-11-11T09:00:00Z", force_edition=True)
        fresh = [make_story("s-new", "Entirely new and much bigger story breaks", score=99.0, sources=9,
                            updated="2026-11-11T08:50:00Z")]
        self.assertEqual(edition.build(forced, fresh + stories(20)), {"date": "2026-11-11", "number": 1})
        printed = self.read(ctx)
        self.assertEqual(printed["lead"]["id"], "s-new")
        self.assertEqual(printed["generatedAt"], "2026-11-11T09:00:00Z")

    def test_force_prints_even_before_the_hour(self):
        ctx = self.context(BEFORE, force_edition=True)
        self.assertIsNotNone(edition.build(ctx, stories(20, updated="2026-11-10T20:00:00Z")))

    def test_number_counts_existing_editions_and_index_lists_newest_first(self):
        ctx = self.context()
        for day, number in (("2026-11-08", 1), ("2026-11-10", 2)):
            jsonio.write_json(ctx.paths.editions_dir / ("%s.json" % day),
                              {"date": day, "number": number, "generatedAt": "%sT01:00:00Z" % day,
                               "headline": "Headline of %s" % day})
        self.assertEqual(edition.build(ctx, stories(20))["number"], 3)
        index = jsonio.read_json(ctx.paths.editions_dir / "index.json")
        self.assertEqual(index, {"editions": [
            {"date": "2026-11-11", "number": 3, "headline": HEADLINES[0]},
            {"date": "2026-11-10", "number": 2, "headline": "Headline of 2026-11-10"},
            {"date": "2026-11-08", "number": 1, "headline": "Headline of 2026-11-08"},
        ]})

    def test_index_forgets_editions_whose_files_are_gone(self):
        ctx = self.context()
        jsonio.write_json(ctx.paths.editions_dir / "index.json",
                          {"editions": [{"date": "2026-10-01", "number": 7, "headline": "Gone"}]})
        edition.build(ctx, stories(20))
        index = jsonio.read_json(ctx.paths.editions_dir / "index.json")
        self.assertEqual([entry["date"] for entry in index["editions"]], ["2026-11-11"])

    def test_nothing_fresh_means_no_edition(self):
        ctx = self.context()
        self.assertIsNone(edition.build(ctx, stories(10, updated="2026-11-08T00:00:00Z")))
        self.assertIsNone(edition.build(ctx, []))
        self.assertFalse((ctx.paths.editions_dir / "2026-11-11.json").exists())


class EligibilityTests(EditionCase):

    def test_only_stories_from_the_last_24_hours_without_a_previous_edition(self):
        ctx = self.context()
        fresh = make_story("s-fresh", HEADLINES[0], score=40.0, updated="2026-11-10T02:00:00Z")
        stale = make_story("s-stale", HEADLINES[1], score=95.0, updated="2026-11-10T00:30:00Z")
        edition.build(ctx, [fresh, stale])
        self.assertEqual(printed_ids(self.read(ctx)), ["s-fresh"])

    def test_everything_since_the_previous_edition_is_eligible(self):
        ctx = self.context()
        jsonio.write_json(ctx.paths.editions_dir / "2026-11-08.json",
                          {"date": "2026-11-08", "number": 1, "generatedAt": "2026-11-08T01:00:00Z", "headline": "x"})
        since = make_story("s-since", HEADLINES[0], score=60.0, updated="2026-11-09T05:00:00Z")
        before = make_story("s-before", HEADLINES[1], score=95.0, updated="2026-11-08T00:59:00Z")
        edition.build(ctx, [since, before])
        self.assertEqual(printed_ids(self.read(ctx)), ["s-since"])

    def test_a_recent_previous_edition_does_not_shrink_the_24_hour_window(self):
        ctx = self.context()
        jsonio.write_json(ctx.paths.editions_dir / "2026-11-10.json",
                          {"date": "2026-11-10", "number": 1, "generatedAt": "2026-11-10T20:00:00Z", "headline": "x"})
        story = make_story("s-yesterday", HEADLINES[0], updated="2026-11-10T05:00:00Z")
        edition.build(ctx, [story])
        self.assertEqual(printed_ids(self.read(ctx)), ["s-yesterday"])

    def test_promos_live_blogs_and_bulletins_never_make_the_paper(self):
        ctx = self.context()
        junk = [make_story("s-promo", "Best Black Friday deals on laptops this week", score=99.0, sources=8),
                make_story("s-live", "Budget session: Live updates", score=98.0, sources=8),
                make_story("s-recurring", "Stocks to watch: Reliance, TCS, Infosys", score=97.0, sources=8),
                make_story("s-thin", "Red Flags", score=96.0, summary="")]
        edition.build(ctx, junk + stories(12))
        self.assertEqual(set(printed_ids(self.read(ctx))) & {"s-promo", "s-live", "s-recurring", "s-thin"}, set())

    def test_stories_considered_counts_the_eligible(self):
        ctx = self.context()
        edition.build(ctx, stories(30) + stories(5, updated="2026-11-01T00:00:00Z"))
        self.assertEqual(self.read(ctx)["stats"]["storiesConsidered"], 30)


class LeadTests(EditionCase):

    def lead(self, pool):
        ctx = self.context()
        edition.build(ctx, pool)
        return self.read(ctx)

    def test_lead_is_the_top_story_with_two_or_more_outlets(self):
        single = make_story("s-single", HEADLINES[30], score=95.0, sources=1)
        multi = make_story("s-multi", HEADLINES[31], score=80.0, sources=5)
        printed = self.lead([single, multi] + stories(10, top=50.0))
        self.assertEqual(printed["lead"]["id"], "s-multi")
        self.assertEqual(printed["headline"], HEADLINES[31])
        self.assertEqual(printed["front"][0]["id"], "s-single")

    def test_single_source_story_leads_when_nothing_has_two_outlets(self):
        pool = [make_story("s%d" % index, HEADLINES[index], score=60.0 - index, sources=1) for index in range(5)]
        self.assertEqual(self.lead(pool)["lead"]["id"], "s0")

    def test_routine_market_wrap_does_not_lead_when_there_is_other_news(self):
        wrap = make_story("s-wrap", "Sensex, Nifty close higher as banks rally", score=95.0, sources=11,
                          section="india-markets")
        news = make_story("s-news", HEADLINES[30], score=70.0, sources=4)
        printed = self.lead([wrap, news] + stories(10, top=50.0))
        self.assertEqual(printed["lead"]["id"], "s-news")
        self.assertIn("s-wrap", printed_ids(printed))

    def test_market_wrap_leads_when_it_is_the_only_multi_outlet_story(self):
        wrap = make_story("s-wrap", "Sensex, Nifty close higher as banks rally", score=60.0, sources=6)
        single = make_story("s-single", HEADLINES[0], score=90.0, sources=1)
        self.assertEqual(self.lead([wrap, single])["lead"]["id"], "s-wrap")

    def test_lead_is_embedded_in_full(self):
        pool = stories(10)
        printed = self.lead(pool)
        self.assertEqual(printed["lead"], json.loads(json.dumps(pool[0])))


class LayoutTests(EditionCase):

    def printed(self, pool, now=MORNING):
        ctx = self.context(now)
        edition.build(ctx, pool)
        return self.read(ctx)

    def test_front_is_the_next_four_by_score(self):
        printed = self.printed(stories(40))
        self.assertEqual([story["id"] for story in printed["front"]], ["s001", "s002", "s003", "s004"])

    def test_front_has_at_most_two_stories_from_one_section(self):
        pool = [make_story("s-w%d" % index, HEADLINES[index], score=90.0 - index, section="world")
                for index in range(8)]
        pool += [make_story("s-a%d" % index, HEADLINES[10 + index], score=50.0 - index, section="ai")
                 for index in range(4)]
        printed = self.printed(pool)
        self.assertEqual([story["id"] for story in printed["front"]], ["s-w1", "s-w2", "s-a0", "s-a1"])

    def test_market_wrap_stays_on_its_desk_when_there_is_other_news_for_the_front(self):
        wrap = make_story("s-wrap", "Sensex, Nifty close higher as banks rally", score=89.5, sources=11,
                          section="india-markets")
        printed = self.printed([wrap] + stories(40))
        self.assertEqual([story["id"] for story in printed["front"]], ["s001", "s002", "s003", "s004"])
        dalal = next(section for section in printed["sections"] if section["id"] == "india-markets")
        self.assertEqual(dalal["stories"][0]["id"], "s-wrap")

    def test_market_wrap_fills_the_front_when_news_runs_short(self):
        wrap = make_story("s-wrap", "Sensex, Nifty close higher as banks rally", score=89.5, sources=11,
                          section="india-markets")
        printed = self.printed([wrap] + stories(3))
        self.assertEqual([story["id"] for story in printed["front"]], ["s001", "s002", "s-wrap"])

    def test_front_section_cap_holds_when_wraps_fill_in(self):
        pool = [make_story("s-lead", HEADLINES[0], score=95.0, section="world"),
                make_story("s-m1", HEADLINES[1], score=90.0, section="markets"),
                make_story("s-m2", HEADLINES[2], score=89.0, section="markets"),
                make_story("s-wrap1", "Wall Street closes higher as tech rallies", score=88.0, section="markets"),
                make_story("s-wrap2", "Sensex, Nifty close higher as banks rally", score=87.0, section="india-markets")]
        printed = self.printed(pool)
        self.assertEqual([story["id"] for story in printed["front"]], ["s-m1", "s-m2", "s-wrap2"])

    def test_front_never_shares_a_thread_with_the_lead(self):
        thread = {"id": "t-saga", "day": 2, "history": []}
        pool = stories(12)
        pool[0]["thread"] = thread
        pool[1]["thread"] = dict(thread)
        printed = self.printed(pool)
        self.assertEqual(printed["lead"]["id"], "s000")
        self.assertNotIn("s001", printed_ids(printed))

    def test_no_two_stories_from_one_thread_anywhere(self):
        pool = stories(40)
        for index, story in enumerate(pool):
            story["thread"] = {"id": "t%d" % (index % 13), "day": 2, "history": []}
        printed = self.printed(pool)
        ids = printed_ids(printed)
        by_id = {story["id"]: story for story in pool}
        threads_seen = [by_id[story_id]["thread"]["id"] for story_id in ids]
        self.assertEqual(len(threads_seen), len(set(threads_seen)))
        self.assertEqual(len(ids), 13)

    def test_no_story_appears_twice(self):
        pool = stories(40)
        ids = printed_ids(self.printed(pool))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {story["id"] for story in pool})  # 1 + 4 + 30 in sections + 5 briefs

    def test_two_takes_on_one_event_are_not_both_printed(self):
        first = make_story("s-take1", "Nvidia hires law firm to investigate alleged Chinese spy affair", score=90.0,
                           section="companies", entities=["nvidia"], sources=6)
        second = make_story("s-take2", "Nvidia board opens investigation into alleged Chinese spy affair",
                            score=80.0, section="companies", entities=["nvidia"], sources=3)
        other = make_story("s-other", "Nvidia unveils Rubin Ultra chips at Taipei keynote", score=70.0,
                           section="companies", entities=["nvidia"], sources=3)
        ids = printed_ids(self.printed([first, second, other] + stories(20)))
        self.assertIn("s-take1", ids)
        self.assertNotIn("s-take2", ids)
        self.assertIn("s-other", ids)

    def test_sections_hold_their_best_remaining_stories_under_the_primary_desk(self):
        pool = stories(40)
        printed = self.printed(pool)
        by_id = {story["id"]: story for story in pool}
        used = {printed["lead"]["id"]} | {story["id"] for story in printed["front"]}
        for section in printed["sections"]:
            ids = [story["id"] for story in section["stories"]]
            self.assertTrue(1 <= len(ids) <= 3)
            self.assertTrue(all(by_id[story_id]["section"] == section["id"] for story_id in ids))
            expected = [story["id"] for story in pool
                        if story["section"] == section["id"] and story["id"] not in used][:3]
            self.assertEqual(ids, expected)

    def test_sections_come_in_canonical_order_with_names(self):
        printed = self.printed(stories(40))
        self.assertEqual([section["id"] for section in printed["sections"]], SECTIONS)
        self.assertEqual(printed["sections"][5]["name"], "Frontier Labs")
        self.assertEqual(printed["sections"][8]["name"], "Dalal Street")

    def test_section_with_nothing_fresh_is_left_out(self):
        pool = [story for story in stories(40) if story["section"] not in ("ml", "science")]
        pool.append(make_story("s-old-ml", HEADLINES[39], score=99.0, section="ml", updated="2026-11-05T00:00:00Z"))
        printed = self.printed(pool)
        self.assertEqual([section["id"] for section in printed["sections"]],
                         [section for section in SECTIONS if section not in ("ml", "science")])

    def test_a_story_filed_under_two_desks_appears_once_under_its_primary(self):
        pool = stories(12)
        pool[7]["sections"] = [pool[7]["section"], "world", "ai"]
        printed = self.printed(pool)
        placements = [section["id"] for section in printed["sections"]
                      if "s007" in [story["id"] for story in section["stories"]]]
        self.assertEqual(placements, [pool[7]["section"]])

    def test_briefs_are_the_best_of_the_rest_with_short_headlines(self):
        ctx = self.context()
        ctx.site["edition"] = dict(ctx.site["edition"], perSection=2, briefCount=6)
        pool = stories(40)
        pool[26]["title"] = "A very long headline that goes on and on " * 3
        edition.build(ctx, pool)
        printed = self.read(ctx)
        briefs = [story["id"] for story in printed["briefs"]]
        self.assertEqual(len(briefs), 6)
        self.assertTrue(all(len(story["title"]) <= edition.BRIEF_TITLE_CHARS for story in printed["briefs"]))
        placed = set(printed_ids(printed)) - set(briefs)
        rest = [story["id"] for story in pool if story["id"] not in placed]
        self.assertEqual(rest[:7], ["s025", "s026", "s027", "s028", "s029", "s030", "s031"])
        self.assertEqual(briefs, ["s025", "s027", "s028", "s029", "s030", "s031"])

    def test_briefs_have_at_most_two_stories_from_one_section(self):
        pool = [make_story("s-w%02d" % index, HEADLINES[index], score=90.0 - index, section="world")
                for index in range(12)]
        pool += [make_story("s-i%02d" % index, HEADLINES[20 + index], score=40.0 - index, section="india")
                 for index in range(6)]
        printed = self.printed(pool)
        sections = [story["section"] for story in printed["briefs"]]
        self.assertEqual(sections, ["world", "world", "india"])

    def test_few_stories_still_make_an_edition(self):
        printed = self.printed(stories(2))
        self.assertEqual(printed["lead"]["id"], "s000")
        self.assertEqual([story["id"] for story in printed["front"]], ["s001"])
        self.assertEqual(printed["sections"], [])
        self.assertEqual(printed["briefs"], [])

    def test_counts_follow_site_config(self):
        ctx = self.context()
        ctx.site["edition"] = {"hour": 6, "frontCount": 2, "briefCount": 1, "perSection": 1}
        edition.build(ctx, stories(40))
        printed = self.read(ctx)
        self.assertEqual(len(printed["front"]), 2)
        self.assertEqual(len(printed["briefs"]), 1)
        self.assertTrue(all(len(section["stories"]) == 1 for section in printed["sections"]))

    def test_edition_hour_follows_site_config(self):
        ctx = self.context("2026-11-11T03:00:00Z")  # 08:30 in Kolkata
        ctx.site["edition"] = dict(ctx.site["edition"], hour=9)
        self.assertIsNone(edition.build(ctx, stories(10)))

    def test_same_stories_give_the_same_edition(self):
        pool = stories(40)
        first = self.printed(pool)
        second = self.printed(list(reversed(pool)))
        self.assertEqual(first, second)


class FurnitureTests(EditionCase):

    def quote(self, symbol, as_of="2026-11-10T10:00:00Z"):
        return {"symbol": symbol, "name": symbol, "short": symbol, "kind": "index", "price": 1.0, "change": 0.1,
                "changePct": 0.5, "asOf": as_of}

    def test_markets_strip_follows_the_strip_order(self):
        ctx = self.context()
        jsonio.write_json(ctx.paths.public / "markets.json", {
            "generatedAt": "2026-11-11T00:00:00Z",
            "groups": [{"id": "india", "quotes": [self.quote("^NSEI"), self.quote("^BSESN", "2026-11-10T10:05:00Z")]},
                       {"id": "us", "quotes": [self.quote("^GSPC"), self.quote("^DJI")]}],
            "strip": ["^GSPC", "^NSEI", "MISSING", "^BSESN"]})
        edition.build(ctx, stories(10))
        strip = self.read(ctx)["markets"]
        self.assertEqual([quote["symbol"] for quote in strip["quotes"]], ["^GSPC", "^NSEI", "^BSESN"])
        self.assertEqual(strip["asOf"], "2026-11-10T10:05:00Z")

    def test_markets_strip_is_capped_at_eight(self):
        ctx = self.context()
        symbols = ["S%d" % index for index in range(12)]
        jsonio.write_json(ctx.paths.public / "markets.json", {
            "generatedAt": "2026-11-11T00:00:00Z", "strip": symbols,
            "groups": [{"id": "all", "quotes": [self.quote(symbol) for symbol in symbols]}]})
        edition.build(ctx, stories(10))
        self.assertEqual(len(self.read(ctx)["markets"]["quotes"]), 8)

    def test_no_markets_file_or_no_usable_quotes_is_null(self):
        ctx = self.context()
        edition.build(ctx, stories(10))
        self.assertIsNone(self.read(ctx)["markets"])
        for broken in ({"strip": ["^NSEI"], "groups": []}, {"groups": "nonsense"}, ["not", "an", "object"]):
            jsonio.write_json(ctx.paths.public / "markets.json", broken)
            self.assertIsNone(edition.markets_strip(ctx.paths.public))

    def update(self, update_id, day, kind="release", features=("projects",)):
        return {"id": update_id, "date": day, "surface": "code", "kind": kind, "title": "Update %s" % update_id,
                "summary": "What changed.", "url": "https://example.org/%s" % update_id, "source": "claude-code",
                "features": list(features)}

    def playbook(self, ctx, count=5):
        jsonio.write_json(ctx.paths.claude_dir / "playbook.json",
                          {"features": [{"id": "feature-%d" % index, "title": "F%d" % index}
                                        for index in range(count)]})

    def test_claude_card_is_the_newest_recent_feature_or_release(self):
        ctx = self.context()
        self.playbook(ctx)
        jsonio.write_json(ctx.paths.claude_dir / "updates.json", {"entries": [
            self.update("u-article", "2026-11-11", kind="article"),
            self.update("u-newest", "2026-11-10", features=["memory", "projects"]),
            self.update("u-same-day-later-in-file", "2026-11-10"),
            self.update("u-old", "2026-11-08"),
        ]})
        edition.build(ctx, stories(10))
        card = self.read(ctx)["claude"]
        self.assertEqual(card["kind"], "update")
        self.assertEqual(card["update"]["id"], "u-newest")
        self.assertEqual(card["featureId"], "memory")

    def test_claude_update_older_than_36_hours_gives_way_to_the_feature_of_the_day(self):
        ctx = self.context()
        self.playbook(ctx)
        jsonio.write_json(ctx.paths.claude_dir / "updates.json", {"entries": [
            self.update("u-old", "2026-11-09"), self.update("u-video", "2026-11-11", kind="video")]})
        edition.build(ctx, stories(10))
        card = self.read(ctx)["claude"]
        self.assertEqual((card["kind"], card["update"]), ("feature", None))
        self.assertIn(card["featureId"], {"feature-%d" % index for index in range(5)})

    def test_claude_update_without_playbook_features_has_no_feature_id(self):
        ctx = self.context()
        jsonio.write_json(ctx.paths.claude_dir / "updates.json",
                          {"entries": [self.update("u-new", "2026-11-11", features=())]})
        edition.build(ctx, stories(10))
        self.assertEqual(self.read(ctx)["claude"]["featureId"], None)

    def test_feature_of_the_day_is_deterministic_and_rotates_through_every_feature(self):
        ctx = self.context()
        self.playbook(ctx, count=7)
        start = date(2026, 11, 11)
        week = [edition.feature_of_the_day(ctx.paths.claude_dir, (start + timedelta(days=offset)).isoformat())
                for offset in range(7)]
        self.assertEqual(sorted(week), ["feature-%d" % index for index in range(7)])
        self.assertEqual(edition.feature_of_the_day(ctx.paths.claude_dir, "2026-11-18"), week[0])
        self.assertEqual(edition.feature_of_the_day(ctx.paths.claude_dir, "2026-11-11"), week[0])
        self.assertNotEqual(week, sorted(week))  # not simply the playbook's own order

    def test_no_claude_data_at_all_is_null(self):
        ctx = self.context()
        edition.build(ctx, stories(10))
        self.assertIsNone(self.read(ctx)["claude"])
        jsonio.write_json(ctx.paths.claude_dir / "playbook.json", {"features": []})
        self.assertIsNone(edition.claude_card(ctx.paths.claude_dir, ctx.now, ctx.tz))

    def weekend_edition(self, now, write_issue=True):
        ctx = self.context(now)
        if write_issue:
            jsonio.write_json(ctx.paths.weekend_dir / "2026-W46.json",
                              {"isoWeek": "2026-W46", "papers": [{"title": "A paper worth a weekend"}]})
        edition.build(ctx, stories(10, updated=now))
        return jsonio.read_json(next(path for path in ctx.paths.editions_dir.glob("2026-*.json")))

    def test_weekend_pointer_on_saturday_and_sunday(self):
        for now in ("2026-11-14T01:00:00Z", "2026-11-15T01:00:00Z"):
            with self.subTest(now):
                self.assertEqual(self.weekend_edition(now)["weekend"],
                                 {"isoWeek": "2026-W46", "title": "A paper worth a weekend"})

    def test_no_weekend_pointer_on_a_weekday_or_without_the_issue(self):
        self.assertIsNone(self.weekend_edition("2026-11-13T01:00:00Z")["weekend"])
        self.assertIsNone(self.weekend_edition("2026-11-14T01:00:00Z", write_issue=False)["weekend"])
        self.assertIsNone(self.weekend_edition("2026-11-21T01:00:00Z")["weekend"])  # the issue is last week's

    def test_stats_report_source_health_and_reading_time(self):
        ctx = self.context()
        jsonio.write_json(ctx.paths.state / "source-health.json",
                          {"a": {"ok": True}, "b": {"ok": True}, "c": {"ok": False, "error": "timeout"}})
        pool = stories(3)
        for story in pool:
            story["title"] = "word " * 10
            story["summary"] = "word " * 220
        edition.build(ctx, pool)
        stats = self.read(ctx)["stats"]
        self.assertEqual((stats["sourcesOk"], stats["sourcesTotal"]), (2, 3))
        self.assertEqual(stats["readMinutes"], 3)  # 690 words at 230 a minute
        self.assertEqual(stats["storiesConsidered"], 3)

    def test_stats_without_health_file(self):
        ctx = self.context()
        edition.build(ctx, stories(2))
        stats = self.read(ctx)["stats"]
        self.assertEqual((stats["sourcesOk"], stats["sourcesTotal"], stats["readMinutes"]), (0, 0, 1))

    def test_edition_has_exactly_the_contract_keys(self):
        ctx = self.context()
        edition.build(ctx, stories(40))
        self.assertEqual(set(self.read(ctx)), {"date", "number", "generatedAt", "headline", "lead", "front", "briefs",
                                               "sections", "markets", "claude", "weekend", "stats"})


if __name__ == "__main__":
    unittest.main()
