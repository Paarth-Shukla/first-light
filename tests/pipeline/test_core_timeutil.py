"""pipeline.core.timeutil: every date shape the source research found, plus the clock helpers."""

import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline.core import timeutil
from pipeline.core.timeutil import (
    UTC, hours_between, iso, iso_week, local_date, now_utc, parse_date, set_now, zone)

IST = "Asia/Kolkata"
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "core" / "real-feed-samples.json"

# (input, default_tz, expected ISO in UTC)
VALID = [
    # RFC 822 as feeds write it
    ("Wed, 11 Nov 2026 10:14:22 GMT", None, "2026-11-11T10:14:22Z"),
    ("Wed, 11 Nov 2026 10:14:22 +0000", None, "2026-11-11T10:14:22Z"),
    ("Wed, 11 Nov 2026 18:47:03 +0530", None, "2026-11-11T13:17:03Z"),
    ("Wed, 11 Nov 2026 08:00:14 -0500", None, "2026-11-11T13:00:14Z"),
    ("Wed, 11 Nov 2026 12:00:00 +0100", None, "2026-11-11T11:00:00Z"),
    ("Wed, 11 Nov 2026 12:00:00 +0800", None, "2026-11-11T04:00:00Z"),
    ("Wed, 11 Nov 2026 07:00:00 EST", None, "2026-11-11T12:00:00Z"),
    ("Wed, 11 Nov 2026 07:00:00 EDT", None, "2026-11-11T11:00:00Z"),
    ("Wed, 11 Nov 2026 07:00:00 PST", None, "2026-11-11T15:00:00Z"),
    ("Wed, 11 Nov 2026 07:00:00 PDT", None, "2026-11-11T14:00:00Z"),
    ("Wed, 11 Nov 2026 07:00:00 CST", None, "2026-11-11T13:00:00Z"),
    ("Wed, 11 Nov 2026 07:00:00 MST", None, "2026-11-11T14:00:00Z"),
    ("Wed, 11 Nov 2026 10:14:22 Z", None, "2026-11-11T10:14:22Z"),
    ("Wed, 11 Nov 2026 10:14:22 UT", None, "2026-11-11T10:14:22Z"),
    ("Wed, 11 Nov 2026 10:14:22 UTC", None, "2026-11-11T10:14:22Z"),
    ("Wed, 11 Nov 2026 10:14:22 -0000", None, "2026-11-11T10:14:22Z"),
    ("Wed, 11 Nov 2026 10:14:22 +0000 (UTC)", None, "2026-11-11T10:14:22Z"),
    ("Sat, 07 Nov 2026 9:05:00 IST", None, "2026-11-07T03:35:00Z"),
    ("5 Sept 2026 10:00 BST", None, "2026-09-05T09:00:00Z"),
    ("11 Nov 2026 10:14:22 +0000", None, "2026-11-11T10:14:22Z"),
    ("Sun, 1 Nov 2026 00:00:00 GMT", None, "2026-11-01T00:00:00Z"),
    ("Tue, 10 Nov 26 12:00:00 -0500", None, "2026-11-10T17:00:00Z"),       # AMD: two-digit year
    ("1 Jan 70 00:00:00 GMT", None, "1970-01-01T00:00:00Z"),
    ("31 Dec 68 00:00 GMT", None, "2068-12-31T00:00:00Z"),
    ("Tue, 10 Nov 2026 15:39 GMT", None, "2026-11-10T15:39:00Z"),           # NASA: no seconds
    ("THU, 17 SEP 2026 09:42:20 -0400", None, "2026-09-17T13:42:20Z"),      # IEEE: upper case
    ("Wed, 11 Nov 2026 00:00:00 -0500", None, "2026-11-11T05:00:00Z"),      # arXiv RSS
    ("  Wed, 11 Nov 2026 10:14:22 GMT \n", None, "2026-11-11T10:14:22Z"),   # CDATA padding
    ("Wed, 11 Nov 2026 23:59:60 GMT", None, "2026-11-11T23:59:59Z"),        # leap second
    # RFC 822 without a zone: read in default_tz
    ("Wed, 11 Nov 2026 17:25:00", IST, "2026-11-11T11:55:00Z"),             # RBI
    ("Wed, 11 Nov 2026 17:25:00", None, "2026-11-11T17:25:00Z"),
    ("Wed, 11 Nov 2026 10:00:00 XYZ", IST, "2026-11-11T04:30:00Z"),         # unknown zone name
    ("11-Nov-2026 18:04:14", IST, "2026-11-11T12:34:14Z"),                  # NSE / BSE
    ("11 Nov, 2026 +0530", None, "2026-11-10T18:30:00Z"),                   # SEBI
    ("11 Nov, 2026 +0530", "America/New_York", "2026-11-10T18:30:00Z"),     # explicit offset wins
    ("11 Nov 2026", None, "2026-11-11T00:00:00Z"),
    ("05 November 2026", None, "2026-11-05T00:00:00Z"),                     # Nature Electronics
    # ISO 8601
    ("2026-11-11T11:31:00Z", None, "2026-11-11T11:31:00Z"),
    ("2026-11-11t11:31:00z", None, "2026-11-11T11:31:00Z"),
    ("2026-11-11T16:06:21+05:30", None, "2026-11-11T10:36:21Z"),            # TOI
    ("2026-11-11T08:00:00-05:00", None, "2026-11-11T13:00:00Z"),            # Verge
    ("2026-11-11T08:00:00-07:00", None, "2026-11-11T15:00:00Z"),            # Google Cloud
    ("2026-11-11T16:06:21+0530", None, "2026-11-11T10:36:21Z"),
    ("2026-11-11T16:06:21+05", None, "2026-11-11T11:06:21Z"),
    ("2026-11-10T20:09:44+00:00", None, "2026-11-10T20:09:44Z"),
    ("2026-11-09T00:00:00.000Z", None, "2026-11-09T00:00:00Z"),             # HF, Apple
    ("2026-11-11T10:14:22.5Z", None, "2026-11-11T10:14:22Z"),
    ("2026-11-11T10:14:22.123456Z", None, "2026-11-11T10:14:22Z"),
    ("2026-11-11T10:14:22.123456789+05:30", None, "2026-11-11T04:44:22Z"),
    ("2026-11-11T10:14:22,5Z", None, "2026-11-11T10:14:22Z"),
    ("2026-11-11T10:14Z", None, "2026-11-11T10:14:00Z"),
    ("2026-11-11 12:24:39", None, "2026-11-11T12:24:39Z"),                  # Investing.com
    ("2026-11-11 12:24:39", IST, "2026-11-11T06:54:39Z"),
    ("2026-11-11T18:04:25+05:30", None, "2026-11-11T12:34:25Z"),            # Moneycontrol sitemap
    ("2026-11-11T10:00:00 EST", None, "2026-11-11T15:00:00Z"),
    # date only
    ("2026-11-11", None, "2026-11-11T00:00:00Z"),                           # Nature, Anthropic
    ("2026-11-11", IST, "2026-11-10T18:30:00Z"),
    ("2026-1-5", None, "2026-01-05T00:00:00Z"),
    ("20261111", None, "2026-11-11T00:00:00Z"),
    # month first
    ("November 6, 2026", None, "2026-11-06T00:00:00Z"),                     # Claude release notes
    ("Nov 6, 2026", None, "2026-11-06T00:00:00Z"),
    ("Sept 5, 2026", None, "2026-09-05T00:00:00Z"),
    ("November 6th, 2026", None, "2026-11-06T00:00:00Z"),
    ("Nov 6, 2026 10:30 PM", None, "2026-11-06T22:30:00Z"),
    ("Nov 6, 2026 12:05 am", None, "2026-11-06T00:05:00Z"),
    ("Nov 6, 2026 12:05 PM", None, "2026-11-06T12:05:00Z"),
    ("Tuesday, November 10, 2026 12:05 AM EST", None, "2026-11-10T05:05:00Z"),
    # epoch
    (1794344401, None, "2026-11-10T21:00:01Z"),
    (1794344401123, None, "2026-11-10T21:00:01Z"),
    (1794344401.5, None, "2026-11-10T21:00:01Z"),
    ("1794344401", None, "2026-11-10T21:00:01Z"),
    ("1794400373000", None, "2026-11-11T12:32:53Z"),
    (1794344401, IST, "2026-11-10T21:00:01Z"),                              # epoch ignores default_tz
    (0, None, "1970-01-01T00:00:00Z"),
]

INVALID = [
    None, "", "   ", "not a date", "yesterday", "null", "2026-13-45", "2026-02-30", "31 Feb 2026",
    "Wed, 11 Foo 2026 10:00:00 GMT", "Wed, 11 Nov 2026 25:00:00 GMT", "2026-11-11T25:00:00Z",
    "2026-11-11T10:61:00Z", "2026-11-11T10:00:00+9900", "Nov 6, 2026 13:00 PM", "12345", "2026",
    "1234567", "99999999", "0000-00-00", True, False, [], {}, -5, float("nan"), float("inf"),
    10 ** 18, "Wed, 11 Nov 202 10:00:00 GMT", "11/11/2026",
]


class ParseDate(unittest.TestCase):
    def test_every_known_shape(self):
        for value, tz, expected in VALID:
            parsed = parse_date(value, tz)
            self.assertIsNotNone(parsed, repr(value))
            self.assertEqual(iso(parsed), expected, repr(value))

    def test_result_is_always_aware_utc(self):
        for value, tz, _ in VALID:
            parsed = parse_date(value, tz)
            self.assertEqual(parsed.utcoffset(), timedelta(0), repr(value))
            self.assertIs(parsed.tzinfo, UTC, repr(value))

    def test_unparseable_values_return_none_and_never_raise(self):
        for value in INVALID:
            self.assertIsNone(parse_date(value), repr(value))
            self.assertIsNone(parse_date(value, IST), repr(value))

    def test_fraction_precision_is_kept_to_microseconds(self):
        self.assertEqual(parse_date("2026-11-11T10:14:22.5Z").microsecond, 500000)
        self.assertEqual(parse_date("2026-11-11T10:14:22.000Z").microsecond, 0)
        self.assertEqual(parse_date("2026-11-11T10:14:22.123456789Z").microsecond, 123456)
        self.assertEqual(parse_date(1794344401123).microsecond, 123000)

    def test_datetime_and_date_inputs(self):
        aware = datetime(2026, 11, 11, 16, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        self.assertEqual(iso(parse_date(aware)), "2026-11-11T10:30:00Z")
        naive = datetime(2026, 11, 11, 16, 0)
        self.assertEqual(iso(parse_date(naive)), "2026-11-11T16:00:00Z")
        self.assertEqual(iso(parse_date(naive, IST)), "2026-11-11T10:30:00Z")
        self.assertEqual(iso(parse_date(date(2026, 11, 11))), "2026-11-11T00:00:00Z")
        self.assertEqual(iso(parse_date(date(2026, 11, 11), IST)), "2026-11-10T18:30:00Z")

    def test_default_tz_accepts_a_tzinfo(self):
        self.assertEqual(iso(parse_date("2026-11-11 12:00:00", ZoneInfo(IST))), "2026-11-11T06:30:00Z")
        self.assertEqual(iso(parse_date("2026-11-11 12:00:00", timezone(timedelta(hours=-3)))),
                         "2026-11-11T15:00:00Z")

    def test_default_tz_follows_daylight_saving(self):
        self.assertEqual(iso(parse_date("2026-07-01 12:00:00", "America/New_York")), "2026-07-01T16:00:00Z")
        self.assertEqual(iso(parse_date("2026-01-15 12:00:00", "America/New_York")), "2026-01-15T17:00:00Z")

    def test_bad_default_tz_is_a_loud_config_error(self):
        with self.assertRaises(ValueError):
            parse_date("2026-11-11", "Mars/Olympus_Mons")
        with self.assertRaises(ValueError):
            parse_date(None, "Mars/Olympus_Mons")

    def test_real_feed_dates(self):
        for sample in json.loads(FIXTURE.read_text(encoding="utf-8"))["dates"]:
            self.assertEqual(iso(parse_date(sample["in"], sample["tz"])), sample["out"], sample["source"])

    def test_iso_round_trip(self):
        for value, tz, expected in VALID:
            self.assertEqual(iso(parse_date(expected)), expected)


class Zone(unittest.TestCase):
    def test_none_is_utc(self):
        self.assertIs(zone(None), UTC)

    def test_name_and_tzinfo(self):
        self.assertEqual(zone(IST), ZoneInfo(IST))
        tz = ZoneInfo("Europe/London")
        self.assertIs(zone(tz), tz)

    def test_unknown_name(self):
        for bad in ("Nowhere/Land", "", "../etc/passwd"):
            with self.assertRaises(ValueError):
                zone(bad)


class Clock(unittest.TestCase):
    def setUp(self):
        self.addCleanup(set_now, None)

    def test_real_clock_is_aware_utc_and_current(self):
        set_now(None)
        now = now_utc()
        self.assertEqual(now.utcoffset(), timedelta(0))
        self.assertLess(abs((datetime.now(timezone.utc) - now).total_seconds()), 5)

    def test_set_now_freezes_the_clock(self):
        set_now("2026-11-11T06:00:00Z")
        self.assertEqual(iso(now_utc()), "2026-11-11T06:00:00Z")
        self.assertEqual(now_utc(), now_utc())

    def test_set_now_accepts_datetimes_and_offsets(self):
        set_now(datetime(2026, 11, 11, 6, 0, tzinfo=ZoneInfo(IST)))
        self.assertEqual(iso(now_utc()), "2026-11-11T00:30:00Z")
        set_now("2026-11-11T06:00:00+05:30")
        self.assertEqual(iso(now_utc()), "2026-11-11T00:30:00Z")
        set_now("2026-11-11")
        self.assertEqual(iso(now_utc()), "2026-11-11T00:00:00Z")

    def test_set_now_none_restores_the_real_clock(self):
        set_now("2001-01-01T00:00:00Z")
        set_now(None)
        self.assertGreater(now_utc().year, 2020)

    def test_set_now_rejects_garbage_and_keeps_the_previous_value(self):
        set_now("2026-11-11T06:00:00Z")
        with self.assertRaises(ValueError):
            set_now("soon")
        self.assertEqual(iso(now_utc()), "2026-11-11T06:00:00Z")


class Formatting(unittest.TestCase):
    def test_iso_shape(self):
        self.assertEqual(iso(datetime(2026, 11, 11, 6, 2, 0, tzinfo=UTC)), "2026-11-11T06:02:00Z")

    def test_iso_converts_to_utc_and_drops_microseconds(self):
        local = datetime(2026, 11, 11, 11, 32, 0, 987654, tzinfo=ZoneInfo(IST))
        self.assertEqual(iso(local), "2026-11-11T06:02:00Z")

    def test_iso_treats_naive_as_utc(self):
        self.assertEqual(iso(datetime(2026, 11, 11, 6, 2)), "2026-11-11T06:02:00Z")

    def test_local_date_changes_at_local_midnight(self):
        before = parse_date("2026-11-10T18:29:59Z")
        after = parse_date("2026-11-10T18:30:00Z")
        self.assertEqual(local_date(before, IST), "2026-11-10")
        self.assertEqual(local_date(after, IST), "2026-11-11")
        self.assertEqual(local_date(after, None), "2026-11-10")
        self.assertEqual(local_date(after, ZoneInfo("America/Los_Angeles")), "2026-11-10")

    def test_iso_week(self):
        self.assertEqual(iso_week(parse_date("2026-11-11T06:00:00Z"), IST), "2026-W46")
        self.assertEqual(iso_week(parse_date("2026-01-05T12:00:00Z"), IST), "2026-W02")

    def test_iso_week_uses_the_iso_year_at_year_boundaries(self):
        self.assertEqual(iso_week(parse_date("2027-01-01T12:00:00Z"), None), "2026-W53")
        self.assertEqual(iso_week(parse_date("2024-12-30T12:00:00Z"), None), "2025-W01")

    def test_iso_week_depends_on_the_zone(self):
        sunday_evening_utc = parse_date("2026-11-08T19:00:00Z")   # already Monday in India
        self.assertEqual(iso_week(sunday_evening_utc, None), "2026-W45")
        self.assertEqual(iso_week(sunday_evening_utc, IST), "2026-W46")

    def test_hours_between_is_signed(self):
        start = parse_date("2026-11-11T00:00:00Z")
        end = parse_date("2026-11-11T18:30:00Z")
        self.assertEqual(hours_between(start, end), 18.5)
        self.assertEqual(hours_between(end, start), -18.5)
        self.assertEqual(hours_between(start, start), 0.0)

    def test_hours_between_mixed_zones_and_naive(self):
        ist_noon = datetime(2026, 11, 11, 12, 0, tzinfo=ZoneInfo(IST))
        utc_noon = datetime(2026, 11, 11, 12, 0)
        self.assertEqual(hours_between(ist_noon, utc_noon), 5.5)

    def test_module_exposes_the_contract_names(self):
        for name in ("parse_date", "now_utc", "iso", "local_date", "iso_week", "set_now", "hours_between"):
            self.assertTrue(callable(getattr(timeutil, name)), name)


if __name__ == "__main__":
    unittest.main()
