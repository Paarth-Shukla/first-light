"""Where things live, how config files are read, and the context a stage runs with.

Stages never build paths by hand or read ``config/*.json`` themselves: one
place knows the layout from docs/ARCHITECTURE.md, so moving a directory is a
one-line change and tests can point a whole run at a temporary data directory.
"""

import json
from dataclasses import dataclass
from datetime import datetime, tzinfo
from pathlib import Path
from typing import Any, Dict

from . import net, timeutil

ROOT = Path(__file__).resolve().parents[2]


class ConfigError(ValueError):
    """A config file is missing or malformed. The message names the file and position."""


def load(name):
    """Read ``config/<name>.json`` from the repository and return its object.

    Config is hand-edited, so a typo must be easy to find: errors carry the
    file path plus line and column instead of a bare decoder message.
    """
    stem = name[:-5] if name.endswith(".json") else name
    path = ROOT / "config" / (stem + ".json")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as err:
        raise ConfigError("cannot read %s: %s" % (path, err.strerror or err)) from err
    try:
        value = json.loads(text)
    except ValueError as err:
        where = ""
        if isinstance(err, json.JSONDecodeError):
            where = " at line %d column %d" % (err.lineno, err.colno)
        raise ConfigError("%s is not valid JSON%s: %s" % (path, where, err)) from err
    if not isinstance(value, dict):
        raise ConfigError("%s must contain a JSON object" % path)
    return value


@dataclass(frozen=True)
class Paths:
    """Every directory a stage may touch. All values are absolute ``pathlib.Path``s."""

    root: Path          # repository root
    data: Path          # data/            (--data)
    state: Path         # data/state/      pipeline working state, never published
    public: Path        # data/public/     published JSON, copied to dist/data/
    items_dir: Path     # state/items/
    stories_dir: Path   # public/stories/
    editions_dir: Path  # public/editions/
    weekend_dir: Path   # public/weekend/
    claude_dir: Path    # public/claude/
    search_dir: Path    # public/search/
    dist: Path          # dist/            the deployable site
    site: Path          # site/            static frontend source

    def ensure(self):
        """Create the data directories so a stage can write on a fresh checkout.

        ``dist`` is left alone: only the build stage owns it.
        """
        for directory in (self.state, self.public, self.items_dir, self.stories_dir,
                          self.editions_dir, self.weekend_dir, self.claude_dir, self.search_dir):
            directory.mkdir(parents=True, exist_ok=True)
        return self


def paths(data_dir=None, dist_dir=None):
    """Build the ``Paths`` for a data directory (default ``<repo>/data``).

    ``dist_dir`` exists so tests can build a site somewhere other than the real
    ``dist/``. Nothing is created until ``ensure()`` is called.
    """
    data = Path(data_dir).expanduser().resolve() if data_dir else ROOT / "data"
    state, public = data / "state", data / "public"
    return Paths(
        root=ROOT,
        data=data,
        state=state,
        public=public,
        items_dir=state / "items",
        stories_dir=public / "stories",
        editions_dir=public / "editions",
        weekend_dir=public / "weekend",
        claude_dir=public / "claude",
        search_dir=public / "search",
        dist=Path(dist_dir).expanduser().resolve() if dist_dir else ROOT / "dist",
        site=ROOT / "site",
    )


@dataclass
class Context:
    """What the CLI hands to a stage's ``run(ctx)``."""

    paths: Paths
    now: datetime           # aware UTC; the run's reference time
    offline: bool           # True: do not touch the network, reuse state
    verbose: bool
    force: bool             # --force: rebuild even when not due
    force_edition: bool     # --force-edition: rewrite today's frozen edition
    args: Any               # the argparse namespace (None in tests)
    tz: tzinfo              # the site's timezone (site.json "timezone")
    site: Dict[str, Any]    # config/site.json


def context(data_dir=None, dist_dir=None, force=False, force_edition=False, verbose=False, args=None):
    """Build a stage context the same way the CLI does; handy in stage tests.

    ``now`` and ``offline`` are read from ``timeutil.now_utc()`` and
    ``net.is_offline()`` instead of being parameters, so a context can never
    disagree with the helpers stages call directly. Freeze the clock with
    ``timeutil.set_now(...)`` and cut the network with ``net.set_offline(True)``
    before calling this.
    """
    site = load("site")
    try:
        tz = timeutil.zone(site.get("timezone"))
    except ValueError as err:
        raise ConfigError("config/site.json: %s" % err) from err
    return Context(
        paths=paths(data_dir, dist_dir),
        now=timeutil.now_utc(),
        offline=net.is_offline(),
        verbose=bool(verbose),
        force=bool(force),
        force_edition=bool(force_edition),
        args=args,
        tz=tz,
        site=site,
    )
