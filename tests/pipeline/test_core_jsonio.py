"""pipeline.core.jsonio: atomic writes, forgiving reads."""

import contextlib
import io
import json
import os
import stat
import tempfile
import threading
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from pipeline.core import jsonio
from pipeline.core.jsonio import read_json, write_json


class JsonTestCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.dir = Path(folder.name)

    def leftovers(self, directory=None):
        return sorted(name for name in os.listdir(directory or self.dir) if name.endswith(".tmp"))

    @contextlib.contextmanager
    def captured_log(self):
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            yield stderr


class Write(JsonTestCase):
    def test_round_trip(self):
        data = {"date": "2026-11-11", "items": {"i1": {"title": "A", "n": 1, "x": 1.5, "ok": True, "none": None}},
                "list": [1, "two", [3]]}
        path = self.dir / "a.json"
        write_json(path, data)
        self.assertEqual(read_json(path), data)

    def test_output_is_compact_utf8_with_a_final_newline(self):
        path = self.dir / "a.json"
        write_json(path, {"title": "Café ₹500 — नमस्ते", "n": [1, 2]})
        raw = path.read_bytes()
        self.assertEqual(raw.decode("utf-8"),
                         '{"title":"Café ₹500 — नमस्ते","n":[1,2]}\n')
        self.assertNotIn(b"\\u", raw)

    def test_key_order_is_preserved_unless_sorting_is_requested(self):
        path = self.dir / "a.json"
        write_json(path, {"b": 1, "a": 2})
        self.assertEqual(path.read_text(encoding="utf-8"), '{"b":1,"a":2}\n')
        write_json(path, {"b": 1, "a": {"z": 1, "y": 2}}, sort_keys=True)
        self.assertEqual(path.read_text(encoding="utf-8"), '{"a":{"y":2,"z":1},"b":1}\n')

    def test_creates_parent_directories(self):
        path = self.dir / "state" / "items" / "2026-11-11.json"
        write_json(path, {"ok": 1})
        self.assertEqual(read_json(path), {"ok": 1})

    def test_accepts_str_and_path(self):
        write_json(str(self.dir / "s.json"), [1])
        self.assertEqual(read_json(str(self.dir / "s.json")), [1])
        self.assertEqual(read_json(self.dir / "s.json"), [1])

    def test_relative_path_without_a_directory(self):
        previous = os.getcwd()
        os.chdir(self.dir)
        self.addCleanup(os.chdir, previous)
        write_json("bare.json", {"a": 1})
        self.assertEqual(read_json("bare.json"), {"a": 1})

    def test_datetimes_become_utc_iso_strings(self):
        path = self.dir / "a.json"
        ist = timezone(timedelta(hours=5, minutes=30))
        write_json(path, {"at": datetime(2026, 11, 11, 11, 32, 0, 123, tzinfo=ist),
                          "naive": datetime(2026, 11, 11, 6, 2), "day": date(2026, 11, 11)})
        self.assertEqual(read_json(path), {"at": "2026-11-11T06:02:00Z", "naive": "2026-11-11T06:02:00Z",
                                           "day": "2026-11-11"})

    def test_sets_become_sorted_lists(self):
        path = self.dir / "a.json"
        write_json(path, {"topics": {"tesla", "ai", "spacex"}, "frozen": frozenset(["b", "a"])})
        self.assertEqual(read_json(path), {"topics": ["ai", "spacex", "tesla"], "frozen": ["a", "b"]})

    def test_lone_surrogate_does_not_fail_the_file(self):
        path = self.dir / "a.json"
        broken = json.loads('"half an emoji ' + chr(92) + 'ud83d here"')
        write_json(path, {"title": broken, "ok": "\U0001F600"})
        self.assertEqual(read_json(path), {"title": "half an emoji ? here", "ok": "\U0001F600"})

    def test_overwrite_replaces_the_whole_file(self):
        path = self.dir / "a.json"
        write_json(path, {"long": "x" * 10000})
        write_json(path, {"short": 1})
        self.assertEqual(path.read_text(encoding="utf-8"), '{"short":1}\n')

    def test_no_temp_files_are_left_behind(self):
        for index in range(5):
            write_json(self.dir / "a.json", {"n": index})
        self.assertEqual(self.leftovers(), [])
        self.assertEqual(os.listdir(self.dir), ["a.json"])

    def test_file_is_world_readable(self):
        path = self.dir / "a.json"
        write_json(path, {})
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)

    def test_dumps_matches_what_is_written(self):
        path = self.dir / "a.json"
        data = {"a": [1, {"b": "₹"}]}
        write_json(path, data)
        self.assertEqual(path.read_text(encoding="utf-8"), jsonio.dumps(data) + "\n")


class WriteFailures(JsonTestCase):
    def test_unserialisable_value_raises_and_keeps_the_old_file(self):
        path = self.dir / "a.json"
        write_json(path, {"good": 1})
        with self.assertRaises(TypeError):
            write_json(path, {"bad": object()})
        self.assertEqual(read_json(path), {"good": 1})
        self.assertEqual(self.leftovers(), [])

    def test_nan_and_infinity_are_refused(self):
        path = self.dir / "a.json"
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.assertRaises(ValueError):
                write_json(path, {"price": value})
        self.assertFalse(path.exists())
        self.assertEqual(self.leftovers(), [])

    def test_failed_rename_keeps_the_old_file_and_cleans_up(self):
        path = self.dir / "a.json"
        write_json(path, {"version": 1})
        with mock.patch("os.replace", side_effect=OSError("disk says no")):
            with self.assertRaises(OSError):
                write_json(path, {"version": 2})
        self.assertEqual(read_json(path), {"version": 1})
        self.assertEqual(self.leftovers(), [])

    def test_failure_while_writing_cleans_up(self):
        path = self.dir / "a.json"
        with mock.patch("os.fsync", side_effect=OSError("no space left")):
            with self.assertRaises(OSError):
                write_json(path, {"version": 1})
        self.assertFalse(path.exists())
        self.assertEqual(self.leftovers(), [])

    def test_parent_that_is_a_file_raises_oserror(self):
        blocker = self.dir / "blocker"
        blocker.write_text("x", encoding="utf-8")
        with self.assertRaises(OSError):
            write_json(blocker / "a.json", {})

    def test_data_is_fsynced_before_the_rename(self):
        order = []
        real_fsync, real_replace = os.fsync, os.replace
        with mock.patch("os.fsync", side_effect=lambda fd: (order.append("fsync"), real_fsync(fd))[1]), \
                mock.patch("os.replace", side_effect=lambda a, b: (order.append("replace"), real_replace(a, b))[1]):
            write_json(self.dir / "a.json", {"a": 1})
        self.assertEqual(order, ["fsync", "replace"])

    def test_temp_file_lives_in_the_target_directory(self):
        seen = []
        real_replace = os.replace
        with mock.patch("os.replace", side_effect=lambda a, b: (seen.append((a, b)), real_replace(a, b))[1]):
            write_json(self.dir / "sub" / "a.json", {"a": 1})
        source, target = seen[0]
        self.assertEqual(os.path.dirname(source), os.path.dirname(target))
        self.assertTrue(os.path.basename(source).startswith(".a.json."))


class Read(JsonTestCase):
    def test_missing_file_returns_the_default_silently(self):
        with self.captured_log() as log:
            self.assertIsNone(read_json(self.dir / "nope.json"))
            self.assertEqual(read_json(self.dir / "nope.json", default={"items": {}}), {"items": {}})
            self.assertEqual(read_json(self.dir / "no" / "such" / "dir.json", default=[]), [])
        self.assertEqual(log.getvalue(), "")

    def test_corrupt_file_returns_the_default_and_logs(self):
        path = self.dir / "bad.json"
        for content in ('{"a": 1', "", "not json at all", '{"a": NaN,}', "[1, 2,,]"):
            path.write_text(content, encoding="utf-8")
            with self.captured_log() as log:
                self.assertEqual(read_json(path, default="fallback"), "fallback", repr(content))
            self.assertIn("corrupt JSON", log.getvalue(), repr(content))
            self.assertIn("bad.json", log.getvalue())

    def test_invalid_utf8_returns_the_default_and_logs(self):
        path = self.dir / "bad.json"
        path.write_bytes(b'{"title": "caf\xe9"}')
        with self.captured_log() as log:
            self.assertEqual(read_json(path, default={}), {})
        self.assertIn("corrupt JSON", log.getvalue())

    def test_bom_is_tolerated(self):
        path = self.dir / "bom.json"
        path.write_bytes(b'\xef\xbb\xbf{"a": 1}')
        self.assertEqual(read_json(path), {"a": 1})

    def test_directory_in_place_of_a_file_returns_the_default_and_logs(self):
        with self.captured_log() as log:
            self.assertEqual(read_json(self.dir, default=7), 7)
        self.assertIn("cannot read", log.getvalue())

    def test_valid_falsy_values_are_not_replaced_by_the_default(self):
        path = self.dir / "a.json"
        for value in (0, "", [], {}, False, None):
            write_json(path, value)
            self.assertEqual(read_json(path, default="fallback"), value)


class Concurrency(JsonTestCase):
    def test_readers_never_see_a_partial_file(self):
        path = self.dir / "shared.json"
        write_json(path, {"n": -1, "pad": "x" * 20000})
        stop = threading.Event()
        problems = []

        def writer(seed):
            for index in range(60):
                write_json(path, {"n": seed * 1000 + index, "pad": "y" * 20000})

        def reader():
            while not stop.is_set():
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                    if len(value["pad"]) != 20000:
                        problems.append("short read")
                except (ValueError, OSError) as err:
                    problems.append(repr(err))

        readers = [threading.Thread(target=reader) for _ in range(3)]
        writers = [threading.Thread(target=writer, args=(seed,)) for seed in range(4)]
        for thread in readers + writers:
            thread.start()
        for thread in writers:
            thread.join()
        stop.set()
        for thread in readers:
            thread.join()
        self.assertEqual(problems, [])
        self.assertEqual(self.leftovers(), [])
        self.assertEqual(len(read_json(path)["pad"]), 20000)


if __name__ == "__main__":
    unittest.main()
