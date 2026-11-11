"""pipeline.fetch: merging into day files, de-duplication, firstSeenAt, pruning, source health,
conditional requests, politeness lanes, --offline, and the shipped config/sources.json.

The network is a stub standing in for ``net.fetch``; every run writes into a temporary data dir.
"""

import contextlib
import io
import json
import tempfile
import threading
import time
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock
from xml.sax.saxutils import escape

from pipeline import fetch
from pipeline.core import config, jsonio, net, timeutil
from tests.pipeline.test_feeds import NOW, fixture

NOT_MODIFIED = object()
REAL_LOAD = config.load


def rss(*items):
    """A small RSS document from (title, link, date-or-None) tuples, in feed order."""
    parts = []
    for title, link, date in items:
        when = "<pubDate>%s</pubDate>" % date if date else ""
        parts.append("<item><title>%s</title><link>%s</link>%s</item>" % (escape(title), escape(link), when))
    return ("<rss><channel><title>T</title>%s</channel></rss>" % "".join(parts)).encode("utf-8")


def google_news(*items):
    """A Google News RSS document from (headline, token, publisher, date) tuples."""
    parts = ["<item><title>%s - %s</title><link>https://news.google.com/rss/articles/%s?oc=5</link>"
             "<pubDate>%s</pubDate><source url=\"https://example.org\">%s</source></item>"
             % (escape(title), escape(publisher), token, date, escape(publisher))
             for title, token, publisher, date in items]
    return ("<rss><channel>%s</channel></rss>" % "".join(parts)).encode("utf-8")


def algolia(*hits):
    """An Algolia response from (title, url, points, comments, created_at) tuples."""
    return json.dumps({"hits": [
        {"title": title, "url": url, "points": points, "num_comments": comments, "created_at": created,
         "objectID": str(index), "_tags": ["story"]}
        for index, (title, url, points, comments, created) in enumerate(hits)]}).encode("utf-8")


def src(id, url, kind="rss", tier=2, mode="firehose", **extra):
    entry = {"id": id, "name": extra.pop("name", id.title()), "url": url, "kind": kind, "section": "world",
             "topics": extra.pop("topics", []), "tier": tier, "mode": mode, "maxItems": 15, "maxAgeHours": 48,
             "enabled": True}
    entry.update(extra)
    return entry


class FakeNet:
    """Stands in for ``net.fetch``: serves bodies by URL, records calls, can answer 304 or fail.

    Like the real client it records validators in the HttpCache it is given.
    """

    def __init__(self):
        self.routes = {}
        self.calls = []
        self.lock = threading.Lock()

    def __call__(self, url, *, timeout=20, retries=1, headers=None, cache=None, max_bytes=8_000_000):
        with self.lock:
            self.calls.append(url)
        route = self.routes.get(url)
        if route is None:
            raise net.NetError("http", 404, "HTTP 404 Not Found", url)
        if isinstance(route, Exception):
            raise route
        if callable(route):
            route = route(url)
        if route is NOT_MODIFIED:
            response = net.Response(304, b"", {}, url, not_modified=True)
        else:
            response = net.Response(200, route, {"ETag": '"%d"' % len(route)}, url)
        if cache is not None:
            cache.record(url, response)
        return response


class FetchCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name)
        self.sources = []
        self.net = FakeNet()
        for patcher in (mock.patch.object(net, "fetch", self.net),
                        mock.patch.object(net, "polite", lambda *args: None),
                        mock.patch.object(fetch, "SEQUENTIAL_PAUSE_S", 0),
                        mock.patch.object(config, "load", self.load)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(timeutil.set_now, None)
        self.addCleanup(net.set_offline, False)
        self.log = ""

    def load(self, name):
        if name == "sources":
            return {"sources": self.sources}
        return REAL_LOAD(name)

    def run_fetch(self, now=NOW, offline=False, force=False):
        timeutil.set_now(now)
        net.set_offline(offline)
        ctx = config.context(data_dir=self.data, force=force)
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            counts = fetch.run(ctx)
        self.log = stderr.getvalue()
        return counts

    @property
    def items_dir(self):
        return self.data / "state" / "items"

    def day(self, date):
        return jsonio.read_json(self.items_dir / (date + ".json"))

    def items(self):
        found = {}
        for path in sorted(self.items_dir.glob("*.json")):
            found.update(jsonio.read_json(path)["items"])
        return found

    def health(self):
        return jsonio.read_json(self.data / "state" / "source-health.json")


class Merge(FetchCase):
    def test_items_are_filed_under_the_local_date_of_publication(self):
        self.sources = [src("a", "https://a.example/feed")]
        self.net.routes["https://a.example/feed"] = rss(
            ("Late evening story in UTC", "https://a.example/late", "2026-11-10T20:00:00Z"),   # 01:30 IST on the 11th
            ("Morning story in UTC", "https://a.example/morning", "2026-11-10T10:00:00Z"))     # 15:30 IST on the 10th
        counts = self.run_fetch()
        self.assertEqual(sorted(path.name for path in self.items_dir.glob("*.json")), ["2026-11-10.json", "2026-11-11.json"])
        late = self.day("2026-11-11")
        self.assertEqual(late["date"], "2026-11-11")
        [item] = late["items"].values()
        self.assertEqual(item["url"], "https://a.example/late")
        self.assertEqual(item["firstSeenAt"], "2026-11-11T14:00:00Z")
        self.assertEqual(counts["newItems"], 2)
        self.assertEqual(counts["filesWritten"], 2)

    def test_day_files_store_ids_sorted(self):
        self.sources = [src("a", "https://a.example/feed")]
        self.net.routes["https://a.example/feed"] = rss(*[
            ("Story number %d of the day" % n, "https://a.example/%d" % n, "2026-11-11T1%d:00:00Z" % n) for n in range(4)])
        self.run_fetch()
        text = (self.items_dir / "2026-11-11.json").read_text(encoding="utf-8")
        ids = list(json.loads(text)["items"])
        self.assertEqual(ids, sorted(ids))

    def test_second_run_keeps_first_seen_and_refreshes_points_comments_and_rank(self):
        self.sources = [src("hn", "https://hn.example/front", kind="hn", mode="curated")]
        self.net.routes["https://hn.example/front"] = algolia(
            ("First story on the front page", "https://x.example/1", 100, 10, "2026-11-11T09:00:00Z"),
            ("Second story on the front page", "https://x.example/2", 50, 5, "2026-11-11T10:00:00Z"))
        self.run_fetch()
        self.net.routes["https://hn.example/front"] = algolia(
            ("Second story on the front page", "https://x.example/2", 400, 120, "2026-11-11T10:00:00Z"),
            ("First story on the front page", "https://x.example/1", 180, 30, "2026-11-11T09:00:00Z"))
        counts = self.run_fetch(now=NOW + timedelta(hours=3))
        stored = {item["url"]: item for item in self.items().values()}
        self.assertEqual(counts["newItems"], 0)
        self.assertEqual(stored["https://x.example/2"]["firstSeenAt"], "2026-11-11T14:00:00Z")
        self.assertEqual((stored["https://x.example/2"]["points"], stored["https://x.example/2"]["comments"]), (400, 120))
        self.assertEqual(stored["https://x.example/2"]["feedRank"], 0)
        self.assertEqual(stored["https://x.example/1"]["feedRank"], 1)
        self.assertEqual(self.health()["hn"]["newItems"], 0)

    def test_a_redated_item_is_not_moved_or_duplicated(self):
        self.sources = [src("a", "https://a.example/feed")]
        self.net.routes["https://a.example/feed"] = rss(("Updated story keeps its day", "https://a.example/s", "2026-11-10T08:00:00Z"))
        self.run_fetch()
        self.net.routes["https://a.example/feed"] = rss(("Updated story keeps its day", "https://a.example/s", "2026-11-11T13:00:00Z"))
        self.run_fetch(now=NOW + timedelta(hours=1))
        [item] = self.items().values()
        self.assertEqual(item["publishedAt"], "2026-11-10T08:00:00Z")
        self.assertIn(item["id"], self.day("2026-11-10")["items"])

    def test_undated_items_keep_their_first_date_on_later_runs(self):
        self.sources = [src("a", "https://a.example/feed")]
        self.net.routes["https://a.example/feed"] = rss(("A feed that never dates its items", "https://a.example/u", None))
        self.run_fetch()
        counts = self.run_fetch(now=NOW + timedelta(hours=20))
        [item] = self.items().values()
        self.assertEqual((item["publishedAt"], item["firstSeenAt"]), ("2026-11-11T14:00:00Z", "2026-11-11T14:00:00Z"))
        self.assertEqual(counts["newItems"], 0)

    def test_missing_summary_and_image_are_filled_in_later(self):
        self.sources = [src("a", "https://a.example/feed")]
        self.net.routes["https://a.example/feed"] = rss(("Story that gains a summary later", "https://a.example/s", "2026-11-11T08:00:00Z"))
        self.run_fetch()
        self.net.routes["https://a.example/feed"] = (
            b"<rss><channel><item><title>Story that gains a summary later</title><link>https://a.example/s</link>"
            b"<pubDate>2026-11-11T08:00:00Z</pubDate><description>Now the desk has written a real standfirst for it."
            b"</description><enclosure url=\"https://cdn.example/s.jpg\" type=\"image/jpeg\"/></item></channel></rss>")
        self.run_fetch(now=NOW + timedelta(hours=1))
        [item] = self.items().values()
        self.assertEqual(item["summary"], "Now the desk has written a real standfirst for it.")
        self.assertEqual(item["image"], "https://cdn.example/s.jpg")

    def test_expired_day_files_are_pruned(self):
        self.items_dir.mkdir(parents=True)
        for name in ("2026-08-01.json", "2026-08-13.json", "2026-08-14.json", "notes.json"):
            (self.items_dir / name).write_text('{"date":"x","items":{}}', encoding="utf-8")
        self.sources = [src("a", "https://a.example/feed")]
        self.net.routes["https://a.example/feed"] = rss(("Something new today for the paper", "https://a.example/n", "2026-11-11T09:00:00Z"))
        counts = self.run_fetch()
        remaining = sorted(path.name for path in self.items_dir.glob("*.json"))
        self.assertEqual(remaining, ["2026-08-13.json", "2026-08-14.json", "2026-11-11.json", "notes.json"])
        self.assertEqual(counts["pruned"], 1)

    def test_malformed_stored_items_are_dropped_not_fatal(self):
        self.items_dir.mkdir(parents=True)
        jsonio.write_json(self.items_dir / "2026-11-11.json", {"date": "2026-11-11", "items": {"ibad": "x", "inone": {}}})
        self.sources = [src("a", "https://a.example/feed")]
        self.net.routes["https://a.example/feed"] = rss(("Story stored beside the damage", "https://a.example/d", "2026-11-11T09:00:00Z"))
        self.run_fetch()
        self.assertEqual([item["title"] for item in self.day("2026-11-11")["items"].values()], ["Story stored beside the damage"])
        self.assertIn("dropped 2 malformed items", self.log)

    def test_a_corrupt_day_file_is_replaced_not_fatal(self):
        self.items_dir.mkdir(parents=True)
        (self.items_dir / "2026-11-11.json").write_text('{"date": "2026-11-11", "items": [1, 2', encoding="utf-8")
        self.sources = [src("a", "https://a.example/feed")]
        self.net.routes["https://a.example/feed"] = rss(("Story written over a corrupt file", "https://a.example/c", "2026-11-11T09:00:00Z"))
        self.run_fetch()
        self.assertEqual(len(self.day("2026-11-11")["items"]), 1)
        self.assertIn("corrupt JSON", self.log)


class Dedupe(FetchCase):
    def test_same_url_keeps_the_best_tier_and_absorbs_points(self):
        self.sources = [src("hn", "https://hn.example/front", kind="hn", tier=3, topics=["hn"]),
                        src("lab", "https://lab.example/feed", tier=1, name="Lab", topics=["lab"])]
        self.net.routes["https://hn.example/front"] = algolia(
            ("Lab releases a new model today", "https://lab.example/news/model?utm_source=hn", 512, 300, "2026-11-11T11:00:00Z"))
        self.net.routes["https://lab.example/feed"] = rss(("Introducing our new model", "https://lab.example/news/model", "2026-11-11T10:00:00Z"))
        counts = self.run_fetch()
        [item] = self.items().values()
        self.assertEqual((item["source"], item["title"]), ("lab", "Introducing our new model"))
        self.assertEqual((item["points"], item["comments"]), (512, 300))
        self.assertEqual(item["topics"], ["lab", "hn"])
        self.assertEqual(counts["items"], 1)
        self.assertEqual(self.health()["hn"]["items"], 1)

    def test_same_headline_from_the_same_publisher_is_one_item(self):
        self.sources = [src("gn-a", "https://news.google.com/rss/search?q=a", kind="google-news"),
                        src("gn-b", "https://news.google.com/rss/search?q=b", kind="google-news")]
        self.net.routes["https://news.google.com/rss/search?q=a"] = google_news(
            ("Central bank holds rates steady again", "TOKEN1", "Reuters", "2026-11-11T08:00:00Z"))
        self.net.routes["https://news.google.com/rss/search?q=b"] = google_news(
            ("Central bank holds rates steady again", "TOKEN2", "Reuters", "2026-11-11T08:00:00Z"),
            ("Central bank holds rates steady again", "TOKEN3", "Bloomberg", "2026-11-11T08:05:00Z"))
        self.run_fetch()
        self.assertEqual(sorted(item["publisher"] for item in self.items().values()), ["Bloomberg", "Reuters"])

    def test_a_new_google_token_for_a_stored_story_is_not_a_new_item(self):
        self.sources = [src("gn", "https://news.google.com/rss/search?q=a", kind="google-news")]
        self.net.routes["https://news.google.com/rss/search?q=a"] = google_news(
            ("Monsoon session of parliament ends early", "TOKEN1", "The Hindu", "2026-11-11T08:00:00Z"))
        self.run_fetch()
        self.net.routes["https://news.google.com/rss/search?q=a"] = google_news(
            ("Monsoon session of parliament ends early", "TOKEN9", "The Hindu", "2026-11-11T08:00:00Z"))
        counts = self.run_fetch(now=NOW + timedelta(hours=1))
        self.assertEqual(counts["newItems"], 0)
        self.assertEqual(len(self.items()), 1)

    def test_short_headlines_are_not_merged_by_title(self):
        self.sources = [src("a", "https://a.example/feed", name="Same")]
        self.net.routes["https://a.example/feed"] = rss(("Live updates", "https://a.example/1", "2026-11-11T08:00:00Z"),
                                                         ("Live updates", "https://a.example/2", "2026-11-11T09:00:00Z"))
        self.run_fetch()
        self.assertEqual(len(self.items()), 2)


class Health(FetchCase):
    def test_failures_count_up_and_success_resets(self):
        self.sources = [src("a", "https://a.example/feed")]
        self.net.routes["https://a.example/feed"] = net.NetError("http", 403, "HTTP 403 Forbidden")
        self.run_fetch()
        self.run_fetch(now=NOW + timedelta(hours=1))
        record = self.health()["a"]
        self.assertEqual(record, {"ok": False, "items": 0, "newItems": 0, "ms": record["ms"], "error": "HTTP 403 Forbidden",
                                  "lastOkAt": None, "consecutiveFailures": 2})
        self.net.routes["https://a.example/feed"] = rss(("Back again after the outage", "https://a.example/b", "2026-11-11T15:00:00Z"))
        self.run_fetch(now=NOW + timedelta(hours=2))
        record = self.health()["a"]
        self.assertEqual((record["ok"], record["items"], record["newItems"], record["error"], record["lastOkAt"],
                          record["consecutiveFailures"]), (True, 1, 1, None, "2026-11-11T16:00:00Z", 0))
        self.net.routes["https://a.example/feed"] = net.NetError("timeout", None, "timed out after 20 s")
        self.run_fetch(now=NOW + timedelta(hours=3))
        record = self.health()["a"]
        self.assertEqual((record["ok"], record["lastOkAt"], record["consecutiveFailures"]),
                         (False, "2026-11-11T16:00:00Z", 1))

    def test_a_failing_source_keeps_its_stored_items(self):
        self.sources = [src("a", "https://a.example/feed")]
        self.net.routes["https://a.example/feed"] = rss(("Stored before the source broke", "https://a.example/s", "2026-11-11T09:00:00Z"))
        self.run_fetch()
        self.net.routes["https://a.example/feed"] = net.NetError("connection", None, "connection failed")
        self.run_fetch(now=NOW + timedelta(hours=1))
        self.assertEqual(len(self.items()), 1)

    def test_one_bad_source_of_each_kind_does_not_stop_the_others(self):
        self.sources = [src("down", "https://down.example/feed"),
                        src("html", "https://html.example/feed"),
                        src("crash", "https://crash.example/api", kind="hn"),
                        src("good", "https://good.example/feed")]
        self.net.routes.update({
            "https://down.example/feed": net.NetError("tls", None, "TLS error: certificate verify failed"),
            "https://html.example/feed": fixture("html-page.html"),
            "https://crash.example/api": b"{}",
            "https://good.example/feed": rss(("The one good story today", "https://good.example/1", "2026-11-11T09:00:00Z")),
        })

        def boom(source, ctx):
            ctx.get(source["url"])
            raise TypeError("unexpected None")

        with mock.patch.dict(fetch.ADAPTERS, {"hn": boom}):
            counts = self.run_fetch()
        health = self.health()
        self.assertEqual(health["down"]["error"], "TLS error: certificate verify failed")
        self.assertEqual(health["html"]["error"], "HTML page, not a feed")
        self.assertEqual(health["crash"]["error"], "TypeError: unexpected None")
        self.assertIn("Traceback", self.log)
        self.assertTrue(health["good"]["ok"])
        self.assertEqual((counts["ok"], counts["failed"], counts["items"]), (1, 3, 1))

    def test_unusable_bodies_lose_their_cache_validators(self):
        self.sources = [src("html", "https://html.example/feed"), src("good", "https://good.example/feed")]
        self.net.routes["https://html.example/feed"] = fixture("html-page.html")
        self.net.routes["https://good.example/feed"] = rss(("A good story for the cache", "https://good.example/1", "2026-11-11T09:00:00Z"))
        self.run_fetch()
        cache = jsonio.read_json(self.data / "state" / "http-cache.json")
        self.assertEqual(list(cache), ["https://good.example/feed"])

    def test_not_modified_is_ok_and_carries_the_item_count(self):
        self.sources = [src("a", "https://a.example/feed")]
        self.net.routes["https://a.example/feed"] = rss(("First of two stories", "https://a.example/1", "2026-11-11T09:00:00Z"),
                                                         ("Second of two stories", "https://a.example/2", "2026-11-11T10:00:00Z"))
        self.run_fetch()
        self.net.routes["https://a.example/feed"] = NOT_MODIFIED
        counts = self.run_fetch(now=NOW + timedelta(hours=1))
        record = self.health()["a"]
        self.assertEqual((record["ok"], record["items"], record["newItems"]), (True, 2, 0))
        self.assertEqual(counts["unchanged"], 1)
        self.assertEqual(len(self.items()), 2)

    def test_force_skips_conditional_requests(self):
        self.sources = [src("a", "https://a.example/feed")]
        seen = []

        def capture(url):
            return rss(("Story fetched without validators", "https://a.example/1", "2026-11-11T09:00:00Z"))

        self.net.routes["https://a.example/feed"] = capture
        original = self.net.__call__

        def spy(url, **kwargs):
            seen.append(kwargs.get("cache"))
            return original(url, **kwargs)

        with mock.patch.object(net, "fetch", spy):
            self.run_fetch()
            self.run_fetch(force=True)
        self.assertIsNotNone(seen[0])
        self.assertIsNone(seen[1])

    def test_invalid_entries_are_reported_and_removed_sources_drop_out(self):
        state = self.data / "state"
        state.mkdir(parents=True)
        jsonio.write_json(state / "source-health.json", {"gone": {"ok": True}})
        good = src("good", "https://good.example/feed")
        self.sources = [good, dict(good), {k: v for k, v in good.items() if k != "url"} | {"id": "nourl"},
                        dict(good, id="weird", kind="html:nope"), dict(good, id="off", enabled=False), "junk"]
        self.net.routes["https://good.example/feed"] = rss(("Only the valid source is fetched", "https://good.example/1", "2026-11-11T09:00:00Z"))
        self.run_fetch()
        health = self.health()
        self.assertEqual(set(health), {"good", "good#1", "nourl", "weird", "sources[5]"})
        self.assertEqual(health["good#1"]["error"], "invalid source config: duplicate id")
        self.assertEqual(health["nourl"]["error"], "invalid source config: missing url")
        self.assertEqual(health["weird"]["error"], "invalid source config: unknown kind 'html:nope'")
        self.assertEqual(health["sources[5]"]["error"], "invalid source config: entry is not an object")
        self.assertEqual(self.net.calls, ["https://good.example/feed"])


class Lanes(FetchCase):
    def test_google_news_sources_never_overlap(self):
        active, peak, lock = [0], [0], threading.Lock()

        def slow(url):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.02)
            with lock:
                active[0] -= 1
            return google_news(("Headline for query %s here" % url[-1], "T" + url[-1], "Reuters", "2026-11-11T08:00:00Z"))

        self.sources = [src("gn-%d" % n, "https://news.google.com/rss/search?q=%d" % n, kind="google-news")
                        for n in range(4)]
        self.sources += [src("other-%d" % n, "https://o%d.example/feed" % n) for n in range(4)]
        for source in self.sources[:4]:
            self.net.routes[source["url"]] = slow
        for source in self.sources[4:]:
            self.net.routes[source["url"]] = rss(("Other story %s" % source["id"], source["url"] + "/1", "2026-11-11T08:00:00Z"))
        self.run_fetch()
        self.assertEqual(peak[0], 1)
        self.assertEqual(len(self.items()), 8)

    def test_every_request_is_spaced_per_host(self):
        calls = []
        cache = net.HttpCache(self.data / "cache.json")
        self.net.routes["https://a.example/feed"] = b"<rss/>"
        with mock.patch.object(net, "polite", lambda host, interval: calls.append((host, interval))):
            fetch.SourceContext(NOW, cache, force=False).get("https://a.example/feed")
        self.assertEqual(calls, [("https://a.example/feed", fetch.HOST_INTERVAL_S)])

    def test_lane_assignment(self):
        self.assertEqual(fetch._lane(src("g", "https://news.google.com/rss", kind="google-news")), "google-news")
        self.assertEqual(fetch._lane(src("r", "https://www.reddit.com/r/x/.rss")), "reddit")
        self.assertIsNone(fetch._lane(src("b", "https://feeds.bbci.co.uk/news/rss.xml")))

    def test_results_come_back_in_config_order(self):
        sources = [src("s%d" % n, "https://s%d.example/feed" % n) for n in range(10)]
        for source in sources:
            self.net.routes[source["url"]] = rss(("Story from %s today" % source["id"], source["url"] + "/1", "2026-11-11T08:00:00Z"))
        with contextlib.redirect_stderr(io.StringIO()):
            results = fetch.fetch_all(sources, NOW, None)
        self.assertEqual([result.source["id"] for result in results], [source["id"] for source in sources])


class Offline(FetchCase):
    def test_offline_touches_nothing_and_reports_what_is_stored(self):
        self.sources = [src("a", "https://a.example/feed")]
        self.net.routes["https://a.example/feed"] = rss(("A stored story for offline", "https://a.example/1", "2026-11-11T09:00:00Z"))
        self.run_fetch()
        health_before = (self.data / "state" / "source-health.json").read_bytes()
        self.net.calls.clear()
        counts = self.run_fetch(now=NOW + timedelta(hours=1), offline=True)
        self.assertEqual(self.net.calls, [])
        self.assertEqual(counts, {"offline": True, "files": 1, "recentItems": 1, "sources": 1})
        self.assertEqual((self.data / "state" / "source-health.json").read_bytes(), health_before)


class LoadSources(unittest.TestCase):
    def check(self, entry):
        with mock.patch.object(config, "load", return_value={"sources": [entry]}):
            return fetch.load_sources(REAL_LOAD("site"))

    def test_problems_are_named_precisely(self):
        good = src("a", "https://a.example/feed")
        cases = {
            "unknown section 'sport'": dict(good, section="sport"),
            "tier must be 1-3 and mode one of curated/firehose/official": dict(good, tier=4),
            "maxItems must be a positive number": dict(good, maxItems=0),
            "maxAgeHours must be a positive number": dict(good, maxAgeHours=True),
            "missing kind, tier": {k: v for k, v in good.items() if k not in ("kind", "tier")},
        }
        for message, entry in cases.items():
            with self.subTest(message=message):
                sources, problems = self.check(entry)
                self.assertEqual((sources, list(problems.values())), ([], [message]))
        _, problems = self.check(dict(good, urlPattern="("))
        self.assertTrue(problems["a"].startswith("bad urlPattern"))

    def test_disabled_sources_are_skipped_silently(self):
        self.assertEqual(self.check(dict(src("a", "https://a.example/feed"), enabled=False)), ([], {}))

    def test_a_missing_sources_list_is_a_config_error(self):
        with mock.patch.object(config, "load", return_value={"feeds": []}):
            with self.assertRaises(config.ConfigError):
                fetch.load_sources(REAL_LOAD("site"))


class ShippedConfig(unittest.TestCase):
    """Guards on config/sources.json itself: valid, balanced, polite."""

    @classmethod
    def setUpClass(cls):
        cls.entries = REAL_LOAD("sources")["sources"]
        cls.site = REAL_LOAD("site")
        cls.enabled = [entry for entry in cls.entries if entry.get("enabled", True)]

    def test_every_enabled_source_is_valid(self):
        sources, problems = fetch.load_sources(self.site)
        self.assertEqual(problems, {})
        self.assertEqual(len(sources), len(self.enabled))

    def test_ids_are_unique_and_urls_are_https(self):
        ids = [entry["id"] for entry in self.entries]
        self.assertEqual(len(ids), len(set(ids)))
        for entry in self.entries:
            self.assertTrue(entry["url"].startswith("https://"), entry["id"])
            self.assertTrue(entry.get("homepage", "").startswith("https://"), entry["id"])

    def test_size_and_section_balance(self):
        self.assertTrue(130 <= len(self.enabled) <= 170, len(self.enabled))
        for section in self.site["sections"]:
            count = sum(1 for entry in self.enabled if entry["section"] == section["id"])
            self.assertGreaterEqual(count, 6, section["id"])

    def test_google_news_is_used_sparingly(self):
        self.assertLessEqual(sum(1 for entry in self.enabled if entry["kind"] == "google-news"), 16)

    def test_disabled_sources_say_why(self):
        for entry in self.entries:
            if not entry.get("enabled", True):
                self.assertTrue(entry.get("disabledReason"), entry["id"])

    def test_labs_lead_with_first_party_anthropic_and_claude_news(self):
        labs = {entry["id"]: entry for entry in self.enabled if entry["section"] == "labs"}
        for source_id in ("openai-news", "anthropic-news", "anthropic-research", "anthropic-engineering",
                          "claude-product-updates", "deepmind"):
            self.assertEqual(labs[source_id]["tier"], 1, source_id)

    def test_claude_changelogs_belong_to_the_claude_stage_not_here(self):
        for entry in self.entries:
            url = entry["url"].lower()
            self.assertFalse(("claude" in url or "anthropic" in url) and
                             any(word in url for word in ("changelog", "release-notes", "releases.atom")), entry["id"])


if __name__ == "__main__":
    unittest.main()
