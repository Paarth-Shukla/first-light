"""pipeline.adapters: the per-kind rules (aggregators, JSON APIs, RSC pages, sitemaps) and the registry."""

import json
import unittest
import urllib.parse

from pipeline import feeds
from pipeline.adapters import ADAPTERS, anthropic, google_news, hf_blog, hn, pulse, rss, sitemap_news, snapi, techmeme
from pipeline.core import config
from tests.pipeline.test_feeds import NOW, StubCtx, by_title, fixture, run_case, source


class NotModifiedCtx(StubCtx):
    """A context whose every request came back 304."""

    def get(self, url, headers=None):
        self.urls.append(url)
        return None

    def json(self, url):
        return self.get(url)


class Registry(unittest.TestCase):
    def test_every_configured_kind_has_an_adapter(self):
        kinds = {entry["kind"] for entry in config.load("sources")["sources"]}
        self.assertLessEqual(kinds, set(ADAPTERS))

    def test_adapters_are_callables(self):
        for kind, adapter in ADAPTERS.items():
            with self.subTest(kind=kind):
                self.assertTrue(callable(adapter))

    def test_not_modified_yields_nothing_for_every_kind(self):
        for kind, adapter in ADAPTERS.items():
            with self.subTest(kind=kind):
                ctx = NotModifiedCtx("unused")
                self.assertEqual(adapter(source(kind=kind), ctx), [])
                self.assertEqual(len(ctx.urls), 1)

    def test_rss_adapter_parses_the_source_url(self):
        ctx = StubCtx("bbc-top.xml")
        self.assertEqual(len(rss.fetch_items(source(url="https://feeds.bbci.co.uk/news/rss.xml"), ctx)), 3)
        self.assertEqual(ctx.urls, ["https://feeds.bbci.co.uk/news/rss.xml"])


class GoogleNews(unittest.TestCase):
    def test_publisher_tail_is_split_using_the_source_element(self):
        cases = [
            (("Iran will not allow material to leave - Reuters", "Reuters"), ("Iran will not allow material to leave", "Reuters")),
            (("Hijack alert on flight a hoax | India News - Hindustan Times", "Hindustan Times"),
             ("Hijack alert on flight a hoax", "Hindustan Times")),
            (("Sensex ends higher - live updates - Mint", "Mint"), ("Sensex ends higher - live updates", "Mint")),
            (("Without a source element at all - Scroll.in", None), ("Without a source element at all", "Scroll.in")),
            (("Tata - Sons", None), ("Tata - Sons", None)),
            (("Reuters", "Reuters"), ("Reuters", "Reuters")),
        ]
        for (title, publisher), wanted in cases:
            with self.subTest(title=title):
                self.assertEqual(google_news.split_title(title, publisher), wanted)

    def test_clustered_description_becomes_alt_without_the_item_itself(self):
        item = by_title(run_case("gnews-top.xml"))[
            "From Bachchans to Modi: What Sonia Gandhi says (and leaves out) in her book"]
        self.assertEqual(item["publisher"], "Scroll.in")
        self.assertEqual([alt["publisher"] for alt in item["alt"]],
                         ["NDTV", "The New Indian Express", "Telegraph India", "Deccan Herald"])
        self.assertTrue(all(alt["title"] and "<" not in alt["title"] for alt in item["alt"]))
        self.assertEqual(item["summary"], "")
        self.assertIsNone(item["image"])

    def test_opaque_links_are_kept_exactly(self):
        body = fixture("gnews-top.xml").decode("utf-8")
        for item in run_case("gnews-top.xml"):
            self.assertTrue(item["url"].startswith("https://news.google.com/rss/articles/"))
            self.assertIn("<link>%s</link>" % item["url"], body)

    def test_ticker_spam_publishers_are_dropped(self):
        self.assertRegex(fixture("gnews-search.xml").decode("utf-8"), r"<source[^>]*>(?:Benzinga|TradingView|MarketBeat|The Motley Fool|Seeking Alpha)<")
        self.assertEqual(len(run_case("gnews-search.xml")), 2)
        for name in ("MarketScreener.com", "www.marketscreener.com", "24/7 Wall St.", "The Motley Fool", "Benzinga"):
            self.assertTrue(google_news.is_spam(name), name)
        for name in ("Reuters", "The Globe and Mail", "Investing.com", None):
            self.assertFalse(google_news.is_spam(name), name)

    def test_seo_headlines_are_dropped(self):
        body = ("<rss><channel>%s</channel></rss>" % "".join(
            "<item><title>%s - Somewhere</title><link>https://news.google.com/rss/articles/T%d</link>"
            "<pubDate>Wed, 11 Nov 2026 10:00:00 GMT</pubDate><source url=\"https://s.example\">Somewhere</source></item>"
            % (title, n) for n, title in enumerate((
                "DeepSeek AI XRP Price Prediction: Could Ripple Really Go This High?",
                "3 AI stocks to buy before the year ends", "DeepSeek releases a new open-weight model")))).encode()

        class Ctx(StubCtx):
            def get(self, url, headers=None):
                return body

        items = google_news.fetch_items(source(kind="google-news"), Ctx("unused"))
        self.assertEqual([item["title"] for item in items], ["DeepSeek releases a new open-weight model"])

    def test_alternatives_skip_spam_and_duplicates(self):
        description = ('<ol><li><a href="x">Main story headline here</a>&nbsp;&nbsp;<font color="#6f6f6f">Reuters</font></li>'
                       '<li><a href="y">Other take &amp; more</a>&nbsp;&nbsp;<font color="#6f6f6f">BBC</font></li>'
                       '<li><a href="z">Ticker note</a>&nbsp;&nbsp;<font color="#6f6f6f">Benzinga</font></li>'
                       '<li><a href="w">Other take &amp; more</a>&nbsp;&nbsp;<font color="#6f6f6f">BBC</font></li></ol>')
        self.assertEqual(google_news.alternatives(description, "Main story headline here", "Reuters"),
                         [{"title": "Other take & more", "publisher": "BBC"}])

    def test_document_without_items_is_a_failure(self):
        ctx = StubCtx("verge-empty.atom")
        with self.assertRaisesRegex(feeds.FeedError, "no items"):
            google_news.fetch_items(source(kind="google-news"), ctx)


class Techmeme(unittest.TestCase):
    def test_items_point_at_the_article_not_the_permalink(self):
        for item in run_case("techmeme.xml"):
            self.assertNotIn("techmeme.com", item["url"])
            self.assertEqual(item["publisher"], "Bloomberg")
            self.assertNotRegex(item["title"], r"\)$")
            self.assertTrue(item["summary"])
            self.assertIsNone(item["image"])  # its only image is plain http

    def test_split_title(self):
        self.assertEqual(techmeme.split_title("Torus raised $500M (Mark Chediak/Bloomberg)"),
                         ("Torus raised $500M", "Bloomberg"))
        self.assertEqual(techmeme.split_title("Apple ships a thing (The Verge)"), ("Apple ships a thing", "The Verge"))
        self.assertEqual(techmeme.split_title("No byline here"), ("No byline here", None))

    def test_article_url_and_teaser(self):
        description = ('<A HREF="https://example.org/story"><IMG SRC="http://t/i.jpg"></A><P>A / <A HREF="https://example.org/">Pub</A>:'
                       '<BR><SPAN><B><A HREF="https://example.org/story">Head</A></B></SPAN>&nbsp; &mdash;&nbsp; The teaser text &hellip; </P>')
        self.assertEqual(techmeme.article_url(description), "https://example.org/story")
        self.assertEqual(techmeme.teaser(description), "The teaser text …")
        self.assertEqual(techmeme.article_url("no links"), "")


class Pulse(unittest.TestCase):
    def test_publisher_comes_from_the_link_host(self):
        self.assertEqual(pulse.publisher_for("https://www.ndtvprofit.com/markets/x"), "NDTV Profit")
        self.assertEqual(pulse.publisher_for("https://economictimes.indiatimes.com/markets/x"), "The Economic Times")
        self.assertEqual(pulse.publisher_for("https://www.example-news.in/a"), "example-news.in")
        self.assertIsNone(pulse.publisher_for(""))

    def test_items_carry_publishers(self):
        self.assertEqual([item["publisher"] for item in run_case("pulse.xml")], ["The Hindu", "NDTV Profit"])


class HackerNews(unittest.TestCase):
    def test_front_page_items_carry_points_and_comments_and_skip_job_ads(self):
        items = run_case("hn-front.json")
        self.assertEqual([(item["points"], item["comments"]) for item in items], [(1068, 374), (893, 192)])
        self.assertEqual([item["feedRank"] for item in items], [0, 1])
        self.assertFalse(any("hiring" in item["title"] for item in items))

    def test_missing_url_links_to_the_thread(self):
        entries = hn.entries_from({"hits": [{"title": "Ask HN: What are you reading?", "objectID": "123",
                                             "url": None, "points": 50, "num_comments": 9,
                                             "created_at": "2026-11-11T10:00:00Z", "_tags": ["story"]}]})
        self.assertEqual(entries[0]["link"], "https://news.ycombinator.com/item?id=123")

    def test_keyword_filter_matches_whole_words_and_plurals(self):
        matcher = hn.keyword_filter("https://hn.algolia.com/api/v1/search_by_date?query=LLM&tags=story")
        for title, wanted in (("LLMs play TIS-100", True), ("An LLM benchmark", True), ("LLMOps platform raises", False),
                              ("Using llm-cli daily", True), ("Smart home devices", False)):
            with self.subTest(title=title):
                self.assertEqual(bool(matcher.search(title.lower())), wanted)
        self.assertIsNone(hn.keyword_filter("https://hn.algolia.com/api/v1/search?tags=front_page"))

    def test_keyword_search_keeps_only_matching_titles(self):
        titles = [hit["title"] for hit in json.loads(fixture("hn-llm.json"))["hits"]]
        self.assertTrue(any("LLM" not in title for title in titles))
        self.assertTrue(all("LLM" in item["title"] for item in run_case("hn-llm.json")))

    def test_bad_payloads_are_failures(self):
        with self.assertRaisesRegex(feeds.FeedError, "no hits list"):
            hn.entries_from({"message": "rate limited"})

        class Empty(StubCtx):
            def json(self, url):
                return {"hits": []}

        with self.assertRaisesRegex(feeds.FeedError, "no hits"):
            hn.fetch_items(source(kind="hn"), Empty("unused"))

    def test_odd_counts_become_none(self):
        entry = hn.entries_from({"hits": [{"title": "T", "objectID": "1", "url": "https://e.org",
                                           "points": "12", "num_comments": -1}]})[0]
        self.assertEqual((entry["points"], entry["comments"]), (None, None))


class Anthropic(unittest.TestCase):
    def test_records_split_across_chunks_are_rejoined(self):
        page = fixture("anthropic-news.html").decode("utf-8")
        self.assertEqual(page.count("self.__next_f.push([1,"), 2)
        self.assertEqual(len(run_case("anthropic-news.html")), 4)

    def test_urls_follow_article_type_and_linked_url(self):
        urls = {item["title"]: item["url"] for item in run_case("anthropic-news.html")}
        self.assertEqual(urls["Anthropic launches roadshow for proposed initial public offering"],
                         "https://www.anthropic.com/news/roadshow-launch")
        self.assertEqual(urls["Teaching AI to build scientific models"],
                         "https://www.anthropic.com/research/teaching-ai-to-build-scientific-models")
        self.assertEqual(urls["Introducing Claude Fable 5.2 and Claude Mythos 5.2"],
                         "https://www.anthropic.com/claude-fable-and-mythos-5-2")

    def test_relative_linked_url_is_resolved(self):
        entry = anthropic.entry_for({"_type": "article", "title": "Introducing Claude Haiku 5.5",
                                     "publishedOn": "2026-10-01", "slug": {"current": "haiku"},
                                     "linkedUrl": "/claude-haiku-5-5", "articleType": "news"})
        item = feeds.build_items([entry], source(url="https://www.anthropic.com/news", maxAgeHours=10000), NOW)[0]
        self.assertEqual(item["url"], "https://www.anthropic.com/claude-haiku-5-5")

    def test_claude_posts_use_the_article_path_and_raster_og_image(self):
        for item in run_case("claude-product-updates.html"):
            self.assertTrue(item["url"].startswith("https://claude.com/resources/articles/"))
            self.assertEqual(item["image"], item["url"] + "/opengraph-image/og")

    def test_other_records_are_ignored(self):
        for record in ({"_type": "slug", "current": "x"}, {"_type": "article", "title": "No date", "slug": {"current": "x"}},
                       {"_type": "blogPost", "title": "", "slug": "x", "date": "2026-11-10"},
                       {"_type": "blogPost", "title": "Slug object", "slug": {"current": "x"}, "date": "2026-11-10"}):
            self.assertIsNone(anthropic.entry_for(record))

    def test_markup_changes_are_reported_not_silent(self):
        with self.assertRaisesRegex(feeds.FeedError, "no Next.js RSC payload"):
            anthropic.entries_from("<html><body><h1>News</h1></body></html>")
        page = '<script>self.__next_f.push([1,"{\\"_id\\":\\"x\\",\\"_type\\":\\"page\\"}"])</script>'
        with self.assertRaisesRegex(feeds.FeedError, "no articles"):
            anthropic.entries_from(page)

    def test_fullest_record_wins_for_a_link(self):
        page = ('<script>self.__next_f.push([1,%s])</script>' % json.dumps(
            '{"_id":"a","_type":"article","title":"T","publishedOn":"2026-11-10","slug":{"current":"t"},"articleType":"news"}'
            '{"_id":"b","_type":"article","title":"T","publishedOn":"2026-11-10","slug":{"current":"t"},'
            '"articleType":"news","summary":"The fuller record has a summary.","cardImage":{"url":"https://cdn.example.org/t.jpg"}}'))
        entries = anthropic.entries_from(page)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["summary"], "The fuller record has a summary.")


class SpaceflightNews(unittest.TestCase):
    def test_request_asks_for_the_age_window_only(self):
        url = snapi.request_url(source(url="https://api.spaceflightnewsapi.net/v4/articles/?limit=50&published_at_gte=old",
                                       maxAgeHours=48), NOW)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query, {"limit": ["50"], "published_at_gte": ["2026-11-09T14:00:00Z"]})

    def test_news_site_becomes_publisher_and_post_footer_is_gone(self):
        items = run_case("snapi.json")
        self.assertEqual([item["publisher"] for item in items], ["SpaceNews", "European Spaceflight"])
        self.assertFalse(any("appeared first on" in item["summary"] for item in items))

    def test_bad_payload_is_a_failure(self):
        with self.assertRaisesRegex(feeds.FeedError, "no results"):
            snapi.entries_from({"detail": "throttled"})


class HuggingFaceBlog(unittest.TestCase):
    def test_only_official_posts_with_absolute_thumbnails(self):
        items = run_case("hf-blog.json")
        self.assertEqual(len(json.loads(fixture("hf-blog.json"))["allBlogs"]), 3)
        self.assertEqual([item["url"] for item in items],
                         ["https://huggingface.co/blog/hub-gcp-marketplace", "https://huggingface.co/blog/decision"])
        self.assertTrue(all(item["image"].startswith("https://huggingface.co/blog/assets/") for item in items))

    def test_is_official(self):
        self.assertTrue(hf_blog.is_official({"url": "/blog/decision"}))
        self.assertFalse(hf_blog.is_official({"url": "/blog/nvidia/nemotron"}))
        self.assertFalse(hf_blog.is_official({}))

    def test_bad_payload_is_a_failure(self):
        with self.assertRaisesRegex(feeds.FeedError, "allBlogs"):
            hf_blog.entries_from([])


class NewsSitemap(unittest.TestCase):
    def test_entries_carry_title_date_and_image(self):
        entries = sitemap_news.entries_from(fixture("moneycontrol-sitemap.xml"))
        self.assertEqual(len(entries), 3)
        self.assertTrue(all(entry["title"] and entry["published"] and entry["image"] for entry in entries))

    def test_url_pattern_keeps_business_paths(self):
        self.assertEqual(len(run_case("moneycontrol-sitemap.xml")), 2)

    def test_a_feed_is_not_a_sitemap(self):
        with self.assertRaisesRegex(feeds.FeedError, "urlset"):
            sitemap_news.entries_from(fixture("bbc-top.xml"))


if __name__ == "__main__":
    unittest.main()
