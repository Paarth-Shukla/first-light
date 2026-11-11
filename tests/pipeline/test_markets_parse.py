"""Parsers of pipeline.markets against real responses saved on 2026-11-11 (tests/fixtures/markets)."""

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from pipeline import markets

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "markets"
NOW = datetime(2026, 11, 11, 14, 0, tzinfo=timezone.utc)


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def spec(symbol, kind="stock", entity=None, **alt):
    return {"symbol": symbol, "name": symbol + " name", "short": symbol[:6], "kind": kind,
            "entity": entity, "alt": alt, "group": "g"}


CONTRACT_KEYS = {"symbol", "name", "short", "kind", "currency", "price", "change", "changePct", "spark",
                 "asOf", "exchange", "entity", "high52", "low52", "stale"}


class MakeQuote(unittest.TestCase):
    def test_contract_shape_and_names_from_config(self):
        quote = markets.make_quote(spec("TCS.NS", entity="tcs"), 2472.1, -0.13, [2475.4, 2472.1], NOW,
                                   currency="INR", exchange="NSE")
        self.assertEqual(set(quote), CONTRACT_KEYS)
        self.assertEqual((quote["name"], quote["short"], quote["entity"]), ("TCS.NS name", "TCS.NS", "tcs"))
        self.assertEqual(quote["asOf"], "2026-11-11T14:00:00Z")
        self.assertIs(quote["stale"], False)

    def test_change_is_derived_from_price_and_percentage(self):
        quote = markets.make_quote(spec("X"), 110.0, 10.0, [], NOW)
        self.assertEqual(quote["change"], 10.0)

    def test_explicit_change_wins(self):
        quote = markets.make_quote(spec("X"), 110.0, 10.0, [], NOW, change=9.99)
        self.assertEqual(quote["change"], 9.99)

    def test_fx_below_ten_keeps_four_decimals_everything_else_two(self):
        fx = markets.make_quote(spec("EURUSD=X", "fx"), 1.111649, -0.4558, [1.122249, 1.111649], NOW)
        self.assertEqual((fx["price"], fx["spark"]), (1.1116, [1.1222, 1.1116]))
        self.assertEqual(fx["changePct"], -0.46)
        rupee = markets.make_quote(spec("USDINR=X", "fx"), 93.6812, -0.2534, [], NOW)
        self.assertEqual(rupee["price"], 93.68)
        cheap_stock = markets.make_quote(spec("PENNY"), 1.23456, 1.0, [], NOW)
        self.assertEqual(cheap_stock["price"], 1.23)

    def test_negative_zero_is_not_published(self):
        quote = markets.make_quote(spec("META"), 641.39, -0.001, [], NOW)
        self.assertEqual(json.dumps(quote["changePct"]), "0.0")

    def test_spark_drops_non_numbers_and_keeps_the_last_32(self):
        closes = [float(n) for n in range(40)] + [None, float("nan"), True, 41.0]
        quote = markets.make_quote(spec("X"), 41.0, 1.0, closes, NOW)
        self.assertEqual(len(quote["spark"]), 32)
        self.assertEqual(quote["spark"][-2:], [39.0, 41.0])

    def test_unusable_numbers_give_no_quote(self):
        for price, pct, as_of in ((None, 1.0, NOW), (0, 1.0, NOW), (-5.0, 1.0, NOW), (float("inf"), 1.0, NOW),
                                  (10.0, None, NOW), (10.0, -100.0, NOW), (10.0, 1.0, None), ("10", 1.0, NOW)):
            self.assertIsNone(markets.make_quote(spec("X"), price, pct, [], as_of), (price, pct, as_of))

    def test_zero_52_week_bound_means_unknown(self):
        quote = markets.make_quote(spec("BZ=F", "commodity"), 92.93, 1.57, [], NOW, high52=126.41, low52=0.0)
        self.assertEqual((quote["high52"], quote["low52"]), (126.41, None))


class Numbers(unittest.TestCase):
    def test_cnbc_formatted_strings(self):
        self.assertEqual(markets._number("25,255.05"), 25255.05)
        self.assertEqual(markets._number("+1,051.15"), 1051.15)
        self.assertEqual(markets._number("-0.2529%"), -0.2529)
        self.assertEqual(markets._number("$346.48"), 346.48)
        self.assertEqual(markets._number(12), 12.0)
        for junk in (None, "", "UNCH", "nan", "inf", [], True):
            self.assertIsNone(markets._number(junk), junk)


class YahooSpark(unittest.TestCase):
    def setUp(self):
        self.specs = [spec("^NSEI", "index", "nifty-50"), spec("MSFT", entity="microsoft"),
                      spec("USDINR=X", "fx"), spec("EURUSD=X", "fx"), spec("BTC-USD", "crypto"), spec("PSTG"),
                      spec("NOT-ASKED-FOR")]
        self.quotes = markets.parse_spark(fixture("yahoo-spark.json"), self.specs)

    def test_results_are_keyed_by_symbol_and_the_renamed_symbol_is_absent(self):
        # The fixture's results are in a different order from the request, like the real API.
        self.assertEqual(set(self.quotes), {"^NSEI", "MSFT", "USDINR=X", "EURUSD=X", "BTC-USD"})

    def test_index_quote(self):
        nifty = self.quotes["^NSEI"]
        self.assertEqual((nifty["price"], nifty["changePct"], nifty["currency"]), (25255.05, 0.84, "INR"))
        self.assertEqual(nifty["asOf"], "2026-11-11T10:01:28Z")  # regularMarketTime
        self.assertEqual((nifty["high52"], nifty["low52"], nifty["exchange"]), (26373.2, 22179.9, "NSE"))
        self.assertEqual(len(nifty["spark"]), 21)
        self.assertEqual(nifty["spark"][-2:], [25044.65, 25255.05])
        self.assertEqual(nifty["entity"], "nifty-50")

    def test_same_session_fullday_change_is_used_exactly(self):
        # Derived from the rounded 0.84% it would be 210.38; Yahoo's fulldayChange is the true 210.40.
        self.assertEqual(self.quotes["^NSEI"]["change"], 210.4)

    def test_premarket_fullday_change_is_ignored(self):
        # MSFT's fullday fields describe pre-market (+3.36); the regular session fell 2.2%.
        msft = self.quotes["MSFT"]
        self.assertEqual(msft["price"], 533.16)
        self.assertEqual(msft["change"], -12.02)
        self.assertAlmostEqual(msft["changePct"], -2.205, delta=0.006)
        self.assertEqual(msft["asOf"], "2026-11-10T21:00:01Z")

    def test_fx_precision(self):
        self.assertEqual(self.quotes["EURUSD=X"]["price"], 1.1116)
        self.assertEqual(self.quotes["EURUSD=X"]["change"], -0.0051)
        self.assertEqual(self.quotes["USDINR=X"]["price"], 93.68)

    def test_crypto_spark_is_capped_at_32_points(self):
        self.assertEqual(len(self.quotes["BTC-USD"]["spark"]), 32)

    def test_change_pct_falls_back_to_the_last_two_closes(self):
        payload = fixture("yahoo-spark.json")
        for item in payload["spark"]["result"]:
            item["response"][0]["meta"].pop("regularMarketChangePercent", None)
        nifty = markets.parse_spark(payload, self.specs)["^NSEI"]
        self.assertEqual(nifty["changePct"], round((25255.05 / 25044.65 - 1) * 100, 2))

    def test_null_closes_are_skipped(self):
        payload = fixture("yahoo-spark.json")
        block = next(r for r in payload["spark"]["result"] if r["symbol"] == "^NSEI")["response"][0]
        block["indicators"]["quote"][0]["close"][3] = None
        self.assertEqual(len(markets.parse_spark(payload, self.specs)["^NSEI"]["spark"]), 20)

    def test_empty_result(self):
        self.assertEqual(markets.parse_spark({"spark": {"result": None, "error": None}}, self.specs), {})

    def test_url_encodes_carets_and_equals_but_not_commas(self):
        url = markets.spark_url(["^NSEI", "USDINR=X", "BZ=F", "BTC-USD"])
        self.assertIn("symbols=%5ENSEI,USDINR%3DX,BZ%3DF,BTC-USD&range=1mo&interval=1d", url)


class YahooChart(unittest.TestCase):
    def test_chart_with_float_noise(self):
        quote = markets.parse_chart(fixture("yahoo-chart-aapl.json"), spec("AAPL", entity="apple"))
        self.assertEqual((quote["price"], quote["change"], quote["currency"]), (348.51, -2.18, "USD"))
        self.assertEqual(quote["spark"][-2:], [350.69, 348.51])  # 350.69000244140625 in the payload
        self.assertEqual(len(quote["spark"]), 22)
        self.assertEqual(quote["asOf"], "2026-11-10T21:00:00Z")

    def test_renamed_symbol_has_meta_but_no_data(self):
        self.assertIsNone(markets.parse_chart(fixture("yahoo-chart-pstg.json"), spec("PSTG")))

    def test_delisted_error_body(self):
        body = {"chart": {"result": None, "error": {"code": "Not Found",
                                                    "description": "No data found, symbol may be delisted"}}}
        self.assertIsNone(markets.parse_chart(body, spec("TATAMOTORS.NS")))

    def test_url_encodes_the_symbol(self):
        self.assertIn("/chart/%5ENSEI?range=1mo", markets.chart_url("^NSEI"))
        self.assertIn("/chart/USDINR%3DX?", markets.chart_url("USDINR=X"))


class CoinGecko(unittest.TestCase):
    def test_price_with_and_without_chart(self):
        specs = [spec("BTC-USD", "crypto", coingecko="bitcoin"), spec("ETH-USD", "crypto", coingecko="ethereum")]
        charts = {"bitcoin": fixture("coingecko-chart-bitcoin.json")}
        quotes = markets.parse_coingecko(fixture("coingecko-price.json"), charts, specs)
        btc, eth = quotes["BTC-USD"], quotes["ETH-USD"]
        self.assertEqual((btc["price"], btc["changePct"], btc["currency"]), (73711.0, -0.27, "USD"))
        self.assertEqual(btc["asOf"], "2026-11-11T13:49:46Z")  # last_updated_at 1794404986, epoch seconds
        prices = charts["bitcoin"]["prices"]
        self.assertEqual(len(btc["spark"]), min(32, len(prices)))
        self.assertEqual(btc["spark"][-1], round(prices[-1][1], 2))
        self.assertEqual(eth["spark"], [])
        self.assertEqual(eth["price"], 2051.02)

    def test_coin_missing_from_the_price_response(self):
        quotes = markets.parse_coingecko({}, {}, [spec("BTC-USD", "crypto", coingecko="bitcoin")])
        self.assertEqual(quotes, {})


class Frankfurter(unittest.TestCase):
    def setUp(self):
        self.specs = [spec("USDINR=X", "fx", frankfurter="USD/INR"), spec("EURUSD=X", "fx", frankfurter="EUR/USD"),
                      spec("GBPINR=X", "fx", frankfurter="GBP/INR")]
        self.quotes = markets.parse_frankfurter(fixture("frankfurter-series.json"), self.specs)

    def test_direct_rate(self):
        rupee = self.quotes["USDINR=X"]
        # The ECB really did fix USD/INR at 93.93 on both 9 and 10 November.
        self.assertEqual((rupee["price"], rupee["changePct"], rupee["currency"]), (93.93, 0.0, "INR"))
        self.assertEqual(rupee["asOf"], "2026-11-10T15:00:00Z")
        self.assertEqual(len(rupee["spark"]), 32)
        self.assertEqual(rupee["exchange"], "ECB reference rate")

    def test_inverted_rate_keeps_four_decimals(self):
        euro = self.quotes["EURUSD=X"]
        self.assertEqual(euro["price"], round(1 / 0.89174, 4))
        self.assertEqual(euro["changePct"], round((0.89342 / 0.89174 - 1) * 100, 2))
        self.assertEqual(euro["currency"], "USD")

    def test_cross_rate(self):
        self.assertEqual(self.quotes["GBPINR=X"]["price"], round(93.93 / 0.74501, 2))

    def test_wrong_base_is_an_error(self):
        payload = dict(fixture("frankfurter-series.json"), base="EUR")
        with self.assertRaises(ValueError):
            markets.parse_frankfurter(payload, self.specs)

    def test_currency_missing_from_the_series(self):
        self.assertEqual(markets.parse_frankfurter(fixture("frankfurter-series.json"),
                                                   [spec("USDJPY=X", "fx", frankfurter="USD/JPY")]), {})


class Moneycontrol(unittest.TestCase):
    def test_stock_history(self):
        quote = markets.parse_moneycontrol(fixture("moneycontrol-stock-reliance.json"),
                                           spec("RELIANCE.NS", moneycontrol="RELIANCE"), NOW)
        self.assertEqual((quote["price"], quote["change"], quote["changePct"]), (1335.4, 11.0, 0.83))
        self.assertEqual((quote["currency"], quote["exchange"]), ("INR", "NSE"))
        self.assertEqual(len(quote["spark"]), 26)
        # The last bar is stamped 05:30 UTC; that is a date label. The close is 15:30 IST.
        self.assertEqual(quote["asOf"], "2026-11-11T10:00:00Z")

    def test_as_of_is_now_while_the_session_is_open(self):
        morning = datetime(2026, 11, 11, 6, 15, tzinfo=timezone.utc)
        quote = markets.parse_moneycontrol(fixture("moneycontrol-stock-reliance.json"),
                                           spec("RELIANCE.NS", moneycontrol="RELIANCE"), morning)
        self.assertEqual(quote["asOf"], "2026-11-11T06:15:00Z")

    def test_index_history(self):
        quote = markets.parse_moneycontrol(fixture("moneycontrol-index-sensex.json"),
                                           spec("^BSESN", "index", moneycontrol="in;SEN"), NOW)
        self.assertEqual((quote["price"], quote["change"]), (81879.4, 772.75))
        self.assertIsNone(quote["exchange"])

    def test_wrong_symbol(self):
        self.assertIsNone(markets.parse_moneycontrol(fixture("moneycontrol-error.json"),
                                                     spec("NOSUCH.NS", moneycontrol="NOSUCH"), NOW))

    def test_index_url_encodes_the_semicolon_and_picks_the_segment(self):
        url = markets.moneycontrol_url(spec("^NSEI", "index", moneycontrol="in;NSX"), NOW)
        self.assertIn("/indianMarket/index/history?symbol=in%3BNSX&", url)
        self.assertIn("&to=%d&" % int(NOW.timestamp()), url)
        stock = markets.moneycontrol_url(spec("TCS.NS", moneycontrol="TCS"), NOW)
        self.assertIn("/indianMarket/stock/history?symbol=TCS&", stock)


class Cnbc(unittest.TestCase):
    def setUp(self):
        self.specs = [spec("^GSPC", "index", cnbc=".SPX"), spec("^NSEI", "index", cnbc=".NSEI"),
                      spec("^BSESN", "index", cnbc=".BSESN"), spec("USDINR=X", "fx", cnbc="INR="),
                      spec("BZ=F", "commodity", cnbc="@LCO.1"), spec("TSLA", cnbc="TSLA")]
        self.quotes = markets.parse_cnbc(fixture("cnbc-quote.json"), self.specs, NOW)

    def test_not_found_symbol_is_skipped(self):
        self.assertNotIn("^BSESN", self.quotes)  # code 3
        self.assertEqual(len(self.quotes), 5)

    def test_formatted_numbers_and_explicit_change(self):
        spx = self.quotes["^GSPC"]
        self.assertEqual((spx["price"], spx["change"], spx["changePct"]), (7520.93, -29.01, -0.38))
        self.assertEqual((spx["high52"], spx["low52"], spx["spark"]), (7844.52, 6316.91, []))
        self.assertEqual(self.quotes["^NSEI"]["change"], 210.4)

    def test_date_only_us_stamp_is_the_new_york_close(self):
        self.assertEqual(self.quotes["^GSPC"]["asOf"], "2026-11-10T21:00:00Z")

    def test_full_timestamp_with_offset(self):
        self.assertEqual(self.quotes["^NSEI"]["asOf"], "2026-11-11T09:59:54Z")

    def test_fx_has_no_currency_code(self):
        self.assertIsNone(self.quotes["USDINR=X"]["currency"])
        self.assertEqual(self.quotes["USDINR=X"]["price"], 93.69)

    def test_zero_year_low_is_dropped(self):
        self.assertEqual((self.quotes["BZ=F"]["high52"], self.quotes["BZ=F"]["low52"]), (126.41, None))

    def test_premarket_price_is_ignored(self):
        self.assertEqual(self.quotes["TSLA"]["price"], 379.78)  # ExtendedMktQuote.last is 385.15


if __name__ == "__main__":
    unittest.main()
