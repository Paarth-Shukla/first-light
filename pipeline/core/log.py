"""A tiny leveled logger that writes to stderr.

Why not ``logging``: every stage runs as its own short process and we want one
line format everywhere (``HH:MM:SS [stage] level: message``) with no handler
setup to forget. Stdout stays free for data.

    from pipeline.core import log
    log.info("fetched %d of %d sources", ok, total)
    log.warn("%s: %s", source_id, err)

``debug`` lines appear only after ``set_verbose(True)`` (the CLI's ``-v``).
"""

import sys
import threading
import time

_lock = threading.Lock()
_state = {"stage": "pipeline", "verbose": False}


def set_stage(name):
    """Set the prefix shown in every line, so interleaved output stays attributable."""
    _state["stage"] = str(name)


def set_verbose(on):
    """Turn ``debug`` output on or off."""
    _state["verbose"] = bool(on)


def is_verbose():
    """Tell callers whether expensive debug detail is worth computing."""
    return _state["verbose"]


def _format(message, args):
    """Apply %-style arguments, but never let a bad format string lose the message."""
    text = str(message)
    if not args:
        return text
    try:
        return text % args
    except (TypeError, ValueError):
        return "%s %r" % (text, args)


def _emit(level, message, args):
    """Write one whole line under a lock so fetch threads cannot interleave output."""
    line = "%s [%s] %s: %s\n" % (
        time.strftime("%H:%M:%S"),
        _state["stage"],
        level,
        _format(message, args),
    )
    with _lock:
        try:
            sys.stderr.write(line)
            sys.stderr.flush()
        except (OSError, ValueError):
            # stderr closed or broken pipe: logging must never be the reason a run fails.
            pass


def debug(message, *args):
    """Detail that only helps when diagnosing; shown with ``-v``."""
    if _state["verbose"]:
        _emit("debug", message, args)


def info(message, *args):
    """Normal progress."""
    _emit("info", message, args)


def warn(message, *args):
    """Something degraded but the run continues (a failed source, a skipped item)."""
    _emit("warn", message, args)


def error(message, *args):
    """A stage or an output failed."""
    _emit("error", message, args)
