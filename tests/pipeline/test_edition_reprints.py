"""An edition does not reprint what the last one carried, unless the story has grown a lot."""
import tempfile
import unittest
from pathlib import Path

from pipeline import edition
from pipeline.core import jsonio


def story(story_id, outlets):
    return {"id": story_id, "sourceCount": outlets, "title": "Story %s" % story_id}


class DropReprints(unittest.TestCase):
    def test_a_story_printed_yesterday_is_left_out(self):
        kept = edition.drop_reprints([story("a", 9), story("b", 4)], {"a": 9})
        self.assertEqual([s["id"] for s in kept], ["b"])

    def test_a_few_more_outlets_is_not_enough(self):
        self.assertEqual(edition.drop_reprints([story("a", 11)], {"a": 9}), [])
        self.assertEqual(edition.drop_reprints([story("small", 3)], {"small": 1}), [])

    def test_a_story_that_became_much_bigger_news_returns(self):
        self.assertEqual(len(edition.drop_reprints([story("a", 14)], {"a": 9})), 1)
        self.assertEqual(len(edition.drop_reprints([story("small", 4)], {"small": 1})), 1)

    def test_stories_never_printed_are_untouched(self):
        stories = [story("a", 1), story("b", 2)]
        self.assertEqual(edition.drop_reprints(stories, {}), stories)

    def test_a_missing_outlet_count_reads_as_one(self):
        self.assertEqual(edition.drop_reprints([{"id": "a"}], {"a": 1}), [])


class PreviouslyPrinted(unittest.TestCase):
    def test_reads_every_slot_of_the_newest_earlier_edition(self):
        with tempfile.TemporaryDirectory() as tmp:
            editions = Path(tmp)
            jsonio.write_json(editions / "2026-11-09.json", {"lead": story("old", 5)})
            jsonio.write_json(editions / "2026-11-10.json", {
                "lead": story("lead", 9), "front": [story("front", 6)], "briefs": [story("brief", 2)],
                "sections": [{"id": "world", "stories": [story("desk", 3)]}]})
            jsonio.write_json(editions / "2026-11-11.json", {"lead": story("today", 4)})
            jsonio.write_json(editions / "index.json", {"editions": []})
            printed = edition._previously_printed(editions, "2026-11-11")
        self.assertEqual(printed, {"lead": 9, "front": 6, "brief": 2, "desk": 3})

    def test_no_earlier_edition_or_a_corrupt_one_means_nothing_was_printed(self):
        with tempfile.TemporaryDirectory() as tmp:
            editions = Path(tmp)
            self.assertEqual(edition._previously_printed(editions, "2026-11-11"), {})
            (editions / "2026-11-10.json").write_text("not json", encoding="utf-8")
            self.assertEqual(edition._previously_printed(editions, "2026-11-11"), {})


if __name__ == "__main__":
    unittest.main()
