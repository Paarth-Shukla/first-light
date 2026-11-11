"""pipeline.claude_updates: parsers against saved real responses, merging, dedupe, links, and run()."""

import json
import tempfile
import textwrap
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from pipeline import claude_updates as cu
from pipeline.core import config, net, timeutil

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "claude"
CONFIG = config.load("claude")


def source(source_id):
    """The configured source with defaults filled in, as run() would use it."""
    raw = next(s for s in CONFIG["sources"] if s["id"] == source_id)
    return cu.check_source(raw, {"summaryChars": CONFIG["summaryChars"], "maxEntries": 100})


def text(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def raw(name):
    return (FIXTURES / name).read_bytes()


def entry(source_id, date, title, url="https://example.test/x", surface="apps", summary=""):
    return {"id": "u-%s-%s-%s" % (source_id, date, title), "date": date, "surface": surface, "kind": "feature",
            "title": title, "summary": summary, "url": url, "source": source_id, "features": []}


class TextHelpersTest(unittest.TestCase):
    def test_md_text(self):
        self.assertEqual(cu.md_text("We’ve launched **Claude X** (`claude-x`), see [docs](https://a.test/(b)).\n"
                                    "* Use `**kwargs` and `a_b_c` with \\$5 and <file>\n<Tip>tip</Tip>"),
                         "We’ve launched Claude X (claude-x), see docs. Use **kwargs and a_b_c with $5 and "
                         "<file> tip")

    def test_first_link_skips_unsafe_targets(self):
        self.assertEqual(cu.first_link("[a](javascript:x) then **[b](https://b.test/p)**"), "https://b.test/p")
        self.assertIsNone(cu.first_link("no links"))

    def test_split_first_sentence(self):
        self.assertEqual(cu.split_first_sentence("Version 5.5 is out. It is fast. Try it."),
                         ("Version 5.5 is out.", "It is fast. Try it."))
        self.assertEqual(cu.split_first_sentence("One sentence only"), ("One sentence only", ""))


class AppsNotesTest(unittest.TestCase):
    def setUp(self):
        self.entries = cu.parse_apps_notes(text("apps-release-notes.md"), source("claude-apps"))
        self.by_title = {e["title"]: e for e in self.entries}

    def test_items_dates_and_links(self):
        self.assertEqual(len(self.entries), 7)
        first = self.entries[0]
        self.assertEqual((first["date"], first["title"], first["surface"], first["kind"], first["source"]),
                         ("2026-11-06", "Track spend by cost code with project tags (beta)", "apps", "feature",
                          "claude-apps"))
        self.assertEqual(first["url"], "https://support.claude.com/en/articles/18251257-track-spend-by-project-with-tags")
        self.assertEqual(self.by_title["Personal Finance in Claude"]["date"], "2026-11-05")

    def test_pointers_to_further_reading_are_removed(self):
        self.assertEqual(self.by_title["Claude Duet research preview for Pro and Max plans"]["summary"],
                         "We just opened a research preview for users on Pro and Max plans: Claude Duet, a new app "
                         "where Claude works as a proactive agent.")
        self.assertEqual(self.by_title["Memory for free users"]["summary"],
                         "Memory from chat history is now available for all Claude users, including free users.")
        self.assertEqual(self.by_title["Project Sharing"]["summary"],
                         "Enabled project permissions and sharing for Team and Enterprise plans.")

    def test_content_bullets_are_kept(self):
        self.assertEqual(self.by_title["Claude Code Security Reviews"]["summary"],
                         "Two new cybersecurity features were added to Claude Code: /security-review command "
                         "GitHub Actions")

    def test_a_note_never_leaks_into_the_next_month(self):
        self.assertNotIn("August", self.by_title["Memory for free users"]["summary"])

    def test_no_dated_notes_is_a_parse_error(self):
        with self.assertRaises(cu.ParseError):
            cu.parse_apps_notes("# Release notes\n\nNothing here.\n", source("claude-apps"))


class PlatformNotesTest(unittest.TestCase):
    def setUp(self):
        self.entries = cu.parse_platform_notes(text("platform-release-notes.md"), source("claude-platform"))

    def find(self, prefix):
        return next(e for e in self.entries if e["title"].startswith(prefix))

    def test_one_entry_per_bullet_with_first_sentence_titles(self):
        self.assertEqual(len(self.entries), 10)
        self.assertEqual([e["date"] for e in self.entries].count("2026-11-05"), 3)
        launch = self.entries[0]
        self.assertEqual(launch["title"], "We’ve launched Claude Fable 5.2 (claude-fable-5-2), built for demanding "
                                          "reasoning and long-horizon agentic work.")
        self.assertTrue(launch["summary"].startswith("Claude Mythos 5.2 (claude-mythos-5-2) offers"))
        self.assertEqual(launch["url"], "https://platform.claude.com/docs/en/release-notes/overview")
        self.assertNotIn("<Tip>", json.dumps(self.entries))

    def test_model_launches_and_retirements_get_the_models_surface(self):
        self.assertEqual(self.find("We’ve launched Claude Fable 5.2")["surface"], "models")
        self.assertEqual(self.find("We announced the deprecation of the Claude Sonnet 4.5")["surface"], "models")
        self.assertEqual(self.find("We’ve launched fast mode for")["surface"], "platform")
        self.assertEqual(self.find("We’ve deprecated fast mode for")["surface"], "platform")
        self.assertEqual(self.find("You can now set up an IP allowlist")["surface"], "platform")

    def test_trailing_see_pointer_is_cut(self):
        self.assertNotIn("See ", self.find("We’ve launched fast mode")["summary"])
        self.assertEqual(self.find("We announced the deprecation")["summary"],
                         "We recommend migrating to Claude Sonnet 5.5.")

    def test_clipped_headline_keeps_its_text_in_the_summary(self):
        sentence = "On the Claude API " + "and many more platforms " * 8 + "it works."
        notes = "### November 1, 2026\n\n* %s Second sentence.\n" % sentence
        [only] = cu.parse_platform_notes(notes, source("claude-platform"))
        self.assertTrue(only["title"].endswith("…"))
        self.assertLessEqual(len(only["title"]), cu.TITLE_CHARS)
        self.assertEqual(only["summary"][:40], sentence[:40])

    def test_leading_bold_span_becomes_the_title(self):
        notes = "### November 1, 2026\n\n* **Batch discounts.** Batches now cost less. See [docs](https://a.test).\n"
        [only] = cu.parse_platform_notes(notes, source("claude-platform"))
        self.assertEqual((only["title"], only["summary"]), ("Batch discounts", "Batches now cost less."))


class ChangelogTest(unittest.TestCase):
    def test_claude_code_keeps_only_added_items(self):
        entries = cu.parse_changelog_rss(raw("code-changelog.xml"), source("claude-code"))
        self.assertEqual([e["title"] for e in entries], ["Claude Code 2.1.322", "Claude Code 2.1.321"])
        newest, labelled = entries
        self.assertEqual((newest["date"], newest["kind"], newest["surface"]), ("2026-11-10", "release", "code"))
        self.assertEqual(newest["url"], "https://code.claude.com/docs/en/changelog#2-1-322")
        self.assertEqual(newest["summary"], "Added fast mode on Vertex in the global, us and eu regions, falling "
                                            "back to standard speed if Vertex refuses it.")
        self.assertEqual(labelled["date"], "2026-11-09")  # 20:24 GMT stays on the publisher's day
        self.assertIn("Added --settings <file> to claude remote-control", labelled["summary"])
        self.assertNotIn("Updated the", labelled["summary"])  # the Changed group is left out

    def test_cap_per_release(self):
        capped = dict(source("claude-code"), maxItemsPerRelease=1)
        entries = cu.parse_changelog_rss(raw("code-changelog.xml"), capped)
        self.assertEqual(entries[1]["summary"].count("Added "), 1)

    def test_cowork_skips_releases_without_user_facing_additions(self):
        entries = cu.parse_changelog_rss(raw("cowork-changelog.xml"), source("claude-cowork"))
        self.assertEqual([e["title"] for e in entries], ["Claude Desktop v5.1231.0"])
        self.assertEqual(entries[0]["surface"], "cowork")
        self.assertTrue(entries[0]["summary"].startswith("Added "))
        self.assertNotIn("Fixed", entries[0]["summary"])

    def test_added_items_rules(self):
        body = ("<p>Bundled Claude Code version: 2.1.1.</p><p><strong>Code</strong></p><ul>"
                "<li>[VSCode] Added a <code>&#x3C;tab></code> key</li><li>Windows: Added a path</li>"
                "<li>Fixed a crash</li><li>No user-facing changes.</li><li>Changed: Added nothing</li>"
                "<li>Additional logging</li></ul><p><strong>Added</strong></p><ul><li>New picker"
                "<ul><li>nested detail</li></ul></li></ul>")
        self.assertEqual(cu.added_items(body), ["[VSCode] Added a <tab> key", "Windows: Added a path",
                                                "Changed: Added nothing", "New picker nested detail"])

    def test_bad_feeds(self):
        with self.assertRaises(cu.ParseError):
            cu.parse_changelog_rss(b"<html>not a feed", source("claude-code"))
        with self.assertRaises(cu.ParseError):
            cu.parse_changelog_rss(b"<rss><channel></channel></rss>", source("claude-code"))


class ListingTest(unittest.TestCase):
    def test_anthropic_news_cards(self):
        entries = cu.parse_anthropic_listing(text("anthropic-news.html"), source("anthropic-news"))
        self.assertEqual([e["title"] for e in entries], [
            "Anthropic launches roadshow for proposed initial public offering",
            "Introducing Claude Fable 5.2 and Claude Mythos 5.2",
            "AI for Science expands to foundations and research institutions"])  # the stub is left out
        roadshow, fable, _ = entries
        self.assertEqual((roadshow["url"], roadshow["surface"], roadshow["kind"], roadshow["date"]),
                         ("https://www.anthropic.com/news/roadshow-launch", "news", "article", "2026-11-10"))
        self.assertEqual((fable["url"], fable["surface"]),
                         ("https://www.anthropic.com/claude-fable-and-mythos-5-2", "models"))
        self.assertTrue(fable["summary"].startswith("Our most capable models"))

    def test_engineering_links_go_to_research(self):
        entries = cu.parse_anthropic_listing(text("anthropic-engineering.html"), source("anthropic-engineering"))
        self.assertEqual(entries[0]["url"], "https://www.anthropic.com/research/components-of-agent-memory")
        self.assertEqual(entries[1]["title"], "Redesigning source control at Anthropic")  # leading space trimmed
        self.assertEqual(len(entries), 2)

    def test_claude_blog_posts(self):
        entries = cu.parse_claude_blog(text("claude-blog.html"), source("claude-blog"))
        by_title = {e["title"]: e for e in entries}
        self.assertEqual(len(entries), 4)
        sheets = by_title["Introducing Claude Whiteboards, Claude Sheets, and Claude Data"]
        self.assertEqual((sheets["url"], sheets["surface"], sheets["date"]),
                         ("https://claude.com/resources/articles/sheets-whiteboards-data", "apps", "2026-11-10"))
        self.assertEqual(by_title["Make long-running agents faster with message threads"]["surface"], "platform")
        self.assertEqual(by_title["Claude Fable 5.2 and Mythos 5.2"]["url"],
                         "https://www.anthropic.com/claude-fable-and-mythos-5-2")
        self.assertEqual(by_title["Introducing Personal Finance in Claude"]["surface"], "apps")  # no product tag

    def test_objects_spanning_chunks_are_decoded(self):
        payload = json.dumps({"items": [{"_id": "a", "_type": "x", "title": "joined"}]})
        page = "".join('<script>self.__next_f.push([1,%s])</script>' % json.dumps(part)
                       for part in (payload[:20], payload[20:]))
        self.assertEqual(cu.rsc_objects(page), [{"_id": "a", "_type": "x", "title": "joined"}])

    def test_pages_without_data(self):
        with self.assertRaises(cu.ParseError):
            cu.rsc_objects("<html><body>redesigned</body></html>")
        page = '<script>self.__next_f.push([1,"{\\"_id\\":\\"x\\",\\"_type\\":\\"page\\"}"])</script>'
        with self.assertRaises(cu.ParseError):
            cu.parse_anthropic_listing(page, source("anthropic-news"))
        with self.assertRaises(cu.ParseError):
            cu.parse_claude_blog(page, source("claude-blog"))


class YoutubeAndStatusTest(unittest.TestCase):
    def test_youtube(self):
        entries = cu.parse_youtube(raw("youtube.xml"), source("claude-youtube"))
        self.assertEqual(len(entries), 4)
        first = entries[0]
        self.assertEqual((first["title"], first["date"], first["kind"], first["surface"], first["url"]),
                         ("Introducing Claude Whiteboards, Sheets, and Data", "2026-11-10", "video", "learn",
                          "https://www.youtube.com/watch?v=YewAJPawE7I"))
        self.assertNotIn("\n", first["summary"])
        mobile = [e for e in entries if e["title"] == "Claude's new mobile app updates are here"]
        self.assertTrue(all(e["summary"] == "A few upgrades to the Claude mobile apps this week." for e in mobile))

    def test_status(self):
        self.assertEqual(cu.parse_status(json.loads(text("status-summary.json"))),
                         {"indicator": "none", "description": "All Systems Operational"})
        for bad in ({}, {"status": {"indicator": "fine", "description": "x"}}, [], {"status": "up"}):
            with self.assertRaises(cu.ParseError):
                cu.parse_status(bad)


class MergeTest(unittest.TestCase):
    def test_failed_source_keeps_everything(self):
        old = [entry("s", "2026-11-01", "a"), entry("s", "2026-06-01", "b")]
        self.assertEqual(cu.merge_source(None, old), old)

    def test_fresh_feed_owns_the_dates_it_covers(self):
        old = [entry("s", "2026-11-05", "renamed before"), entry("s", "2026-11-01", "covered"),
               entry("s", "2026-10-20", "older")]
        fresh = [entry("s", "2026-11-05", "renamed after"), entry("s", "2026-11-01", "covered")]
        self.assertEqual([e["title"] for e in cu.merge_source(fresh, old)],
                         ["renamed after", "covered", "older"])

    def test_dedupe_by_title_and_unique_url(self):
        entries = [
            entry("apps", "2026-11-05", "Personal Finance in Claude", url="https://claude.com/a/finance"),
            entry("platform", "2026-11-05", "Shared page one", url="https://p.test/notes"),
            entry("platform", "2026-11-05", "Shared page two", url="https://p.test/notes"),
            entry("blog", "2026-11-05", "Introducing Personal Finance", url="https://claude.com/a/finance/"),
            entry("news", "2026-11-04", "Personal finance in Claude!", url="https://n.test/1"),
            entry("news", "2026-11-04", "Other", url="https://p.test/notes"),
        ]
        self.assertEqual([e["title"] for e in cu.dedupe(entries)],
                         ["Personal Finance in Claude", "Shared page one", "Shared page two", "Other"])

    def test_window(self):
        now = timeutil.parse_date("2026-11-11T06:00:00Z")
        entries = [entry("s", d, d) for d in ("2026-11-13", "2026-11-12", "2026-05-15", "2026-05-14")]
        self.assertEqual([e["date"] for e in cu.in_window(entries, now, 180)], ["2026-11-12", "2026-05-15"])


FEATURES = [
    {"id": "cc-hooks", "title": "Hooks", "surface": "code", "tags": ["hooks", "automation", "formatting"]},
    {"id": "cc-model-and-effort", "title": "Model, effort level and fast mode", "surface": "code",
     "tags": ["model", "fast-mode"]},
    {"id": "api-fast-mode", "title": "Fast mode", "surface": "platform", "tags": ["fast-mode", "latency"]},
    {"id": "research", "title": "Research", "surface": "apps", "tags": ["research", "citations", "web"]},
    {"id": "claude-sheets", "title": "Claude Sheets", "surface": "apps", "tags": ["sheets", "spreadsheets"]},
    {"id": "cc-desktop-app", "title": "Claude Code in the desktop app", "surface": "code",
     "tags": ["desktop", "code-tab", "diff-view", "preview"]},
    {"id": "api-web-fetch-tool", "title": "Web fetch tool", "surface": "platform", "tags": ["web-fetch", "urls"]},
    {"id": "cc-a", "title": "Alpha thing", "surface": "code", "tags": ["context"]},
    {"id": "cc-b", "title": "Beta thing", "surface": "code", "tags": ["context"]},
    {"id": "cc-c", "title": "Gamma thing", "surface": "code", "tags": ["context"]},
]
SURFACE_OF = {"claude-code": "code", "claude-platform": "platform", "claude-apps": "apps",
              "claude-youtube": "learn", "anthropic-news": "news"}


class FeatureLinkTest(unittest.TestCase):
    def links(self, source_id, title, summary="", surface=None):
        item = entry(source_id, "2026-11-10", title, summary=summary, surface=surface or SURFACE_OF[source_id])
        return cu.link_features([item], FEATURES, SURFACE_OF)[0]["features"]

    def test_title_and_title_segments(self):
        self.assertEqual(self.links("claude-code", "Claude Code 2.1.322", "Added fast mode on Vertex."),
                         ["cc-model-and-effort"])
        self.assertEqual(self.links("claude-code", "Claude Code 2.1.300", "Added a PreToolUse hook."), ["cc-hooks"])
        self.assertEqual(self.links("claude-platform", "The web_fetch tool now follows limits."),
                         ["api-web-fetch-tool"])

    def test_surface_gating_follows_the_source(self):
        self.assertEqual(self.links("claude-platform", "We’ve launched fast mode for Claude X."), ["api-fast-mode"])
        self.assertEqual(self.links("claude-platform", "We’ve launched Claude X with fast mode.", surface="models"),
                         ["api-fast-mode"])

    def test_one_word_titles_need_their_own_surface(self):
        self.assertEqual(self.links("claude-apps", "Research now cites sources"), ["research"])
        self.assertEqual(self.links("anthropic-news", "New research on interpretability"), [])
        self.assertEqual(self.links("claude-youtube", "Meet Claude Sheets"), ["claude-sheets"])

    def test_release_stage_wording_is_not_a_feature(self):
        self.assertEqual(self.links("claude-apps", "Claude Duet research preview for Pro plans"), [])

    def test_tags_alone_need_three_points_and_a_product_surface(self):
        self.assertEqual(self.links("claude-code", "Claude Code 2.1.1", "Added a code tab with diff view."), [])
        self.assertEqual(self.links("claude-code", "Claude Code 2.1.2", "Added a code tab, diff view and preview."),
                         ["cc-desktop-app"])
        self.assertEqual(self.links("anthropic-news", "Code tab, diff view and preview"), [])

    def test_generic_tags_do_not_count_and_three_links_at_most(self):
        self.assertEqual(self.links("claude-code", "Claude Code 2.1.3", "Context context context."), [])
        summary = "Alpha thing, beta thing, gamma thing and hooks."
        self.assertEqual(len(self.links("claude-code", "Claude Code 2.1.4", summary)), 3)


class RunTest(unittest.TestCase):
    """run() end to end with the network replaced by the saved fixtures."""

    RESPONSES = {
        "https://support.claude.com/en/articles/12138966-release-notes.md": "apps-release-notes.md",
        "https://platform.claude.com/docs/en/release-notes/overview.md": "platform-release-notes.md",
        "https://code.claude.com/docs/en/changelog/rss.xml": "code-changelog.xml",
        "https://claude.com/docs/cowork/changelog/rss.xml": "cowork-changelog.xml",
        "https://www.anthropic.com/news": "anthropic-news.html",
        "https://www.anthropic.com/engineering": "anthropic-engineering.html",
        "https://claude.com/resources/product-updates": "claude-blog.html",
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCV03SRZXJEz-hchIAogeJOg": "youtube.xml",
        "https://status.claude.com/api/v2/summary.json": "status-summary.json",
    }

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        features = self.root / "content" / "claude" / "features"
        features.mkdir(parents=True)
        (features / "cc-model-and-effort.md").write_text(textwrap.dedent("""\
            ---
            id: cc-model-and-effort
            title: Model, effort level and fast mode
            surface: code
            group: Configure
            status: stable
            level: intermediate
            payoff: 2
            effort: 1
            jobs: [coding]
            tags: [model, effort, fast-mode]
            summary: Pick the model and effort.
            when: When speed or depth matters.
            replaces: Guessing.
            example_kind: command
            docs:
              - title: Model configuration
                url: https://code.claude.com/docs/en/model-config
            verified: 2026-11-11
            ---
            ## Example
            ```text
            /model
            ```
            """), encoding="utf-8")
        timeutil.set_now(timeutil.parse_date("2026-11-11T06:00:00Z"))
        self.addCleanup(timeutil.set_now, None)
        self.ctx = config.context(data_dir=self.root / "data")
        self.ctx.paths = replace(self.ctx.paths, root=self.root)
        self.ctx.paths.ensure()
        self.down = set()
        patcher = mock.patch.object(cu.net, "fetch", side_effect=self.fake_fetch)
        patcher.start()
        self.addCleanup(patcher.stop)
        mock.patch.object(cu.net, "polite").start()
        self.addCleanup(mock.patch.stopall)
        quiet = mock.patch.multiple(cu.log, info=mock.DEFAULT, warn=mock.DEFAULT, error=mock.DEFAULT)
        quiet.start()

    def fake_fetch(self, url, **kw):
        if url in self.down:
            raise net.NetError("http", 503, "HTTP 503 Service Unavailable", url)
        body = raw(self.RESPONSES[url])
        return net.Response(status=200, body=body, headers={"Content-Type": "text/plain; charset=utf-8"}, url=url)

    def updates(self):
        return json.loads((self.ctx.paths.claude_dir / "updates.json").read_text())

    def test_full_run(self):
        counts = cu.run(self.ctx)
        data = self.updates()
        self.assertEqual(data["generatedAt"], "2026-11-11T06:00:00Z")
        self.assertEqual(data["status"], {"indicator": "none", "description": "All Systems Operational"})
        entries = data["entries"]
        self.assertEqual(counts["entries"], len(entries))
        self.assertEqual((counts["sourcesOk"], counts["sourcesFailed"], counts["failed"]), (8, 0, []))
        self.assertEqual((counts["features"], counts["contentErrors"]), (1, 0))
        dates = [e["date"] for e in entries]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertTrue(all(d >= "2026-05-15" for d in dates))  # 180-day window drops August 2025
        self.assertEqual(len({e["id"] for e in entries}), len(entries))
        for item in entries:
            self.assertEqual(list(item), ["id", "date", "surface", "kind", "title", "summary", "url", "source",
                                          "features"])
            self.assertIn(item["surface"], cu.SURFACES)
            self.assertIn(item["kind"], cu.KINDS)
        titles = [e["title"] for e in entries]
        # The blog's Fable post and the news card share a URL; the news card comes first in priority.
        self.assertEqual(sum("Fable 5.2 and" in t and "Mythos" in t for t in titles), 1)
        self.assertEqual(titles.count("Claude's new mobile app updates are here"), 1)
        code = next(e for e in entries if e["title"] == "Claude Code 2.1.322")
        self.assertEqual(code["features"], ["cc-model-and-effort"])
        self.assertTrue((self.ctx.paths.claude_dir / "playbook.json").exists())

    def test_failed_source_keeps_previous_entries(self):
        cu.run(self.ctx)
        before = [e for e in self.updates()["entries"] if e["source"] == "claude-code"]
        self.down = {"https://code.claude.com/docs/en/changelog/rss.xml",
                     "https://status.claude.com/api/v2/summary.json"}
        counts = cu.run(self.ctx)
        after = self.updates()
        self.assertEqual([e for e in after["entries"] if e["source"] == "claude-code"], before)
        self.assertIsNone(after["status"])
        self.assertEqual(counts["sourcesOk"], 7)
        self.assertEqual(counts["failed"], ["claude-code: HTTP 503 Service Unavailable",
                                            "claude-status: HTTP 503 Service Unavailable"])
        self.assertEqual(counts["newEntries"], 0)

    def test_markup_change_counts_as_failure_not_as_empty(self):
        cu.run(self.ctx)
        before = [e for e in self.updates()["entries"] if e["source"] == "claude-blog"]
        self.RESPONSES = dict(self.RESPONSES)
        self.RESPONSES["https://claude.com/resources/product-updates"] = "status-summary.json"
        counts = cu.run(self.ctx)
        self.assertEqual([e for e in self.updates()["entries"] if e["source"] == "claude-blog"], before)
        self.assertTrue(counts["failed"][0].startswith("claude-blog: ParseError: no Next.js data chunks"))

    def test_older_history_survives_a_short_feed(self):
        old = entry("claude-code", "2026-09-01", "Claude Code 2.1.200", surface="code")
        jsonio_path = self.ctx.paths.claude_dir / "updates.json"
        jsonio_path.write_text(json.dumps({"generatedAt": "x", "status": None,
                                           "entries": [old, {"broken": True}]}))
        cu.run(self.ctx)
        self.assertIn("Claude Code 2.1.200", [e["title"] for e in self.updates()["entries"]])

    def test_offline_run_keeps_everything(self):
        cu.run(self.ctx)
        before = self.updates()["entries"]
        net.set_offline(True)
        self.addCleanup(net.set_offline, False)
        self.down = set(self.RESPONSES)
        counts = cu.run(self.ctx)
        self.assertEqual(self.updates()["entries"], before)
        self.assertEqual(counts["sourcesOk"], 0)

    def test_bad_source_config_is_reported_not_fatal(self):
        settings = dict(CONFIG, sources=CONFIG["sources"] + [{"id": "x", "name": "X", "kind": "nope",
                                                               "url": "https://x.test", "surface": "apps"}])
        with mock.patch.object(cu.config, "load", return_value=settings):
            counts = cu.run(self.ctx)
        self.assertEqual(counts["failed"], ["x: bad config: unknown kind 'nope'"])
        self.assertEqual(counts["sourcesOk"], 8)


if __name__ == "__main__":
    unittest.main()
