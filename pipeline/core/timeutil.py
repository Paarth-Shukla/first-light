"""Dates and clocks for the pipeline.

Feeds disagree about how to write a date, and Python 3.9 cannot parse several
common forms (``datetime.fromisoformat`` rejects a trailing ``Z`` and odd
fraction lengths; ``email.utils`` changes behaviour between versions). So every
stage parses through ``parse_date`` here, which accepts every shape the source
research found and always answers with an aware UTC datetime or ``None``.

The clock is also owned here: ``now_utc()`` honours ``set_now()`` (the CLI's
``--now``) so tests and backfills are reproducible.
"""

import math
import re
from datetime import date, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

UTC = timezone.utc

_MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)

# Offsets in minutes for the zone abbreviations feeds actually use. "IST" is
# India Standard Time here: this is an Indian reader's paper and the only IST
# feeds found were Indian. Unknown names fall back to default_tz.
_ZONE_MINUTES = {
    "z": 0, "ut": 0, "utc": 0, "gmt": 0,
    "est": -300, "edt": -240, "cst": -360, "cdt": -300,
    "mst": -420, "mdt": -360, "pst": -480, "pdt": -420,
    "akst": -540, "akdt": -480, "hst": -600,
    "bst": 60, "cet": 60, "cest": 120, "eet": 120, "eest": 180,
    "ist": 330, "sgt": 480, "hkt": 480, "jst": 540, "kst": 540,
    "aest": 600, "aedt": 660,
}

_TIME = r"(\d{1,2}):(\d{2})(?::(\d{2})(?:[.,](\d+))?)?(?:\s*([AaPp])\.?[Mm]\.?)?"
_ZONE = r"(?:([+-]\d{2}(?::?\d{2})?)|\(?([A-Za-z]{1,5})\)?)?(?:\s*\([^)]*\))?"

# 2026-11-11 / 2026-11-11T16:06:21+05:30 / 2026-11-11 12:24:39 / ...00.000Z
_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[Tt\s]\s*" + _TIME + r")?\s*" + _ZONE + r"$")

# Wed, 11 Nov 2026 10:14:22 GMT / 10 Nov 26 14:00 EST / 11-Nov-2026 18:04:14 / 11 Nov, 2026 +0530
_DAY_FIRST = re.compile(
    r"^(?:[A-Za-z]{3,9}\.?,?\s+)?(\d{1,2})[\s-]+([A-Za-z]{3,9})\.?,?[\s-]+(\d{4}|\d{2})"
    r"(?:[\s,T]+" + _TIME + r")?\s*" + _ZONE + r"$"
)

# November 6, 2026 / Nov 6, 2026 10:30 AM
_MONTH_FIRST = re.compile(
    r"^(?:[A-Za-z]{3,9}\.?,?\s+)?([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})"
    r"(?:[\s,]+(?:at\s+)?" + _TIME + r")?\s*" + _ZONE + r"$"
)

_EPOCH_MAX = 4102444800  # 2100-01-01: anything later is not a publication time


def zone(tz):
    """Turn a zone name (or tzinfo, or None for UTC) into a tzinfo.

    Config files carry names like "Asia/Kolkata"; accepting both forms keeps
    callers from each writing their own lookup. A bad name is a config error and
    raises ``ValueError`` rather than silently shifting every date.
    """
    if tz is None:
        return UTC
    if isinstance(tz, tzinfo):
        return tz
    try:
        return ZoneInfo(str(tz))
    except (KeyError, ValueError, OSError) as err:
        raise ValueError("unknown timezone %r" % (tz,)) from err


def _month(name):
    """Month number for a full or abbreviated English month name, or None."""
    key = name.lower()
    if len(key) < 3:
        return None
    for number, full in enumerate(_MONTHS, 1):
        if full.startswith(key):
            return number
    return None


def _year(text):
    """Expand two-digit years the way RFC 2822 readers do (69-99 are 1900s)."""
    year = int(text)
    if len(text) == 2:
        return year + (1900 if year > 68 else 2000)
    return year


def _offset(numeric, name):
    """tzinfo for a numeric offset or known abbreviation; None means 'naive'."""
    if numeric:
        digits = numeric[1:].replace(":", "")
        hours, minutes = int(digits[:2]), int(digits[2:] or 0)
        if hours > 14 or minutes > 59:
            raise ValueError("offset out of range")
        total = hours * 60 + minutes
        return timezone(timedelta(minutes=-total if numeric[0] == "-" else total))
    if name and name.lower() in _ZONE_MINUTES:
        return timezone(timedelta(minutes=_ZONE_MINUTES[name.lower()]))
    return None


def _clock(hour, minute, second, fraction, meridiem):
    """(hour, minute, second, microsecond) from regex groups, any of which may be None."""
    hour = int(hour or 0)
    if meridiem:
        if not 1 <= hour <= 12:
            raise ValueError("bad 12-hour time")
        hour = hour % 12 + (12 if meridiem.lower() == "p" else 0)
    micro = int((fraction + "000000")[:6]) if fraction else 0
    # A leap second (":60") is real but datetime cannot hold it.
    return hour, int(minute or 0), min(int(second or 0), 59), micro


def _from_epoch(number):
    """Epoch seconds or milliseconds to a datetime; None when not a plausible time."""
    if not math.isfinite(number) or number < 0:
        return None
    seconds = number / 1000.0 if number >= 1e11 else float(number)
    if seconds > _EPOCH_MAX:
        return None
    return datetime.fromtimestamp(seconds, UTC)


def _from_digits(text):
    """All-digit strings: YYYYMMDD, epoch seconds (9-10 digits) or milliseconds (12-13)."""
    if len(text) == 8:
        return datetime(int(text[:4]), int(text[4:6]), int(text[6:]))
    if len(text) in (9, 10, 12, 13):
        return _from_epoch(int(text))
    return None


def _from_text(text):
    """Parse one of the textual shapes; returns an aware or naive datetime, or None."""
    if text.isdigit():
        return _from_digits(text)
    match = _ISO.match(text)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    else:
        match = _DAY_FIRST.match(text)
        if match:
            day, month, year = int(match.group(1)), _month(match.group(2)), _year(match.group(3))
        else:
            match = _MONTH_FIRST.match(text)
            if not match:
                return None
            month, day, year = _month(match.group(1)), int(match.group(2)), int(match.group(3))
    if month is None:
        return None
    hour, minute, second, micro = _clock(*match.group(4, 5, 6, 7, 8))
    return datetime(year, month, day, hour, minute, second, micro,
                    tzinfo=_offset(match.group(9), match.group(10)))


def parse_date(value, default_tz=None):
    """Parse any date a source gives us into an aware UTC datetime, or None.

    Accepts RFC 822 (numeric offsets, GMT, named zones, two-digit years, no
    seconds), ISO 8601 (``Z``, offsets, fractions of any length), date-only,
    ``11 Nov, 2026 +0530``, ``11-Nov-2026 18:04:14``, ``November 6, 2026``,
    epoch seconds or milliseconds (number or digit string), and datetimes.

    A value with no zone (several Indian regulators publish local wall-clock
    times) is read in ``default_tz`` (a zone name or tzinfo; UTC when omitted).
    None is returned, never an exception, for anything unparseable, because one
    odd item must not cost a whole feed.
    """
    tz = zone(default_tz)
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, date):
            parsed = datetime(value.year, value.month, value.day)
        elif isinstance(value, (int, float)):
            parsed = _from_epoch(value)
        else:
            parsed = _from_text(str(value).strip())
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tz)
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError, OSError):
        return None


_now_override = None


def set_now(value):
    """Freeze the pipeline clock (``--now``), or pass None to use the real clock again.

    Accepts anything ``parse_date`` does; a naive value is taken as UTC.
    """
    global _now_override
    if value is None:
        _now_override = None
        return
    parsed = parse_date(value)
    if parsed is None:
        raise ValueError("not a date: %r" % (value,))
    _now_override = parsed


def now_utc():
    """The current time as an aware UTC datetime; the frozen time when ``set_now`` was used."""
    return _now_override if _now_override is not None else datetime.now(UTC)


def _aware(dt):
    """Treat a naive datetime as UTC so formatting helpers never guess local time."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def iso(dt):
    """Format as ``2026-11-11T06:02:00Z``: the one timestamp shape in every JSON file."""
    return _aware(dt).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_date(dt, tz):
    """The calendar date (``2026-11-11``) of ``dt`` in zone ``tz``; files are keyed by it."""
    return _aware(dt).astimezone(zone(tz)).date().isoformat()


def iso_week(dt, tz):
    """The ISO week (``2026-W46``) of ``dt`` in zone ``tz``; uses the ISO year, not the calendar year."""
    year, week, _ = _aware(dt).astimezone(zone(tz)).isocalendar()
    return "%04d-W%02d" % (year, week)


def hours_between(start, end):
    """Signed hours from ``start`` to ``end`` (negative when ``end`` is earlier)."""
    return (_aware(end) - _aware(start)).total_seconds() / 3600.0
