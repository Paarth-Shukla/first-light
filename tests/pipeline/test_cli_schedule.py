"""Cross-stage scheduling rules for ``python3 -m pipeline all``.

Each stage tests its own logic; these tests pin down what only shows when the
stages run together: the order ``all`` runs them in (a stage must run after
every stage whose output it freezes or indexes), and the Saturday Weekend
Review still being built after a mid-week ``papers --force``.
"""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from pipeline import __main__ as cli
from pipeline import papers
from pipeline.core import timeutil

IST = timeutil.zone("Asia/Kolkata")
SATURDAY = timeutil.parse_date("2026-11-14T00:35:00Z")    # 06:05 IST, Saturday
WEDNESDAY = timeutil.parse_date("2026-11-11T00:35:00Z")


class StageOrder(unittest.TestCase):
    """Who reads whom (docs/ARCHITECTURE.md, CLI table) decides the order."""

    def position(self, stage):
        return cli.ALL_ORDER.index(stage)

    def test_every_stage_runs_once(self):
        self.assertEqual(sorted(cli.ALL_ORDER), sorted(cli.STAGES))

    def test_fetch_first_build_last(self):
        self.assertEqual((cli.ALL_ORDER[0], cli.ALL_ORDER[-1]), ("fetch", "build"))

    def test_edition_inputs_run_before_process(self):
        # The edition is frozen for the day and embeds the market strip, the
        # Claude card and, at weekends, the Weekend Review pointer.
        for stage in ("markets", "claude", "papers"):
            self.assertLess(self.position(stage), self.position("process"), stage)

    def test_search_indexes_every_content_stage(self):
        for stage in ("process", "papers", "claude"):
            self.assertLess(self.position(stage), self.position("search"), stage)


class SaturdayAfterForcedBuild(unittest.TestCase):
    """A ``papers --force`` on Wednesday writes the same ISO week's file as Saturday's issue."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.issue = Path(folder.name) / "2026-W46.json"
        self.saturday_window = papers.Window(SATURDAY, IST, 7)

    def write_issue(self, first, last):
        self.issue.write_text(json.dumps({"isoWeek": "2026-W46", "from": first, "to": last}))

    def due(self, now):
        return papers.is_due(now, IST, 5, self.issue, False, self.saturday_window.last)

    def test_both_runs_name_the_same_week(self):
        self.assertEqual(papers.Window(WEDNESDAY, IST, 7).iso_week, self.saturday_window.iso_week)
        self.assertEqual(self.saturday_window.last, date(2026, 11, 13))

    def test_saturday_rebuilds_over_a_mid_week_issue(self):
        self.write_issue("2026-11-04", "2026-11-10")
        self.assertTrue(self.due(SATURDAY))

    def test_saturday_issue_is_built_once(self):
        self.write_issue("2026-11-07", "2026-11-13")
        self.assertFalse(self.due(SATURDAY))

    def test_unreadable_issue_is_not_overwritten(self):
        self.issue.write_text("{}")
        self.assertFalse(self.due(SATURDAY))

    def test_never_due_mid_week_without_force(self):
        self.assertFalse(self.due(WEDNESDAY))


if __name__ == "__main__":
    unittest.main()
