"""Markets stage: config/markets.json -> public/markets.json and state/markets-cache.json.

Why it works the way it does (every endpoint and quirk below was verified live
on 2026-11-11, see docs/research/sources-2026-11-11.json, "sources:market-data"):

* Yahoo's v7 spark returns a full quote plus a month of daily closes for up to
  20 symbols per request, with no key or cookie, so a normal run is three
  requests. A symbol spark drops (renamed, delisted, or just missing) gets one
  v8 chart request of its own.
* Yahoo is unofficial. A provider that throttles (429), refuses or times out
  is not asked again in the same run; we fall straight through to asset-class
  fallbacks verified with the same honest client: CoinGecko (crypto),
  Frankfurter/ECB (FX), Moneycontrol techCharts (Indian stocks and indices) and
  CNBC's quote service (indices, US stocks, commodities, FX; quote only).
* The last good quote per symbol is kept in state/markets-cache.json. A symbol
  nobody could refresh is published from that cache with ``stale: true``, so
  the page never goes blank and never pretends old numbers are new.
* Movers join to the hot set in public/latest.json so the page can say *why*
  something moved, or say plainly that no story is linked.
"""

import math
import urllib.parse
from datetime import datetime, timedelta

from .core import config, jsonio, log, net, timeutil

SPARK_URL = "https://query1.finance.yahoo.com/v7/finance/spark?symbols={symbols}&range=1mo&interval=1d"
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1mo&interval=1d"
COINGECKO_PRICE_URL = ("https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
                       "&include_24hr_change=true&include_last_updated_at=true")
COINGECKO_CHART_URL = "https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency=usd&days=30&interval=daily"
FRANKFURTER_URL = "https://api.frankfurter.dev/v1/{start}..?base=USD&symbols={codes}"
MONEYCONTROL_URL = ("https://priceapi.moneycontrol.com/techCharts/indianMarket/{segment}/history?symbol={symbol}"
                    "&resolution=1D&from={start}&to={end}&countback={count}&currencyCode=INR")
CNBC_URL = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols={symbols}"
            "&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json&events=1")

KINDS = ("index", "stock", "fx", "commodity", "crypto")
FALLBACK_PROVIDERS = ("coingecko", "frankfurter", "moneycontrol", "cnbc")  # tried in this order
PROVIDERS = ("yahoo",) + FALLBACK_PROVIDERS
DEFAULT_THRESHOLDS = {"stock": 2.0, "index": 1.0}

SPARK_BATCH = 20          # Yahoo answers HTTP 400 above 20 symbols
SPARK_POINTS = 32         # contract: spark holds at most 32 closes
CNBC_BATCH = 25           # 24 symbols in one call verified; keep URLs short
HISTORY_DAYS = 50         # window asked of Frankfurter and Moneycontrol, about 34 sessions
TIMEOUT_S = 20
CHART_SPACING_S = 0.3     # per-symbol Yahoo chart calls, as the research advises
MONEYCONTROL_SPACING_S = 0.2
ECB_PUBLISH_HOUR_UTC = 15  # ECB reference rates are published around 16:00 CET
INDIA = timeutil.zone("Asia/Kolkata")
NEW_YORK = timeutil.zone("America/New_York")
# asOf gap below which two quotes describe the same session. Fallbacks estimate
# close times (Yahoo stamps US index closes up to 75 min after 16:00 New York);
# exchange sessions are at least 15 h apart, and 24-hour markets' fallbacks are live.
SAME_SESSION = timedelta(hours=6)
STORY_WINDOW = timedelta(hours=36)
MAX_MOVERS = 10
MAX_REPORTED_PROBLEMS = 12
EXCHANGE_SUFFIXES = (".NS", ".BO")


# ---------------------------------------------------------------- config

def load_specs(cfg):
    """Flatten config groups into symbol specs, each carrying its group id.

    config/markets.json is hand-edited; a typo must stop the stage with the
    symbol named rather than quietly publish a page with holes in it.
    """
    groups = cfg.get("groups")
    if not isinstance(groups, list) or not groups:
        raise config.ConfigError("config/markets.json: 'groups' must be a non-empty list")
    specs, seen = [], set()
    for group in groups:
        if not isinstance(group, dict) or not group.get("id") or not group.get("name"):
            raise config.ConfigError("config/markets.json: every group needs an id and a name")
        for entry in group.get("symbols") or []:
            spec = _check_symbol(entry, group["id"])
            if spec["symbol"] in seen:
                raise config.ConfigError("config/markets.json: %s is listed twice" % spec["symbol"])
            seen.add(spec["symbol"])
            specs.append(spec)
    return specs


def _check_symbol(entry, group_id):
    """Validate one symbol entry and return it as a spec (a copy plus ``group``)."""
    if not isinstance(entry, dict) or not isinstance(entry.get("symbol"), str) or not entry["symbol"]:
        raise config.ConfigError("config/markets.json: group %s has an entry without a symbol" % group_id)
    where = "config/markets.json: %s" % entry["symbol"]
    for key in ("name", "short"):
        if not isinstance(entry.get(key), str) or not entry[key].strip():
            raise config.ConfigError("%s needs a %r" % (where, key))
    if entry.get("kind") not in KINDS:
        raise config.ConfigError("%s: kind must be one of %s" % (where, ", ".join(KINDS)))
    if entry.get("entity") is not None and not isinstance(entry.get("entity"), str):
        raise config.ConfigError("%s: entity must be a string or null" % where)
    alt = entry.get("alt") or {}
    if not isinstance(alt, dict):
        raise config.ConfigError("%s: alt must be an object" % where)
    for provider, code in alt.items():
        if provider not in FALLBACK_PROVIDERS or not isinstance(code, str) or not code:
            raise config.ConfigError("%s: bad fallback %r: %r" % (where, provider, code))
    pair = alt.get("frankfurter")
    if pair is not None and not _is_pair(pair):
        raise config.ConfigError("%s: frankfurter pair must look like USD/INR" % where)
    return dict(entry, alt=alt, group=group_id)


def _is_pair(text):
    """True for an ISO currency pair written BASE/QUOTE, e.g. ``USD/INR``."""
    parts = text.split("/")
    return len(parts) == 2 and all(len(p) == 3 and p.isalpha() and p.isupper() for p in parts)


def load_thresholds(cfg):
    """Mover thresholds by kind (absolute day change, in percent)."""
    value = cfg.get("moverThresholdPct", DEFAULT_THRESHOLDS)
    if not isinstance(value, dict) or not all(kind in KINDS and _finite(pct) and pct > 0
                                              for kind, pct in value.items()):
        raise config.ConfigError("config/markets.json: moverThresholdPct must map kinds to positive numbers")
    return value


def load_enabled(cfg):
    """Provider switches. A provider that rejects our User-Agent is turned off here, never worked around."""
    providers = cfg.get("providers") or {}
    enabled = {}
    for name in PROVIDERS:
        entry = providers.get(name, {})
        if not isinstance(entry, dict):
            raise config.ConfigError("config/markets.json: providers.%s must be an object" % name)
        enabled[name] = entry.get("enabled", True) is not False
    unknown = sorted(set(providers) - set(PROVIDERS))
    if unknown:
        raise config.ConfigError("config/markets.json: unknown providers %s" % ", ".join(unknown))
    return enabled


# ---------------------------------------------------------------- numbers and quotes

def _finite(value):
    """A real, finite number (bools are not prices)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _digits(kind, price):
    """Decimal places to publish: FX below 10 (EUR/USD 1.1116) needs four, everything else two."""
    return 4 if kind == "fx" and abs(price) < 10 else 2


def _round(value, digits):
    """Round for display; ``+ 0.0`` turns a rounded ``-0.0`` into ``0.0``."""
    return round(value, digits) + 0.0


def _pct(last, previous):
    """Percent change from ``previous`` to ``last``, or None when it cannot be computed."""
    if not (_finite(last) and _finite(previous)) or previous == 0:
        return None
    return (last / previous - 1.0) * 100.0


def _number(text):
    """Parse CNBC-style numbers: strings with thousands commas, signs, '%' and '$' ('+1,051.15')."""
    if _finite(text):
        return float(text)
    if not isinstance(text, str):
        return None
    cleaned = text.replace(",", "").replace("%", "").replace("$", "").replace("+", "").strip()
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def make_quote(spec, price, change_pct, spark, as_of, currency=None, exchange=None,
               high52=None, low52=None, change=None):
    """Build a contract Quote, or None when the provider's numbers are unusable.

    Names, kind and entity come from config, not the provider, so a symbol
    reads the same whichever fallback served it. When the provider gives no
    absolute change it is derived from the price and the percentage, which is
    exact: change = price - price / (1 + pct/100). A 52-week bound of zero
    means "unknown" (CNBC sends "0.00" for Brent) and becomes null.
    """
    if not (_finite(price) and price > 0 and _finite(change_pct) and change_pct > -100 and as_of is not None):
        return None
    digits = _digits(spec["kind"], price)
    if not _finite(change):
        change = price - price / (1.0 + change_pct / 100.0)
    closes = [_round(c, digits) for c in spark if _finite(c)][-SPARK_POINTS:]
    return {
        "symbol": spec["symbol"],
        "name": spec["name"],
        "short": spec["short"],
        "kind": spec["kind"],
        "currency": currency,
        "price": _round(price, digits),
        "change": _round(change, digits),
        "changePct": _round(change_pct, 2),
        "spark": closes,
        "asOf": timeutil.iso(as_of),
        "exchange": exchange,
        "entity": spec.get("entity"),
        "high52": _round(high52, digits) if _finite(high52) and high52 > 0 else None,
        "low52": _round(low52, digits) if _finite(low52) and low52 > 0 else None,
        "stale": False,
    }


# ---------------------------------------------------------------- network bookkeeping

class Session:
    """One run's view of the providers: which are switched off, which failed, and what went wrong.

    A provider that throttles, refuses or times out is not asked again this
    run: retrying an unofficial API after a 429 is how a personal script gets
    blocked for good. A 400/404 is about one request (a bad symbol), so the
    provider stays usable for the others.
    """

    def __init__(self, enabled):
        self.enabled = dict(enabled)
        self.down = set()
        self.problems = []

    def usable(self, provider):
        """True while the provider is enabled in config and has not failed this run."""
        return self.enabled.get(provider, False) and provider not in self.down

    def note(self, provider, message):
        """Record a problem for status.json and the log."""
        text = "%s: %s" % (provider, message)
        self.problems.append(text)
        log.warn("%s", text)

    def get_json(self, provider, url, what, spacing_s=0.0):
        """Fetch JSON from ``provider``; None (and a recorded problem) on any failure."""
        if not self.usable(provider):
            return None
        if spacing_s:
            net.polite(url, spacing_s)
        try:
            return net.fetch_json(url, timeout=TIMEOUT_S, retries=1)
        except net.NetError as err:
            self.note(provider, "%s: %s" % (what, err))
            if not (err.kind == "http" and err.status in (400, 404)):
                self.down.add(provider)
                log.warn("%s: not asking it again this run", provider)
            return None

    def parse(self, provider, what, parser, *args):
        """Run a parser; a response whose shape changed is reported, not raised."""
        try:
            return parser(*args)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError, ZeroDivisionError) as err:
            self.note(provider, "%s: unexpected response (%s: %s)" % (what, type(err).__name__, err))
            return None


def _symbols(specs):
    """The ticker strings of a list of specs, in order."""
    return [spec["symbol"] for spec in specs]


# ---------------------------------------------------------------- Yahoo

def spark_url(symbols):
    """v7 spark URL; ``^`` and ``=`` must be percent-encoded, the commas must not."""
    return SPARK_URL.format(symbols=urllib.parse.quote(",".join(symbols), safe=","))


def chart_url(symbol):
    return CHART_URL.format(symbol=urllib.parse.quote(symbol, safe=""))


def quote_from_yahoo(spec, block):
    """Quote from one spark response or chart result ({meta, timestamp, indicators}).

    A renamed symbol (PSTG) comes back with meta but no timestamps and no
    price, which counts as no data. The day change is Yahoo's own
    regularMarketChangePercent; chartPreviousClose is a month old and must not
    be used for it. The last close is the latest session, i.e. the price.

    Yahoo sends no regularMarketChange here. Its fulldayChange is that change
    exactly when the fullday price and percentage equal the regular ones
    (during US pre-market they measure the extended session instead), so it is
    used only then; otherwise the change is derived from the percentage, which
    Yahoo rounds to three decimals and so is a few hundredths off on big indices.
    """
    meta = block.get("meta") or {}
    price = meta.get("regularMarketPrice")
    if not block.get("timestamp") or not _finite(price):
        return None
    series = (block.get("indicators") or {}).get("quote") or [{}]
    closes = [c for c in (series[0].get("close") or []) if _finite(c)]
    change_pct = meta.get("regularMarketChangePercent")
    if not _finite(change_pct) and len(closes) >= 2:
        change_pct = _pct(closes[-1], closes[-2])
    same_session = meta.get("fulldayPrice") == price and meta.get("fulldayChangePercent") == change_pct
    change = meta.get("fulldayChange") if same_session else None
    return make_quote(
        spec, price, change_pct, closes,
        timeutil.parse_date(meta.get("regularMarketTime")),
        currency=meta.get("currency"),
        exchange=meta.get("fullExchangeName") or meta.get("exchangeName"),
        high52=meta.get("fiftyTwoWeekHigh"), low52=meta.get("fiftyTwoWeekLow"),
        change=change,
    )


def parse_spark(payload, specs):
    """Quotes keyed by symbol. Results are not in request order; unknown symbols are just absent."""
    wanted = {spec["symbol"]: spec for spec in specs}
    quotes = {}
    for item in payload["spark"]["result"] or []:
        spec = wanted.get(item.get("symbol"))
        responses = item.get("response") or []
        quote = quote_from_yahoo(spec, responses[0]) if spec and responses else None
        if quote:
            quotes[spec["symbol"]] = quote
    return quotes


def parse_chart(payload, spec):
    """Quote from a v8 chart response, or None when it carries no usable data."""
    results = payload["chart"]["result"] or []
    return quote_from_yahoo(spec, results[0]) if results else None


def from_yahoo(session, specs, now):
    """Spark in batches of 20, then one chart request per symbol spark did not return.

    Once Yahoo fails provider-wide (a 429, say) ``get_json`` refuses every
    further call, so the remaining batches and charts cost nothing.
    """
    quotes = {}
    for start in range(0, len(specs), SPARK_BATCH):
        batch = specs[start:start + SPARK_BATCH]
        payload = session.get_json("yahoo", spark_url(_symbols(batch)), "spark")
        if payload is not None:
            quotes.update(session.parse("yahoo", "spark", parse_spark, payload, batch) or {})
    for spec in specs:
        if spec["symbol"] in quotes:
            continue
        what = "chart %s" % spec["symbol"]
        payload = session.get_json("yahoo", chart_url(spec["symbol"]), what, CHART_SPACING_S)
        if payload is None:
            continue
        quote = session.parse("yahoo", what, parse_chart, payload, spec)
        if quote:
            quotes[spec["symbol"]] = quote
        else:
            session.note("yahoo", "%s: no price (renamed or delisted?)" % what)
    return quotes


# ---------------------------------------------------------------- CoinGecko (crypto)

def parse_coingecko(prices, charts, specs):
    """Quotes from simple/price plus per-coin market_chart.

    CoinGecko's change is a rolling 24 hours, not a session change; it is the
    closest thing a 24/7 market has. A missing chart just means no sparkline.
    """
    quotes = {}
    for spec in specs:
        coin = spec["alt"]["coingecko"]
        row = prices.get(coin) or {}
        points = (charts.get(coin) or {}).get("prices") or []
        spark = [point[1] for point in points if isinstance(point, list) and len(point) == 2]
        quote = make_quote(spec, row.get("usd"), row.get("usd_24h_change"), spark,
                           timeutil.parse_date(row.get("last_updated_at")),
                           currency="USD", exchange="CoinGecko")
        if quote:
            quotes[spec["symbol"]] = quote
    return quotes


def from_coingecko(session, specs, now):
    """One price call for every coin, then one 30-day chart per coin for the sparkline."""
    coins = [spec["alt"]["coingecko"] for spec in specs]
    prices = session.get_json("coingecko", COINGECKO_PRICE_URL.format(ids=",".join(coins)), "price")
    if prices is None:
        return {}
    charts = {}
    for coin in coins:
        chart = session.get_json("coingecko", COINGECKO_CHART_URL.format(coin=coin), "chart %s" % coin)
        if chart is not None:
            charts[coin] = chart
    return session.parse("coingecko", "price", parse_coingecko, prices, charts, specs) or {}


# ---------------------------------------------------------------- Frankfurter (FX)

def _cross(rates, base, quote):
    """BASE/QUOTE from USD-based rates (USD itself is 1), or None when a leg is missing."""
    legs = [1.0 if code == "USD" else rates.get(code) for code in (base, quote)]
    if not all(_finite(leg) and leg > 0 for leg in legs):
        return None
    return legs[1] / legs[0]


def parse_frankfurter(payload, specs):
    """Quotes from a USD-based time series. These are ECB daily fixes, one business day behind live."""
    if payload.get("base") != "USD":
        raise ValueError("base is %r, expected USD" % payload.get("base"))
    rates = payload["rates"]
    quotes = {}
    for spec in specs:
        base, quote_code = spec["alt"]["frankfurter"].split("/")
        days = [(day, _cross(rates[day], base, quote_code)) for day in sorted(rates)]
        days = [(day, rate) for day, rate in days if rate is not None]
        if len(days) < 2:
            continue
        last_day, price = days[-1]
        as_of = datetime.strptime(last_day, "%Y-%m-%d").replace(hour=ECB_PUBLISH_HOUR_UTC, tzinfo=timeutil.UTC)
        quote = make_quote(spec, price, _pct(price, days[-2][1]), [rate for _, rate in days], as_of,
                           currency=quote_code, exchange="ECB reference rate")
        if quote:
            quotes[spec["symbol"]] = quote
    return quotes


def from_frankfurter(session, specs, now):
    """One USD-based series call covering every currency any configured pair needs."""
    codes = sorted({code for spec in specs for code in spec["alt"]["frankfurter"].split("/")} - {"USD"})
    start = (now - timedelta(days=HISTORY_DAYS)).date().isoformat()
    payload = session.get_json("frankfurter", FRANKFURTER_URL.format(start=start, codes=",".join(codes)), "rates")
    if payload is None:
        return {}
    return session.parse("frankfurter", "rates", parse_frankfurter, payload, specs) or {}


# ---------------------------------------------------------------- Moneycontrol (India)

def moneycontrol_url(spec, now):
    """Indices use codes like ``in;NSX`` (semicolon encoded); stocks use the bare NSE symbol."""
    end = int(now.timestamp())
    return MONEYCONTROL_URL.format(
        segment="index" if spec["kind"] == "index" else "stock",
        symbol=urllib.parse.quote(spec["alt"]["moneycontrol"], safe=""),
        start=end - HISTORY_DAYS * 86400, end=end, count=SPARK_POINTS,
    )


def _session_close(stamp, hour, minute, tz, now):
    """When the session that a date-only provider stamp refers to closed (``now`` if it is still open)."""
    close = datetime(stamp.year, stamp.month, stamp.day, hour, minute, tzinfo=tz)
    return min(close, now)


def parse_moneycontrol(payload, spec, now):
    """Quote from a TradingView-style history ({s, t[], c[]}); the last bar is the latest session.

    Bar stamps label a date (00:00 UTC, or 05:30 UTC on the current bar), not
    a time, so asOf is that day's 15:30 IST close, or now while it is open.
    """
    if payload.get("s") != "ok":
        return None
    bars = [(stamp, close) for stamp, close in zip(payload["t"], payload["c"]) if _finite(close)]
    if len(bars) < 2:
        return None
    price = bars[-1][1]
    day = timeutil.parse_date(bars[-1][0])
    as_of = _session_close(day.astimezone(INDIA), 15, 30, INDIA, now) if day is not None else None
    return make_quote(spec, price, _pct(price, bars[-2][1]), [close for _, close in bars], as_of,
                      currency="INR", exchange="NSE" if spec["kind"] == "stock" else None)


def from_moneycontrol(session, specs, now):
    """One history call per symbol (the API takes one), politely spaced."""
    quotes = {}
    for spec in specs:
        what = "history %s" % spec["alt"]["moneycontrol"]
        payload = session.get_json("moneycontrol", moneycontrol_url(spec, now), what, MONEYCONTROL_SPACING_S)
        if payload is None:
            continue
        quote = session.parse("moneycontrol", what, parse_moneycontrol, payload, spec, now)
        if quote:
            quotes[spec["symbol"]] = quote
        elif isinstance(payload, dict):
            session.note("moneycontrol", "%s: %s" % (what, payload.get("errmsg") or "no usable bars"))
    return quotes


# ---------------------------------------------------------------- CNBC (quote only)

def _cnbc_time(row, now):
    """asOf for a CNBC row. A closed US symbol is stamped with its date only ('2026-11-10',
    timeZone 'EST'): that is the 16:00 New York close, not midnight UTC."""
    text = row.get("last_time")
    when = timeutil.parse_date(text)
    date_only = isinstance(text, str) and len(text.strip()) == 10
    if when is not None and date_only and row.get("timeZone") in ("EST", "EDT"):
        when = _session_close(when, 16, 0, NEW_YORK, now)
    return when


def parse_cnbc(payload, specs, now):
    """Quotes from CNBC's quote service. Every number is a formatted string; code 0 means found.

    There is no history here, so the spark is empty (the cached one is reused
    later). For closed US symbols previous_day_closing equals last, so the
    explicit change fields are used instead. Pre-market prices sit apart in
    ExtendedMktQuote and are ignored: the page shows regular sessions.
    """
    wanted = {spec["alt"]["cnbc"]: spec for spec in specs}
    quotes = {}
    for row in payload["FormattedQuoteResult"]["FormattedQuote"]:
        spec = wanted.get(row.get("symbol"))
        if spec is None or row.get("code") != 0:
            continue
        quote = make_quote(spec, _number(row.get("last")), _number(row.get("change_pct")), [],
                           _cnbc_time(row, now), currency=row.get("currencyCode"),
                           high52=_number(row.get("yrhiprice")), low52=_number(row.get("yrloprice")),
                           change=_number(row.get("change")))
        if quote:
            quotes[spec["symbol"]] = quote
    return quotes


def from_cnbc(session, specs, now):
    """Pipe-separated batches; one call normally covers everything still missing."""
    quotes = {}
    for start in range(0, len(specs), CNBC_BATCH):
        batch = specs[start:start + CNBC_BATCH]
        codes = urllib.parse.quote("|".join(spec["alt"]["cnbc"] for spec in batch), safe="")
        payload = session.get_json("cnbc", CNBC_URL.format(symbols=codes), "quote")
        if payload is not None:
            quotes.update(session.parse("cnbc", "quote", parse_cnbc, payload, batch, now) or {})
    return quotes


# ---------------------------------------------------------------- choosing what to publish

# Every step takes (session, specs, now) so the chain is one loop; not all of them need ``now``.
STEPS = (("yahoo", from_yahoo), ("coingecko", from_coingecko), ("frankfurter", from_frankfurter),
         ("moneycontrol", from_moneycontrol), ("cnbc", from_cnbc))


def collect(session, specs, now, cached):
    """Fresh quotes by symbol, and which provider supplied each, walking the fallback chain.

    A symbol stays on the to-do list while its best quote is clearly older
    than the cached one (Frankfurter's day-old ECB fix after a live Yahoo rate
    yesterday), so a later provider with a live price still gets asked.
    """
    fresh, source = {}, {}

    def settled(symbol):
        return symbol in fresh and not (symbol in cached and _clearly_newer(cached[symbol], fresh[symbol]))

    for provider, step in STEPS:
        todo = [spec for spec in specs if not settled(spec["symbol"])
                and (provider == "yahoo" or provider in spec["alt"])]
        if not todo or not session.usable(provider):
            continue
        for symbol, quote in step(session, todo, now).items():
            if symbol not in fresh or _clearly_newer(quote, fresh[symbol]):
                fresh[symbol] = quote
                source[symbol] = provider
    return fresh, source


def read_cache(path):
    """Last good quote per symbol from state/markets-cache.json; damaged entries are dropped."""
    stored = jsonio.read_json(path, default={})
    quotes = stored.get("quotes") if isinstance(stored, dict) else None
    if not isinstance(quotes, dict):
        if stored:
            log.warn("ignoring malformed markets cache %s", path)
        return {}
    good = {}
    for symbol, quote in quotes.items():
        if (isinstance(quote, dict) and _finite(quote.get("price")) and _finite(quote.get("changePct"))
                and isinstance(quote.get("asOf"), str) and isinstance(quote.get("spark"), list)):
            good[symbol] = quote
        else:
            log.warn("markets cache: dropping malformed entry for %s", symbol)
    return good


def _fill_gaps(quote, cached):
    """Fallbacks lack some fields (CNBC has no series, CoinGecko no 52-week range); reuse the cached ones."""
    filled = dict(quote)
    for key in ("currency", "exchange", "high52", "low52"):
        if filled.get(key) is None:
            filled[key] = cached.get(key)
    if not filled["spark"]:
        filled["spark"] = list(cached.get("spark") or [])
    return filled


def _from_cache(cached, spec):
    """A cached quote re-labelled from current config and marked stale."""
    quote = dict(cached)
    quote.update(symbol=spec["symbol"], name=spec["name"], short=spec["short"], kind=spec["kind"],
                 entity=spec.get("entity"), stale=True)
    return quote


def _clearly_newer(old, new):
    """True when ``old`` is from a later session than ``new`` (an unparseable cached asOf never is)."""
    old_time, new_time = timeutil.parse_date(old.get("asOf")), timeutil.parse_date(new["asOf"])
    return old_time is not None and old_time - new_time > SAME_SESSION


def assemble(specs, fresh, cached):
    """Per symbol: the fresh quote, else the cached one marked stale, else nothing.

    A fallback never replaces clearly newer data: Frankfurter's ECB fix is a
    day behind Yahoo's live rate, so a cached quote more than SAME_SESSION
    newer wins (and says it is stale). Within that margin the two describe the
    same session and the fresh one is kept: fallbacks estimate the close time.
    Returns (published by symbol, stale symbols, missing symbols).
    """
    published, stale, missing = {}, [], []
    for spec in specs:
        symbol = spec["symbol"]
        new, old = fresh.get(symbol), cached.get(symbol)
        if new is not None and old is not None:
            new = _fill_gaps(new, old)
        if new is not None and (old is None or not _clearly_newer(old, new)):
            published[symbol] = new
        elif old is not None:
            published[symbol] = _from_cache(old, spec)
            stale.append(symbol)
        else:
            missing.append(symbol)
    return published, stale, missing


# ---------------------------------------------------------------- movers

def read_stories(path):
    """Stories from public/latest.json, or [] before the process stage has ever run."""
    latest = jsonio.read_json(path, default=None)
    if latest is None:
        log.debug("no %s yet; movers will have no linked stories", path)
        return []
    stories = latest.get("stories") if isinstance(latest, dict) else None
    if not isinstance(stories, list):
        log.warn("%s has no stories list; movers will have no linked stories", path)
        return []
    return [story for story in stories if isinstance(story, dict)]


def _ticker_keys(symbol):
    """Ticker spellings a story may use: RELIANCE.NS matches RELIANCE.NS and RELIANCE."""
    keys = {symbol.upper()}
    for suffix in EXCHANGE_SUFFIXES:
        if symbol.upper().endswith(suffix):
            keys.add(symbol.upper()[:-len(suffix)])
    return keys


def linked_story(spec, stories, now):
    """The highest-scoring story of the last 36 h that names this symbol or its entity, or None."""
    keys = _ticker_keys(spec["symbol"])
    entity = spec.get("entity")
    best, best_score = None, None
    for story in stories:
        tickers = {str(t).upper() for t in story.get("tickers") or []}
        if not (tickers & keys or (entity and entity in (story.get("entities") or []))):
            continue
        when = timeutil.parse_date(story.get("updatedAt") or story.get("publishedAt"))
        if when is None or not timedelta(0) <= now - when <= STORY_WINDOW:
            continue
        score = story.get("score") if _finite(story.get("score")) else 0
        if best is None or score > best_score:
            best, best_score = story, score
    if best is None:
        return None
    return {"id": best.get("id"), "title": best.get("title"), "sourceCount": best.get("sourceCount")}


def find_movers(specs, published, thresholds, stories, now):
    """Fresh stocks and indices whose day change reaches the threshold for their kind, biggest first.

    Stale quotes are left out: yesterday's move is not today's news. A symbol
    can opt out with ``"mover": false`` (India VIX swings by design).
    """
    candidates = []
    for spec in specs:
        quote = published.get(spec["symbol"])
        limit = thresholds.get(spec["kind"])
        if quote is None or quote["stale"] or limit is None or spec.get("mover") is False:
            continue
        if abs(quote["changePct"]) >= limit:
            candidates.append((spec, quote))
    candidates.sort(key=lambda pair: -abs(pair[1]["changePct"]))
    return [{"symbol": spec["symbol"], "name": spec["name"], "changePct": quote["changePct"],
             "story": linked_story(spec, stories, now)}
            for spec, quote in candidates[:MAX_MOVERS]]


# ---------------------------------------------------------------- stage

def build_document(cfg, specs, published, movers, now, stale):
    """public/markets.json in contract shape; groups that ended up empty are left out."""
    groups = []
    for group in cfg["groups"]:
        quotes = [published[spec["symbol"]] for spec in specs
                  if spec["group"] == group["id"] and spec["symbol"] in published]
        if quotes:
            groups.append({"id": group["id"], "name": group["name"], "quotes": quotes})
    return {
        "generatedAt": timeutil.iso(now),
        "stale": stale,
        "groups": groups,
        "strip": [symbol for symbol in cfg.get("strip") or [] if symbol in published],
        "movers": movers,
    }


def refresh(ctx, cfg):
    """Fetch, fall back, publish and cache. Raises only when an output file cannot be written."""
    specs = load_specs(cfg)
    thresholds = load_thresholds(cfg)
    session = Session(load_enabled(cfg))
    cache_path = ctx.paths.state / "markets-cache.json"
    cached = read_cache(cache_path)
    if ctx.offline:
        log.info("offline: serving the %d cached quotes", len(cached))
        fresh, source = {}, {}
    else:
        fresh, source = collect(session, specs, ctx.now, cached)
    published, stale, missing = assemble(specs, fresh, cached)
    is_stale = 2 * (len(stale) + len(missing)) > len(specs)
    movers = find_movers(specs, published, thresholds, read_stories(ctx.paths.public / "latest.json"), ctx.now)

    jsonio.write_json(ctx.paths.public / "markets.json",
                      build_document(cfg, specs, published, movers, ctx.now, is_stale))
    jsonio.write_json(cache_path, {
        "savedAt": timeutil.iso(ctx.now),
        "quotes": {symbol: dict(quote, stale=False) for symbol, quote in published.items()},
    }, sort_keys=True)

    by_source = {}
    for symbol, quote in published.items():
        if not quote["stale"]:
            by_source[source[symbol]] = by_source.get(source[symbol], 0) + 1
    if stale:
        log.warn("served from cache (stale): %s", " ".join(stale))
    if missing:
        log.warn("no data at all for: %s", " ".join(missing))
    log.info("%d of %d fresh %s, %d stale, %d missing, %d movers", len(published) - len(stale), len(specs),
             jsonio.dumps(by_source), len(stale), len(missing), len(movers))
    return {
        "symbols": len(specs),
        "fresh": len(published) - len(stale),
        "stale": len(stale),
        "missing": len(missing),
        "movers": len(movers),
        "sources": by_source,
        "problems": session.problems[:MAX_REPORTED_PROBLEMS],
    }


def run(ctx):
    """Stage entry point: ``python3 -m pipeline markets``."""
    return refresh(ctx, config.load("markets"))
