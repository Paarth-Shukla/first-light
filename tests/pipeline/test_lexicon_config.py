"""config/lexicon.json as shipped: valid, broad enough, accurate tickers, and right on real headlines.

Headlines live in tests/fixtures/lexicon/headlines.json (mostly real titles from
2026-11-11 feeds plus ambiguity traps). Each fixture row is its own subTest, so a
failure names the headline.
"""

import json
import time
import unittest
from pathlib import Path

from pipeline import lexicon
from pipeline.core import config

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "lexicon"

# Symbols verified live on Yahoo Finance on 2026-11-11 (docs/research/sources-2026-11-11.json, market-data).
VERIFIED_SYMBOLS = (
    "^GSPC ^IXIC ^DJI ^NSEI ^BSESN ^NSEBANK ^FTSE ^N225 ^HSI TSLA NVDA AAPL MSFT GOOGL AMZN META AMD P "
    "RELIANCE.NS TCS.NS INFY.NS HDFCBANK.NS ICICIBANK.NS TMPV.NS TMCV.NS USDINR=X EURUSD=X GC=F CL=F BTC-USD "
    "ETH-USD BZ=F").split()
# Symbols the same research found dead; they must not be used as tickers.
DEAD_SYMBOLS = ("PSTG", "TATAMOTORS.NS")


def setUpModule():
    lexicon._cache.clear()


def raw_config():
    return config.load("lexicon")


def section_ids():
    return [section["id"] for section in config.load("site")["sections"]]


class ConfigIsValid(unittest.TestCase):
    def test_validate_reports_nothing(self):
        self.assertEqual(lexicon.validate(raw_config(), section_ids()), [])

    def test_ids_are_unique(self):
        ids = [entity["id"] for entity in raw_config()["entities"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_related_id_and_section_exists(self):
        data = raw_config()
        ids = {entity["id"] for entity in data["entities"]}
        sections = set(section_ids())
        for entity in data["entities"]:
            self.assertLessEqual(set(entity["related"]), ids, entity["id"])
            self.assertLessEqual(set(entity["sections"]), sections, entity["id"])
        for entry in data["glossary"]:
            self.assertIn(entry["section"], sections, entry["term"])
        self.assertEqual(set(data["sectionRules"]), sections)

    def test_no_alias_names_two_ordinary_entities(self):
        owners = {}
        for entity in raw_config()["entities"]:
            if entity["ambiguous"]:
                continue
            for alias in entity["aliases"]:
                key = " ".join(lexicon._alias_tokens(alias)[1])
                self.assertIn(owners.setdefault(key, entity["id"]), (entity["id"],),
                              "%r is an alias of %s and %s" % (alias, owners[key], entity["id"]))

    def test_size(self):
        data = raw_config()
        self.assertGreaterEqual(len(data["entities"]), 320)
        self.assertGreaterEqual(len(data["synonyms"]), 120)
        self.assertGreaterEqual(len(data["glossary"]), 160)

    def test_ambiguous_names_from_the_brief_are_gated(self):
        data = {entity["id"]: entity for entity in raw_config()["entities"]}
        for entity_id, word in (("apple", "Apple"), ("meta", "Meta"), ("amazon", "Amazon"), ("intel", "Intel"),
                                ("gemini", "Gemini"), ("claude", "Claude"), ("llama", "Llama"),
                                ("mistral", "Mistral"), ("nifty-50", "Nifty"), ("federal-reserve", "Fed")):
            with self.subTest(entity_id):
                self.assertTrue(data[entity_id]["ambiguous"])
                self.assertIn(word, data[entity_id]["gated"])


class Coverage(unittest.TestCase):
    def setUp(self):
        self.lex = lexicon.load()

    def test_brief_entities_exist(self):
        for entity_id in (
                "openai", "chatgpt", "gpt", "sora", "sam-altman", "anthropic", "claude", "claude-code",
                "dario-amodei", "google-deepmind", "gemini", "demis-hassabis", "meta-ai", "llama", "xai", "grok",
                "mistral", "microsoft", "copilot", "nvidia", "jensen-huang", "hugging-face", "deepseek", "qwen",
                "alibaba", "cohere", "perplexity", "cursor", "transformer", "diffusion-models", "rag", "ai-agents",
                "mcp", "fine-tuning", "lora", "quantization", "evals", "benchmarks", "reasoning-models",
                "context-window", "alignment", "interpretability", "gpu", "inference", "open-weights", "tesla",
                "spacex", "starlink", "starship", "elon-musk", "neuralink", "boring-company", "apple", "google",
                "amazon", "meta", "tsmc", "intel", "amd", "qualcomm", "arm", "asml", "samsung", "sk-hynix",
                "micron", "broadcom", "risc-v", "nasa", "isro", "blue-origin", "esa", "rocket-lab", "artemis",
                "gaganyaan", "chandrayaan", "everpure", "netapp", "dell", "snowflake", "databricks", "aws",
                "azure", "google-cloud", "sp-500", "nasdaq", "dow-jones", "ftse-100", "nikkei", "hang-seng",
                "federal-reserve", "ecb", "jerome-powell", "us-treasuries", "brent-crude", "gold", "bitcoin",
                "ethereum", "nifty-50", "sensex", "bank-nifty", "nse", "bse", "rbi", "sebi", "repo-rate", "fii",
                "dii", "rupee", "reliance", "tcs", "infosys", "hdfc-bank", "icici-bank", "sbi", "bharti-airtel",
                "itc", "larsen-toubro", "tata-motors", "tata-motors-pv", "tata-steel", "adani-group", "wipro",
                "hcltech", "bajaj-finance", "maruti-suzuki", "mahindra", "eternal", "paytm", "ola-electric", "un",
                "nato", "eu", "who", "imf", "world-bank", "g20", "brics"):
            with self.subTest(entity_id):
                self.assertIsNotNone(self.lex.entity(entity_id))

    def test_brief_synonym_groups(self):
        for term, synonym in (("llm", "large language model"), ("ev", "electric vehicle"),
                              ("rate cut", "monetary easing"), ("layoffs", "redundancies"),
                              ("ipo", "initial public offering"), ("chip", "semiconductor"),
                              ("gpu", "graphics card"), ("earnings", "quarterly results"),
                              ("acquisition", "takeover"), ("f&o", "futures and options")):
            with self.subTest(term):
                self.assertIn(synonym, self.lex.expand_term(term))

    def test_brief_glossary_terms(self):
        glossary = {term.lower() for term in self.lex.export_public()["glossary"]}
        for term in ("f&o", "fii", "dii", "repo rate", "crr", "circuit limit", "bhavcopy", "t+1 settlement",
                     "asm", "gmp", "retrieval-augmented generation", "hbm", "euv lithography", "basis point"):
            with self.subTest(term):
                self.assertIn(term, glossary)

    def test_glossary_spans_the_four_areas(self):
        by_section = {}
        for entry in raw_config()["glossary"]:
            by_section[entry["section"]] = by_section.get(entry["section"], 0) + 1
        for section, minimum in (("ai", 5), ("ml", 20), ("llm", 20), ("companies", 25), ("markets", 30),
                                 ("india-markets", 40)):
            with self.subTest(section):
                self.assertGreaterEqual(by_section.get(section, 0), minimum)


class Tickers(unittest.TestCase):
    def setUp(self):
        self.tickers = lexicon.load().ticker_map()

    def test_every_verified_market_symbol_maps_to_an_entity(self):
        for symbol in VERIFIED_SYMBOLS:
            with self.subTest(symbol):
                self.assertIn(symbol, self.tickers)

    def test_known_joins(self):
        expected = {"TSLA": "tesla", "RELIANCE.NS": "reliance", "^NSEI": "nifty-50", "^BSESN": "sensex",
                    "^NSEBANK": "bank-nifty", "P": "everpure", "TMPV.NS": "tata-motors-pv",
                    "TMCV.NS": "tata-motors", "USDINR=X": "rupee", "BZ=F": "brent-crude", "GC=F": "gold",
                    "^GSPC": "sp-500", "M&M.NS": "mahindra", "ETERNAL.NS": "eternal"}
        for symbol, entity_id in expected.items():
            with self.subTest(symbol):
                self.assertEqual(self.tickers.get(symbol), entity_id)

    def test_dead_symbols_are_not_used(self):
        for symbol in DEAD_SYMBOLS:
            self.assertNotIn(symbol, self.tickers)

    def test_symbols_look_like_yahoo_symbols(self):
        for symbol in self.tickers:
            with self.subTest(symbol):
                self.assertRegex(symbol, r"\A[\^]?[A-Z0-9&.\-]+(=X|=F)?\Z")


class OtherConfigsAgree(unittest.TestCase):
    """Other stages name lexicon ids and sections; a rename here must not silently break their joins."""

    def test_markets_config_entities_exist(self):
        try:
            markets = config.load("markets")
        except config.ConfigError as err:
            self.skipTest("config/markets.json not readable: %s" % err)
        lex = lexicon.load()
        for symbol, entity_id in _symbol_entities(markets):
            with self.subTest(symbol):
                self.assertIsNotNone(lex.entity(entity_id), "%s names unknown entity %r" % (symbol, entity_id))

    def test_source_home_sections_are_accepted(self):
        try:
            sources = config.load("sources").get("sources", [])
        except config.ConfigError as err:
            self.skipTest("config/sources.json not readable: %s" % err)
        lex = lexicon.load()
        for source in sources:
            with self.subTest(source.get("id")):
                self.assertEqual(lex.sections_for("", source["section"]), (source["section"], [source["section"]]))


def _symbol_entities(node):
    """Every (symbol, entity) pair in a config tree, wherever the markets config nests its quotes."""
    if isinstance(node, dict):
        if isinstance(node.get("symbol"), str) and node.get("entity"):
            yield node["symbol"], node["entity"]
        for value in node.values():
            yield from _symbol_entities(value)
    elif isinstance(node, list):
        for value in node:
            yield from _symbol_entities(value)


class Headlines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIXTURES / "headlines.json", encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        cls.lex = lexicon.load()

    def test_fixture_is_substantial(self):
        self.assertGreaterEqual(len(self.fixture["entities"]), 60)
        self.assertGreaterEqual(len(self.fixture["sections"]), 20)

    def test_entities(self):
        for case in self.fixture["entities"]:
            with self.subTest(case["text"]):
                found = self.lex.match_entities(case["text"])
                for entity_id in case["expect"]:
                    self.assertIn(entity_id, found)
                for entity_id in case["forbid"]:
                    self.assertNotIn(entity_id, found)
                self.assertEqual(len(found), len(set(found)))

    def test_sections(self):
        for case in self.fixture["sections"]:
            with self.subTest(case["text"]):
                primary, sections = self.lex.sections_for(case["text"], case["home"])
                self.assertEqual(primary, case["primary"])
                self.assertEqual(sections[0], primary)
                for section in case["include"]:
                    self.assertIn(section, sections)
                for section in case["exclude"]:
                    self.assertNotIn(section, sections)

    def test_passing_entity_ids_gives_the_same_answer(self):
        for case in self.fixture["sections"]:
            with self.subTest(case["text"]):
                ids = self.lex.match_entities(case["text"])
                self.assertEqual(self.lex.sections_for(case["text"], case["home"], ids),
                                 self.lex.sections_for(case["text"], case["home"]))


class Speed(unittest.TestCase):
    def test_ten_thousand_titles_per_second(self):
        lex = lexicon.load()
        with open(FIXTURES / "headlines.json", encoding="utf-8") as handle:
            titles = [case["text"] for case in json.load(handle)["entities"]]
        batch = (titles * (10000 // len(titles) + 1))[:10000]
        best = min(self._time(lex.match_entities, batch) for _ in range(3))
        self.assertLess(best, 1.0, "10,000 titles took %.2fs" % best)

    def test_sections_for_keeps_up(self):
        lex = lexicon.load()
        batch = ["Nvidia's GPUs power OpenAI's new data centre as Sensex rallies"] * 10000
        best = min(self._time(lambda text: lex.sections_for(text, "world"), batch) for _ in range(3))
        self.assertLess(best, 2.0, "10,000 section lookups took %.2fs" % best)

    @staticmethod
    def _time(function, batch):
        started = time.perf_counter()
        for text in batch:
            function(text)
        return time.perf_counter() - started


if __name__ == "__main__":
    unittest.main()
