"""pipeline.cluster: outlet keys, tokens, the similarity guards, over- and under-merging on
hand-built and real pairs, and id stability across runs.

Real pairs come from tests/fixtures/process (items snapshotted from the live store and
labelled by hand); invented pairs are judged inside that corpus so word weights are realistic.
"""

import copy
import unittest
from datetime import timedelta

from pipeline import cluster
from pipeline.core import textutil, timeutil
from tests.pipeline.test_process_helpers import (LIVE_DAYS, cluster_items, fixture, make_doc, make_item,
                                                 real_items)

WIDE_DAYS = ["2026-11-%02d" % day for day in range(7, 21)]


def doc(title, source_name="Reuters", published="2026-11-11T08:00:00Z", **fields):
    return make_doc(make_item(title, source_name, published, **fields))


class OutletTests(unittest.TestCase):

    def test_spellings_of_one_newsroom_share_a_key(self):
        for names in (("The Times of India", "Times of India", "TOI"),
                      ("BBC", "BBC News"),
                      ("Moneycontrol.com", "Moneycontrol"),
                      ("WSJ", "The Wall Street Journal"),
                      ("Bloomberg.com", "Bloomberg"),
                      ("ABC News - Breaking News, Latest News and Videos", "ABC News")):
            keys = {cluster.outlet_key(name) for name in names}
            self.assertEqual(len(keys), 1, names)

    def test_different_newsrooms_differ(self):
        self.assertNotEqual(cluster.outlet_key("BBC News"), cluster.outlet_key("ABC News"))
        self.assertNotEqual(cluster.outlet_key("The Hindu"), cluster.outlet_key("Hindustan Times"))

    def test_label_drops_tagline_and_domain(self):
        self.assertEqual(cluster.outlet_label("ABC News - Breaking News, Latest News and Videos"), "ABC News")
        self.assertEqual(cluster.outlet_label("Moneycontrol.com"), "Moneycontrol")
        self.assertEqual(cluster.outlet_label("The New York Times"), "The New York Times")

    def test_missing_name_is_empty_not_an_error(self):
        self.assertEqual(cluster.outlet_key(None), "")


class TokenTests(unittest.TestCase):

    def test_entity_becomes_one_token_and_its_words_disappear(self):
        tokens = cluster.text_tokens("U.S. aircraft leave United States base", ["united-states"])
        self.assertIn("@united-states", tokens)
        self.assertFalse({"united", "states", "state", "us"} & tokens)
        self.assertIn("aircraft", tokens)

    def test_stopwords_are_dropped(self):
        self.assertFalse({"the", "of", "says"} & cluster.text_tokens("The cost of living, says the report", []))

    def test_demonym_meets_country(self):
        self.assertEqual(cluster.text_tokens("Bulgarian motorway", []), cluster.text_tokens("Bulgaria motorway", []))

    def test_demonym_of_a_lexicon_place_becomes_its_entity(self):
        self.assertIn("@russia", cluster.text_tokens("Russian diplomat", []))

    def test_magnitude_suffix_is_spelt_out(self):
        short = cluster.text_tokens("valued at $1.4tn", [])
        long = cluster.text_tokens("valued at $1.4 trillion", [])
        self.assertEqual(short, long)
        self.assertIn("trillion", short)

    def test_verb_forms_the_stemmer_leaves_apart_are_joined(self):
        self.assertEqual(cluster.text_tokens("leak exposes data", []), cluster.text_tokens("leak exposed data", []))


class SimilarityTests(unittest.TestCase):
    """The guards, one at a time, with weights from the real corpus."""

    @classmethod
    def setUpClass(cls):
        cls.weights = cluster.Weights([make_doc(item) for item in real_items()])

    def sim(self, a, b):
        return cluster.similarity(a, b, self.weights)

    def test_same_headline_from_two_outlets_is_certain(self):
        a = doc("Ferry capsizes off Zanzibar with 200 aboard", "AP News")
        b = doc("Ferry capsizes off Zanzibar with 200 aboard", "ABC News", "2026-11-11T10:00:00Z")
        self.assertEqual(self.sim(a, b), 1.0)

    def test_publisher_tail_does_not_break_headline_equality(self):
        a = doc("Ferry capsizes off Zanzibar with 200 aboard - AP News", "Google News")
        b = doc("Ferry capsizes off Zanzibar with 200 aboard", "ABC News")
        self.assertEqual(self.sim(a, b), 1.0)

    def test_very_short_identical_headlines_prove_nothing(self):
        self.assertEqual(self.sim(doc("Red Flags", "The New York Times"), doc("Red Flags", "The Guardian")), 0.0)

    def test_unrelated_headlines_score_zero(self):
        self.assertEqual(self.sim(doc("Ferry capsizes off Zanzibar"), doc("Parliament passes budget bill")), 0.0)

    def test_beyond_the_window_never_matches(self):
        a = doc("Ferry capsizes off Zanzibar with 200 aboard", "AP News", "2026-11-08T08:00:00Z")
        b = doc("Ferry capsizes off Zanzibar with 200 aboard", "ABC News", "2026-11-11T08:00:00Z")
        self.assertEqual(self.sim(a, b), 0.0)

    def test_time_costs_but_does_not_forbid_within_the_window(self):
        a = doc("Volcano erupts near Arequipa as Peru declares emergency", "BBC News", "2026-11-10T02:00:00Z")
        near = doc("Peru declares emergency after volcano erupts near Arequipa", "DW", "2026-11-10T06:00:00Z")
        far = doc("Peru declares emergency after volcano erupts near Arequipa", "DW", "2026-11-11T20:00:00Z")
        self.assertGreater(self.sim(a, near), self.sim(a, far))
        self.assertGreater(self.sim(a, far), 0.0)

    def test_recurring_template_only_matches_within_one_day(self):
        monday = doc("Sensex, Nifty close higher as banks rally", "Mint", "2026-11-10T10:15:00Z")
        tuesday = doc("Sensex, Nifty close higher as banks rally", "The Economic Times", "2026-11-11T10:15:00Z")
        same_day = doc("Sensex, Nifty close higher as banks rally", "The Economic Times", "2026-11-10T10:45:00Z")
        self.assertTrue(monday.routine)
        self.assertEqual(self.sim(monday, tuesday), 0.0)
        self.assertEqual(self.sim(monday, same_day), 1.0)

    def test_recurring_template_needs_the_same_session(self):
        opening = doc("Stock market today: Sensex, Nifty open higher", "Mint", "2026-11-11T03:50:00Z")
        closing = doc("Stock market today: Sensex, Nifty open higher", "NDTV", "2026-11-11T12:30:00Z")
        self.assertEqual(self.sim(opening, closing), 0.0)

    def test_opposite_market_directions_count_against(self):
        up = doc("Acme Widgets shares jump after quarterly numbers", "CNBC")
        also_up = doc("Acme Widgets shares surge after quarterly numbers", "Bloomberg")
        down = doc("Acme Widgets shares fall after quarterly numbers", "Bloomberg")
        self.assertEqual((up.direction, down.direction), (1, -1))
        self.assertLess(self.sim(up, down), 0.75 * self.sim(up, also_up))

    def test_disjoint_named_subjects_count_against(self):
        tcs = doc("TCS quarterly net profit rises 12%, beats estimates", "Mint")
        tcs_again = doc("TCS quarterly net profit rises 12%, beats estimates on deals", "Business Standard")
        infosys = doc("Infosys quarterly net profit rises 12%, beats estimates", "Business Standard")
        self.assertTrue(tcs.anchors and infosys.anchors and tcs.anchors.isdisjoint(infosys.anchors))
        self.assertLess(self.sim(tcs, infosys), cluster.JOIN_THRESHOLD)
        self.assertGreater(self.sim(tcs, tcs_again), cluster.JOIN_THRESHOLD)

    def test_one_outlet_series_instalments_are_different_stories(self):
        first = doc("Money Market Operations as on November 09, 2026", "Reserve Bank of India")
        second = doc("Money Market Operations as on November 10, 2026", "Reserve Bank of India",
                     "2026-11-11T09:00:00Z")
        self.assertEqual(self.sim(first, second), 0.0)

    def test_same_outlet_needs_a_closer_match_than_two_outlets(self):
        a = doc("Volcano erupts near Arequipa as Peru declares emergency", "BBC News")
        same_outlet = doc("Peru declares emergency after volcano erupts", "BBC News", "2026-11-11T09:00:00Z")
        other_outlet = doc("Peru declares emergency after volcano erupts", "DW", "2026-11-11T09:00:00Z")
        self.assertLess(self.sim(a, same_outlet), self.sim(a, other_outlet))

    def test_aggregator_listing_adds_to_text_evidence(self):
        listed = doc("Flights grounded at Lisbon airport as Portugal investigates drones", "Google News",
                     publisher="Euronews.com",
                     alt=[{"title": "Drone sightings shut Lisbon airport for six hours", "publisher": "The Guardian"}])
        unlisted = doc("Flights grounded at Lisbon airport as Portugal investigates drones", "Google News",
                       publisher="Euronews.com")
        other = doc("Drone sightings shut Lisbon airport for six hours", "The Guardian")
        self.assertAlmostEqual(self.sim(listed, other), self.sim(unlisted, other) + cluster.ALT_BONUS, places=6)

    def test_aggregator_listing_alone_is_not_enough(self):
        listed = doc("Russian Offensive Campaign Assessment, November 10, 2026", "Google News",
                     publisher="Institute for the Study of War",
                     alt=[{"title": "Russian diplomat says Moscow could sign non-aggression pacts",
                           "publisher": "Reuters"}])
        other = doc("Russian diplomat says Moscow could sign non-aggression pacts", "Reuters")
        self.assertLess(self.sim(listed, other), cluster.JOIN_THRESHOLD)

    def test_containment_needs_most_of_the_headline_by_count_too(self):
        short = doc("US and China trade ties", "Bloomberg")
        long = doc("Sheikh Hasina, water and trade: Roadblocks in India-Bangladesh ties", "The Times of India")
        self.assertLessEqual(cluster.containment(short, long, self.weights), 0.5)
        self.assertLess(self.sim(short, long), cluster.JOIN_THRESHOLD)

    def test_similarity_is_symmetric(self):
        a = doc("Peru declares state of emergency after volcano erupts near Arequipa", "BBC News",
                summary="Thousands have been moved from villages near the Ubinas volcano.")
        b = doc("Volcano eruption near Arequipa forces Peru to declare emergency", "Reuters", "2026-11-11T09:30:00Z")
        self.assertAlmostEqual(self.sim(a, b), self.sim(b, a), places=9)


class AdversarialPairTests(unittest.TestCase):
    """Invented pairs for the two classic failures, each judged inside the real corpus."""

    @classmethod
    def setUpClass(cls):
        cls.cases = fixture("adversarial.json")["cases"]
        cls.background = real_items()

    def outcome(self, case):
        a, b = (make_item(spec["title"], spec["sourceName"], spec["publishedAt"],
                          **{key: value for key, value in spec.items()
                             if key not in ("title", "sourceName", "publishedAt")})
                for spec in (case["a"], case["b"]))
        state = cluster_items(self.background + [a, b], WIDE_DAYS)
        return state["items"][a["id"]] == state["items"][b["id"]]

    def test_fixture_covers_both_failures(self):
        self.assertGreaterEqual(sum(1 for case in self.cases if not case["same"]), 20)
        self.assertGreaterEqual(sum(1 for case in self.cases if case["same"]), 9)

    def test_different_stories_stay_apart(self):
        for case in self.cases:
            if not case["same"]:
                with self.subTest(case["name"]):
                    self.assertFalse(self.outcome(case))

    def test_one_event_in_different_words_is_one_story(self):
        for case in self.cases:
            if case["same"]:
                with self.subTest(case["name"]):
                    self.assertTrue(self.outcome(case))


class RealPairTests(unittest.TestCase):
    """Hand-labelled pairs from the live store."""

    @classmethod
    def setUpClass(cls):
        cls.pairs = fixture("pairs.json")
        cls.state = cluster_items(real_items(), LIVE_DAYS)

    def together(self, pair):
        return self.state["items"][pair[0]] == self.state["items"][pair[1]]

    def test_enough_pairs_of_each_kind(self):
        self.assertGreaterEqual(len(self.pairs["must"]), 25)
        self.assertGreaterEqual(len(self.pairs["cannot"]), 25)

    def test_must_link_pairs_share_a_story(self):
        for pair in self.pairs["must"]:
            with self.subTest(pair[2]):
                self.assertTrue(self.together(pair))

    def test_cannot_link_pairs_do_not(self):
        for pair in self.pairs["cannot"]:
            with self.subTest(pair[2]):
                self.assertFalse(self.together(pair))

    def test_recall_including_the_hard_pairs(self):
        every = self.pairs["must"] + self.pairs["hard"]
        linked = sum(1 for pair in every if self.together(pair))
        self.assertGreaterEqual(linked / float(len(every)), 0.8)

    def test_no_story_mixes_recurring_templates_from_two_days(self):
        docs = {item["id"]: make_doc(item) for item in real_items()}
        days = {}
        for item_id, story_id in self.state["items"].items():
            if docs[item_id].routine:
                days.setdefault(story_id, set()).add(docs[item_id].day)
        self.assertEqual([story for story, seen in days.items() if len(seen) > 1], [])

    def test_big_stories_are_found_whole(self):
        sizes = {}
        for story_id in self.state["items"].values():
            sizes[story_id] = sizes.get(story_id, 0) + 1
        italy = [item["id"] for item in real_items()
                 if "bomb" in item["title"].lower() and "school" in item["title"].lower()]
        stories = {self.state["items"][item_id] for item_id in italy}
        self.assertGreaterEqual(len(italy), 8)
        self.assertEqual(len(stories), 1)
        self.assertGreaterEqual(max(sizes.values()), 10)


class StabilityTests(unittest.TestCase):
    """Story ids across runs: recorded assignments are final."""

    @classmethod
    def setUpClass(cls):
        cls.items = sorted(real_items(), key=lambda item: (item["publishedAt"], item["id"]))
        cut = len(cls.items) * 3 // 5
        cls.first, cls.rest = cls.items[:cut], cls.items[cut:]
        cls.run1 = cluster_items(cls.first, LIVE_DAYS)
        cls.run2 = cluster_items(cls.items, LIVE_DAYS, copy.deepcopy(cls.run1))

    def test_story_id_is_derived_from_a_member_item(self):
        members = {}
        for item_id, story_id in self.run2["items"].items():
            members.setdefault(story_id, []).append(item_id)
        for story_id, item_ids in members.items():
            self.assertIn(story_id, {textutil.stable_id("s", item_id) for item_id in item_ids})

    def test_assignments_survive_new_items(self):
        for item_id, story_id in self.run1["items"].items():
            self.assertEqual(self.run2["items"][item_id], story_id)

    def test_published_stories_are_never_absorbed(self):
        self.assertEqual(set(self.run1["stories"]) - set(self.run2["stories"]), set())
        for story_id, meta in self.run1["stories"].items():
            self.assertEqual(self.run2["stories"][story_id], meta)

    def test_new_items_join_old_stories_and_seed_new_ones(self):
        new_ids = {item["id"] for item in self.rest}
        joined = sum(1 for item_id in new_ids if self.run2["items"][item_id] in self.run1["stories"])
        seeded = {self.run2["items"][item_id] for item_id in new_ids} - set(self.run1["stories"])
        self.assertGreater(joined, 10)
        self.assertGreater(len(seeded), 50)

    def test_every_item_is_assigned_to_a_recorded_story(self):
        self.assertEqual(set(self.run2["items"]), {item["id"] for item in self.items})
        self.assertTrue(set(self.run2["items"].values()) <= set(self.run2["stories"]))

    def test_rerun_without_new_items_changes_nothing(self):
        again = cluster_items(self.items, LIVE_DAYS, copy.deepcopy(self.run2))
        self.assertEqual(again, self.run2)

    def test_same_input_gives_same_clusters(self):
        self.assertEqual(cluster_items(self.items, LIVE_DAYS), cluster_items(list(reversed(self.items)), LIVE_DAYS))

    def test_story_day_is_the_seed_items_local_date(self):
        by_id = {item["id"]: item for item in self.items}
        for story_id, meta in self.run2["stories"].items():
            seeds = [item_id for item_id in by_id if textutil.stable_id("s", item_id) == story_id]
            self.assertEqual(len(seeds), 1)
            seed_time = timeutil.parse_date(by_id[seeds[0]]["publishedAt"])
            self.assertEqual(meta["day"], timeutil.local_date(seed_time, "Asia/Kolkata"))


class AssignRuleTests(unittest.TestCase):

    def setUp(self):
        self.background = real_items()

    def pair_state(self, a, b, days=WIDE_DAYS, state=None):
        return cluster_items(self.background + [a, b], days, state)

    def test_item_cannot_join_a_story_on_a_frozen_day(self):
        old = make_item("Ferry capsizes off Zanzibar with 200 aboard, dozens missing", "AP News",
                        "2026-11-14T10:00:00Z")
        new = make_item("Ferry capsizes off Zanzibar with 200 aboard, dozens missing", "ABC News",
                        "2026-11-15T20:00:00Z")
        together = self.pair_state(old, new)
        self.assertEqual(together["items"][old["id"]], together["items"][new["id"]])
        # Second run: the story's day (the 14th) is no longer live, so the late item starts its own story.
        state = cluster_items(self.background + [old], WIDE_DAYS)
        frozen = cluster_items([old, new], ["2026-11-15", "2026-11-16", "2026-11-17"], state)
        self.assertNotEqual(frozen["items"][old["id"]], frozen["items"][new["id"]])
        self.assertEqual(frozen["stories"][frozen["items"][new["id"]]]["day"], "2026-11-16")

    def test_story_closes_48_hours_after_its_newest_item(self):
        old = make_item("Ferry capsizes off Zanzibar with 200 aboard, dozens missing", "AP News",
                        "2026-11-14T10:00:00Z")
        late = make_item("Ferry capsizes off Zanzibar with 200 aboard, dozens missing", "ABC News",
                         "2026-11-16T11:00:00Z")
        state = self.pair_state(old, late)
        self.assertNotEqual(state["items"][old["id"]], state["items"][late["id"]])

    def test_fresh_fragments_merge_but_published_ones_keep_their_ids(self):
        """Two outlets word a breaking story differently; later items show they are one story."""
        when = timeutil.parse_date("2026-11-17T06:00:00Z")
        titles = [
            ("Harbour Daily", "Cargo ship rams Tasman Bridge in Hobart, two spans collapse"),
            ("Island Times", "Hobart: Tasman Bridge closed after collapse, cars in river"),
            ("City Herald", "Tasman Bridge collapse in Hobart: cargo ship rams bridge, two spans fall"),
            ("Coast Wire", "Cars in river after Tasman Bridge collapse in Hobart, bridge closed"),
            ("Morning Post", "Cargo ship rams Tasman Bridge; two spans collapse, cars in river, Hobart bridge closed"),
        ]
        items = [make_item(title, outlet, timeutil.iso(when + timedelta(minutes=20 * index)))
                 for index, (outlet, title) in enumerate(titles)]
        one_run = cluster_items(self.background + items, WIDE_DAYS)
        self.assertEqual(len({one_run["items"][item["id"]] for item in items}), 1)
        self.assertEqual(one_run["items"][items[0]["id"]], textutil.stable_id("s", items[0]["id"]))

        first = cluster_items(self.background + items[:2], WIDE_DAYS)
        published = {first["items"][item["id"]] for item in items[:2]}
        second = cluster_items(self.background + items, WIDE_DAYS, copy.deepcopy(first))
        for item in items[:2]:
            self.assertEqual(second["items"][item["id"]], first["items"][item["id"]])
        self.assertTrue(published <= set(second["stories"]))
        self.assertTrue({second["items"][item["id"]] for item in items[2:]} <= published)

    def test_prune_forgets_old_stories_and_their_items(self):
        state = {"items": {"i1": "s1", "i2": "s2", "i3": "s2"},
                 "stories": {"s1": {"day": "2026-10-30"}, "s2": {"day": "2026-11-10"}}}
        self.assertEqual(cluster.prune(state, "2026-11-01"), 1)
        self.assertEqual(state, {"items": {"i2": "s2", "i3": "s2"}, "stories": {"s2": {"day": "2026-11-10"}}})
        self.assertEqual(cluster.prune(state, "2026-11-01"), 0)

    def test_item_without_a_date_is_refused(self):
        with self.assertRaises(ValueError):
            make_doc(make_item("A headline with no usable date at all", published="not a date"))


if __name__ == "__main__":
    unittest.main()
