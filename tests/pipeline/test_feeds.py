"""pipeline.feeds: formats, repairs, images, summaries, dates and ordering, on trimmed real feeds.

Every fixture in tests/fixtures/feeds/ is a real response from 2026-11-11, cut
down to a few items. ``CASES`` runs each through its adapter and compares the
whole output with tests/fixtures/feeds/expected/<fixture>.json; the classes
below then pin each individual quirk so a failure says what broke.
"""

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from pipeline import feeds
from pipeline.adapters import ADAPTERS
from pipeline.core import textutil, timeutil

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "feeds"
NOW = datetime(2026, 11, 11, 14, 0, tzinfo=timezone.utc)


def fixture(name):
    return (FIXTURES / name).read_bytes()


def source(**overrides):
    """A valid source entry; tests override only what they exercise."""
    base = {"id": "test", "name": "Test", "url": "https://example.org/feed", "kind": "rss",
            "section": "world", "topics": ["t"], "tier": 2, "mode": "firehose", "maxItems": 15,
            "maxAgeHours": 48}
    base.update(overrides)
    return base


class StubCtx:
    """The adapter context, serving one fixture for every URL and recording the URLs asked for."""

    def __init__(self, name, now=NOW):
        self.name = name
        self.now = now
        self.urls = []

    def get(self, url, headers=None):
        self.urls.append(url)
        return fixture(self.name)

    def json(self, url):
        return json.loads(self.get(url))


# fixture -> (kind, source overrides). Windows are wide where a feed is low-volume.
CASES = {
    "bbc-top.xml": ("rss", {"mode": "curated"}),
    "guardian-world.xml": ("rss", {"mode": "curated"}),
    "verge.atom": ("rss", {}),
    "apple-newsroom.atom": ("rss", {"mode": "official", "maxAgeHours": 168}),
    "dw-top.rdf": ("rss", {"mode": "curated"}),
    "nature.rdf": ("rss", {"maxAgeHours": 168, "urlPattern": "/d41586-"}),
    "rbi-press.xml": ("rss", {"mode": "official", "maxAgeHours": 168, "timezone": "Asia/Kolkata"}),
    "indiatoday-top.xml": ("rss", {}),
    "google-devs-undated.xml": ("rss", {"mode": "official"}),
    "npr-world.xml": ("rss", {}),
    "wired-ai.xml": ("rss", {}),
    "toi-india.xml": ("rss", {}),
    "nasa-science.xml": ("rss", {}),
    "ars-ai.xml": ("rss", {"maxAgeHours": 168}),
    "rediff-latin1.xml": ("rss", {}),
    "gnews-top.xml": ("google-news", {"mode": "curated"}),
    "gnews-search.xml": ("google-news", {}),
    "techmeme.xml": ("rss:techmeme", {"mode": "curated"}),
    "pulse.xml": ("rss:pulse", {}),
    "hn-front.json": ("hn", {"mode": "curated", "url": "https://hn.algolia.com/api/v1/search?tags=front_page"}),
    "hn-llm.json": ("hn", {"maxAgeHours": 72,
                           "url": "https://hn.algolia.com/api/v1/search_by_date?query=LLM&tags=story"}),
    "anthropic-news.html": ("html:anthropic", {"mode": "official", "maxAgeHours": 720,
                                               "url": "https://www.anthropic.com/news"}),
    "claude-product-updates.html": ("html:anthropic", {"mode": "official", "maxAgeHours": 168,
                                                       "url": "https://claude.com/resources/product-updates"}),
    "snapi.json": ("json:snapi", {"url": "https://api.spaceflightnewsapi.net/v4/articles/?limit=50"}),
    "hf-blog.json": ("json:hf-blog", {"mode": "official", "maxAgeHours": 168}),
    "moneycontrol-sitemap.xml": ("sitemap-news", {"urlPattern": "/news/business/(?:markets|stocks)/"}),
}


def run_case(name):
    kind, overrides = CASES[name]
    return ADAPTERS[kind](source(kind=kind, **overrides), StubCtx(name))


def expected(name):
    return json.loads((FIXTURES / "expected" / (name + ".json")).read_text(encoding="utf-8"))


def by_title(items):
    return {item["title"]: item for item in items}


class GoldenOutput(unittest.TestCase):
    def test_every_fixture_parses_to_its_expected_items(self):
        for name in CASES:
            with self.subTest(fixture=name):
                self.assertEqual(run_case(name), expected(name))

    def test_every_fixture_yields_items(self):
        for name in CASES:
            with self.subTest(fixture=name):
                self.assertTrue(run_case(name), "no items from %s" % name)

    def test_items_have_exactly_the_contract_fields(self):
        keys = {"id", "url", "title", "summary", "source", "sourceName", "publishedAt", "firstSeenAt",
                "image", "section", "topics", "feedRank", "publisher", "points", "comments", "alt"}
        for name in CASES:
            for item in run_case(name):
                with self.subTest(fixture=name, title=item["title"]):
                    self.assertEqual(set(item), keys)
                    self.assertTrue(item["url"].startswith("https://"))
                    self.assertLessEqual(len(item["summary"]), feeds.SUMMARY_LIMIT)
                    self.assertNotRegex(item["title"], r"<[a-zA-Z/]|&[a-z]+;|^\s|\s$")
                    self.assertLessEqual(item["publishedAt"], timeutil.iso(NOW))
                    if item["image"]:
                        self.assertTrue(item["image"].startswith("https://"), item["image"])


class Formats(unittest.TestCase):
    def test_root_tag_decides_the_format(self):
        self.assertEqual(feeds.document(fixture("verge.atom"))[0], "atom")
        self.assertEqual(feeds.document(fixture("dw-top.rdf"))[0], "rdf")
        self.assertEqual(feeds.document(fixture("bbc-top.xml"))[0], "rss")

    def test_rdf_items_outside_channel_are_found(self):
        kind, root = feeds.document(fixture("dw-top.rdf"))
        self.assertEqual(len(feeds.entry_elements(kind, root)), 3)
        self.assertEqual(len(run_case("dw-top.rdf")), 3)

    def test_html_page_with_status_200_is_a_failure(self):
        with self.assertRaisesRegex(feeds.FeedError, "HTML page"):
            feeds.parse(fixture("html-page.html"), source(), NOW)

    def test_valid_feed_with_no_entries_is_a_failure(self):
        with self.assertRaisesRegex(feeds.FeedError, "no items"):
            feeds.parse(fixture("verge-empty.atom"), source(), NOW)

    def test_empty_and_whitespace_bodies_are_failures(self):
        for body in (b"", b"  \n\t"):
            with self.assertRaisesRegex(feeds.FeedError, "empty"):
                feeds.parse(body, source(), NOW)

    def test_unknown_root_is_a_failure(self):
        with self.assertRaisesRegex(feeds.FeedError, "unrecognised feed root <urlset>"):
            feeds.document(fixture("moneycontrol-sitemap.xml"))

    def test_nasa_glued_namespace_attributes_are_repaired(self):
        body = fixture("nasa-science.xml")
        self.assertIn(b'apod/"xmlns:media', body)
        self.assertEqual(len(feeds.parse(body, source(), NOW)), 2)

    def test_utf8_bom_is_accepted(self):
        self.assertTrue(fixture("rbi-press.xml").startswith(b"\xef\xbb\xbf"))
        self.assertEqual(len(run_case("rbi-press.xml")), 2)

    def test_declared_latin1_bytes_are_decoded(self):
        body = ('<?xml version="1.0" encoding="ISO-8859-1"?><rss><channel><item>'
                '<title>Café owners in München protest rents</title>'
                '<link>https://example.org/a</link></item></channel></rss>').encode("latin-1")
        self.assertEqual(feeds.parse(body, source(), NOW)[0]["title"], "Café owners in München protest rents")

    def test_declared_multibyte_encoding_is_transcoded(self):
        body = ('<?xml version="1.0" encoding="gb2312"?><rss><channel><item><title>人工智能'
                '新闻标题</title><link>https://example.org/a</link></item></channel></rss>'
                ).encode("gb2312")
        self.assertEqual(feeds.parse(body, source(), NOW)[0]["title"], "人工智能新闻标题")

    def test_unknown_declared_encoding_is_a_failure_not_a_crash(self):
        body = b'<?xml version="1.0" encoding="no-such-codec"?><rss><channel><item><title>x</title></item></channel></rss>'
        with self.assertRaisesRegex(feeds.FeedError, "encoding"):
            feeds.parse(body, source(), NOW)

    def test_bare_ampersands_html_entities_and_control_characters_are_repaired(self):
        body = (b"<rss><channel><item><title>Q&A: Tata &amp; Sons&nbsp;plan \x0b\xe2\x82\xb9500 crore</title>"
                b"<link>https://example.org/a?x=1&y=2</link></item></channel></rss>")
        item = feeds.parse(body, source(), NOW)[0]
        self.assertEqual(item["title"], "Q&A: Tata & Sons plan ₹500 crore")
        self.assertEqual(item["url"], "https://example.org/a?x=1&y=2")

    def test_entity_declarations_are_refused(self):
        body = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><rss><channel><item><title>&a;</title></item></channel></rss>'
        with self.assertRaisesRegex(feeds.FeedError, "entities"):
            feeds.parse(body, source(), NOW)

    def test_garbage_is_a_failure(self):
        with self.assertRaisesRegex(feeds.FeedError, "not well-formed"):
            feeds.parse(b"<rss><channel><item><title>open", source(), NOW)

    def test_xhtml_atom_title_and_unescaped_html_description(self):
        body = (b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title type="xhtml">'
                b'<div xmlns="http://www.w3.org/1999/xhtml">Chips <b>bold</b> move</div></title>'
                b'<link href="https://example.org/a"/><updated>2026-11-11T10:00:00Z</updated>'
                b'<summary type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml"><p>A summary long enough to'
                b' be kept by the cleaner, with <img src="https://cdn.example.org/a.jpg"/> inline.</p></div>'
                b'</summary></entry></feed>')
        item = feeds.parse(body, source(), NOW)[0]
        self.assertEqual(item["title"], "Chips bold move")
        self.assertEqual(item["summary"], "A summary long enough to be kept by the cleaner, with inline.")
        self.assertEqual(item["image"], "https://cdn.example.org/a.jpg")


class Images(unittest.TestCase):
    def test_usable_image_rules(self):
        cases = {
            "undefined": None,
            "http://www.techmeme.com/261111/i27.jpg": None,
            "https://www.hindustantimes.com/ht-img/img/logo/ht-generic_india1.jpg": None,
            "https://media.npr.org/include/images/tracking/npr-rss-pixel.png?story=1": None,
            "https://avatars.githubusercontent.com/u/1?s=60&v=4": None,
            "https://s.w.org/images/core/emoji/15.0.3/72x72/1f680.png": None,
            "//cdn.example.org/a.jpg": "https://cdn.example.org/a.jpg",
            "https://cdn.example.org/a.jpg?w=1&amp;h=2": "https://cdn.example.org/a.jpg?w=1&h=2",
            "https://ichef.bbci.co.uk/ace/standard/240/cpsprodpb/x.jpg":
                "https://ichef.bbci.co.uk/ace/standard/976/cpsprodpb/x.jpg",
        }
        for url, wanted in cases.items():
            with self.subTest(url=url):
                self.assertEqual(feeds.usable_image(url), wanted)
        self.assertEqual(feeds.usable_image("/blog/assets/x/thumb.png", "https://huggingface.co/"),
                         "https://huggingface.co/blog/assets/x/thumb.png")

    def test_bbc_thumbnails_are_upscaled(self):
        for item in run_case("bbc-top.xml"):
            self.assertIn("/976/", item["image"])

    def test_widest_media_content_wins(self):
        for item in run_case("guardian-world.xml"):
            self.assertIn("width=700", item["image"])

    def test_empty_media_content_falls_through_to_thumbnail(self):
        body = fixture("wired-ai.xml")
        self.assertIn(b"<media:content/>", body)
        for item in run_case("wired-ai.xml"):
            self.assertTrue(item["image"].startswith("https://media.wired.com/photos/"))

    def test_atom_enclosure_link_is_the_image(self):
        for item in run_case("apple-newsroom.atom"):
            self.assertRegex(item["image"], r"^https://www\.apple\.com/newsroom/images/.*\.jpg")

    def test_npr_single_quoted_img_and_tracking_pixel(self):
        images = [item["image"] for item in run_case("npr-world.xml")]
        self.assertTrue(any(image and image.startswith("https://npr.brightspotcdn.com/") for image in images))
        self.assertFalse(any(image and "tracking" in image for image in images))

    def test_video_enclosure_is_not_an_image_but_image_enclosure_is(self):
        body = (b'<rss><channel><item><title>Video item title here</title><link>https://example.org/v</link>'
                b'<enclosure url="https://cdn.example.org/v.mp4" type="video/mp4"/></item>'
                b'<item><title>Image item title here</title><link>https://example.org/i</link>'
                b'<enclosure url="https://cdn.example.org/i.jpg" type="image/jpeg" length="0"/></item>'
                b'</channel></rss>')
        items = feeds.parse(body, source(mode="curated"), NOW)
        self.assertEqual([item["image"] for item in items], [None, "https://cdn.example.org/i.jpg"])

    def test_lookup_order(self):
        media = '<media:content url="https://c.example/content.jpg" width="10"/>'
        thumb = '<media:thumbnail url="https://c.example/thumb.jpg"/>'
        enclosure = '<enclosure url="https://c.example/enclosure.jpg" type="image/jpeg"/>'
        body_img = '<content:encoded><![CDATA[<p><img src="https://c.example/body.jpg"></p>]]></content:encoded>'
        desc_img = '<description><![CDATA[<img src="https://c.example/desc.jpg"> A description long enough.]]></description>'
        layers = [media, thumb, enclosure, body_img, desc_img]
        wanted = ["content", "thumb", "enclosure", "body", "desc"]
        for start, name in enumerate(wanted):
            body = ('<rss xmlns:media="http://search.yahoo.com/mrss/" xmlns:content="http://purl.org/rss/1.0/modules/'
                    'content/"><channel><item><title>Image order story</title><link>https://example.org/a</link>%s'
                    '</item></channel></rss>' % "".join(layers[start:]))
            with self.subTest(expected=name):
                self.assertEqual(feeds.parse(body.encode(), source(), NOW)[0]["image"], "https://c.example/%s.jpg" % name)

    def test_first_img_takes_uppercase_tags_and_skips_one_pixel_images(self):
        markup = ("<IMG SRC='https://x.example.org/p.gif' WIDTH=1 HEIGHT=1>"
                  '<p><img alt="" src="https://x.example.org/real.jpg"></p>')
        self.assertEqual(feeds.first_img(markup), "https://x.example.org/real.jpg")


class Summaries(unittest.TestCase):
    def test_media_description_caption_is_never_the_summary(self):
        body = (b'<rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item><title>Flood waters rise in the valley</title>'
                b'<link>https://example.org/a</link><media:content url="https://c.example/a.jpg">'
                b'<media:description>Residents wade through a flooded street on Tuesday. Photo: Agency</media:description>'
                b'</media:content></item></channel></rss>')
        self.assertEqual(feeds.parse(body, source(), NOW)[0]["summary"], "")

    def test_summary_that_repeats_the_title_is_blank(self):
        entry = {"title": "Sensex closes 400 points higher on bank rally",
                 "summary": "Sensex closes 400 points higher on bank rally.", "link": "https://example.org/a"}
        self.assertEqual(feeds.build_items([entry], source(), NOW)[0]["summary"], "")

    def test_short_summary_is_blank_and_content_is_the_fallback(self):
        entry = {"title": "A headline", "summary": "A short dek.", "link": "https://example.org/a",
                 "content": "<p>The opening paragraph of the full post explains what happened and why.</p>"}
        self.assertEqual(feeds.build_items([entry], source(), NOW)[0]["summary"],
                         "The opening paragraph of the full post explains what happened and why.")

    def test_title_echo_at_the_start_of_a_summary_is_cut(self):
        entry = {"title": "Army wing gets new address",
                 "summary": "Army wing gets new address. The directorate moves from South Block this month.",
                 "link": "https://example.org/a"}
        self.assertEqual(feeds.build_items([entry], source(), NOW)[0]["summary"],
                         "The directorate moves from South Block this month.")

    def test_long_html_summary_is_cleaned_and_truncated(self):
        summaries = [item["summary"] for item in run_case("guardian-world.xml")]
        for summary in summaries:
            self.assertLessEqual(len(summary), 300)
            self.assertTrue(summary.endswith("…"))
            self.assertNotIn("Continue reading", summary)

    def test_newsletter_plug_is_removed(self):
        entry = {"title": "Directors disqualified", "link": "https://example.org/a",
                 "summary": "<p>Three directors were fined in a federal court judgment.</p>"
                            "<p>Get our breaking news email, free app or daily news podcast</p>"}
        self.assertEqual(feeds.build_items([entry], source(), NOW)[0]["summary"],
                         "Three directors were fined in a federal court judgment.")

    def test_reddit_footer_is_removed(self):
        link_post = {"title": "NVIDIA cancels a GPU launch", "link": "https://example.org/a",
                     "content": '&#32; submitted by &#32; <a href="https://www.reddit.com/user/x"> /u/Norwood_Reaper_ </a>'
                                ' &#32; to &#32; <a href="https://www.reddit.com/r/LocalLLaMA/"> r/LocalLLaMA </a>'
                                ' <br/> <span><a href="https://e.org">[link]</a></span> <span><a href="https://e.org/c">'
                                '[comments]</a></span>'}
        text_post = dict(link_post, content="<p>Be careful if you are running any sketchy quants or finetunes this week.</p>"
                                            + link_post["content"])
        items = feeds.build_items([link_post, dict(text_post, link="https://example.org/b")], source(mode="curated"), NOW)
        self.assertEqual([item["summary"] for item in items],
                         ["", "Be careful if you are running any sketchy quants or finetunes this week."])

    def test_nature_published_online_prefix_is_removed(self):
        for item in run_case("nature.rdf"):
            self.assertNotIn("Published online", item["summary"])

    def test_scraped_navigation_is_not_a_summary(self):
        apod = by_title(run_case("nasa-science.xml"))
        self.assertEqual(apod["APOD: 2026 November 11 – NGC 4449: Small Galaxy, Big Impact"]["summary"], "")
        prose = "Prime Minister Narendra Modi on Tuesday inaugurated the Delhi Metro's Phase Four corridor."
        entry = {"title": "Metro opens", "summary": prose, "link": "https://example.org/a"}
        self.assertEqual(feeds.build_items([entry], source(), NOW)[0]["summary"], prose)


class Dates(unittest.TestCase):
    def entry(self, published, link="https://example.org/a"):
        return {"title": "Title of the story", "link": link, "published": published}

    def test_future_dates_are_clamped_to_now(self):
        item = feeds.build_items([self.entry("Thu, 12 Nov 2026 00:00:00 GMT")], source(), NOW)[0]
        self.assertEqual(item["publishedAt"], "2026-11-11T14:00:00Z")

    def test_undated_items_count_as_seen_now(self):
        for item in run_case("google-devs-undated.xml"):
            self.assertEqual(item["publishedAt"], "2026-11-11T14:00:00Z")

    def test_items_older_than_the_window_are_dropped(self):
        entries = [self.entry("2026-11-09T13:59:00Z", "https://example.org/old"),
                   self.entry("2026-11-09T14:01:00Z", "https://example.org/new")]
        items = feeds.build_items(entries, source(maxAgeHours=48), NOW)
        self.assertEqual([item["url"] for item in items], ["https://example.org/new"])

    def test_naive_dates_use_the_source_timezone(self):
        items = run_case("rbi-press.xml")
        self.assertEqual(items[0]["publishedAt"], "2026-11-11T12:40:00Z")  # 18:10 IST

    def test_atom_entry_with_only_updated(self):
        self.assertEqual(run_case("apple-newsroom.atom")[0]["publishedAt"], "2026-11-10T16:00:26Z")

    def test_date_only_values(self):
        self.assertTrue(all(item["publishedAt"].endswith("T00:00:00Z") for item in run_case("nature.rdf")))


class Ordering(unittest.TestCase):
    def entries(self):
        return [
            {"title": "Pinned evergreen promo", "link": "https://example.org/promo", "published": "2025-04-30T09:00:00Z"},
            {"title": "Second story of the day", "link": "https://example.org/b", "published": "2026-11-11T08:00:00Z"},
            {"title": "Newest story of the day", "link": "https://example.org/c", "published": "2026-11-11T12:00:00Z"},
            {"title": "Oldest kept story", "link": "https://example.org/d", "published": "2026-11-10T20:00:00Z"},
        ]

    def test_curated_feeds_keep_feed_order_as_feed_rank(self):
        items = feeds.build_items(self.entries(), source(mode="curated", maxItems=2), NOW)
        self.assertEqual([(item["title"], item["feedRank"]) for item in items],
                         [("Second story of the day", 0), ("Newest story of the day", 1)])

    def test_firehoses_sort_newest_first_without_rank(self):
        items = feeds.build_items(self.entries(), source(mode="firehose", maxItems=2), NOW)
        self.assertEqual([(item["title"], item["feedRank"]) for item in items],
                         [("Newest story of the day", None), ("Second story of the day", None)])

    def test_official_feeds_sort_like_firehoses(self):
        items = feeds.build_items(self.entries(), source(mode="official"), NOW)
        self.assertEqual(items[0]["title"], "Newest story of the day")

    def test_duplicate_entries_in_one_feed_collapse(self):
        entries = self.entries()[1:] + [dict(self.entries()[1], link="https://example.org/b?utm_source=rss")]
        self.assertEqual(len(feeds.build_items(entries, source(), NOW)), 3)

    def test_url_pattern_filters_before_the_cap(self):
        titles = [item["title"] for item in run_case("nature.rdf")]
        self.assertEqual(len(titles), 2)
        items = run_case("moneycontrol-sitemap.xml")
        self.assertTrue(all("/news/business/" in item["url"] for item in items))
        self.assertEqual(len(items), 2)


class Links(unittest.TestCase):
    def test_tracking_parameters_and_fragments_are_stripped(self):
        for item in run_case("bbc-top.xml"):
            self.assertNotIn("at_medium", item["url"])
        pulse = run_case("pulse.xml")
        self.assertFalse(any("#" in item["url"] for item in pulse))

    def test_http_links_are_upgraded_and_relative_links_resolved(self):
        entries = [{"title": "Plain http link story", "link": "http://bair.berkeley.edu/blog/2026/11/09/x/"},
                   {"title": "Relative link story", "link": "/news/relative-story"},
                   {"title": "Not a web link story", "link": "mailto:desk@example.org"}]
        items = feeds.build_items(entries, source(mode="curated"), NOW)
        self.assertEqual([item["url"] for item in items],
                         ["https://bair.berkeley.edu/blog/2026/11/09/x", "https://example.org/news/relative-story"])

    def test_cdata_padded_links_and_titles_are_trimmed(self):
        self.assertIn(b"<link><![CDATA[ https://", fixture("indiatoday-top.xml"))
        for item in run_case("indiatoday-top.xml"):
            self.assertTrue(item["url"].startswith("https://www.indiatoday.in/"))
            self.assertNotIn("utm_", item["url"])

    def test_id_is_derived_from_the_canonical_url(self):
        item = run_case("bbc-top.xml")[0]
        self.assertEqual(item["id"], textutil.stable_id("i", item["url"]))


if __name__ == "__main__":
    unittest.main()
