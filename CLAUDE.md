# First Light

A personal daily newspaper: a static site (`site/`) fed by a scheduled Python pipeline (`pipeline/`). Read `docs/ARCHITECTURE.md` before changing a JSON shape or a module boundary; it is the contract between stages and between pipeline and frontend.

## Hard rules

- Pipeline is Python standard library only and must run on Python 3.9 (`/usr/bin/python3`). No `match`, no `X | Y` annotations evaluated at runtime, no `zip(strict=)`, no third-party imports.
- Frontend is vanilla ES modules. No framework, no bundler, no Node, no CDN at runtime. There is no Node on this machine; JavaScript is tested in headless Chrome.
- One honest User-Agent (`pipeline/core/net.py`). A source that rejects it gets `enabled: false`; do not add per-source browser identities or any workaround for a bot check.
- A failing source or stage must never take the run down, and must show up in `status.json`.
- Never put personal data (watchlists, notes, reading state) in the repo or in `data/public/`.
- Never insert remote text with `innerHTML`.
- `data/` and `dist/` are build products and are git-ignored.

## Commands

- `python3 -m pipeline all` — full update into `data/`, then `dist/`.
- `python3 -m pipeline <stage> -v` — one stage (`fetch`, `markets`, `process`, `papers`, `claude`, `search`, `build`).
- `python3 scripts/serve.py` — serve `dist/` at http://localhost:8080.
- `python3 -m unittest discover -s tests/pipeline -t .` — pipeline tests (no network).
- `python3 tests/e2e/run.py` — browser unit tests and end-to-end checks in headless Chrome.

## Environment notes

- This Mac is behind a corporate TLS-intercepting proxy; a few hosts are blocked locally but reachable from CI. Treat local fetch failures for single hosts as normal.
- Python 3.9 `urllib` does not follow HTTP 308 and cannot parse ISO dates ending in `Z`; `core/net.py` and `core/timeutil.py` handle both. Use them instead of calling `urllib` or `datetime.fromisoformat` directly.

## Voice

The product speaks like a newspaper: Front Page, The Wire, desks, Clippings, Back Issues, Colophon. UI copy is short, literal and never cute about errors.
