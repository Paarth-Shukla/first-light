"""Atomic JSON files.

Stages talk through files, and a scheduled run can be killed at any moment, so
a reader must never see a half-written file. ``write_json`` writes to a
temporary file in the same directory, fsyncs it, then renames it over the
target; ``read_json`` treats a missing or damaged file as "no data yet" so the
previous run's absence or a truncated file never takes a stage down.
"""

import json
import os
import tempfile
from datetime import date, datetime

from . import log, timeutil


def _default(value):
    """Serialise the few non-JSON types stages hand us, deterministically."""
    if isinstance(value, datetime):
        return timeutil.iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError("cannot write %s to JSON" % type(value).__name__)


def dumps(obj, sort_keys=False):
    """Compact UTF-8 JSON text, exactly as ``write_json`` stores it.

    NaN and Infinity are refused (``ValueError``) because the browser's
    ``JSON.parse`` rejects them; better a failed stage than an unreadable site.
    """
    return json.dumps(
        obj,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=sort_keys,
        allow_nan=False,
        default=_default,
    )


def read_json(path, default=None):
    """Load a JSON file, or return ``default`` when it is missing, unreadable or corrupt.

    Corruption is logged (it means a previous run was interrupted or something
    else wrote the file) but not raised: the caller rebuilds from ``default``.
    """
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (FileNotFoundError, NotADirectoryError):
        return default
    except ValueError as err:  # JSONDecodeError and UnicodeDecodeError
        log.warn("corrupt JSON in %s (%s); using default", path, err)
        return default
    except OSError as err:
        log.error("cannot read %s (%s); using default", path, err)
        return default


def write_json(path, obj, sort_keys=False):
    """Write ``obj`` to ``path`` atomically, creating parent directories.

    ``sort_keys=True`` is for id-keyed maps where a stable key order keeps the
    data branch's diffs small. Raises ``OSError`` if the file cannot be written
    and ``TypeError``/``ValueError`` if ``obj`` is not serialisable; the target
    is untouched in both cases.
    """
    path = os.fspath(path)
    text = dumps(obj, sort_keys=sort_keys)
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    handle, temp_path = tempfile.mkstemp(
        dir=directory, prefix="." + os.path.basename(path) + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "wb") as out:
            # "replace" turns a lone surrogate (half an emoji from a sloppy API) into "?"
            # instead of failing the whole file over one character.
            out.write(text.encode("utf-8", "replace"))
            out.write(b"\n")
            out.flush()
            os.fsync(out.fileno())
        # mkstemp creates 0600; published files must be readable by the web server and CI.
        os.chmod(temp_path, 0o644)
        os.replace(temp_path, path)
    except BaseException:
        _discard(temp_path)
        raise


def _discard(temp_path):
    """Remove a leftover temp file; failing to clean up must not mask the real error."""
    try:
        os.unlink(temp_path)
    except FileNotFoundError:
        return
    except OSError as err:
        log.warn("could not remove temp file %s (%s)", temp_path, err)
