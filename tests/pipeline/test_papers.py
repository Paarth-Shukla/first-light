"""pipeline.papers: provider parsers, signals, scoring, selection, the review block and the stage.

Network responses are real ones saved under tests/fixtures/papers/; nothing here touches the network.
"""

import copy
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from pipeline import papers
from pipeline.core import config, jsonio, log, net, timeutil

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "papers"
IST = ZoneInfo("Asia/Kolkata")
CFG = config.load("papers")


def fixture(name):
    return (FIXTURES / name).read_bytes()


def venue_patterns():
    return [(venue, papers._venue_pattern(venue)) for venue in sorted(CFG["venues"], key=len, reverse=True)]


class ArxivParseTest(unittest.TestCase):
    def setUp(self):
        self.feed = papers.parse_arxiv(fixture("arxiv-category.xml"))
        self.by_id = {entry["id"]: entry for entry in self.feed["entries"]}

    def test_feed_totals_and_ids(self):
        self.assertEqual(self.feed["total"], 66)
        self.assertEqual(len(self.feed["entries"]), 6)
        for pid in self.by_id:
            self.assertRegex(pid, r"^\d{4}\.\d{5}$", "version suffix stripped")

    def test_entry_fields(self):
        entry = self.by_id["2611.13931"]
        self.assertTrue(entry["title"].startswith("TAPCO-G: LLM-Guided Design-Adaptive Timing"))
        self.assertEqual(entry["primary"], "cs.AR")
        self.assertEqual(entry["categories"], ["cs.AR", "cs.AI"])
        self.assertEqual(entry["published"], "2026-11-10T11:19:50Z")
        self.assertEqual(entry["comment"], "27 pages")
        self.assertEqual(entry["authors"][0], "Wuqian Tang")
        self.assertLessEqual(len(entry["authors"]), 4)
        self.assertEqual(entry["version"], 1)
        self.assertNotIn("\n", entry["abstract"])

    def test_latex_is_cleaned_and_journal_ref_read(self):
        self.assertIn("TB∧Synth", self.by_id["2611.07324"]["abstract"])
        self.assertIn("μs", self.by_id["2611.08380"]["abstract"])
        self.assertTrue(self.by_id["2611.10913"]["journalRef"])

    def test_missing_ids_are_absent_not_errors(self):
        feed = papers.parse_arxiv(fixture("arxiv-missing-id.xml"))
        self.assertEqual([entry["id"] for entry in feed["entries"]], ["2611.07149"])

    def test_not_atom_is_a_provider_error(self):
        with self.assertRaises(papers.ProviderError):
            papers.parse_arxiv(b"<rss><channel/></rss>")

    def test_query_urls(self):
        start = datetime(2026, 11, 3, 18, 30, tzinfo=timezone.utc)
        url = papers.arxiv_category_url("https://export.arxiv.org/api/query", "cs.AR", start,
                                        start + timedelta(days=7), 2000)
        self.assertIn("search_query=cat%3Acs.AR+AND+submittedDate%3A%5B202611031830+TO+202611101829%5D", url)
        self.assertIn("max_results=2000", url)
        ids_url = papers.arxiv_ids_url("https://export.arxiv.org/api/query", ["2611.00001", "2611.00002"])
        self.assertIn("id_list=2611.00001%2C2611.00002&max_results=2", ids_url)


class SignalParseTest(unittest.TestCase):
    def test_hugging_face(self):
        data = papers.parse_hf(fixture("hf-daily.json"))
        self.assertEqual(data["rows"], 4)
        tactile = data["papers"]["2611.12806"]
        self.assertEqual(tactile["hfUpvotes"], 97)
        self.assertEqual(tactile["githubStars"], 170)
        self.assertEqual(tactile["codeUrl"], "https://github.com/Robbyant/lingbot-touch")
        no_repo = [signals for signals in data["papers"].values() if signals["codeUrl"] is None]
        self.assertEqual(len(no_repo), 1)
        self.assertEqual(no_repo[0]["githubStars"], 0)

    def test_hugging_face_rejects_non_list(self):
        with self.assertRaises(papers.ProviderError):
            papers.parse_hf(b'{"error": "rate limited"}')

    def test_alphaxiv_skips_slug_ids(self):
        data = papers.parse_alphaxiv(fixture("alphaxiv-feed.json"))
        self.assertEqual(set(data), {"2611.09825", "2611.08399", "2611.07559"})
        self.assertEqual(data["2611.09825"], {"alphaxivVotes": 7, "alphaxivViews": 51, "githubStars": 0,
                                              "codeUrl": None})

    def test_hacker_news_sums_stories_and_keeps_best_link(self):
        data = papers.parse_hn(fixture("hn-search.json"))
        ncm = data["2610.14162"]
        self.assertEqual(ncm["hnPoints"], 185)
        self.assertEqual(ncm["hnComments"], 47)
        self.assertEqual(ncm["hnUrl"], "https://news.ycombinator.com/item?id=50422168")
        self.assertEqual(data["2611.02618"]["hnPoints"], 49)

    def test_hacker_news_link_forms(self):
        hits = json.loads(fixture("hn-search.json"))["hits"][:1]
        pdf, other = copy.deepcopy(hits[0]), copy.deepcopy(hits[0])
        pdf["url"], pdf["objectID"] = "https://arxiv.org/pdf/2611.10866v2", "1"
        other["url"], other["points"] = "https://example.com/2611.10866", 500
        data = papers.parse_hn(json.dumps({"hits": hits + [pdf, other]}).encode())
        self.assertEqual(data["2611.10866"]["hnPoints"], 2 * hits[0]["points"])

    def test_openalex(self):
        self.assertEqual(papers.parse_openalex(fixture("openalex-works.json")), {"2611.00859": 0, "2611.07496": 0})


class VenueSignalTest(unittest.TestCase):
    CASES = [
        ("ASP-DAC'27 Invited Paper", (1.0, "ASP-DAC 2027 paper")),
        ("Accepted at IEEE HPCA 2027", (1.0, "accepted at HPCA 2027")),
        ("Accepted to NeurIPS 2026 (Poster)", (1.0, "accepted at NeurIPS 2026")),
        ("Accepted at NeurIPS 2026 E&D Track", (1.0, "accepted at NeurIPS 2026")),
        ("Accepted to the ACM International Conference on Parallel Architectures and Compilation "
         "Techniques (PACT), 2026", (1.0, "accepted at PACT")),
        ("Accepted at the ICML 2026 Workshop on Efficient Systems", (0.5, "accepted at ICML 2026 workshop")),
        ("Published in the H2RC workshop at the International Conference on High Performance Computing, "
         "Networking, Storage and Analysis 2026", (0.5, "accepted at a workshop")),
        ("10 pages, 4 figures, 2 tables, conference paper that have been accepted after peer-review",
         (0.5, "accepted for publication")),
        ("An anonymous version of this manuscript was submitted to HPCA 2027 on August 1, 2026.", (0.0, None)),
        ("Submitted to IEEE ISCAS 2027 (under review). 5 pages", (0.0, None)),
        ("Author manuscript of Proceedings of the 46th International Symposium on Computer Architecture "
         "(ISCA '19), pp. 27-38 (2019).", (0.0, None)),
        ("14 pages, 7 figures", (0.0, None)),
        ("Accepted at DAC 2026; extended version submitted to TCAD", (1.0, "accepted at DAC 2026")),
        ("Fixed a typo in DATE", (0.0, None)),
        ("", (0.0, None)),
    ]

    def test_comments(self):
        patterns = venue_patterns()
        for comment, expected in self.CASES:
            with self.subTest(comment=comment):
                self.assertEqual(papers.venue_signal(comment, "", patterns, current_year=2026), expected)

    def test_journal_references(self):
        patterns = venue_patterns()
        self.assertEqual(papers.venue_signal("", "CIGRE Paris Session 2026", patterns, current_year=2026),
                         (1.0, "published in CIGRE Paris Session"))
        self.assertEqual(papers.venue_signal("", "Isaac Ariza, Lorenzo J. Tardon (2026) Applied Sciences", patterns,
                                             authors=["Isaac Ariza", "Lorenzo J. Tardon"], current_year=2026),
                         (1.0, "published, with a journal reference"))
        self.assertEqual(papers.venue_signal("", "Proc. of the 3rd Workshop on X, 2026", patterns, current_year=2026)[0], 0.5)
        self.assertEqual(papers.venue_signal("", "ISCA '19, pp. 27-38 (2019)", patterns, current_year=2026), (0.0, None))
        self.assertEqual(papers.venue_signal("", "IEEE TPAMI 2026", patterns, current_year=2026),
                         (1.0, "published in TPAMI"))


class ContentSignalTest(unittest.TestCase):
    def test_code_links(self):
        self.assertEqual(papers.code_signal("", "14 pages. Code: https://github.com/rudykon/FPTR_Scheduler", None),
                         ("https://github.com/rudykon/FPTR_Scheduler", "code"))
        self.assertEqual(papers.code_signal("", "Measurement data: https://doi.org/10.5281/zenodo.23982873", None),
                         ("https://doi.org/10.5281/zenodo.23982873", "artifacts"))
        self.assertEqual(papers.code_signal("Code is at github.com/foo/bar.", "", None),
                         ("https://github.com/foo/bar", "code"))
        self.assertEqual(papers.code_signal("Code will be released at https://github.com/x/y.", "", None), (None, None))
        self.assertEqual(papers.code_signal("", "", "https://github.com/a/b"), ("https://github.com/a/b", "code"))
        self.assertEqual(papers.code_signal("No code here.", "12 pages", None), (None, None))

    def test_measured_numbers(self):
        self.assertEqual(papers.measured_count("It reaches 4.2 TOPS/W at 0.6 V, 31% less area and a 2.1x speedup."), 4)
        self.assertEqual(papers.measured_count("We study 3 designs over 2 years."), 0)


class TrackTest(unittest.TestCase):
    def paper(self, primary, title, abstract="We build it."):
        return {"primary": primary, "title": title, "abstract": abstract}

    def test_classification(self):
        tracks = CFG["tracks"]
        cases = [
            (self.paper("cs.AR", "CAMP: Mapping LLMs on 3D-IMC Arrays"), "electronics"),
            (self.paper("physics.app-ph", "A GaN power stage"), "electronics"),
            (self.paper("eess.AS", "SubRoformer: Subband Representation for Music Source Separation"), "cs"),
            (self.paper("eess.SY", "An Interline Multiport DC Circuit Breaker", "A power transformer feeds it."),
             "electronics"),
            (self.paper("eess.SP", "Channel estimation", "A neural network is trained on a large dataset."), "cs"),
            (self.paper("cs.DC", "ZYFA: Speed and Accuracy of FP8 FlashAttention on AMD CDNA4"), "electronics"),
            (self.paper("cs.DC", "Consensus for geo-replicated databases"), "cs"),
            (self.paper("cs.CL", "A language model"), "cs"),
            (self.paper("stat.ML", "Kernel methods"), "cs"),
            (self.paper("quant-ph", "Qubit routing"), None),
        ]
        for paper, expected in cases:
            with self.subTest(title=paper["title"]):
                self.assertEqual(papers.classify_track(paper, tracks), expected)


class MentionsTest(unittest.TestCase):
    def test_title_and_id_mentions_skip_arxiv_link_posts(self):
        items = json.loads(fixture("items.json"))["items"]
        records = {
            "2611.10866": {"title": "The Surprising Effectiveness of Deleting Weights in LLM Post-Training"},
            "2611.07149": {"title": "FastAFD: When Does Attention-FFN Disaggregation Pay on Rack-Scale NVLink?"},
            "2611.00001": {"title": "Short Title"},
        }
        extra = [
            {"id": "x1", "source": "eetimes", "url": "https://eetimes.com/a", "title": "Rack-scale serving",
             "summary": "The paper (arXiv:2611.07149) measures GB200 NVL72."},
            {"id": "x2", "source": "hn-front", "url": "https://arxiv.org/abs/2611.07149",
             "title": "FastAFD: When Does Attention-FFN Disaggregation Pay on Rack-Scale NVLink?"},
            {"id": "x3", "source": "eetimes", "url": "https://eetimes.com/b", "title": "Short Title"},
        ]
        mentions = papers.count_mentions(records, items + extra)
        self.assertEqual(mentions, {"2611.10866": 1, "2611.07149": 1})

    def test_load_items_reads_window_days(self):
        with tempfile.TemporaryDirectory() as folder:
            items_dir = Path(folder)
            jsonio.write_json(items_dir / "2026-11-10.json", {"date": "2026-11-10", "items": {"a": {"id": "a"}}})
            jsonio.write_json(items_dir / "2026-11-01.json", {"date": "2026-11-01", "items": {"b": {"id": "b"}}})
            (items_dir / "2026-11-09.json").write_text("{broken")
            with mock.patch.object(log, "warn"):
                loaded = papers.load_items(items_dir, date(2026, 11, 4), date(2026, 11, 11))
        self.assertEqual([item["id"] for item in loaded], ["a"])


def draft(pid, track="cs", primary="cs.LG", published="2026-11-08T00:00:00Z", **signals):
    """A scored-paper draft with every signal zero unless given."""
    base = {name: 0 for name in papers.SIGNAL_PROVIDERS}
    base.update(signals)
    return {"id": pid, "track": track, "primary": primary, "published": published, "signals": base,
            "labels": {"venue": None, "code": None}, "title": pid, "score": 0.0, "parts": {}}


class ScoringTest(unittest.TestCase):
    WEIGHTS = {"hfUpvotes": 0.6, "alphaxivVotes": 0.5, "hnPoints": 0.5, "venue": 0.15}
    FLOORS = {"hfUpvotes": 10, "alphaxivVotes": 5, "hnPoints": 100}

    def test_normalise(self):
        self.assertEqual(papers.normalise("hfUpvotes", 0, 100, self.FLOORS, {}), 0.0)
        self.assertEqual(papers.normalise("hfUpvotes", 100, 100, self.FLOORS, {}), 1.0)
        self.assertAlmostEqual(papers.normalise("hnPoints", 27, 27, self.FLOORS, {}), 0.7220, places=3)
        self.assertEqual(papers.normalise("githubStars", 41399, 41399, {}, {"githubStars": 2000}), 1.0)
        self.assertEqual(papers.normalise("measured", 6, 0, {}, {}), 1.0)
        self.assertAlmostEqual(papers.normalise("crossLists", 1, 0, {}, {}), 1 / 3)

    def test_single_strong_signal_and_agreement(self):
        both = draft("both", hfUpvotes=50, alphaxivVotes=50)
        hf_only = draft("hf", hfUpvotes=100)
        nothing = draft("none")
        group = [both, hf_only, nothing]
        papers.score_track(group, self.WEIGHTS, self.FLOORS, {}, papers.present_signals({"hf", "alphaxiv", "hn"}))
        self.assertGreater(both["score"], hf_only["score"])
        self.assertGreater(hf_only["score"], 50, "one community's top paper still scores well")
        self.assertEqual(nothing["score"], 0.0)
        self.assertEqual(set(both["parts"]), {"hfUpvotes", "alphaxivVotes"})

    def test_missing_provider_renormalises(self):
        def score(available):
            paper = draft("a", hfUpvotes=40, alphaxivVotes=50)
            top = draft("top", hfUpvotes=100, alphaxivVotes=50, hnPoints=100, venue=1.0)
            papers.score_track([paper, top], self.WEIGHTS, self.FLOORS, {}, papers.present_signals(available))
            return paper["score"], top["score"]
        with_hn, top_with_hn = score({"hf", "alphaxiv", "hn"})
        without_hn, top_without_hn = score({"hf", "alphaxiv"})
        self.assertGreater(without_hn, with_hn, "HN down must not drag a paper HN never saw")
        self.assertEqual(top_with_hn, 100.0)
        self.assertEqual(top_without_hn, 100.0)
        only_content, _ = score(set())
        self.assertEqual(only_content, 0.0)

    def test_signals_follow_their_providers(self):
        self.assertIn("githubStars", papers.present_signals({"alphaxiv"}))
        self.assertNotIn("hfUpvotes", papers.present_signals({"alphaxiv"}))
        self.assertTrue({"venue", "code", "crossLists", "measured"} <= papers.present_signals(set()))

    def test_config_weights_are_checked(self):
        bad = copy.deepcopy(CFG)
        bad["weights"]["cs"]["hfUpvotes"] = 1.5
        with self.assertRaises(config.ConfigError):
            papers.check_config(bad)
        bad = copy.deepcopy(CFG)
        bad["weights"]["cs"]["stars"] = 0.1
        with self.assertRaises(config.ConfigError):
            papers.check_config(bad)
        papers.check_config(CFG)


class SelectTest(unittest.TestCase):
    def pool(self):
        pool = []
        for index, primary in enumerate(["cs.CL", "cs.CL", "cs.CL", "cs.CV", "cs.LG", "cs.RO"]):
            paper = draft("c%d" % index, primary=primary)
            paper["score"] = 90.0 - index
            pool.append(paper)
        for index, primary in enumerate(["cs.DC", "cs.DC", "cs.AR"]):
            paper = draft("e%d" % index, track="electronics", primary=primary)
            paper["score"] = 60.0 - index
            pool.append(paper)
        return pool

    def test_quota_diversity_and_ranking(self):
        top, rest = papers.select(self.pool(), 5, {"electronics": 2}, 2, 10)
        ids = [paper["id"] for paper in top]
        self.assertEqual(ids, ["c0", "c1", "c3", "e0", "e2"])
        self.assertEqual(sum(1 for paper in top if paper["track"] == "electronics"), 2)
        self.assertEqual(len(rest), 4)
        self.assertIn("c2", [paper["id"] for paper in rest], "third cs.CL paper waits for the runners-up")

    def test_quota_falls_back_to_same_category(self):
        pool = [paper for paper in self.pool() if paper["id"] != "e2"]
        top, _ = papers.select(pool, 5, {"electronics": 2}, 2, 10)
        self.assertEqual([paper["id"] for paper in top if paper["track"] == "electronics"], ["e0", "e1"])

    def test_exclusions_zero_scores_and_short_pools(self):
        pool = self.pool()
        pool[0]["score"] = 0.0
        top, rest = papers.select(pool, 5, {"electronics": 2}, 2, 10, exclude={"c1"})
        ids = [paper["id"] for paper in top + rest]
        self.assertNotIn("c0", ids)
        self.assertNotIn("c1", ids)
        top, rest = papers.select(pool[:2], 5, {"electronics": 2}, 2, 10)
        self.assertEqual([paper["id"] for paper in top], ["c1"])
        self.assertEqual(rest, [])

    def test_ties_go_to_social_attention_then_newer(self):
        older = draft("older", hfUpvotes=5, published="2026-11-04T00:00:00Z")
        newer = draft("newer", hfUpvotes=5, published="2026-11-09T00:00:00Z")
        louder = draft("louder", hfUpvotes=9, published="2026-11-01T00:00:00Z")
        for paper in (older, newer, louder):
            paper["score"] = 50.0
        self.assertEqual([p["id"] for p in sorted([older, newer, louder], key=papers.rank_key)],
                         ["louder", "newer", "older"])


class WhyChipsTest(unittest.TestCase):
    def test_chips_state_real_values_strongest_first(self):
        paper = draft("p", hfUpvotes=1312, hnPoints=1, venue=1.0, code=1, crossLists=1, measured=5, mentions=2)
        paper["labels"] = {"venue": "accepted at ISSCC 2027", "code": "code"}
        paper["parts"] = {"venue": 0.45, "hfUpvotes": 0.6, "hnPoints": 0.1, "code": 0.25, "crossLists": 0.03,
                          "measured": 0.2, "mentions": 0.3}
        self.assertEqual(papers.why_chips(paper), ["1,312 upvotes on Hugging Face", "accepted at ISSCC 2027",
                                                   "mentioned in 2 of our feeds", "code available"])
        self.assertEqual(papers.why_chips(paper, limit=10)[-2:], ["reports measured results", "1 point on Hacker News"])

    def test_no_chip_without_a_value(self):
        paper = draft("p")
        paper["parts"] = {"hfUpvotes": 0.5}
        self.assertEqual(papers.why_chips(paper), [])


class WindowAndDueTest(unittest.TestCase):
    def test_window_ends_yesterday_and_names_the_week_of_its_end(self):
        wednesday = datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc)
        window = papers.Window(wednesday, IST, 7)
        self.assertEqual((window.first, window.last), (date(2026, 11, 4), date(2026, 11, 10)))
        self.assertEqual(window.iso_week, "2026-W46")
        self.assertEqual(window.start, datetime(2026, 11, 3, 18, 30, tzinfo=timezone.utc))
        self.assertEqual(window.end, datetime(2026, 11, 10, 18, 30, tzinfo=timezone.utc))
        saturday = papers.Window(datetime(2026, 11, 14, 1, 0, tzinfo=timezone.utc), IST, 7)
        self.assertEqual((saturday.first, saturday.last, saturday.iso_week),
                         (date(2026, 11, 7), date(2026, 11, 13), "2026-W46"))
        monday = papers.Window(datetime(2026, 11, 16, 3, 0, tzinfo=timezone.utc), IST, 7)
        self.assertEqual(monday.iso_week, "2026-W46", "a Monday run reviews the week that just ended")

    def test_due_on_local_weekday_until_the_file_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            issue = Path(folder) / "2026-W46.json"
            friday_utc_saturday_ist = datetime(2026, 11, 13, 19, 0, tzinfo=timezone.utc)
            self.assertTrue(papers.is_due(friday_utc_saturday_ist, IST, 5, issue, False))
            self.assertFalse(papers.is_due(datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc), IST, 5, issue, False))
            self.assertTrue(papers.is_due(datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc), IST, 5, issue, True))
            issue.write_text("{}")
            self.assertFalse(papers.is_due(friday_utc_saturday_ist, IST, 5, issue, False))
            self.assertTrue(papers.is_due(friday_utc_saturday_ist, IST, 5, issue, True))


class ReviewTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.paths = config.paths(folder.name).ensure()

    def story(self, sid, score, thread=None):
        return {"id": sid, "title": sid, "score": score, "thread": {"id": thread} if thread else None}

    def test_everything_missing_gives_an_empty_review(self):
        self.assertEqual(papers.build_review(self.paths, date(2026, 11, 4), date(2026, 11, 10)), {})

    def test_stories_markets_and_claude(self):
        jsonio.write_json(self.paths.stories_dir / "2026-11-05.json", {"date": "2026-11-05", "stories": [
            self.story("s1", 60, "t1"), self.story("s2", 40), self.story("bad", "n/a")]})
        jsonio.write_json(self.paths.stories_dir / "2026-11-06.json", {"date": "2026-11-06", "stories": [
            self.story("s3", 80, "t1")] + [self.story("x%d" % n, 10 + n) for n in range(8)]})
        jsonio.write_json(self.paths.stories_dir / "2026-11-20.json", {"date": "2026-11-20", "stories": [
            self.story("late", 99)]})
        jsonio.write_json(self.paths.public / "markets.json", {"strip": ["^NSEI", "BTC-USD", "MISSING"], "groups": [
            {"id": "india", "quotes": [{"symbol": "^NSEI", "name": "Nifty 50",
                                        "spark": [100, 101, 102, 103, 104, 105, 110.0]}]},
            {"id": "crypto", "quotes": [{"symbol": "BTC-USD", "name": "Bitcoin", "spark": [50, 45]}]}]})
        jsonio.write_json(self.paths.claude_dir / "updates.json", {"entries": [
            {"id": "u1", "date": "2026-11-10", "title": "a"}, {"id": "u2", "date": "2026-11-03", "title": "b"},
            {"id": "u3", "date": "2026-11-04", "title": "c"}]})
        review = papers.build_review(self.paths, date(2026, 11, 4), date(2026, 11, 10))
        stories = review["stories"]
        self.assertEqual(len(stories), 7)
        self.assertEqual(stories[0]["id"], "s3", "a thread appears once, at its peak")
        self.assertNotIn("s1", [story["id"] for story in stories])
        self.assertNotIn("late", [story["id"] for story in stories])
        self.assertEqual(review["markets"], [{"symbol": "^NSEI", "name": "Nifty 50", "weekPct": 8.91},
                                             {"symbol": "BTC-USD", "name": "Bitcoin", "weekPct": -10.0}])
        self.assertEqual([entry["id"] for entry in review["claude"]], ["u1", "u3"])


class DayCacheTest(unittest.TestCase):
    def test_round_trip_and_prune(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "2026-11-10").mkdir()
            (root / "2026-11-10" / "old.json").write_text("{}")
            cache = papers.DayCache(root, "2026-11-11")
            self.assertFalse((root / "2026-11-10").exists())
            self.assertEqual(cache.get("https://a"), (False, None))
            cache.put("https://a", [])
            self.assertEqual(cache.get("https://a"), (True, []))
            self.assertEqual(papers.DayCache(root, "2026-11-11").get("https://a"), (True, []))


class FakeNetwork:
    """Serves the saved fixtures by URL, counting requests; ``down`` names hosts that fail."""

    def __init__(self, down=()):
        self.calls = []
        self.down = set(down)

    def fetch(self, url, **kwargs):
        self.calls.append(url)
        host = url.split("/")[2]
        if host in self.down:
            raise net.NetError("connection", None, "connection failed: test", url)
        if host == "export.arxiv.org":
            body = fixture("arxiv-idlist.xml" if "id_list=" in url else "arxiv-category.xml")
        elif host == "huggingface.co":
            body = fixture("hf-daily.json") if "date=2026-11-10" in url and "p=0" in url else b"[]"
        elif host == "api.alphaxiv.org":
            body = fixture("alphaxiv-feed.json")
        elif host == "hn.algolia.com":
            body = fixture("hn-search.json")
        elif host == "api.openalex.org":
            body = fixture("openalex-works.json")
        else:
            raise AssertionError("unexpected host %s" % host)
        return net.Response(status=200, body=body, headers={}, url=url)


class RunTest(unittest.TestCase):
    """The whole stage against fixtures, with the clock frozen by --now."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name)
        self.addCleanup(timeutil.set_now, None)
        for patcher in (mock.patch.object(net, "polite"), mock.patch.object(log, "info"),
                        mock.patch.object(log, "warn")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_stage(self, now, force=False, network=None):
        timeutil.set_now(now)
        network = network or FakeNetwork()
        ctx = config.context(data_dir=self.data, force=force)
        ctx.paths.ensure()
        with mock.patch.object(net, "fetch", network.fetch):
            return papers.run(ctx), network

    def issue(self, week="2026-W46"):
        return jsonio.read_json(self.data / "public" / "weekend" / ("%s.json" % week))

    def test_not_due_midweek_without_force(self):
        counts, network = self.run_stage("2026-11-11T08:00:00Z")
        self.assertEqual(counts, {"skipped": True})
        self.assertEqual(network.calls, [])

    def test_saturday_builds_then_skips(self):
        counts, network = self.run_stage("2026-11-14T03:00:00Z")
        self.assertEqual(counts["isoWeek"], "2026-W46")
        self.assertGreater(len(network.calls), 0)
        issue = self.issue()
        self.assertEqual((issue["from"], issue["to"]), ("2026-11-07", "2026-11-13"))
        counts, network = self.run_stage("2026-11-14T09:00:00Z")
        self.assertEqual(counts, {"skipped": True})

    def test_forced_build_matches_the_contract(self):
        counts, _ = self.run_stage("2026-11-11T08:00:00Z", force=True)
        issue = self.issue()
        self.assertEqual(set(issue), {"isoWeek", "from", "to", "generatedAt", "title", "method", "papers",
                                      "runnersUp", "review"})
        self.assertEqual(len(issue["papers"]), 5)
        self.assertGreaterEqual(sum(1 for paper in issue["papers"] if paper["track"] == "electronics"), 2)
        self.assertEqual([paper["rank"] for paper in issue["papers"]], [1, 2, 3, 4, 5])
        paper_keys = {"id", "title", "authors", "primary", "categories", "track", "published", "abstract",
                      "digest", "signals", "score", "why", "links", "rank"}
        for paper in issue["papers"] + issue["runnersUp"]:
            self.assertEqual(set(paper), paper_keys)
            self.assertEqual(set(paper["links"]), {"abs", "pdf", "code", "hf", "hn"})
            self.assertTrue({"hfUpvotes", "hnPoints", "citations", "githubStars", "mentions"} <= set(paper["signals"]))
            self.assertTrue(0 < paper["score"] <= 100)
            for text in paper["digest"].values():
                if text:
                    self.assertIn(text, paper["abstract"])
        self.assertEqual(issue["review"], {})
        self.assertIn("not a judgement of which are best", issue["method"])
        self.assertIn("coverage in our own news feeds", issue["method"], "no item store: named as unavailable")
        index = jsonio.read_json(self.data / "public" / "weekend" / "index.json")
        self.assertEqual(index, {"weeks": [{"isoWeek": "2026-W46", "from": "2026-11-04", "to": "2026-11-10",
                                            "title": issue["title"]}]})
        self.assertEqual(counts["signalsMissing"], ["items"])

    def test_same_day_rerun_uses_the_cache(self):
        self.run_stage("2026-11-11T08:00:00Z", force=True)
        _, network = self.run_stage("2026-11-11T09:00:00Z", force=True)
        self.assertEqual(network.calls, [])

    def test_provider_down_is_reported_and_tolerated(self):
        network = FakeNetwork(down={"api.alphaxiv.org", "hn.algolia.com"})
        counts, _ = self.run_stage("2026-11-11T08:00:00Z", force=True, network=network)
        self.assertEqual(counts["signalsMissing"], ["alphaxiv", "hn", "items"])
        self.assertIn("alphaxiv", counts["providerErrors"])
        self.assertIn("Unavailable this week: alphaXiv views and votes, Hacker News points", self.issue()["method"])

    def test_arxiv_down_fails_without_writing(self):
        with self.assertRaises(RuntimeError):
            self.run_stage("2026-11-11T08:00:00Z", force=True, network=FakeNetwork(down={"export.arxiv.org"}))
        self.assertIsNone(self.issue())

    def test_featured_papers_are_not_repeated_and_index_keeps_order(self):
        self.run_stage("2026-11-11T08:00:00Z", force=True)
        first = [paper["id"] for paper in self.issue()["papers"]]
        weekend = self.data / "public" / "weekend"
        jsonio.write_json(weekend / "2026-W45.json", {"papers": [{"id": first[0]}]})
        papers.update_index(weekend, {"isoWeek": "2026-W45", "from": "2026-10-28", "to": "2026-11-03", "title": "t"})
        self.run_stage("2026-11-12T08:00:00Z", force=True)
        again = [paper["id"] for paper in self.issue()["papers"]]
        self.assertNotIn(first[0], again)
        index = jsonio.read_json(weekend / "index.json")
        self.assertEqual([week["isoWeek"] for week in index["weeks"]], ["2026-W46", "2026-W45"])


if __name__ == "__main__":
    unittest.main()
