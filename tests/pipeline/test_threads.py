"""pipeline.threads: which stories continue an earlier day's event, and which merely
share a name; stable thread ids, day numbers, history and pruning."""

import copy
import unittest

from pipeline import threads
from pipeline.core import textutil
from tests.pipeline.test_process_helpers import make_story


def story(story_id, day, titles, entities=(), outlets=None, score=50.0):
    """A story filed on ``day`` whose outlets ran ``titles`` (the first is the story's own).

    Outlets are unique to the story unless ``outlets`` names them, so the
    one-newsroom series rule only applies where a test asks for it.
    """
    titles = [titles] if isinstance(titles, str) else list(titles)
    names = outlets or ["%s outlet %d" % (story_id, index) for index in range(1, len(titles) + 1)]
    made = make_story(story_id, titles[0], score=score, sources=names, updated="%sT08:00:00Z" % day,
                      entities=list(entities), day=day)
    for source, title in zip(made["sources"], titles):
        source["title"] = title
    return made


# A continuing event: the Nvidia inquiry, three days running.
DAY1 = story("s-probe-1", "2026-11-09", [
    "FBI investigating Nvidia CEO over affair with alleged Chinese spy",
    "Nvidia shares tumble over investigation into Huang's affair with alleged spy",
], ["nvidia", "jensen-huang", "fbi"])
DAY2 = story("s-probe-2", "2026-11-10", [
    "Nvidia hires law firm to investigate alleged Chinese spy affair",
    "Nvidia board opens investigation into CEO Huang's affair with alleged spy",
], ["nvidia", "jensen-huang"])
DAY3 = story("s-probe-3", "2026-11-11", [
    "Nvidia investigation into Huang's affair with alleged spy widens",
    "Law firm widens Nvidia inquiry into alleged Chinese spy affair",
], ["nvidia", "jensen-huang"])
# Noise: other stories that share a name with something above, or nothing at all.
OTHER_NVIDIA = story("s-chips", "2026-11-10", [
    "Nvidia unveils Rubin Ultra chips at Taipei keynote",
    "Nvidia's new Rubin Ultra GPUs promise cheaper inference",
], ["nvidia"])
BACKGROUND = [
    story("s-bg-%d" % index, day, title, entities)
    for index, (day, title, entities) in enumerate([
        ("2026-11-09", "Spain's workers hold general strike over housing costs", []),
        ("2026-11-09", "Trump signs executive order restricting AI chip exports", ["donald-trump"]),
        ("2026-11-10", "Trump meets Xi in Beijing for trade talks", ["donald-trump", "xi-jinping"]),
        ("2026-11-10", "Sensex, Nifty close higher as banks rally", ["sensex", "nifty-50"]),
        ("2026-11-11", "Nifty slips below 25,000 as IT stocks drag", ["nifty-50"]),
        ("2026-11-10", "Tesla recalls 200,000 Cybertrucks over faulty accelerator pedal", ["tesla", "cybertruck"]),
        ("2026-11-11", "Tesla opens first Mumbai showroom as India sales begin", ["tesla", "india"]),
        ("2026-11-11", "Kenya discharges last Ebola patient in milestone", []),
        ("2026-11-09", "Pope Leo returns to Peru, his adopted homeland", []),
        ("2026-11-10", "ISRO test fires cryogenic engine for GSLV launch", ["isro"]),
        ("2026-11-11", "Apple to close its Support Community forums", ["apple"]),
        ("2026-11-10", "Gemini 4 Carbon is now available for developers", ["gemini", "google"]),
    ])
]


def link(live, archive=(), state=None):
    """Run the linker on copies; returns (live stories by id, state)."""
    state = threads.empty_state() if state is None else state
    live = copy.deepcopy(list(live))
    threads.link(live, copy.deepcopy(list(archive)), state)
    return {item["id"]: item for item in live}, state


class LinkingTests(unittest.TestCase):

    def test_continuing_event_is_linked_across_days(self):
        stories, state = link([DAY1, DAY2, DAY3, OTHER_NVIDIA] + BACKGROUND)
        thread_id = textutil.stable_id("t", "s-probe-1")
        self.assertEqual(stories["s-probe-2"]["thread"]["id"], thread_id)
        self.assertEqual(stories["s-probe-3"]["thread"]["id"], thread_id)
        self.assertEqual(state["stories"]["s-probe-3"], thread_id)

    def test_day_numbers_and_history(self):
        stories, _state = link([DAY1, DAY2, DAY3, OTHER_NVIDIA] + BACKGROUND)
        self.assertEqual(stories["s-probe-2"]["thread"]["day"], 2)
        self.assertEqual(stories["s-probe-3"]["thread"]["day"], 3)
        self.assertEqual(stories["s-probe-3"]["thread"]["history"], [
            {"date": "2026-11-09", "id": "s-probe-1", "title": DAY1["title"]},
            {"date": "2026-11-10", "id": "s-probe-2", "title": DAY2["title"]},
        ])

    def test_root_story_gets_the_thread_while_its_file_is_live(self):
        stories, _state = link([DAY1, DAY2] + BACKGROUND)
        self.assertEqual(stories["s-probe-1"]["thread"],
                         {"id": textutil.stable_id("t", "s-probe-1"), "day": 1, "history": []})

    def test_story_with_no_earlier_instalment_has_no_thread(self):
        stories, state = link([DAY1] + BACKGROUND)
        self.assertIsNone(stories["s-probe-1"]["thread"])
        self.assertTrue(all(item["thread"] is None for item in stories.values()))
        self.assertEqual(state, threads.empty_state())

    def test_sharing_a_common_entity_is_not_enough(self):
        stories, _state = link([DAY1, DAY2, OTHER_NVIDIA] + BACKGROUND)
        self.assertIsNone(stories["s-chips"]["thread"])
        for story_id in ("s-bg-2", "s-bg-4", "s-bg-6"):  # Trump, Nifty, Tesla on a later day
            with self.subTest(story_id):
                self.assertIsNone(stories[story_id]["thread"])

    def test_two_tesla_stories_sharing_two_entities_stay_apart(self):
        recall = story("s-recall", "2026-11-10", "Tesla recalls 200,000 Cybertrucks over faulty accelerator pedal",
                       ["tesla", "cybertruck"])
        trim = story("s-trim", "2026-11-11", "Tesla slims Cybertruck line-up to its most expensive trim",
                     ["tesla", "cybertruck"])
        stories, _state = link([recall, trim] + BACKGROUND)
        self.assertIsNone(stories["s-trim"]["thread"])

    def test_stories_on_the_same_day_are_never_linked(self):
        twin = story("s-probe-2b", "2026-11-10", DAY2["sources"][0]["title"], ["nvidia", "jensen-huang"])
        stories, _state = link([DAY2, twin] + BACKGROUND)
        self.assertIsNone(stories["s-probe-2"]["thread"])
        self.assertIsNone(stories["s-probe-2b"]["thread"])

    def test_event_unknown_to_the_lexicon_links_on_strong_wording(self):
        first = story("s-strike-1", "2026-11-10", [
            "Spain's dock workers begin general strike over pension reform",
            "Dock workers across Spain strike over pension reform"])
        second = story("s-strike-2", "2026-11-11", [
            "Spain's dock workers extend general strike over pension reform",
            "Dock workers across Spain extend strike over pension reform"])
        stories, _state = link([first, second] + BACKGROUND)
        self.assertEqual(stories["s-strike-2"]["thread"]["id"], textutil.stable_id("t", "s-strike-1"))

    def test_loose_wording_without_a_shared_entity_does_not_link(self):
        first = story("s-book-1", "2026-11-10", "Why I wrote the BEAM book")
        second = story("s-book-2", "2026-11-11", "Why Sonia Gandhi wrote her book at all")
        stories, _state = link([first, second] + BACKGROUND)
        self.assertIsNone(stories["s-book-2"]["thread"])

    def test_one_outlets_series_is_not_a_thread(self):
        monday = story("s-rbi-1", "2026-11-10", "State Government Securities - Full Auction Result",
                       outlets=["Reserve Bank of India"])
        tuesday = story("s-rbi-2", "2026-11-11", "Treasury Bills: Full Auction Result",
                        outlets=["Reserve Bank of India"])
        stories, _state = link([monday, tuesday] + BACKGROUND)
        self.assertIsNone(stories["s-rbi-2"]["thread"])

    def test_nothing_older_than_two_weeks_is_linked(self):
        old = copy.deepcopy(DAY1)
        old["day"] = "2026-10-26"
        stories, _state = link([DAY3] + BACKGROUND, archive=[old])
        self.assertIsNone(stories["s-probe-3"]["thread"])
        recent = copy.deepcopy(DAY1)
        recent["day"] = "2026-10-29"
        stories, _state = link([DAY3] + BACKGROUND, archive=[recent])
        self.assertEqual(stories["s-probe-3"]["thread"]["day"], 14)

    def test_links_to_a_story_in_a_frozen_file(self):
        stories, state = link([DAY3] + BACKGROUND, archive=[DAY1])
        self.assertEqual(stories["s-probe-3"]["thread"], {
            "id": textutil.stable_id("t", "s-probe-1"), "day": 3,
            "history": [{"date": "2026-11-09", "id": "s-probe-1", "title": DAY1["title"]}]})
        self.assertIn("s-probe-1", state["stories"])


# Pairs that each trip exactly one rule.
MUSK_DEMAND = story("s-musk-1", "2026-11-10", "Musk says Tesla Cybertruck demand is strong",
                    ["elon-musk", "tesla", "cybertruck"])
MUSK_RECALL = story("s-musk-2", "2026-11-11", "Tesla Cybertruck recall: Musk blames supplier",
                    ["elon-musk", "tesla", "cybertruck"])
CHIP_SHORTAGE = story("s-shortage", "2026-11-11", "Nvidia chips shortage hits carmakers as Taipei plants pause",
                      ["nvidia"])
ROVER_MONDAY = story("s-rover-1", "2026-11-10", "Rover blog: drilling begins at the Nazca site this week", ["nasa"],
                     outlets=["NASA"])
ROVER_TUESDAY = story("s-rover-2", "2026-11-11", "Rover blog: charging pause at the Nazca site continues", ["nasa"],
                      outlets=["NASA"])
ROVER_ELSEWHERE = story("s-rover-3", "2026-11-11", "Rover blog: charging pause at the Nazca site continues",
                        ["nasa"], outlets=["Space.com"])
RULE_PAIRS = [MUSK_DEMAND, MUSK_RECALL, CHIP_SHORTAGE, ROVER_MONDAY, ROVER_TUESDAY, ROVER_ELSEWHERE]


class SimilarityRuleTests(unittest.TestCase):

    def setUp(self):
        pool = [DAY1, DAY2, DAY3, OTHER_NVIDIA] + BACKGROUND + RULE_PAIRS
        self.profiles = {item["id"]: threads.Profile(item) for item in pool}
        self.weights = threads.cluster.Weights(list(self.profiles.values()))

    def sim(self, a, b, **thresholds):
        return threads.similarity(self.profiles[a], self.profiles[b], self.weights, **thresholds)

    def test_shared_names_without_shared_words_do_not_link(self):
        """Three entities in common push the centroids together; the words say they are two stories."""
        self.assertEqual(self.sim("s-musk-2", "s-musk-1"), 0.0)
        self.assertGreaterEqual(self.sim("s-musk-2", "s-musk-1", words_share=0.0), threads.LINK_THRESHOLD)

    def test_a_shared_name_and_a_few_shared_words_are_below_the_link_threshold(self):
        self.assertEqual(self.sim("s-shortage", "s-chips"), 0.0)
        self.assertEqual(self.sim("s-shortage", "s-chips", words_share=0.1), 0.0)
        self.assertGreater(self.sim("s-shortage", "s-chips", words_share=0.1, link=0.2), 0.0)

    def test_one_outlets_series_needs_a_much_closer_match(self):
        self.assertEqual(self.sim("s-rover-2", "s-rover-1"), 0.0)
        elsewhere = self.sim("s-rover-3", "s-rover-1")
        self.assertGreaterEqual(elsewhere, threads.LINK_THRESHOLD)
        self.assertLess(elsewhere, threads.SERIES_THRESHOLD)

    def test_instalments_score_above_zero_and_unrelated_stories_zero(self):
        self.assertGreater(self.sim("s-probe-2", "s-probe-1"), 0.0)
        self.assertEqual(self.sim("s-chips", "s-probe-1"), 0.0)
        self.assertEqual(self.sim("s-bg-7", "s-probe-1"), 0.0)

    def test_symmetric(self):
        self.assertAlmostEqual(self.sim("s-probe-2", "s-probe-1"), self.sim("s-probe-1", "s-probe-2"))

    def test_looser_thresholds_admit_more(self):
        strict = self.sim("s-chips", "s-probe-2")
        loose = self.sim("s-chips", "s-probe-2", link=0.0, words_share=0.0, strict=0.0)
        self.assertEqual(strict, 0.0)
        self.assertGreater(loose, 0.0)


class StateTests(unittest.TestCase):

    def test_thread_ids_are_stable_across_runs(self):
        first, state = link([DAY1, DAY2] + BACKGROUND)
        second, state = link([DAY1, DAY2, DAY3] + BACKGROUND, state=state)
        self.assertEqual(second["s-probe-2"]["thread"]["id"], first["s-probe-2"]["thread"]["id"])
        self.assertEqual(second["s-probe-3"]["thread"]["id"], first["s-probe-2"]["thread"]["id"])
        third, state_again = link([DAY1, DAY2, DAY3] + BACKGROUND, state=copy.deepcopy(state))
        self.assertEqual(third, second)
        self.assertEqual(state_again, state)

    def test_an_assigned_story_keeps_its_thread_even_if_its_headline_moves_on(self):
        _first, state = link([DAY1, DAY2] + BACKGROUND)
        changed = copy.deepcopy(DAY2)
        changed["title"] = "Something else entirely"
        for source in changed["sources"]:
            source["title"] = "Something else entirely"
        second, state = link([DAY1, changed] + BACKGROUND, state=state)
        self.assertEqual(second["s-probe-2"]["thread"]["id"], textutil.stable_id("t", "s-probe-1"))
        thread = state["threads"][textutil.stable_id("t", "s-probe-1")]
        self.assertEqual(thread["s-probe-2"]["title"], "Something else entirely")

    def test_history_is_one_story_per_day_oldest_first_at_most_six(self):
        thread_id = "t-long"
        state = threads.empty_state()
        state["threads"][thread_id] = {}
        for offset in range(9):
            day = "2026-11-%02d" % (1 + offset)
            for rank_in_day, score in enumerate((40.0, 60.0)):
                story_id = "s-%d-%d" % (offset, rank_in_day)
                state["stories"][story_id] = thread_id
                state["threads"][thread_id][story_id] = {"date": day, "title": "Day %d take %d" % (offset, rank_in_day),
                                                         "score": score}
        latest = story("s-latest", "2026-11-11", "The latest instalment")
        state["stories"]["s-latest"] = thread_id
        stories, _state = link([latest], state=state)
        thread = stories["s-latest"]["thread"]
        self.assertEqual(thread["day"], 11)
        self.assertEqual([entry["date"] for entry in thread["history"]],
                         ["2026-11-%02d" % day for day in range(4, 10)])
        self.assertTrue(all(entry["id"].endswith("-1") for entry in thread["history"]))  # the better-scored take

    def test_prune_drops_old_members_and_empty_threads(self):
        state = {"stories": {"s-old": "t1", "s-new": "t2", "s-old2": "t2"},
                 "threads": {"t1": {"s-old": {"date": "2026-09-01", "title": "a", "score": 1.0}},
                             "t2": {"s-new": {"date": "2026-11-10", "title": "b", "score": 1.0},
                                    "s-old2": {"date": "2026-09-02", "title": "c", "score": 1.0}}}}
        self.assertEqual(threads.prune(state, "2026-11-11"), 2)
        self.assertEqual(state, {"stories": {"s-new": "t2"},
                                 "threads": {"t2": {"s-new": {"date": "2026-11-10", "title": "b", "score": 1.0}}}})

    def test_story_whose_thread_was_pruned_is_treated_as_unthreaded(self):
        state = {"stories": {"s-probe-1": "t-gone"}, "threads": {}}
        stories, _state = link([DAY1] + BACKGROUND, state=state)
        self.assertIsNone(stories["s-probe-1"]["thread"])


if __name__ == "__main__":
    unittest.main()
