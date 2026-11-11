"""pipeline.core.textutil: feed text cleaning, URL canonicalisation, ids, tokens and stems."""

import hashlib
import json
import re
import unittest
from pathlib import Path

from pipeline.core import textutil
from pipeline.core.textutil import (
    STOPWORDS, canonical_url, clean_text, norm_title, stable_id, stem, tokenize, truncate)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
VECTORS = json.loads((FIXTURES / "stem-vectors.json").read_text(encoding="utf-8"))
SAMPLES = json.loads((FIXTURES / "core" / "real-feed-samples.json").read_text(encoding="utf-8"))


class CleanTextMarkup(unittest.TestCase):
    def check(self, cases):
        for raw, expected in cases:
            self.assertEqual(clean_text(raw), expected, repr(raw))

    def test_empty_and_non_string_input(self):
        self.check([(None, ""), ("", ""), ("   \n\t ", ""), (123, "123"), (0, "0")])

    def test_plain_text_is_left_alone(self):
        text = "Sensex rises 0.95% as crude eases; Nifty above 25,250."
        self.assertEqual(clean_text(text), text)

    def test_inline_tags_close_up(self):
        self.check([
            ("H<sub>2</sub>O and CO<sub>2</sub>", "H2O and CO2"),
            ("<b>Bold</b> and <i>italic</i> and <a href='x'>a link</a>.", "Bold and italic and a link."),
            ("An <em>emph</em>atic word", "An emphatic word"),
            ("<span class=\"x\">Span</span><strong>Strong</strong>", "SpanStrong"),
            ("<article-title>kept apart</article-title>", "kept apart"),
        ])

    def test_block_tags_separate_text(self):
        self.check([
            ("<p>One.</p><p>Two.</p>", "One. Two."),
            ("<div>Alpha!</div><div>Beta?</div>", "Alpha! Beta?"),
            ("Line one.<br>Line two.<br/>Line three.", "Line one. Line two. Line three."),
            ("<td>Cell A</td><td>Cell B</td>", "Cell A Cell B"),
            ("<img src='a.jpg'/>Caption text", "Caption text"),
        ])

    def test_paragraph_without_a_full_stop_gets_one(self):
        self.check([
            ("<p>Standfirst without a stop</p><p>Body text follows.</p>", "Standfirst without a stop. Body text follows."),
            ("<h2>Heading</h2><p>Text.</p>", "Heading. Text."),
            ("<ul><li>Added fast mode</li><li>Added voice input</li></ul>", "Added fast mode. Added voice input"),
            ("<p>Ends with a colon:</p><p>then more</p>", "Ends with a colon: then more"),
            ("<p></p><p> </p><p>Only one</p>", "Only one"),
        ])

    def test_hidden_content_is_removed(self):
        self.check([
            ("Before<script>alert('x < y')</script>After", "Before After"),
            ("<style>p { color: red }</style>Visible", "Visible"),
            ("Shown<!-- a comment with <b>tags</b> -->Text", "Shown Text"),
            ("<iframe src='x'>fallback</iframe>Real", "Real"),
            ("<SCRIPT TYPE='text/javascript'>var a;</SCRIPT>Upper", "Upper"),
        ])

    def test_uppercase_and_attribute_heavy_tags(self):
        raw = ('<A HREF="https://example.com/x"><IMG VSPACE="4" SRC="http://example.com/i.jpg"></A>\n'
               '<P>Author / <A HREF="http://example.com/">Outlet</A>:<BR>\n<SPAN STYLE="font-size:1.3em;">'
               '<B><A HREF="https://example.com/x">Headline here</A></B></SPAN>&nbsp; &mdash;&nbsp; Summary text.</P>')
        self.assertEqual(clean_text(raw), "Author / Outlet: Headline here — Summary text.")

    def test_escaped_html(self):
        self.check([
            ("&lt;p&gt;Hello &amp;amp; goodbye&lt;/p&gt;", "Hello & goodbye"),
            ("&lt;a href=&quot;https://example.com&quot;&gt;Title&lt;/a&gt;&amp;nbsp;&amp;nbsp;&lt;font color=&quot;#6f6f6f&quot;&gt;Publisher&lt;/font&gt;",
             "Title Publisher"),
        ])

    def test_double_escaped_html_and_entities(self):
        self.check([
            ("&amp;lt;b&amp;gt;Bold&amp;lt;/b&amp;gt; claim", "Bold claim"),
            ("AT&amp;amp;T results", "AT&T results"),
            ("It&amp;#8217;s here", "It’s here"),
            ("Fish &amp;amp;amp; chips", "Fish &amp; chips"),   # three levels is past what feeds do
        ])

    def test_entities(self):
        self.check([
            ("It&#8217;s &#x2019;quoted&#x2019;", "It’s ’quoted’"),
            ("Caf&eacute; &mdash; fine &hellip;", "Café — fine …"),
            ("AT&amp;T &amp; Verizon", "AT&T & Verizon"),
            ("SpaceX and AT&#038;T", "SpaceX and AT&T"),
            ("R&D and Q&A stay", "R&D and Q&A stay"),
            ("5 &lt; 10 &gt; 3", "5 < 10 > 3"),
            ("France&#039;s game", "France's game"),
        ])

    def test_cdata_leftovers(self):
        self.check([
            ("<![CDATA[Hello <b>world</b>]]>", "Hello world"),
            ("Title text]]>", "Title text"),
            ("<![CDATA[ padded ]]>", "padded"),
            ("&lt;![CDATA[Escaped wrapper]]&gt;", "Escaped wrapper"),
        ])

    def test_comparisons_and_stray_angle_brackets_survive(self):
        self.check([
            ("x < y and y > z", "x < y and y > z"),
            ("I <3 Python", "I <3 Python"),
            ("Why p<0.05 is not enough", "Why p<0.05 is not enough"),
            ("1 > 0", "1 > 0"),
        ])

    def test_unterminated_tag_at_the_end_is_dropped(self):
        self.check([
            ('Summary text <a href="https://example.com/very/long', "Summary text"),
            ("Summary text <img", "Summary text"),
            ("Summary text </p", "Summary text"),
        ])

    def test_declarations_and_processing_instructions(self):
        self.check([
            ("<!DOCTYPE html><html><body><p>Body</p></body></html>", "Body"),
            ("<?xml version='1.0'?>Text", "Text"),
        ])


class CleanTextWhitespace(unittest.TestCase):
    def test_whitespace_collapses(self):
        self.assertEqual(clean_text("  a \t b\r\n\n c  "), "a b c")

    def test_non_breaking_and_exotic_spaces_become_plain_spaces(self):
        self.assertEqual(clean_text("a b c　d e f"), "a b c d e f")
        self.assertEqual(clean_text("Ajit Prasad&nbsp;&nbsp;&nbsp;&nbsp;Manager"), "Ajit Prasad Manager")
        self.assertEqual(clean_text("  lead and trail "), "lead and trail")

    def test_zero_width_characters_vanish(self):
        self.assertEqual(clean_text("zero​width﻿ ⁠join­er"), "zerowidth joiner")
        self.assertEqual(clean_text("﻿BOM first"), "BOM first")
        self.assertEqual(clean_text("left‎to‏right"), "lefttoright")
        self.assertEqual(clean_text("entity&#8203;zero&#xFEFF;width"), "entityzerowidth")

    def test_emoji_joiners_are_kept(self):
        family = "\U0001F468‍\U0001F469‍\U0001F467"
        self.assertEqual(clean_text("Family " + family), "Family " + family)

    def test_control_characters_are_removed(self):
        self.assertEqual(clean_text("a\x00b\x07c\x1bd\x7fe\x1ef"), "abcdef")

    def test_lone_surrogates_are_removed_but_real_emoji_stay(self):
        self.assertEqual(clean_text("half \ud83d emoji"), "half emoji")
        self.assertEqual(clean_text("whole \U0001F600 emoji"), "whole \U0001F600 emoji")
        clean_text("half \ud83d emoji").encode("utf-8")

    def test_result_is_a_single_line(self):
        cleaned = clean_text("<p>One</p>\n\n<p>Two</p>\r\n<ul>\n<li>Three</li>\n</ul>")
        self.assertNotIn("\n", cleaned)
        self.assertEqual(cleaned, "One. Two. Three")


class CleanTextTails(unittest.TestCase):
    def check(self, cases):
        for raw, expected in cases:
            self.assertEqual(clean_text(raw), expected, repr(raw))

    def test_wordpress_post_footer(self):
        self.check([
            ("<p>Real summary.</p>\n<p>The post <a href=\"https://x.example/a/\">A Title</a> appeared first on "
             "<a href=\"https://x.example\">Site Name</a>.</p>\n", "Real summary."),
            ("Real summary. The post A Title appeared first on Site Name.", "Real summary."),
            ("Real summary. The post A Title appeared first on Site Name", "Real summary."),
            ("Real summary. The article A Title appeared first on The Decoder.", "Real summary."),
            ("The post A Title appeared first on Site.", ""),
        ])

    def test_post_footer_with_excerpt_ellipsis(self):
        self.check([
            ("Tesla said on Monday it would [&#8230;]\nThe post Tesla plans appeared first on Electrek.",
             "Tesla said on Monday it would…"),
            ("A finished sentence. [&#8230;] The post Title appeared first on Site.", "A finished sentence."),
        ])

    def test_body_text_starting_with_the_post_survives(self):
        self.check([
            ("The post office will close. More details soon. The post Closure news appeared first on Daily.",
             "The post office will close. More details soon."),
            ("Summary here. The post Why The post office matters appeared first on Daily.", "Summary here."),
        ])

    def test_marker_far_from_the_end_is_not_a_footer(self):
        text = ("The post about turbines appeared first on our radar in March, and since then the "
                "company has shipped four more models, opened two plants, signed a supply agreement "
                "and doubled its headcount across three countries, people familiar with it said.")
        self.assertEqual(clean_text(text), text)

    def test_bracketed_ellipsis(self):
        self.check([
            ("The company said it would [...]", "The company said it would…"),
            ("The company said it would […]", "The company said it would…"),
            ("The company said it would [&hellip;]", "The company said it would…"),
            ("The company said it would [ ... ]", "The company said it would…"),
            ("A complete sentence. [...]", "A complete sentence."),
            ("Is it over? [...]", "Is it over?"),
            ("[...]", ""),
        ])

    def test_ellipsis_in_the_middle_is_a_quotation_mark_not_boilerplate(self):
        text = "They describe it as: [...] our smallest model, designed for agents."
        self.assertEqual(clean_text(text), text)

    def test_read_more_links(self):
        self.check([
            ("Summary sentence. Read more", "Summary sentence."),
            ("Summary sentence. Read More »", "Summary sentence."),
            ("Summary sentence. Read more...", "Summary sentence."),
            ("Summary sentence. READ MORE", "Summary sentence."),
            ("Summary sentence. Read the full story", "Summary sentence."),
            ("Summary sentence. Read full article →", "Summary sentence."),
            ("Summary sentence. <a href='x'>Read more</a>", "Summary sentence."),
            ("Summary without a stop <a href='x'>Read more...</a>", "Summary without a stop"),
            ("Summary sentence&hellip; Read more", "Summary sentence…"),
            ("Headline text | Read More", "Headline text"),
            ("Read more", ""),
        ])

    def test_continue_reading_links(self):
        self.check([
            ("Body text ends.</p> <a href=\"https://example.com/x\">Continue reading...</a>", "Body text ends."),
            ("Sign up for the newsletter here <a href=\"x\">Continue reading...</a>", "Sign up for the newsletter here"),
            ("Body text ends. Continue reading →", "Body text ends."),
            ("Body text ends. Continue reading", "Body text ends."),
            ("Body text ends. Continue reading Tesla's next move on Electrek", "Body text ends."),
            ("Body text ends. Keep reading", "Body text ends."),
            ("Continue reading...", ""),
        ])

    def test_more_links(self):
        self.check([
            ("Summary sentence. (more…)", "Summary sentence."),
            ("Summary sentence. more...", "Summary sentence."),
            ("Summary sentence. More...", "Summary sentence."),
        ])

    def test_stacked_boilerplate(self):
        self.check([
            ("Summary sentence. [...] Read more »", "Summary sentence."),
            ("Cut off mid [...] Read more", "Cut off mid…"),
            ("Summary sentence. Read more The post T appeared first on S.", "Summary sentence."),
        ])

    def test_headlines_that_merely_contain_the_phrases_are_untouched(self):
        for title in (
            "Why Kids Should Read More",
            "Read More Books, Says Study",
            "Continue Reading the Classics",
            "Investors want more...",
            "Schools urged to keep reading programmes",
            "Students told to continue reading during the break.",
            "We asked readers what they read more of this year",
            "Bezos memo: read the full story of Blue Origin",
        ):
            self.assertEqual(clean_text(title), title)


class CleanTextLimitAndSamples(unittest.TestCase):
    def test_limit_is_applied_after_cleaning(self):
        cleaned = clean_text("<p>" + "word " * 200 + "</p>", 50)
        self.assertLessEqual(len(cleaned), 50)
        self.assertTrue(cleaned.endswith("word…"))
        self.assertEqual(clean_text("<p>Short &amp; sweet</p>", 300), "Short & sweet")

    def test_real_feed_samples(self):
        self.assertGreaterEqual(len(SAMPLES["text"]), 12)
        for sample in SAMPLES["text"]:
            self.assertEqual(clean_text(sample["raw"], sample["limit"]), sample["clean"], sample["source"])

    def test_real_samples_have_no_markup_or_boilerplate_left(self):
        leftovers = re.compile(r"<[a-zA-Z/]|&[a-z]+;|&#\d+;|\]\]>|appeared first on|Continue reading|\s{2,}| ")
        for sample in SAMPLES["text"]:
            self.assertIsNone(leftovers.search(clean_text(sample["raw"])), sample["source"])

    def test_cleaning_is_idempotent_on_real_samples(self):
        for sample in SAMPLES["text"]:
            once = clean_text(sample["raw"])
            self.assertEqual(clean_text(once), once, sample["source"])

    def test_large_input_is_handled_quickly(self):
        big = ("<p>Paragraph with <a href='https://example.com'>a link</a> &amp; entities.</p>\n" * 20000)
        self.assertTrue(clean_text(big, 300).startswith("Paragraph with a link & entities."))
        self.assertEqual(clean_text("<script>" + "x" * 500000), "")


class Truncate(unittest.TestCase):
    def test_short_text_is_unchanged(self):
        self.assertEqual(truncate("short", 10), "short")
        self.assertEqual(truncate("exactly ten", 11), "exactly ten")
        self.assertEqual(truncate("", 5), "")
        self.assertEqual(truncate(None, 5), "")
        self.assertEqual(truncate("no limit at all", None), "no limit at all")

    def test_cuts_at_a_word_boundary_with_an_ellipsis(self):
        self.assertEqual(truncate("The quick brown fox jumps over the lazy dog", 20), "The quick brown fox…")
        self.assertEqual(truncate("The quick brown fox jumps over the lazy dog", 18), "The quick brown…")

    def test_never_longer_than_the_limit(self):
        text = "Markets rallied on Wednesday as crude oil prices eased, and analysts expect more gains ahead."
        for limit in range(0, len(text) + 5):
            result = truncate(text, limit)
            self.assertLessEqual(len(result), limit, limit)
            if limit < len(text) and limit >= 1:
                self.assertTrue(result.endswith("…"), limit)

    def test_boundary_exactly_at_the_limit(self):
        self.assertEqual(truncate("alpha beta gamma", 11), "alpha beta…")
        self.assertEqual(truncate("alpha beta gamma", 12), "alpha beta…")

    def test_trailing_punctuation_is_dropped_before_the_ellipsis(self):
        self.assertEqual(truncate("First clause, second clause, third clause", 14), "First clause…")
        self.assertEqual(truncate("One sentence. Another sentence follows here", 15), "One sentence…")
        self.assertEqual(truncate("A range – from here to there and back", 10), "A range…")

    def test_one_long_word_is_cut_hard(self):
        self.assertEqual(truncate("Supercalifragilisticexpialidocious", 10), "Supercali…")
        self.assertEqual(truncate("a " + "x" * 50, 20), "a " + "x" * 17 + "…")

    def test_tiny_limits(self):
        self.assertEqual(truncate("hello world", 1), "…")
        self.assertEqual(truncate("hello world", 0), "")
        self.assertEqual(truncate("hello world", 2), "h…")


class NormTitle(unittest.TestCase):
    def test_lowercases_and_strips_punctuation(self):
        self.assertEqual(norm_title("Tesla’s Q3: Record Deliveries, Says Musk!"), "teslas q3 record deliveries says musk")
        self.assertEqual(norm_title("S&P 500 hits 7,000"), "s p 500 hits 7 000")
        self.assertEqual(norm_title("  Extra   spaces\there "), "extra spaces here")

    def test_publisher_tails(self):
        headline = "RBI holds repo rate at 5.25% for third time"
        for tail in (" - Reuters", " | The Verge", " – BBC News", " — Mint", " - The Times of India",
                     " - livemint.com", " - CNBC TV18", " - 9to5Mac"):
            self.assertEqual(norm_title(headline + tail), "rbi holds repo rate at 5 25 for third time", tail)

    def test_section_then_publisher(self):
        self.assertEqual(
            norm_title("Hijack scare on Kolkata-Mumbai flight, plane moved to bay | India News - Hindustan Times"),
            "hijack scare on kolkata mumbai flight plane moved to bay")

    def test_google_news_title_matches_first_party_title(self):
        first_party = "‘Climate crisis is outrunning us,’ UN chief Guterres says at COP31"
        google = "'Climate crisis is outrunning us,' UN chief Guterres says at COP31 - Al Jazeera"
        self.assertEqual(norm_title(first_party), norm_title(google))

    def test_tail_that_is_part_of_the_headline_is_kept(self):
        self.assertEqual(norm_title("Sensex ends 500 points higher - live updates"), "sensex ends 500 points higher live updates")
        self.assertEqual(norm_title("Tesla - Reuters"), "tesla reuters")
        self.assertEqual(norm_title("US-China talks: what we know"), "us china talks what we know")
        self.assertEqual(
            norm_title("Budget 2026 - Everything the finance minister announced for salaried taxpayers today"),
            "budget 2026 everything the finance minister announced for salaried taxpayers today")

    def test_html_and_entities(self):
        self.assertEqual(norm_title("<b>AT&amp;T</b> wins &#8216;key&#8217; ruling"), "at t wins key ruling")

    def test_accents_fold(self):
        self.assertEqual(norm_title("Café society in São Paulo"), norm_title("Cafe society in Sao Paulo"))

    def test_apostrophe_variants_agree(self):
        self.assertEqual(norm_title("India's plan"), norm_title("India’s plan"))

    def test_non_latin_titles_keep_their_letters(self):
        self.assertNotEqual(norm_title("भारत की खबर"), "")

    def test_empty(self):
        self.assertEqual(norm_title(None), "")
        self.assertEqual(norm_title(""), "")
        self.assertEqual(norm_title("!!!"), "")


URL_CASES = [
    # tracking parameters
    ("https://example.com/a?utm_source=rss&utm_medium=feed&utm_campaign=x", "https://example.com/a"),
    ("https://example.com/a?id=7&utm_source=rss&page=2", "https://example.com/a?id=7&page=2"),
    ("https://www.bbc.co.uk/news/articles/c3rryrryk59zo?at_medium=RSS&at_campaign=rss",
     "https://www.bbc.co.uk/news/articles/c3rryrryk59zo"),
    ("https://www.aljazeera.com/news/2026/11/11/story?traffic_source=rss", "https://www.aljazeera.com/news/2026/11/11/story"),
    ("https://www.dw.com/en/story/a-79916290?maca=en-rss-en-top-1022-rdf", "https://www.dw.com/en/story/a-79916290"),
    ("https://example.com/a?ref=homepage", "https://example.com/a"),
    ("https://example.com/a?fbclid=AbC123&gclid=XyZ", "https://example.com/a"),
    ("https://example.com/a?oc=5", "https://example.com/a"),
    ("https://example.com/a?UTM_Source=x&Ref=y&keep=1", "https://example.com/a?keep=1"),
    ("https://example.com/a?reference=1&utmost=2&attic=3&refs=4", "https://example.com/a?reference=1&utmost=2&attic=3&refs=4"),
    # fragments
    ("https://www.ndtvprofit.com/markets/story-12312616#publisher=newsstand", "https://www.ndtvprofit.com/markets/story-12312616"),
    ("https://example.com/a#comments", "https://example.com/a"),
    ("https://example.com/a?id=1#top", "https://example.com/a?id=1"),
    # scheme, host, port
    ("http://example.com/a", "https://example.com/a"),
    ("HTTP://Example.COM/Path/Case", "https://example.com/Path/Case"),
    ("https://WWW.TheHindu.com/news/Article71685854.ece", "https://www.thehindu.com/news/Article71685854.ece"),
    ("http://example.com:80/a", "https://example.com/a"),
    ("https://example.com:443/a", "https://example.com/a"),
    ("http://example.com:8080/a/", "http://example.com:8080/a"),
    ("https://example.com:8443/a", "https://example.com:8443/a"),
    ("//example.com/a", "https://example.com/a"),
    # trailing slash
    ("https://example.com/a/", "https://example.com/a"),
    ("https://example.com/", "https://example.com"),
    ("https://example.com", "https://example.com"),
    ("https://example.com/a/?id=3", "https://example.com/a?id=3"),
    ("https://example.com/a//", "https://example.com/a"),
    # whitespace and escaped ampersands
    ("  https://www.indiatoday.in/india/story/x-3036818-2026-11-11?utm_source=rss \n",
     "https://www.indiatoday.in/india/story/x-3036818-2026-11-11"),
    ("https://example.com/a?x=1&amp;y=2&#038;utm_source=z", "https://example.com/a?x=1&y=2"),
    ("https://example.com/a?lang=en&region=us&copy=2&para=3", "https://example.com/a?lang=en&region=us&copy=2&para=3"),
    # query encoding and order are preserved
    ("https://example.com/s?q=a+b%20c&empty=&flag", "https://example.com/s?q=a+b%20c&empty=&flag"),
    ("https://example.com/s?b=2&a=1", "https://example.com/s?b=2&a=1"),
    ("https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=63958",
     "https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=63958"),
    ("https://example.com/a?&&x=1&", "https://example.com/a?x=1"),
    # Google News article links are opaque and stay exactly as given
    ("https://news.google.com/rss/articles/CBMitwFBVV95cUxPTXlxdXZUcVVCcHEyOHpXWVZn?oc=5",
     "https://news.google.com/rss/articles/CBMitwFBVV95cUxPTXlxdXZUcVVCcHEyOHpXWVZn?oc=5"),
    ("https://news.google.com/rss/articles/CBMiTokenWithCase/?oc=5&hl=en-IN#frag",
     "https://news.google.com/rss/articles/CBMiTokenWithCase/?oc=5&hl=en-IN#frag"),
    # odd hosts
    ("http://[2001:db8::1]:8080/a/", "http://[2001:db8::1]:8080/a"),
    ("https://user:pw@Example.com/a/", "https://user:pw@example.com/a"),
    # not http(s): returned trimmed, untouched
    ("mailto:someone@example.com", "mailto:someone@example.com"),
    ("/relative/path/", "/relative/path/"),
    ("not a url", "not a url"),
    ("ftp://example.com/file/", "ftp://example.com/file/"),
    ("https://", "https://"),
    ("http://[broken", "http://[broken"),
    ("https://example.com:notaport/a", "https://example.com:notaport/a"),
    ("", ""),
    (None, ""),
]


class CanonicalUrl(unittest.TestCase):
    def test_cases(self):
        for raw, expected in URL_CASES:
            self.assertEqual(canonical_url(raw), expected, repr(raw))

    def test_idempotent(self):
        for raw, expected in URL_CASES:
            self.assertEqual(canonical_url(expected), expected, repr(raw))

    def test_real_feed_links(self):
        for sample in SAMPLES["urls"]:
            self.assertEqual(canonical_url(sample["in"]), sample["out"], sample["source"])

    def test_same_article_from_two_feeds_gets_one_id(self):
        first = "http://www.Example.com/story/123/?utm_source=rss&utm_medium=feed#top"
        second = "https://www.example.com/story/123"
        self.assertEqual(stable_id("i", canonical_url(first)), stable_id("i", canonical_url(second)))


class StableId(unittest.TestCase):
    def test_shape(self):
        value = stable_id("i", "https://example.com/a")
        self.assertRegex(value, r"^i[0-9a-f]{10}$")

    def test_is_sha1_of_the_single_part(self):
        expected = "i" + hashlib.sha1(b"https://example.com/a").hexdigest()[:10]
        self.assertEqual(stable_id("i", "https://example.com/a"), expected)

    def test_deterministic_and_distinct(self):
        self.assertEqual(stable_id("s", "a", "b"), stable_id("s", "a", "b"))
        self.assertNotEqual(stable_id("s", "a", "b"), stable_id("s", "a", "c"))
        self.assertNotEqual(stable_id("s", "ab", "c"), stable_id("s", "a", "bc"))
        self.assertNotEqual(stable_id("s", "a"), stable_id("t", "a"))
        self.assertEqual(stable_id("s", "a")[1:], stable_id("t", "a")[1:])

    def test_lone_surrogate_does_not_raise(self):
        self.assertRegex(stable_id("i", "broken \ud83d title"), r"^i[0-9a-f]{10}$")

    def test_non_string_and_unicode_parts(self):
        self.assertEqual(stable_id("p", 2611, "₹"), stable_id("p", "2611", "₹"))
        self.assertRegex(stable_id("", ), r"^[0-9a-f]{10}$")


class TokensAndStems(unittest.TestCase):
    def test_vector_file_shape(self):
        self.assertGreaterEqual(len(VECTORS["tokenize"]) + len(VECTORS["stem"]), 150)
        self.assertGreaterEqual(len(VECTORS["tokenize"]), 60)
        self.assertGreaterEqual(len(VECTORS["stem"]), 90)
        for vector in VECTORS["tokenize"]:
            self.assertIsInstance(vector["in"], str)
            self.assertIsInstance(vector["out"], list)
        for vector in VECTORS["stem"]:
            self.assertIsInstance(vector["in"], str)
            self.assertIsInstance(vector["out"], str)

    def test_tokenize_vectors(self):
        for vector in VECTORS["tokenize"]:
            self.assertEqual(tokenize(vector["in"]), vector["out"], repr(vector["in"]))

    def test_stem_vectors(self):
        for vector in VECTORS["stem"]:
            self.assertEqual(stem(vector["in"]), vector["out"], vector["in"])

    def test_vectors_cover_the_edges_named_in_the_contract(self):
        inputs = " ".join(vector["in"].lower() for vector in VECTORS["tokenize"])
        for edge in ("gpt-5.5", "s&p 500", "c++", "u.s.", "3.5-turbo", "reliance.ns", "café"):
            self.assertIn(edge, inputs, edge)
        stems = {vector["in"] for vector in VECTORS["stem"]}
        for word in ("cities", "classes", "boxes", "watches", "pushes", "quizzes", "running", "stopped",
                     "quickly", "falling", "passing", "buzzing", "virus", "analysis", "gpt-5.5", "dies"):
            self.assertIn(word, stems, word)

    def test_tokens_use_only_the_token_alphabet(self):
        shape = re.compile(r"^[a-z0-9]+(?:[&.\-][a-z0-9]+)*\+*$")
        texts = [vector["in"] for vector in VECTORS["tokenize"]] + [sample["clean"] for sample in SAMPLES["text"]]
        for text in texts:
            for token in tokenize(text):
                self.assertRegex(token, shape, repr(text))
                self.assertTrue(len(token) > 1 or token.isdigit(), repr(text))

    def test_tokenize_none_and_empty(self):
        self.assertEqual(tokenize(None), [])
        self.assertEqual(tokenize(""), [])

    def test_tokenize_keeps_stopwords_and_order(self):
        self.assertEqual(tokenize("The Fed and the RBI"), ["the", "fed", "and", "the", "rbi"])

    def test_stem_leaves_short_and_digit_tokens_alone(self):
        for token in ("ai", "us", "its", "gpt-5.5", "q3s", "2020s", "h-1b", "v2.1.322", "s&p500"):
            self.assertEqual(stem(token), token)

    def test_stem_never_returns_an_empty_or_longer_string(self):
        words = set()
        for sample in SAMPLES["text"]:
            words.update(tokenize(sample["clean"]))
        self.assertGreater(len(words), 150)
        for word in words:
            result = stem(word)
            self.assertTrue(result, word)
            self.assertLessEqual(len(result), len(word), word)

    def test_related_word_forms_share_a_stem(self):
        groups = [
            ("model", "models"), ("launch", "launches", "launched", "launching"), ("market", "markets"),
            ("build", "building", "buildings"), ("company", "companies"), ("report", "reported", "reporting", "reports"),
            ("plan", "planned", "planning", "plans"), ("quick", "quickly"), ("class", "classes"),
        ]
        for group in groups:
            self.assertEqual(len({stem(word) for word in group}), 1, group)


class Stopwords(unittest.TestCase):
    BOILERPLATE = ("says", "said", "new", "report", "reports", "amid", "via", "video", "watch", "live",
                   "update", "updates")

    def test_is_a_frozenset_of_reasonable_size(self):
        self.assertIsInstance(STOPWORDS, frozenset)
        self.assertGreaterEqual(len(STOPWORDS), 170)
        self.assertLessEqual(len(STOPWORDS), 230)

    def test_contains_english_function_words_and_news_boilerplate(self):
        for word in ("the", "and", "of", "to", "in", "is", "was", "with", "that", "this", "from", "would",
                     "don", "isn", "ll", "ve") + self.BOILERPLATE:
            self.assertIn(word, STOPWORDS, word)

    def test_does_not_swallow_words_that_matter_in_this_paper(self):
        for word in ("us", "ai", "india", "fed", "first", "one", "apple", "meta", "will.i.am", "news"):
            self.assertNotIn(word, STOPWORDS, word)

    def test_every_stopword_is_a_token_tokenize_can_produce(self):
        for word in STOPWORDS:
            self.assertEqual(word, word.lower())
            self.assertIn(tokenize(word), ([word], []), word)   # single letters tokenize to nothing

    def test_matches_the_list_shared_with_the_javascript_twin(self):
        self.assertEqual(sorted(STOPWORDS), VECTORS["stopwords"])


class Api(unittest.TestCase):
    def test_contract_names_exist(self):
        for name in ("clean_text", "truncate", "norm_title", "canonical_url", "tokenize", "stem", "stable_id"):
            self.assertTrue(callable(getattr(textutil, name)), name)


if __name__ == "__main__":
    unittest.main()
