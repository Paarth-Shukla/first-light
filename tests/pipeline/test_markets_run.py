"""pipeline.markets end to end: fallback chain, throttling, stale cache, movers and config.

The network is replaced by a router over the saved real responses in
tests/fixtures/markets; two tests drive the real ``net.fetch`` against a
loopback server to check what a 429 with a plain-text body does.
"""

import contextlib
import copy
import io
import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from pipeline import markets
from pipeline.core import config, jsonio, net, timeutil

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "markets"
NOW = datetime(2026, 11, 11, 14, 0, tzinfo=timezone.utc)


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def sym(symbol, kind, entity, **alt):
    return {"symbol": symbol, "name": symbol + " name", "short": symbol[:8], "kind": kind,
            "entity": entity, "alt": alt}


CFG = {
    "moverThresholdPct": {"stock": 2.0, "index": 1.0},
    "strip": ["^NSEI", "USDINR=X", "BTC-USD", "NOT-CONFIGURED"],
    "providers": {},
    "groups": [
        {"id": "india", "name": "India", "symbols": [
            sym("^NSEI", "index", "nifty-50", moneycontrol="in;NSX", cnbc=".NSEI"),
            sym("^BSESN", "index", "sensex", moneycontrol="in;SEN")]},
        {"id": "watch-in", "name": "Indian stocks", "symbols": [
            sym("RELIANCE.NS", "stock", "reliance", moneycontrol="RELIANCE")]},
        {"id": "watch-us", "name": "US stocks", "symbols": [
            sym("MSFT", "stock", "microsoft", cnbc="MSFT"), sym("AAPL", "stock", "apple", cnbc="AAPL"),
            sym("PSTG", "stock", None, cnbc="PSTG")]},
        {"id": "fx", "name": "Currencies", "symbols": [
            sym("USDINR=X", "fx", "rupee", frankfurter="USD/INR", cnbc="INR="),
            sym("EURUSD=X", "fx", None, frankfurter="EUR/USD")]},
        {"id": "commodities", "name": "Commodities", "symbols": [sym("BZ=F", "commodity", "oil", cnbc="@LCO.1")]},
        {"id": "crypto", "name": "Crypto", "symbols": [
            sym("BTC-USD", "crypto", "bitcoin", coingecko="bitcoin"),
            sym("ETH-USD", "crypto", "ethereum", coingecko="ethereum")]},
    ],
}

# Every provider answering the way it did on 2026-11-11. Anything unrouted is a 404.
ROUTES = [
    ("/v7/finance/spark", "yahoo-spark.json"),
    ("/chart/AAPL?", "yahoo-chart-aapl.json"),
    ("/chart/PSTG?", "yahoo-chart-pstg.json"),
    ("simple/price", "coingecko-price.json"),
    ("coins/bitcoin/market_chart", "coingecko-chart-bitcoin.json"),
    ("api.frankfurter.dev", "frankfurter-series.json"),
    ("symbol=in%3BSEN&", "moneycontrol-index-sensex.json"),
    ("symbol=RELIANCE&", "moneycontrol-stock-reliance.json"),
    ("quote.cnbc.com", "cnbc-quote.json"),
]

THROTTLED = net.NetError("http", 429, "HTTP 429 Too Many Requests")


class FakeNet:
    """Stands in for ``net.fetch_json``: routes URLs to fixtures or errors and records each request."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, url, **kw):
        self.calls.append(url)
        for needle, result in self.routes:
            if needle in url:
                if isinstance(result, Exception):
                    raise result
                return fixture(result) if isinstance(result, str) else copy.deepcopy(result)
        raise net.NetError("http", 404, "HTTP 404 Not Found", url)

    def hits(self, needle):
        return [url for url in self.calls if needle in url]


def with_routes(*overrides):
    """ROUTES with some entries replaced or added in front (first match wins)."""
    return list(overrides) + ROUTES


class StageTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        timeutil.set_now(NOW)
        self.addCleanup(timeutil.set_now, None)
        net.set_offline(False)
        self.addCleanup(net.set_offline, False)
        self.ctx = config.context(data_dir=self.tmp.name)
        self.stderr = io.StringIO()
        quiet = contextlib.redirect_stderr(self.stderr)
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        polite = mock.patch.object(net, "polite", lambda *args: None)
        polite.start()
        self.addCleanup(polite.stop)

    def refresh(self, routes=ROUTES, cfg=CFG, offline=False):
        net.set_offline(offline)
        self.ctx = config.context(data_dir=self.tmp.name)
        self.ctx.paths.ensure()
        fake = FakeNet(routes)
        with mock.patch.object(net, "fetch_json", fake):
            counts = markets.refresh(self.ctx, copy.deepcopy(cfg))
        return counts, fake

    def published(self):
        return jsonio.read_json(self.ctx.paths.public / "markets.json")

    def quotes(self):
        return {q["symbol"]: q for group in self.published()["groups"] for q in group["quotes"]}

    def cache(self):
        return jsonio.read_json(self.ctx.paths.state / "markets-cache.json")

    def write_latest(self, stories):
        jsonio.write_json(self.ctx.paths.public / "latest.json", {"generatedAt": timeutil.iso(NOW), "stories": stories})


class FallbackChain(StageTestCase):
    def test_every_provider_fills_what_the_previous_one_missed(self):
        counts, fake = self.refresh()
        self.assertEqual(counts["sources"], {"yahoo": 6, "coingecko": 1, "moneycontrol": 2, "cnbc": 1})
        self.assertEqual((counts["fresh"], counts["stale"], counts["missing"]), (10, 0, 1))
        quotes = self.quotes()
        self.assertNotIn("PSTG", quotes)  # renamed: empty on Yahoo, unknown to CNBC
        self.assertEqual(quotes["AAPL"]["price"], 348.51)  # per-symbol chart
        self.assertEqual(quotes["ETH-USD"]["price"], 2051.02)  # CoinGecko
        self.assertEqual(quotes["ETH-USD"]["spark"], [])  # its chart was a 404
        self.assertEqual(quotes["^BSESN"]["price"], 81879.4)  # Moneycontrol index
        self.assertEqual(quotes["RELIANCE.NS"]["currency"], "INR")
        self.assertEqual(quotes["BZ=F"]["price"], 92.93)  # CNBC

    def test_requests_stay_minimal(self):
        _, fake = self.refresh()
        self.assertEqual(len(fake.hits("/v7/finance/spark")), 1)
        charted = sorted(url.split("/chart/")[1].split("?")[0] for url in fake.hits("/v8/finance/chart/"))
        self.assertEqual(charted, sorted(["%5EBSESN", "RELIANCE.NS", "AAPL", "PSTG", "BZ%3DF", "ETH-USD"]))
        self.assertEqual(fake.hits("frankfurter"), [])  # FX was already fresh
        self.assertEqual(len(fake.hits("moneycontrol")), 2)
        cnbc = fake.hits("quote.cnbc.com")
        self.assertEqual(len(cnbc), 1)
        self.assertIn("symbols=PSTG%7C%40LCO.1&", cnbc[0])

    def test_document_shape(self):
        self.refresh()
        doc = self.published()
        self.assertEqual(set(doc), {"generatedAt", "stale", "groups", "strip", "movers"})
        self.assertEqual(doc["generatedAt"], "2026-11-11T14:00:00Z")
        self.assertIs(doc["stale"], False)
        self.assertEqual([g["id"] for g in doc["groups"]],
                         ["india", "watch-in", "watch-us", "fx", "commodities", "crypto"])
        self.assertEqual([q["symbol"] for q in doc["groups"][2]["quotes"]], ["MSFT", "AAPL"])
        self.assertEqual(doc["strip"], ["^NSEI", "USDINR=X", "BTC-USD"])
        for quote in self.quotes().values():
            self.assertEqual(set(quote), {"symbol", "name", "short", "kind", "currency", "price", "change",
                                          "changePct", "spark", "asOf", "exchange", "entity", "high52",
                                          "low52", "stale"})
            self.assertEqual(quote["name"], quote["symbol"] + " name")

    def test_cache_holds_the_last_good_quotes(self):
        self.refresh()
        cache = self.cache()
        self.assertEqual(cache["savedAt"], "2026-11-11T14:00:00Z")
        self.assertEqual(set(cache["quotes"]), set(self.quotes()))
        self.assertEqual(cache["quotes"]["MSFT"], self.quotes()["MSFT"])

    def test_missing_symbols_and_404s_are_reported(self):
        counts, _ = self.refresh()
        problems = " | ".join(counts["problems"])
        self.assertIn("yahoo: chart PSTG: no price", problems)
        self.assertIn("coingecko: chart ethereum: HTTP 404", problems)
        self.assertIn("no data at all for: PSTG", self.stderr.getvalue())

    def test_disabled_provider_is_never_called(self):
        cfg = dict(CFG, providers={"moneycontrol": {"enabled": False}})
        counts, fake = self.refresh(cfg=cfg)
        self.assertEqual(fake.hits("moneycontrol"), [])
        self.assertNotIn("^BSESN", self.quotes())

    def test_garbage_response_is_reported_not_raised(self):
        counts, _ = self.refresh(with_routes(("quote.cnbc.com", {"unexpected": True})))
        self.assertTrue(any("cnbc: quote: unexpected response (KeyError" in p for p in counts["problems"]))
        self.assertNotIn("BZ=F", self.quotes())


class Throttling(StageTestCase):
    def test_a_429_stops_all_yahoo_calls_and_the_fallbacks_take_over(self):
        counts, fake = self.refresh(with_routes(("finance.yahoo.com", THROTTLED)))
        self.assertEqual(len(fake.hits("finance.yahoo.com")), 1)  # no batch 2, no per-symbol charts
        self.assertTrue(any("yahoo: spark: HTTP 429" in p for p in counts["problems"]))
        quotes = self.quotes()
        self.assertEqual(quotes["^NSEI"]["asOf"], "2026-11-11T09:59:54Z")  # Moneycontrol 404, then CNBC
        self.assertEqual(quotes["USDINR=X"]["exchange"], "ECB reference rate")  # Frankfurter
        self.assertEqual(quotes["BTC-USD"]["price"], 73711.0)  # CoinGecko
        self.assertEqual(counts["sources"], {"moneycontrol": 2, "frankfurter": 2, "coingecko": 2, "cnbc": 2})
        self.assertEqual(counts["missing"], 3)  # MSFT AAPL PSTG: no cache yet, not in CNBC's answer
        self.assertIs(self.published()["stale"], False)  # 3 of 11 is not more than half

    def test_a_throttled_fallback_is_not_asked_again(self):
        counts, fake = self.refresh(with_routes(("finance.yahoo.com", THROTTLED), ("moneycontrol", THROTTLED)))
        self.assertEqual(len(fake.hits("moneycontrol")), 1)


class StaleCache(StageTestCase):
    def test_offline_serves_every_cached_quote_marked_stale(self):
        self.refresh()
        before = self.quotes()
        counts, fake = self.refresh(offline=True)
        self.assertEqual(fake.calls, [])
        self.assertEqual((counts["fresh"], counts["stale"], counts["missing"]), (0, 10, 1))
        doc = self.published()
        self.assertIs(doc["stale"], True)
        self.assertEqual(doc["movers"], [])  # yesterday's move is not today's news
        for symbol, quote in self.quotes().items():
            self.assertIs(quote["stale"], True)
            self.assertEqual(dict(quote, stale=False), before[symbol])
        self.assertTrue(all(q["stale"] is False for q in self.cache()["quotes"].values()))

    def test_unrefreshed_symbols_fall_back_to_the_cache(self):
        self.refresh()
        counts, _ = self.refresh(with_routes(("finance.yahoo.com", THROTTLED)))
        quotes = self.quotes()
        self.assertIs(quotes["MSFT"]["stale"], True)
        self.assertEqual(quotes["MSFT"]["price"], 533.16)
        self.assertEqual(counts["missing"], 1)  # PSTG never had data

    def test_a_newer_cached_quote_beats_an_older_fallback_and_the_chain_keeps_looking(self):
        self.refresh()  # cache: Yahoo's live USD/INR (10:03:38Z) and EUR/USD (13:49:29Z)
        counts, fake = self.refresh(with_routes(("finance.yahoo.com", THROTTLED)))
        quotes = self.quotes()
        # Frankfurter's fix (10 Nov) is a day older, so CNBC was asked and had a live rate.
        self.assertIn("INR%3D", fake.hits("quote.cnbc.com")[0])
        rupee = quotes["USDINR=X"]
        self.assertEqual((rupee["price"], rupee["asOf"], rupee["stale"]), (93.69, "2026-11-11T10:03:00Z", False))
        self.assertEqual(rupee["currency"], "INR")  # CNBC has no currency code; filled from cache
        self.assertEqual(len(rupee["spark"]), 23)  # CNBC has no history; cached series reused
        # Nobody but Frankfurter quotes EUR/USD, and its fix is older than the cache.
        self.assertIs(quotes["EURUSD=X"]["stale"], True)
        self.assertEqual(quotes["EURUSD=X"]["price"], 1.1116)

    def test_more_than_half_stale_marks_the_page_stale(self):
        down = [(host, THROTTLED) for host in ("finance.yahoo.com", "moneycontrol", "quote.cnbc.com")]
        counts, _ = self.refresh(with_routes(*down))
        self.assertEqual(counts["fresh"], 4)  # Frankfurter 2, CoinGecko 2
        self.assertIs(self.published()["stale"], True)

    def test_cached_labels_follow_current_config(self):
        self.refresh()
        cfg = copy.deepcopy(CFG)
        cfg["groups"][3]["symbols"][0].update(name="Dollar in rupees", short="USD/INR", entity="inr")
        self.refresh(cfg=cfg, offline=True)
        rupee = self.quotes()["USDINR=X"]
        self.assertEqual((rupee["name"], rupee["short"], rupee["entity"]), ("Dollar in rupees", "USD/INR", "inr"))

    def test_damaged_cache_entries_are_dropped(self):
        path = self.ctx.paths.state / "markets-cache.json"
        jsonio.write_json(path, {"quotes": {"MSFT": {"price": "lots"}, "AAPL": fixture_quote("AAPL")}})
        self.assertEqual(set(markets.read_cache(path)), {"AAPL"})
        path.write_text("{not json", encoding="utf-8")
        self.assertEqual(markets.read_cache(path), {})
        jsonio.write_json(path, ["not", "a", "cache"])
        self.assertEqual(markets.read_cache(path), {})


def fixture_quote(symbol, kind="stock", pct=1.0, entity=None, stale=False):
    spec = {"symbol": symbol, "name": symbol, "short": symbol, "kind": kind, "entity": entity}
    quote = markets.make_quote(spec, 100.0, pct, [99.0, 100.0], NOW)
    quote["stale"] = stale
    return quote


def story(story_id, hours_ago, score, tickers=(), entities=(), updated=True):
    stamp = timeutil.iso(NOW - timedelta(hours=hours_ago))
    item = {"id": story_id, "title": "Title " + story_id, "sourceCount": 3, "score": score,
            "tickers": list(tickers), "entities": list(entities), "publishedAt": stamp}
    if updated:
        item["updatedAt"] = stamp
    return item


class Movers(unittest.TestCase):
    def specs(self, *entries):
        return [dict({"alt": {}, "group": "g", "name": e[0], "short": e[0], "entity": None}, symbol=e[0], kind=e[1],
                     **(e[2] if len(e) > 2 else {})) for e in entries]

    def test_thresholds_by_kind_sorted_by_magnitude(self):
        specs = self.specs(("A", "stock"), ("B", "stock"), ("C", "index"), ("D", "index"), ("E", "fx"),
                           ("F", "crypto"), ("G", "stock"))
        published = {"A": fixture_quote("A", pct=2.0), "B": fixture_quote("B", pct=-1.99),
                     "C": fixture_quote("C", "index", pct=-1.0), "D": fixture_quote("D", "index", pct=0.99),
                     "E": fixture_quote("E", "fx", pct=3.0), "F": fixture_quote("F", "crypto", pct=-9.0),
                     "G": fixture_quote("G", pct=-4.2)}
        movers = markets.find_movers(specs, published, {"stock": 2.0, "index": 1.0}, [], NOW)
        self.assertEqual([(m["symbol"], m["changePct"]) for m in movers], [("G", -4.2), ("A", 2.0), ("C", -1.0)])
        self.assertEqual(set(movers[0]), {"symbol", "name", "changePct", "story"})
        self.assertIsNone(movers[0]["story"])

    def test_stale_opted_out_and_absent_quotes_are_not_movers(self):
        specs = self.specs(("A", "stock"), ("VIX", "index", {"mover": False}), ("GONE", "stock"))
        published = {"A": fixture_quote("A", pct=5.0, stale=True), "VIX": fixture_quote("VIX", "index", pct=8.0)}
        self.assertEqual(markets.find_movers(specs, published, {"stock": 2.0, "index": 1.0}, [], NOW), [])

    def test_at_most_ten(self):
        specs = self.specs(*[("S%d" % n, "stock") for n in range(15)])
        published = {s["symbol"]: fixture_quote(s["symbol"], pct=3.0 + n) for n, s in enumerate(specs)}
        movers = markets.find_movers(specs, published, {"stock": 2.0}, [], NOW)
        self.assertEqual(len(movers), markets.MAX_MOVERS)
        self.assertEqual(movers[0]["symbol"], "S14")

    def test_story_join_prefers_the_highest_score_within_36_hours(self):
        nvda = self.specs(("NVDA", "stock", {"entity": "nvidia"}))[0]
        stories = [story("s-ticker", 2, 60, tickers=["NVDA"]),
                   story("s-entity", 3, 80, entities=["nvidia", "openai"]),
                   story("s-old", 37, 99, entities=["nvidia"]),
                   story("s-future", -2, 99, tickers=["NVDA"]),
                   story("s-other", 1, 100, tickers=["AMD"], entities=["amd"])]
        self.assertEqual(markets.linked_story(nvda, stories, NOW),
                         {"id": "s-entity", "title": "Title s-entity", "sourceCount": 3})
        self.assertEqual(markets.linked_story(nvda, stories[:1], NOW)["id"], "s-ticker")
        self.assertIsNone(markets.linked_story(nvda, stories[2:], NOW))

    def test_indian_tickers_match_with_or_without_the_exchange_suffix(self):
        reliance = self.specs(("RELIANCE.NS", "stock"))[0]
        self.assertEqual(markets.linked_story(reliance, [story("s1", 1, 10, tickers=["reliance"])], NOW)["id"], "s1")
        self.assertEqual(markets.linked_story(reliance, [story("s2", 1, 10, tickers=["RELIANCE.NS"])], NOW)["id"],
                         "s2")
        self.assertIsNone(markets.linked_story(reliance, [story("s3", 1, 10, tickers=["RELIANCEX"])], NOW))

    def test_story_time_falls_back_to_published_at_and_missing_score_counts_as_zero(self):
        spec = self.specs(("TSLA", "stock", {"entity": "tesla"}))[0]
        unscored = story("s-unscored", 30, None, entities=["tesla"], updated=False)
        self.assertEqual(markets.linked_story(spec, [unscored], NOW)["id"], "s-unscored")
        undated = dict(story("s-undated", 1, 50, entities=["tesla"], updated=False), publishedAt=None)
        self.assertIsNone(markets.linked_story(spec, [undated], NOW))


class MoversInTheStage(StageTestCase):
    def test_movers_join_latest_json(self):
        self.write_latest([story("s-msft", 5, 70, tickers=["MSFT"]), "not a story"])
        self.refresh()
        self.assertEqual(self.published()["movers"],
                         [{"symbol": "MSFT", "name": "MSFT name", "changePct": -2.21,
                           "story": {"id": "s-msft", "title": "Title s-msft", "sourceCount": 3}}])

    def test_without_latest_json_movers_have_no_story(self):
        self.refresh()
        self.assertEqual([(m["symbol"], m["story"]) for m in self.published()["movers"]], [("MSFT", None)])

    def test_malformed_latest_json_is_survived(self):
        jsonio.write_json(self.ctx.paths.public / "latest.json", {"stories": "nope"})
        counts, _ = self.refresh()
        self.assertEqual(counts["movers"], 1)
        self.assertIn("has no stories list", self.stderr.getvalue())


class YahooBatches(unittest.TestCase):
    def test_spark_batches_of_twenty_and_charts_stop_at_the_first_429(self):
        specs = markets.load_specs(config.load("markets"))
        session = markets.Session({"yahoo": True})
        fake = FakeNet([("/v7/finance/spark", {"spark": {"result": []}}), ("/v8/finance/chart/", THROTTLED)])
        with mock.patch.object(net, "fetch_json", fake), mock.patch.object(net, "polite", lambda *a: None), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(markets.from_yahoo(session, specs, NOW), {})
        sparks = fake.hits("/v7/finance/spark")
        self.assertEqual(len(sparks), -(-len(specs) // 20))
        for url in sparks:
            self.assertLessEqual(url.split("symbols=")[1].split("&")[0].count(",") + 1, 20)
        self.assertEqual(len(fake.hits("/v8/finance/chart/")), 1)
        self.assertFalse(session.usable("yahoo"))


class SessionErrors(unittest.TestCase):
    def test_a_404_is_about_one_request_anything_else_about_the_provider(self):
        for error, down in ((net.NetError("http", 404, "HTTP 404"), False),
                            (net.NetError("http", 400, "HTTP 400"), False),
                            (net.NetError("http", 429, "HTTP 429"), True),
                            (net.NetError("http", 403, "HTTP 403"), True),
                            (net.NetError("http", 200, "response is not valid JSON"), True),
                            (net.NetError("timeout", None, "timed out"), True),
                            (net.NetError("tls", None, "TLS error"), True)):
            session = markets.Session({"cnbc": True})
            with mock.patch.object(net, "fetch_json", FakeNet([("", error)])), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertIsNone(session.get_json("cnbc", "https://quote.cnbc.com/x", "quote"))
            self.assertEqual(session.usable("cnbc"), not down, error)
            self.assertEqual(len(session.problems), 1)


# --------------------------------------------------------------- real net.fetch against loopback

class _Yahoo(BaseHTTPRequestHandler):
    """Yahoo as seen when it throttles: a 429 (or a 200) with a plain-text body."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        with self.server.lock:
            self.server.hits[self.path.split("?")[0].split("/")[3]] += 1
        body = (FIXTURES / "yahoo-429.txt").read_bytes()
        self.send_response(self.server.status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class PlainTextThrottle(StageTestCase):
    CFG = {"providers": {name: {"enabled": False} for name in markets.FALLBACK_PROVIDERS},
           "groups": [{"id": "watch-us", "name": "US stocks",
                       "symbols": [sym("MSFT", "stock", "microsoft"), sym("AAPL", "stock", "apple")]}]}

    def serve(self, status):
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Yahoo)
        server.status, server.lock = status, threading.Lock()
        server.hits = {"spark": 0, "chart": 0}
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = "http://127.0.0.1:%d" % server.server_address[1]
        for name, value in (("SPARK_URL", base + "/v7/finance/spark?symbols={symbols}&range=1mo&interval=1d"),
                            ("CHART_URL", base + "/v8/finance/chart/{symbol}?range=1mo&interval=1d")):
            patcher = mock.patch.object(markets, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        saved = (net._opener, net._RETRY_429_S)
        net._opener, net._RETRY_429_S = net._build_opener(proxies={}), 0
        self.addCleanup(setattr, net, "_RETRY_429_S", saved[1])
        self.addCleanup(setattr, net, "_opener", saved[0])
        return server

    def run_stage(self):
        self.ctx.paths.ensure()
        jsonio.write_json(self.ctx.paths.state / "markets-cache.json",
                          {"quotes": {"MSFT": fixture_quote("MSFT", entity="microsoft")}})
        return markets.refresh(self.ctx, copy.deepcopy(self.CFG))

    def test_429_gets_one_polite_retry_then_yahoo_is_left_alone(self):
        server = self.serve(429)
        counts = self.run_stage()
        self.assertEqual(server.hits, {"spark": 2, "chart": 0})
        self.assertEqual((counts["stale"], counts["missing"]), (1, 1))
        self.assertIn("yahoo: spark: HTTP 429 Too Many Requests", counts["problems"])
        self.assertIs(self.quotes()["MSFT"]["stale"], True)

    def test_plain_text_with_200_is_a_failure_not_a_crash(self):
        server = self.serve(200)
        counts = self.run_stage()
        self.assertEqual(server.hits, {"spark": 1, "chart": 0})
        self.assertIn("yahoo: spark: response is not valid JSON", counts["problems"])
        self.assertIs(self.published()["stale"], True)  # 1 stale + 1 missing of 2


# --------------------------------------------------------------- config

class Config(unittest.TestCase):
    def test_the_real_config_is_valid_and_matches_the_contract(self):
        cfg = config.load("markets")
        specs = markets.load_specs(cfg)
        self.assertEqual(markets.load_thresholds(cfg), {"stock": 2.0, "index": 1.0})
        self.assertTrue(all(markets.load_enabled(cfg).values()))
        self.assertEqual([g["id"] for g in cfg["groups"]],
                         ["india", "us", "world", "watch-in", "watch-us", "fx", "commodities", "crypto"])
        symbols = {s["symbol"] for s in specs}
        self.assertEqual(cfg["strip"], ["^NSEI", "^BSESN", "^GSPC", "^IXIC", "USDINR=X", "BZ=F", "GC=F", "BTC-USD"])
        self.assertLessEqual(set(cfg["strip"]), symbols)
        for renamed in ("PSTG", "TATAMOTORS.NS"):
            self.assertNotIn(renamed, symbols)
        self.assertLessEqual({"P", "TMPV.NS", "TMCV.NS"}, symbols)
        for spec in specs:
            if spec["entity"] is not None:
                self.assertRegex(spec["entity"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
            if spec["symbol"].endswith(".NS"):
                self.assertEqual(spec["alt"].get("moneycontrol"), spec["symbol"][:-3])

    def bad(self, mutate, message):
        cfg = copy.deepcopy(CFG)
        mutate(cfg)
        with self.assertRaisesRegex(config.ConfigError, message):
            markets.load_specs(cfg)
            markets.load_thresholds(cfg)
            markets.load_enabled(cfg)

    def test_mistakes_name_the_symbol(self):
        first = lambda cfg: cfg["groups"][0]["symbols"][0]  # noqa: E731
        self.bad(lambda cfg: cfg["groups"][1]["symbols"].append(sym("^NSEI", "index", None)), r"\^NSEI is listed twice")
        self.bad(lambda cfg: first(cfg).update(kind="etf"), r"\^NSEI: kind must be one of")
        self.bad(lambda cfg: first(cfg).pop("short"), r"\^NSEI needs a 'short'")
        self.bad(lambda cfg: first(cfg)["alt"].update(stooq="x"), r"bad fallback 'stooq'")
        self.bad(lambda cfg: cfg["groups"][3]["symbols"][0]["alt"].update(frankfurter="USDINR"), "USD/INR")
        self.bad(lambda cfg: first(cfg).update(entity=7), "entity must be a string or null")
        self.bad(lambda cfg: cfg.update(groups=[]), "non-empty list")
        self.bad(lambda cfg: cfg.update(moverThresholdPct={"stock": -1}), "moverThresholdPct")
        self.bad(lambda cfg: cfg.update(providers={"stooq": {"enabled": True}}), "unknown providers stooq")

    def test_bad_config_fails_the_stage_before_any_request(self):
        fake = FakeNet(ROUTES)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(net, "fetch_json", fake):
            ctx = config.context(data_dir=tmp)
            with self.assertRaises(config.ConfigError):
                markets.refresh(ctx, {"groups": []})
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
