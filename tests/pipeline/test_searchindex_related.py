"""pipeline.searchindex "related" terms, learned from a synthetic corpus whose right answers are known.

The corpus has three topics (space, chips, currency) over a bed of everyday
filler, plus traps: a rare word that only ever appears in space stories (raw
PMI would rank it first), a pair seen only twice, a word below the document
frequency floor, inflections, and an entity whose name words always travel
together.
"""

import json
import unittest

from pipeline import searchindex as si
from pipeline.core import jsonio

FILLER = ["city", "council", "weather", "school", "festival", "traffic", "budget", "court"]
ENTITIES = {
    "bank-nifty": {"name": "Bank Nifty", "aliases": ["Bank Nifty"]},
    "isro": {"name": "ISRO", "aliases": ["ISRO", "Indian Space Research Organisation"]},
    "ai": {"name": "AI", "aliases": ["AI"]},
    "orbit-booster": {"name": "Orbit Booster", "aliases": ["Orbit Booster"]},
}


def story(words, entities=()):
    return {"title": " ".join(words), "summary": "", "entities": list(entities)}


def filler(i, n=2):
    """Two everyday words that rotate through the pool, so none of them is tied to a topic."""
    return [FILLER[(i + k * 3) % len(FILLER)] for k in range(n)]


def corpus():
    stories = []
    for i in range(40):  # space
        words = ["rocket"] + filler(i)
        if i < 30:
            words.append("orbit")
        if i < 25:
            words.append("booster")
        if i < 30:
            words.append("launch")
        if 20 <= i < 30:
            words.append("launcher")   # an inflection of "launch"
        if 10 <= i < 25:
            words.append("orbital")    # an inflection of "orbit"
        if i < 5:
            words.append("quokka")     # rare, and only ever in space stories
        if i < 2:
            words.append("yak")        # seen with "rocket" twice only
        entities = (["isro"] if i % 2 else []) + (["orbit-booster"] if i < 5 else [])
        stories.append(story(words, entities))
    for i in range(40):  # chips
        words = ["wafer"] + filler(i + 1)
        if i < 30:
            words.append("foundry")
        if i < 20:
            words.append("lithography")
        stories.append(story(words))
    for i in range(40):  # currency, with an entity whose two name words always co-occur
        words = ["rupee"] + filler(i + 2)
        if i < 30:
            words.append("dollar")
        if i < 25:
            words.append("forex")
        if i < 12:
            words += ["bank", "nifty"]
        stories.append(story(words, ["bank-nifty"] if i < 12 else []))
    for i in range(80):
        words = filler(i, 3)
        if i < 3:
            words.append("yak")
        if i < 4:
            words.append("zebu")       # df 4: below the floor
        if 10 <= i < 15:
            words.append("orbit")      # so its raw PMI with "rocket" is lower than the quokka's
        if i < 3:
            words.append("ai")         # too short to learn from on its own
        stories.append(story(words, ["ai"] if i < 6 else []))
    return stories


def learn(**kw):
    terms, families = si.entity_terms(ENTITIES)
    sets = [si.story_terms(s, terms) for s in corpus()]
    return si.learn_related(sets, families, **kw)


def neighbours(related, term):
    return [other for other, _weight in related.get(term, [])]


class KnownNeighbours(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.related, cls.df = learn()

    def test_topic_words_find_each_other(self):
        self.assertEqual(set(neighbours(self.related, "rocket")[:3]), {"orbit", "launch", "booster"})
        self.assertEqual(set(neighbours(self.related, "wafer")), {"foundry", "lithography"})
        self.assertEqual(neighbours(self.related, "rupee")[:2], ["dollar", "forex"])
        self.assertIn("rocket", neighbours(self.related, "orbit"))

    def test_no_cross_topic_or_filler_neighbours(self):
        for term in ("rocket", "wafer", "rupee"):
            found = set(neighbours(self.related, term))
            self.assertFalse(found & set(FILLER), term)
        self.assertNotIn("wafer", neighbours(self.related, "rocket"))
        self.assertNotIn("dollar", neighbours(self.related, "foundry"))

    def test_rare_junk_does_not_top_the_list(self):
        # Raw PMI puts "quokka" above "orbit" for "rocket": it never appears anywhere else.
        docs = len(corpus())
        raw = lambda together, other: together * docs / (self.df["rocket"] * self.df[other])
        self.assertGreater(raw(5, "quokka"), raw(30, "orbit"))
        ranked = neighbours(self.related, "rocket")
        if "quokka" in ranked:
            self.assertGreater(ranked.index("quokka"), ranked.index("orbit"))
            self.assertGreater(ranked.index("quokka"), ranked.index("booster"))

    def test_pairs_seen_fewer_than_three_times_are_ignored(self):
        self.assertGreaterEqual(self.df["yak"], si.MIN_DF)
        self.assertNotIn("yak", neighbours(self.related, "rocket"))
        self.assertNotIn("rocket", neighbours(self.related, "yak"))

    def test_terms_below_the_document_frequency_floor_get_nothing(self):
        self.assertEqual(self.df["zebu"], 4)
        self.assertNotIn("zebu", self.related)
        for row in self.related.values():
            self.assertNotIn("zebu", [other for other, _ in row])

    def test_inflections_are_dropped(self):
        self.assertNotIn("launcher", neighbours(self.related, "launch"))
        self.assertNotIn("launch", neighbours(self.related, "launcher"))
        rocket = neighbours(self.related, "rocket")
        self.assertFalse({"orbit", "orbital"} <= set(rocket), rocket)

    def test_entity_terms(self):
        terms, families = si.entity_terms(ENTITIES)
        self.assertEqual(terms, {"bank-nifty": "@bank-nifty", "isro": "isro", "ai": "@ai",
                                 "orbit-booster": "@orbit-booster"})
        self.assertEqual(families["bank"], {"bank-nifty"})
        self.assertEqual(families["@bank-nifty"], {"bank-nifty"})
        self.assertNotIn("isro", families)
        # a one-word name is learned as that word, so ISRO is tied to space stories
        self.assertIn("isro", self.related)
        self.assertIn(neighbours(self.related, "isro")[0], {"rocket", "orbit", "launch", "booster"})

    def test_words_that_spell_one_entity_are_not_each_others_neighbours(self):
        for term, other in (("bank", "nifty"), ("nifty", "bank"), ("bank", "@bank-nifty"),
                            ("@bank-nifty", "nifty"), ("@bank-nifty", "bank")):
            self.assertNotIn(other, neighbours(self.related, term), term)
        self.assertIn("rupee", neighbours(self.related, "@bank-nifty"))

    def test_common_words_in_an_entity_name_stay_free(self):
        # "Orbit Booster" is named in only 5 of the 35 orbit stories: the words are not its spelling.
        self.assertIn("booster", neighbours(self.related, "orbit"))
        self.assertIn("orbit", neighbours(self.related, "booster"))
        # ...but the entity itself is never a neighbour of a word of its own name
        self.assertNotIn("@orbit-booster", neighbours(self.related, "orbit"))
        self.assertNotIn("orbit", neighbours(self.related, "@orbit-booster"))
        terms, families = si.entity_terms(ENTITIES)
        _related, df = learn()
        _df, _vocab, pairs = si.count_terms([si.story_terms(s, terms) for s in corpus()], si.VOCAB_CAP)
        confirmed = si.spelling(families, df, pairs)
        self.assertNotIn("orbit", confirmed)
        self.assertEqual(confirmed["nifty"], {"bank-nifty"})

    def test_short_tokens_are_not_learned_but_their_entity_is(self):
        self.assertNotIn("ai", self.related)
        self.assertEqual(self.df["@ai"], 6)

    def test_weights_are_normalised_sorted_and_capped(self):
        for term, row in self.related.items():
            self.assertLessEqual(len(row), si.TOP_NEIGHBOURS, term)
            weights = [weight for _, weight in row]
            self.assertEqual(weights, sorted(weights, reverse=True), term)
            for weight in weights:
                self.assertGreater(weight, 0)
                self.assertLessEqual(weight, 1)
                self.assertEqual(weight, round(weight, 2))
            self.assertNotIn(term, [other for other, _ in row])

    def test_deterministic(self):
        again, _ = learn()
        self.assertEqual(jsonio.dumps(again, sort_keys=True), jsonio.dumps(self.related, sort_keys=True))


class Caps(unittest.TestCase):
    def test_vocabulary_cap_keeps_the_most_frequent_terms(self):
        related, df = learn(vocab_cap=6)
        used = set(related) | {other for row in related.values() for other, _ in row}
        self.assertLessEqual(len(used), 6)
        top = sorted((t for t in df if df[t] >= si.MIN_DF), key=lambda t: (-df[t], t))[:6]
        self.assertLessEqual(used, set(top))

    def test_empty_corpus(self):
        related, df = si.learn_related([], {})
        self.assertEqual((related, dict(df)), ({}, {}))

    def test_neighbour_cap(self):
        related, _ = learn(top=2)
        self.assertTrue(related)
        self.assertTrue(all(len(row) <= 2 for row in related.values()))

    def test_fit_related_drops_rarest_terms_first(self):
        related = {"common": [["a", 0.5]], "middle": [["b", 0.5]], "rare": [["c", 0.5]]}
        df = {"common": 50, "middle": 20, "rare": 5}
        base = {"aliases": {}, "entities": {}, "glossary": {}}
        full = len(jsonio.dumps(dict(base, related=related)).encode("utf-8")) + 1
        kept, dropped = si.fit_related(base, related, df, full)
        self.assertEqual((kept, dropped), (related, 0))
        kept, dropped = si.fit_related(base, related, df, full - 1)
        self.assertEqual((sorted(kept), dropped), (["common", "middle"], 1))
        self.assertLessEqual(len(jsonio.dumps(dict(base, related=kept)).encode("utf-8")) + 1, full - 1)

    def test_fit_related_estimate_is_exact(self):
        related, df = learn()
        base = {"aliases": {"x": ["y"]}, "entities": {}, "glossary": {}}
        exact = len(jsonio.dumps(dict(base, related=related)).encode("utf-8")) + 1
        kept, dropped = si.fit_related(base, related, df, exact)
        self.assertEqual(dropped, 0)
        self.assertEqual(json.loads(jsonio.dumps(kept)), json.loads(jsonio.dumps(related)))


class Variants(unittest.TestCase):
    def test_is_variant(self):
        for a, b in (("chip", "chipmaker"), ("investor", "investment"), ("china", "chinese"),
                     ("gpt", "gpt-5.5"), ("launch", "launcher"), ("israel", "israeli")):
            self.assertTrue(si._is_variant(a, b), (a, b))
            self.assertTrue(si._is_variant(b, a), (b, a))
        for a, b in (("china", "chip"), ("price", "prime"), ("rupee", "dollar"), ("@isro", "isro"),
                     ("model", "modi")):
            self.assertFalse(si._is_variant(a, b), (a, b))


class SurfaceWords(unittest.TestCase):
    def test_stems_that_are_not_words_get_the_commonest_word(self):
        stories = [story(["released"]), story(["released"]), story(["releasing"]), story(["agents"]),
                   story(["agent"])]
        related = {"releas": [["agent", 0.5]]}
        self.assertEqual(si.surface_words(stories, related), {"releas": "released"})


if __name__ == "__main__":
    unittest.main()
