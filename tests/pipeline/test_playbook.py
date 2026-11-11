"""pipeline.playbook: front matter parser, markdown renderer, validation and compilation."""

import json
import tempfile
import textwrap
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from pipeline import playbook
from pipeline.core import config, net, timeutil
from pipeline.playbook import ContentError

FEATURE = textwrap.dedent("""\
    ---
    id: projects
    title: Projects
    surface: apps            # apps | code | platform | cowork | integrations
    group: Context
    status: stable
    since: 2024-06
    level: starter
    payoff: 3
    effort: 1
    jobs: [writing, research]
    tags: [context, knowledge]
    summary: One sentence, what it is.
    when: One or two sentences, when to reach for it.
    replaces: The manual habit this removes.
    example_kind: prompt
    docs:
      - title: What are projects?
        url: https://support.claude.com/en/articles/9517075-what-are-projects
    verified: 2026-11-11
    ---
    ## Try it in a minute
    1. Open **Projects**.
    2. Add files.

    ## Example
    ```text
    Summarise the attached brief.
    ```

    ## At work
    Use it for *long-running* work.

    ## Pitfalls
    - Keep it small.
    """)

RECIPE = textwrap.dedent("""\
    ---
    id: weekly-status
    title: Weekly status report
    job: writing
    level: starter
    minutes_saved: 30
    features: [projects]
    prerequisites: [A project with last week's notes, "Access to the tracker, read-only"]
    fields:
      - name: team
        label: Team name
        placeholder: Platform
      - name: week
        label: Week
        placeholder: 2026-W46
    docs:
      - title: Projects
        url: https://support.claude.com/en/articles/9517075-what-are-projects
    verified: 2026-11-11
    ---
    ## Steps
    1. Open the project.

    ## Prompt
    ```text
    Write the {{team}} status for {{ week }}.
    ```

    ## Why it works
    It keeps the format.
    """)


def fm(text):
    """Parse a front matter body given without the --- lines (its first line is line 1)."""
    return playbook.parse_front_matter(textwrap.dedent(text).strip("\n").split("\n"), first_line=1)[0]


def replace_line(text, old, new):
    """``text`` with the one line starting ``old`` replaced (or removed when ``new`` is None)."""
    lines = text.split("\n")
    index = next(i for i, line in enumerate(lines) if line.startswith(old))
    if new is None:
        del lines[index]
    else:
        lines[index] = new
    return "\n".join(lines)


class FrontMatterTest(unittest.TestCase):
    def test_full_feature_front_matter(self):
        lines, body, body_line = playbook.split_document(FEATURE)
        values, key_lines = playbook.parse_front_matter(lines)
        self.assertEqual(values["surface"], "apps")  # trailing comment removed
        self.assertEqual(values["payoff"], 3)
        self.assertEqual(values["since"], "2024-06")
        self.assertEqual(values["jobs"], ["writing", "research"])
        self.assertEqual(values["docs"], [{"title": "What are projects?",
                                           "url": "https://support.claude.com/en/articles/9517075-what-are-projects"}])
        self.assertEqual(key_lines["id"], 2)
        self.assertEqual(body_line, 22)
        self.assertTrue(body.startswith("## Try it in a minute"))

    def test_quotes_comments_and_lists(self):
        values = fm('''
            # a comment line
            a: "Say \\"hi\\": now"   # comment after a quote
            b: 'It''s fine: really'
            c: ["x, y", 'z', plain words]
            d: []
            e: plain # comment
            f: Issue#12 stays
            g: -4
            h: 2026-11-11
            ''')
        self.assertEqual(values["a"], 'Say "hi": now')
        self.assertEqual(values["b"], "It's fine: really")
        self.assertEqual(values["c"], ["x, y", "z", "plain words"])
        self.assertEqual(values["d"], [])
        self.assertEqual(values["e"], "plain")
        self.assertEqual(values["f"], "Issue#12 stays")
        self.assertEqual(values["g"], -4)
        self.assertEqual(values["h"], "2026-11-11")

    def test_object_list_with_comments_between_items(self):
        values = fm("""
            fields:
              - name: a
                label: "A: first"
              # second item next
              - name: b
            """)
        self.assertEqual(values["fields"], [{"name": "a", "label": "A: first"}, {"name": "b"}])

    def assert_line_error(self, text, line, fragment):
        with self.assertRaises(ContentError) as caught:
            fm(text)
        self.assertEqual(caught.exception.line, line)
        self.assertIn(fragment, caught.exception.message)

    def test_invalid_front_matter(self):
        cases = [
            ("a: 1\nb:\t2", 2, "tab"),
            ('a: "open', 1, "closing double quote"),
            ("a: 'open", 1, "closing single quote"),
            ('a: "bad \\q"', 1, "unsupported escape"),
            ('a: "x" y', 1, "unexpected text"),
            ("a: 1\na: 2", 2, "duplicate key"),
            ("docs:\n  - title: x\n    title: y", 3, "duplicate key"),
            ("tags:\n  - one", 2, "inline list"),
            ("a: 1\n  title: x", 2, "cannot read"),
            ("a: 1\n    title: x", 2, "does not belong"),
            ("a: 1\n  - title: x", 2, "does not belong"),
            ("docs:\n   - title: x", 2, "cannot read"),
            ("docs:\n    url: x", 2, "start a list item"),
            ("a: 1\ndocs:", 2, "has no value"),
            ("a: [x, y", 1, "not closed"),
            ("a: [x, [y]]", 1, "nested"),
            ("a: [x, , y]", 1, "empty item"),
            ("a: one: two", 1, "contains ': '; wrap it in quotes"),
            ("a: *ref", 1, "wrap it in quotes"),
            ("a: {x: 1}", 1, "wrap it in quotes"),
            ("not a key line", 1, "cannot read"),
        ]
        for text, line, fragment in cases:
            with self.subTest(text=text):
                self.assert_line_error(text, line, fragment)

    def test_document_framing(self):
        with self.assertRaises(ContentError) as caught:
            playbook.split_document("id: x\n")
        self.assertIn("must start", caught.exception.message)
        with self.assertRaises(ContentError) as caught:
            playbook.split_document("---\nid: x\n")
        self.assertIn("not closed", caught.exception.message)
        lines, body, _ = playbook.split_document("﻿---\r\nid: x\r\n---\r\nbody\r\n")
        self.assertEqual((lines, body), (["id: x"], "body\n"))


class MarkdownTest(unittest.TestCase):
    def render(self, text, warnings=None):
        return playbook.render_markdown(textwrap.dedent(text), warnings)

    def test_blocks(self):
        out = self.render("""\
            # Title
            ### Small

            First line
            continues here.

            > Quoted **bold**
            > - item

            ---
            """)
        self.assertEqual(out, "<h1>Title</h1>\n<h3>Small</h3>\n<p>First line\ncontinues here.</p>\n"
                              "<blockquote><p>Quoted <strong>bold</strong></p>\n<ul>\n<li>item</li>\n</ul>"
                              "</blockquote>\n<hr>")

    def test_lists_with_one_nesting_level(self):
        out = self.render("""\
            3. three
            4. four
               - nested a
               - nested b
            5. five
               with a continuation

            - after
            * star bullet
            """)
        self.assertEqual(out, '<ol start="3">\n<li>three</li>\n<li>four\n<ul>\n<li>nested a</li>\n'
                              '<li>nested b</li>\n</ul></li>\n<li>five\nwith a continuation</li>\n</ol>\n'
                              "<ul>\n<li>after</li>\n<li>star bullet</li>\n</ul>")

    def test_loose_list_stays_one_list(self):
        out = self.render("- a\n\n- b\n")
        self.assertEqual(out, "<ul>\n<li>a</li>\n<li>b</li>\n</ul>")

    def test_fenced_code_keeps_content_verbatim(self):
        out = self.render("""\
            ```json title
            {"a": "<b>**not bold**</b>"}

            ## not a heading
            ```
            ~~~
            plain
            ~~~
            """)
        self.assertEqual(out, '<pre><code class="language-json">{&quot;a&quot;: &quot;&lt;b&gt;**not bold**'
                              "&lt;/b&gt;&quot;}\n\n## not a heading</code></pre>\n<pre><code>plain</code></pre>")

    def test_inline_markup(self):
        out = playbook.render_inline(
            "Use `a_b *c*` and **bold [link](https://x.test/a_b?q=1&r=2)** or *em* or _em_ and snake_case_name "
            "with \\*literal\\* and 2 * 3 * 4")
        self.assertEqual(out, "Use <code>a_b *c*</code> and <strong>bold <a href=\"https://x.test/a_b?q=1&amp;r=2\" "
                              "rel=\"noopener noreferrer\">link</a></strong> or <em>em</em> or <em>em</em> and "
                              "snake_case_name with *literal* and 2 * 3 * 4")

    def test_unclosed_fence_is_an_error_with_its_line(self):
        with self.assertRaises(ContentError) as caught:
            playbook.parse_markdown("text\n\n```python\ncode\n", first_line=10)
        self.assertEqual(caught.exception.line, 12)

    def test_odd_fence_language_is_refused(self):
        with self.assertRaises(ContentError):
            playbook.parse_markdown('```"><script>alert(1)</script>\nx\n```\n')

    def test_xss_attempts_come_out_inert(self):
        warnings = []
        out = self.render("""\
            <script>alert(1)</script>

            <img src=x onerror=alert(1)>

            [click](javascript:alert(1)) [mixed](JaVaScRiPt:alert(1)) [data](data:text/html,<b>x</b>)
            [relative](/etc/passwd) [entity](&#106;avascript:alert(1))
            [quote](https://ok.test/"onmouseover="alert(1)) **<i onclick=alert(1)>x</i>**

            # <svg onload=alert(1)>
            - `<script>` and <a href="javascript:alert(1)">raw</a>
            """, warnings)
        self.assertNotIn("<script", out)
        self.assertNotIn("<img", out)
        self.assertNotIn("<svg", out)
        self.assertNotIn("<i ", out)
        self.assertNotIn('href="javascript', out.lower())
        self.assertNotIn("href=\"data", out)
        self.assertNotIn("<a href", out)  # every link above is unsafe
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", out)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", out)
        self.assertEqual(len(warnings), 6)
        # Every '<' in the output starts one of our own tags.
        tags = {piece.split(">")[0].split(" ")[0] for piece in out.split("<")[1:]}
        self.assertLessEqual(tags, {"p", "/p", "h1", "/h1", "ul", "/ul", "li", "/li", "code", "/code",
                                    "strong", "/strong"})

    def test_safe_url(self):
        self.assertTrue(playbook.safe_url("https://code.claude.com/docs/en/hooks#x"))
        self.assertTrue(playbook.safe_url("http://example.com"))
        for url in ("javascript:alert(1)", "//evil.test", "/path", "https://", "mailto:a@b.c",
                    "https://a.test/<x>", "vbscript:x", "https://a.test/\"x"):
            self.assertFalse(playbook.safe_url(url), url)

    def test_first_code_under_a_heading(self):
        blocks = playbook.parse_markdown("## Example\ntext\n### Sub\n```sh\nls\n```\n## Next\n```\nno\n```\n")
        self.assertEqual(playbook.first_code_under(blocks, "example")["code"], "ls")
        self.assertIsNone(playbook.first_code_under(blocks, "Prompt"))


class FeatureValidationTest(unittest.TestCase):
    def errors(self, text, stem="projects"):
        feature, errors = playbook.compile_feature(text, stem)
        self.assertIsNone(feature)
        return " | ".join(err.message for err in errors)

    def test_valid_feature(self):
        feature, errors = playbook.compile_feature(FEATURE, "projects")
        self.assertEqual(errors, [])
        self.assertEqual(list(feature), list(playbook.FEATURE_FIELDS) + ["example", "html"])
        self.assertEqual(feature["example"], "Summarise the attached brief.")
        self.assertIn("<li>Open <strong>Projects</strong>.</li>", feature["html"])
        self.assertIn("<em>long-running</em>", feature["html"])

    def test_since_is_optional(self):
        feature, errors = playbook.compile_feature(replace_line(FEATURE, "since:", None), "projects")
        self.assertEqual(errors, [])
        self.assertIsNone(feature["since"])

    def test_each_invalid_case(self):
        cases = [
            (replace_line(FEATURE, "title:", None), "title: must be non-empty text"),
            (replace_line(FEATURE, "summary:", 'summary: ""'), "summary: must be non-empty text"),
            (replace_line(FEATURE, "surface:", "surface: web"), "surface: 'web' is not one of"),
            (replace_line(FEATURE, "level:", "level: expert"), "level: 'expert' is not one of"),
            (replace_line(FEATURE, "status:", "status: alpha"), "status: 'alpha' is not one of"),
            (replace_line(FEATURE, "jobs:", "jobs: [writing, juggling]"), "unknown value(s) juggling"),
            (replace_line(FEATURE, "jobs:", "jobs: []"), "jobs: must list at least one value"),
            (replace_line(FEATURE, "jobs:", "jobs: writing"), "jobs: must be an inline list"),
            (replace_line(FEATURE, "payoff:", "payoff: 4"), "payoff: must be a whole number 1-3"),
            (replace_line(FEATURE, "effort:", "effort: '2'"), "effort: must be a whole number"),
            (replace_line(FEATURE, "verified:", "verified: 2026-02-30"), "not a valid date"),
            (replace_line(FEATURE, "verified:", "verified: 11/11/2026"), "not a valid date"),
            (replace_line(FEATURE, "since:", "since: 2024-13"), "since: '2024-13' is not a valid date"),
            (replace_line(FEATURE, "    url:", "    url: http://support.claude.com/x"), "is not an https URL"),
            (replace_line(FEATURE, "    url:", "    url: javascript:alert(1)"), "is not an https URL"),
            (replace_line(FEATURE, "example_kind:", "example_kind: video"), "example_kind: 'video'"),
            (replace_line(FEATURE, "group:", "group: Context\ncolour: red"), "colour: unknown field"),
            (replace_line(FEATURE, "id:", "id: Projects_X"), "must be lowercase words"),
            (replace_line(FEATURE, "    url:", "    link: https://a.test"), "item 1 needs exactly title, url"),
            (FEATURE.replace("```text", "```txt").replace("## Example", "## Sample"), "'## Example' has no fenced"),
            (FEATURE.replace("Use it for", "See [x](javascript:void(0)) for"), "not an http(s) URL"),
            (FEATURE.replace("```text\nSummarise", "```text\nSummarise\n").replace("```\n\n## At", "\n## At"),
             "never closed"),
        ]
        for text, fragment in cases:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.errors(text))

    def test_id_must_match_the_file_name(self):
        self.assertIn("does not match the file name other.md", self.errors(FEATURE, "other"))

    def test_all_problems_are_reported_together(self):
        text = replace_line(replace_line(FEATURE, "level:", "level: x"), "payoff:", "payoff: 9")
        _, errors = playbook.compile_feature(text, "projects")
        self.assertEqual([err.line for err in errors], [8, 9])


class RecipeValidationTest(unittest.TestCase):
    def compile(self, text, features=("projects",)):
        return playbook.compile_recipe(text, "weekly-status", set(features))

    def test_valid_recipe(self):
        recipe, errors = self.compile(RECIPE)
        self.assertEqual(errors, [])
        self.assertEqual(recipe["template"], "Write the {{team}} status for {{ week }}.")
        self.assertEqual(recipe["prerequisites"], ["A project with last week's notes",
                                                   "Access to the tracker, read-only"])
        self.assertEqual(recipe["fields"][1], {"name": "week", "label": "Week", "placeholder": "2026-W46"})
        self.assertEqual(list(recipe), list(playbook.RECIPE_FIELDS) + ["template", "html"])

    def messages(self, text, features=("projects",)):
        recipe, errors = self.compile(text, features)
        self.assertIsNone(recipe)
        return " | ".join(err.message for err in errors)

    def test_unknown_feature(self):
        self.assertIn("unknown or invalid feature id(s): projects", self.messages(RECIPE, features=()))

    def test_template_and_fields_must_match_both_ways(self):
        extra_placeholder = RECIPE.replace("{{ week }}", "{{ week }} by {{owner}}")
        self.assertIn("template uses {{owner}} with no matching entry in fields", self.messages(extra_placeholder))
        unused_field = RECIPE.replace(" for {{ week }}", "")
        self.assertIn("fields week are never used", self.messages(unused_field))

    def test_bad_placeholders(self):
        self.assertIn("{{Team Name}} is not a valid field name",
                      self.messages(RECIPE.replace("{{team}}", "{{Team Name}}")))
        self.assertIn("unbalanced", self.messages(RECIPE.replace("{{team}}", "{{team}} {{")))

    def test_template_needs_a_fence_under_prompt(self):
        self.assertIn("'## Prompt' has no fenced code block", self.messages(RECIPE.replace("## Prompt", "## Ask")))

    def test_field_problems(self):
        self.assertIn("two fields share a name", self.messages(RECIPE.replace("name: week", "name: team")))
        self.assertIn("lowercase words with underscores",
                      self.messages(RECIPE.replace("name: week", "name: Week").replace("{{ week }}", "{{Week}}")))
        self.assertIn("minutes_saved: must be a whole number of at least 1",
                      self.messages(RECIPE.replace("minutes_saved: 30", "minutes_saved: 0")))
        self.assertIn("job: 'cooking' is not one of", self.messages(RECIPE.replace("job: writing", "job: cooking")))


class CompileDirectoryTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.content = self.root / "content" / "claude"
        (self.content / "features").mkdir(parents=True)
        (self.content / "recipes").mkdir()

    def write(self, kind, stem, text):
        (self.content / kind / (stem + ".md")).write_text(text, encoding="utf-8")

    def test_bad_files_are_skipped_and_reported(self):
        self.write("features", "projects", FEATURE)
        self.write("features", "memory", FEATURE.replace("id: projects", "id: memory")
                   .replace("title: Projects", "title: Memory").replace("surface: apps", "surface: code")
                   .replace("level: starter", "level: guru"))
        self.write("recipes", "weekly-status", RECIPE.replace("features: [projects]", "features: [projects, memory]"))
        self.write("recipes", "projects", RECIPE.replace("id: weekly-status", "id: projects"))
        features, recipes, errors = playbook.compile_playbook(self.content, self.root)
        self.assertEqual([f["id"] for f in features], ["projects"])
        self.assertEqual(recipes, [])
        self.assertEqual(errors, [
            {"file": "content/claude/features/memory.md", "line": 8,
             "message": "level: 'guru' is not one of starter, intermediate, power"},
            {"file": "content/claude/recipes/projects.md", "line": None,
             "message": "duplicate id 'projects' (also used by content/claude/features/projects.md)"},
            {"file": "content/claude/recipes/weekly-status.md", "line": 7,
             "message": "features: unknown or invalid feature id(s): memory"},
        ])

    def test_unreadable_file_is_reported(self):
        (self.content / "features" / "broken.md").write_bytes(b"---\nid: \xff\n---\n")
        _, _, errors = playbook.compile_playbook(self.content, self.root)
        self.assertIn("cannot read file", errors[0]["message"])

    def test_build_writes_playbook_and_error_report(self):
        self.write("features", "projects", FEATURE)
        self.write("features", "broken", "no front matter")
        self.write("recipes", "weekly-status", RECIPE)
        data = self.root / "data"
        timeutil.set_now(timeutil.parse_date("2026-11-11T06:00:00Z"))
        self.addCleanup(timeutil.set_now, None)
        net.set_offline(True)
        self.addCleanup(net.set_offline, False)
        ctx = config.context(data_dir=data)
        ctx.paths = replace(ctx.paths, root=self.root)
        ctx.paths.ensure()
        with mock.patch.multiple(playbook.log, info=mock.DEFAULT, warn=mock.DEFAULT) as logged:
            features, counts = playbook.build(ctx)
        self.assertIn("broken.md", logged["warn"].call_args[0][1])
        self.assertEqual(counts, {"features": 1, "recipes": 1, "contentErrors": 1, "contentFilesSkipped": 1})
        self.assertEqual([f["id"] for f in features], ["projects"])
        published = json.loads((data / "public" / "claude" / "playbook.json").read_text())
        self.assertEqual(published["generatedAt"], "2026-11-11T06:00:00Z")
        self.assertEqual([s["id"] for s in published["surfaces"]],
                         ["apps", "code", "platform", "cowork", "integrations"])
        self.assertEqual([j["id"] for j in published["jobs"]],
                         ["coding", "review", "debugging", "writing", "research", "analysis", "meetings",
                          "planning", "automation", "learning"])
        self.assertEqual(published["recipes"][0]["id"], "weekly-status")
        report = json.loads((data / "state" / "playbook-errors.json").read_text())
        self.assertEqual(report["errors"][0]["file"], "content/claude/features/broken.md")


if __name__ == "__main__":
    unittest.main()
