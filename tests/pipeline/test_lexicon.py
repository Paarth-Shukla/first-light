"""pipeline.lexicon mechanics, pinned with the small hand-built lexicon in tests/fixtures/lexicon/mini-lexicon.json.

These tests do not depend on what config/lexicon.json happens to contain; they
fix the matching, gating, section and validation rules themselves.
test_lexicon_config.py covers the real config.
"""

import copy
import json
import unittest
from pathlib import Path
from unittest import mock

from pipeline import lexicon
from pipeline.core import config

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "lexicon"
SECTIONS = ["world", "india", "ai", "ml", "llm", "labs", "companies", "markets", "india-markets", "science"]


def mini_data():
    """A fresh copy of the mini lexicon, safe to mutate."""
    with open(FIXTURES / "mini-lexicon.json", encoding="utf-8") as handle:
        return json.load(handle)


def mini():
    return lexicon.Lexicon(mini_data(), SECTIONS)


def entity_by_id(data, entity_id):
    return next(entity for entity in data["entities"] if entity["id"] == entity_id)


class Tokenising(unittest.TestCase):
    def setUp(self):
        self.lex = mini()

    def test_whole_words_only(self):
        self.assertEqual(self.lex.match_entities("Acme"), ["acme"])
        self.assertEqual(self.lex.match_entities("Acmeville council meets"), [])
        self.assertEqual(self.lex.match_entities("The Peacme project"), [])

    def test_case_and_accents_are_ignored_for_ordinary_aliases(self):
        self.assertEqual(self.lex.match_entities("ACME and acme"), ["acme"])
        self.assertEqual(self.lex.match_entities("Nestle results"), ["nestle"])
        self.assertEqual(self.lex.match_entities("NESTLÉ results"), ["nestle"])

    def test_all_capital_aliases_must_match_exactly(self):
        self.assertEqual(self.lex.match_entities("WHO warns of measles"), ["who"])
        self.assertEqual(self.lex.match_entities("Who will win?"), [])
        self.assertEqual(self.lex.match_entities("who knows"), [])

    def test_possessives_and_plurals(self):
        self.assertEqual(self.lex.match_entities("Acme's chief quits"), ["acme"])
        self.assertEqual(self.lex.match_entities("Acme’s chief quits"), ["acme"])
        self.assertEqual(self.lex.match_entities("GPUs are scarce"), ["gpu"])
        self.assertEqual(self.lex.match_entities("cheap graphics cards"), ["gpu"])

    def test_capitalised_names_of_ambiguous_entities_take_no_plural(self):
        self.assertEqual(self.lex.match_entities("Apples and pears, shares of farms"), [])

    def test_order_is_first_mention_and_ids_are_unique(self):
        self.assertEqual(self.lex.match_entities("GPU prices: Acme, then WHO, then Acme again"),
                         ["gpu", "acme", "who"])

    def test_empty_and_none_text(self):
        self.assertEqual(self.lex.match_entities(""), [])
        self.assertEqual(self.lex.match_entities(None), [])


class Phrases(unittest.TestCase):
    def setUp(self):
        self.lex = mini()

    def test_longest_alias_wins(self):
        self.assertEqual(self.lex.match_entities("Bank Nifty hits record, Sensex flat"), ["bank-nifty"])

    def test_phrases_span_hyphens_dots_and_initials(self):
        self.assertEqual(self.lex.match_entities("TSMC chief C.C. Wei speaks"), ["cc-wei"])
        self.assertEqual(self.lex.match_entities("Dr. Reddy's recalls a drug"), ["dr-reddys"])
        self.assertEqual(self.lex.match_entities("World-Health-Organization data"), ["who"])

    def test_phrases_do_not_span_commas_or_sentence_ends(self):
        self.assertEqual(self.lex.match_entities("Jane, Roe and others"), [])
        self.assertEqual(self.lex.match_entities("Ask Jane. Roe said no"), [])
        self.assertEqual(self.lex.match_entities("Headline - Jane Roe"), ["jane-roe"])


class Gating(unittest.TestCase):
    def setUp(self):
        self.lex = mini()

    def test_gated_word_needs_context(self):
        self.assertEqual(self.lex.match_entities("Apple harvest hit by frost"), [])
        self.assertEqual(self.lex.match_entities("Apple shares fall"), ["apple"])
        self.assertEqual(self.lex.match_entities("Apple, led by Tim Cook, unveils"), ["apple"])

    def test_exact_case_for_capitalised_ambiguous_aliases(self):
        self.assertEqual(self.lex.match_entities("apple shares fall"), [])
        self.assertEqual(self.lex.match_entities("AAPL slides"), ["apple"])
        self.assertEqual(self.lex.match_entities("Apple Inc said"), ["apple"])

    def test_related_entity_opens_the_gate(self):
        self.assertEqual(self.lex.match_entities("Apple unveils a new iPhone"), ["apple", "iphone"])

    def test_version_opens_the_gate_for_models(self):
        self.assertEqual(self.lex.match_entities("Llama 4 is out"), ["llama"])
        self.assertEqual(self.lex.match_entities("Llama 3.1 70B"), ["llama"])
        self.assertEqual(self.lex.match_entities("Llama farm visit"), [])

    def test_a_year_is_not_a_version(self):
        self.assertEqual(self.lex.match_entities("Llama 2026 calendar"), [])

    def test_version_does_not_open_gates_for_companies(self):
        self.assertEqual(self.lex.match_entities("Apple 2 growers"), [])

    def test_lowercase_gated_topic_matches_any_case(self):
        self.assertEqual(self.lex.match_entities("Fine-tuning a model on chat logs"), ["fine-tuning"])
        self.assertEqual(self.lex.match_entities("Government to fine-tuning of taxes"), [])

    def test_shared_gated_word_resolves_by_context(self):
        self.assertEqual(self.lex.match_entities("Congress slams BJP"), ["party-in"])
        self.assertEqual(self.lex.match_entities("Congress and the Senate agree"), ["congress-us"])
        self.assertEqual(self.lex.match_entities("Congress meets"), [])

    def test_context_words_ignore_a_plural_s_either_way(self):
        # context lists "points" and "sensex"
        self.assertEqual(self.lex.match_entities("Nifty gains 120 points"), ["nifty-50"])
        self.assertEqual(self.lex.match_entities("Nifty up one point"), ["nifty-50"])
        self.assertEqual(self.lex.match_entities("Nifty, like the SENSEX, rose"), ["nifty-50"])
        self.assertEqual(self.lex.match_entities("Nifty gains 120 pounds"), [])


class Sections(unittest.TestCase):
    def setUp(self):
        self.lex = mini()

    def test_home_is_primary_and_first(self):
        self.assertEqual(self.lex.sections_for("A quiet day", "markets"), ("markets", ["markets"]))

    def test_strong_phrase_adds_section_in_canonical_order(self):
        primary, sections = self.lex.sections_for("Acme bets on AI", "markets")
        self.assertEqual(primary, "markets")
        self.assertEqual(sections, ["markets", "ai", "companies"])

    def test_one_weak_phrase_is_not_enough(self):
        self.assertEqual(self.lex.sections_for("Bonds wobble", "companies")[1], ["companies"])

    def test_two_weak_phrases_add_a_section(self):
        self.assertEqual(self.lex.sections_for("Bonds and yields wobble", "companies")[1],
                         ["companies", "markets"])

    def test_one_weak_phrase_counts_from_an_adjacent_home(self):
        self.assertEqual(self.lex.sections_for("A new robot", "companies")[1], ["companies", "ai"])
        self.assertEqual(self.lex.sections_for("A new robot", "world")[1], ["world"])

    def test_entity_sections_are_strong_hints(self):
        self.assertEqual(self.lex.sections_for("Bank Nifty slips", "companies")[1],
                         ["companies", "india-markets"])

    def test_generic_home_gives_way_to_a_strong_specific_desk(self):
        self.assertEqual(self.lex.sections_for("Acme, the chipmaker, grows", "world"),
                         ("companies", ["companies", "world"]))

    def test_specific_home_is_never_displaced(self):
        self.assertEqual(self.lex.sections_for("Acme, the chipmaker, uses AI", "ai")[0], "ai")

    def test_generic_home_keeps_stories_where_its_own_evidence_is_as_strong(self):
        self.assertEqual(self.lex.sections_for("Astronomers back Acme", "science")[0], "science")

    def test_people_and_places_do_not_move_the_primary_desk(self):
        primary, sections = self.lex.sections_for("Jane Roe visits", "world")
        self.assertEqual((primary, sections), ("world", ["world", "markets"]))

    def test_tie_goes_to_the_desk_mentioned_first(self):
        self.assertEqual(self.lex.sections_for("Acme rises in the stock market", "world")[0], "companies")
        self.assertEqual(self.lex.sections_for("In the stock market, Acme rises", "world")[0], "markets")

    def test_overlapping_phrases_of_one_desk_count_once(self):
        # "AI agent" (llm) contains "AI" (ai): both desks get it, but within a desk it is one signal.
        self.assertEqual(self.lex.sections_for("An AI agent books flights", "world"),
                         ("ai", ["ai", "world", "llm"]))

    def test_weak_phrase_inside_a_longer_phrase_is_not_evidence(self):
        self.assertEqual(self.lex.sections_for("Indian equities and bonds rise", "india-markets")[1],
                         ["india-markets"])

    def test_words_inside_a_longer_name_are_not_evidence(self):
        self.assertEqual(self.lex.sections_for("Italy evacuates schools, The Times of India reports", "world")[1],
                         ["world"])
        self.assertEqual(self.lex.sections_for("Floods in India", "world")[1], ["world", "india"])

    def test_given_entity_ids_are_used_for_hints(self):
        self.assertEqual(self.lex.sections_for("A quiet day", "world", ["acme"]), ("companies", ["companies", "world"]))

    def test_unknown_home_or_entity_is_an_error(self):
        with self.assertRaises(ValueError):
            self.lex.sections_for("text", "sports")
        with self.assertRaises(ValueError):
            self.lex.sections_for("text", "world", ["no-such-entity"])


class Lookups(unittest.TestCase):
    def setUp(self):
        self.lex = mini()

    def test_expand_term_lists_every_group_member(self):
        self.assertEqual(self.lex.expand_term("LLM"), ["llm", "large language model", "language model"])
        self.assertEqual(self.lex.expand_term("  Layoffs "), ["layoffs", "job cuts", "redundancies"])

    def test_expand_term_falls_back_to_the_singular(self):
        self.assertEqual(self.lex.expand_term("LLMs"), ["llms", "llm", "large language model", "language model"])

    def test_expand_term_without_synonyms(self):
        self.assertEqual(self.lex.expand_term("Quantum"), ["quantum"])
        self.assertEqual(self.lex.expand_term("   "), [])

    def test_entity_returns_a_copy(self):
        found = self.lex.entity("apple")
        self.assertEqual(found["ticker"], "AAPL")
        found["aliases"].append("Pear")
        self.assertNotIn("Pear", self.lex.entity("apple")["aliases"])
        self.assertIsNone(self.lex.entity("nope"))

    def test_ticker_map(self):
        self.assertEqual(self.lex.ticker_map(), {
            "AAPL": "apple", "^NSEI": "nifty-50", "^NSEBANK": "bank-nifty", "DRREDDY.NS": "dr-reddys",
            "ACME": "acme"})

    def test_export_public_shape(self):
        public = self.lex.export_public()
        self.assertEqual(sorted(public), ["aliases", "entities", "glossary"])
        self.assertEqual(public["aliases"]["llm"], ["large language model", "language model"])
        self.assertEqual(public["aliases"]["job cuts"], ["layoffs"])
        self.assertEqual(public["entities"]["apple"], {
            "name": "Apple", "type": "company", "aliases": ["Apple", "Apple Inc", "AAPL"],
            "related": ["iphone"], "ticker": "AAPL"})
        self.assertEqual(public["glossary"], {
            "repo rate": "The rate at which the central bank lends to banks overnight."})
        json.dumps(public)  # must be serialisable as is

    def test_export_does_not_share_lists_with_the_lexicon(self):
        public = self.lex.export_public()
        public["entities"]["apple"]["aliases"].clear()
        public["aliases"]["llm"].clear()
        self.assertTrue(self.lex.entity("apple")["aliases"])
        self.assertEqual(self.lex.expand_term("llm")[1], "large language model")


class Validation(unittest.TestCase):
    def problems(self, mutate):
        data = mini_data()
        mutate(data)
        return lexicon.validate(data, SECTIONS)

    def assertProblem(self, mutate, fragment):
        found = self.problems(mutate)
        self.assertTrue(any(fragment in problem for problem in found), found)

    def test_mini_lexicon_is_valid(self):
        self.assertEqual(lexicon.validate(mini_data(), SECTIONS), [])

    def test_duplicate_id(self):
        self.assertProblem(lambda d: d["entities"].append(copy.deepcopy(d["entities"][0])), "duplicate id")

    def test_id_must_be_kebab_case(self):
        self.assertProblem(lambda d: entity_by_id(d, "acme").update(id="Acme_Corp"), "kebab-case")

    def test_unknown_related_id(self):
        self.assertProblem(lambda d: entity_by_id(d, "acme")["related"].append("ghost"), "related id 'ghost'")

    def test_unknown_section(self):
        self.assertProblem(lambda d: entity_by_id(d, "acme")["sections"].append("sport"), "unknown section 'sport'")

    def test_unknown_type(self):
        self.assertProblem(lambda d: entity_by_id(d, "acme").update(type="fruit"), "unknown type")

    def test_alias_shared_by_two_entities(self):
        self.assertProblem(lambda d: entity_by_id(d, "gpu")["aliases"].append("ACME"),
                           "entity acme: alias 'Acme' already belongs to gpu")

    def test_gated_alias_may_be_shared(self):
        self.assertEqual(self.problems(lambda d: None), [])  # "Congress" is gated on two entities

    def test_gated_word_must_be_an_alias_and_have_context(self):
        self.assertProblem(lambda d: entity_by_id(d, "apple")["gated"].append("Pear"), "not one of its aliases")
        self.assertProblem(lambda d: entity_by_id(d, "apple").update(context=[]), "need context")

    def test_gating_needs_ambiguous(self):
        self.assertProblem(lambda d: entity_by_id(d, "apple").update(ambiguous=False), "only ambiguous")

    def test_duplicate_ticker(self):
        self.assertProblem(lambda d: entity_by_id(d, "gpu").update(ticker="AAPL"), "ticker AAPL already used")

    def test_synonyms_must_be_lowercase_groups(self):
        self.assertProblem(lambda d: d["synonyms"].append(["EV", "electric car"]), "lowercase")
        self.assertProblem(lambda d: d["synonyms"].append(["alone"]), "at least two")

    def test_every_section_needs_a_rule(self):
        self.assertProblem(lambda d: d["sectionRules"].pop("science"), "no rule for 'science'")
        self.assertProblem(lambda d: d["sectionRules"]["ai"].update(adjacent=["sport"]), "bad adjacent")
        self.assertProblem(lambda d: d["sectionRules"]["ai"]["weak"].append("AI"), "both strong and weak")

    def test_glossary_terms(self):
        self.assertProblem(lambda d: d["glossary"].append(copy.deepcopy(d["glossary"][0])), "duplicate term")
        self.assertProblem(lambda d: d["glossary"][0].update(section="sport"), "unknown section")
        self.assertProblem(lambda d: d["glossary"][0].update(definition="Short."), "definition")

    def test_unknown_keys(self):
        self.assertProblem(lambda d: d.update(extra=1), "unknown top-level keys")
        self.assertProblem(lambda d: entity_by_id(d, "acme").update(colour="red"), "unknown keys colour")

    def test_constructor_raises_config_error_listing_problems(self):
        data = mini_data()
        entity_by_id(data, "acme")["related"].append("ghost")
        with self.assertRaises(config.ConfigError) as caught:
            lexicon.Lexicon(data, SECTIONS)
        self.assertIn("ghost", str(caught.exception))


class Loading(unittest.TestCase):
    def setUp(self):
        lexicon._cache.clear()
        self.addCleanup(lexicon._cache.clear)

    def fake_config(self, lexicon_data):
        site = {"sections": [{"id": section, "name": section} for section in SECTIONS]}
        files = {"site": site, "lexicon": lexicon_data}
        calls = []

        def load(name):
            calls.append(name)
            return files[name]

        patcher = mock.patch.object(config, "load", side_effect=load)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def test_load_is_cached(self):
        calls = self.fake_config(mini_data())
        first = lexicon.load()
        self.assertIs(lexicon.load(), first)
        self.assertEqual(calls, ["site", "lexicon"])

    def test_module_functions_use_the_cached_lexicon(self):
        self.fake_config(mini_data())
        self.assertEqual(lexicon.match_entities("Acme rises"), ["acme"])
        self.assertEqual(lexicon.sections_for("Acme rises", "markets"), ("markets", ["markets", "companies"]))
        self.assertEqual(lexicon.expand_term("ev"), ["ev", "electric vehicle"])
        self.assertEqual(lexicon.entity("acme")["name"], "Acme")
        self.assertEqual(lexicon.ticker_map()["ACME"], "acme")
        self.assertIn("acme", lexicon.export_public()["entities"])

    def test_invalid_config_raises_and_is_not_cached(self):
        data = mini_data()
        data["entities"][0]["related"] = ["ghost"]
        self.fake_config(data)
        with self.assertRaises(config.ConfigError):
            lexicon.load()
        self.assertEqual(lexicon._cache, {})


if __name__ == "__main__":
    unittest.main()
