# First Light — architecture and contracts

First Light is a personal daily newspaper: a static site built by a scheduled, zero-dependency Python pipeline.
This file is the source of truth for module boundaries and JSON shapes. If code and this file disagree, fix one of them in the same change.

## Principles

1. **No dependencies.** Pipeline: Python standard library only, must run on Python 3.9 (macOS system Python, LibreSSL 2.8.3) and on current Python in CI. Frontend: vanilla ES modules, no framework, no bundler, no Node anywhere. Fonts are self-hosted.
2. **Stages talk through files, not imports.** Each pipeline stage reads JSON from `data/` and writes JSON to `data/`. Stages share only `pipeline/core/`. Any stage can be run, tested and replaced alone.
3. **A failed source never fails a run.** Every fetch is isolated; the previous good output stays in place and the failure is recorded in `status.json`.
4. **Honest client.** One User-Agent everywhere: `Mozilla/5.0 (compatible; FirstLight/1.0; personal news digest)`. A source that rejects it is disabled in config. Never rotate identities, never work around a bot check.
5. **Nothing personal in the repo or the build.** Reading state, saved items, watchlists and notes live only in the browser (`localStorage`, prefix `fl.`). The published site may be public.
6. **Honesty in the UI.** Every number carries an as-of time; stale data says it is stale; ranking shows why.
7. **Only headlines.** We store title, short summary, source, time, link, optional image URL. Never article bodies.

## Layout

```
config/            site.json sources.json lexicon.json markets.json papers.json claude.json
content/claude/    features/*.md  recipes/*.md      hand-authored playbook (front matter + markdown)
pipeline/          python package (python3 -m pipeline <stage>)
  core/            net.py textutil.py timeutil.py jsonio.py config.py log.py
  fetch.py feeds.py adapters/        -> state/items
  lexicon.py                         entity + synonym matching
  process.py cluster.py rank.py threads.py edition.py   -> public/stories, latest, editions
  markets.py                         -> public/markets.json
  papers.py                          -> public/weekend
  claude_updates.py playbook.py      -> public/claude
  searchindex.py                     -> public/search
  build.py                           -> dist/
site/              static frontend, copied verbatim to dist/
data/state/        pipeline working state (not published)
data/public/       published JSON, copied to dist/data/
dist/              the deployable site (site/ + data/public/ as dist/data/)
tests/pipeline/    unittest + fixtures        tests/js/ browser unit tests        tests/e2e/ CDP-driven end-to-end
scripts/           serve.py, local scheduler installer
```

`data/` and `dist/` are git-ignored on `main`. In CI, `data/` is a checkout of the `data` branch, committed back after each run.

## CLI

`python3 -m pipeline <stage> [--data DIR] [--now ISO] [--offline] [-v]`

| Stage | Reads | Writes |
|---|---|---|
| `fetch` | config, network | `state/items/*.json`, `state/source-health.json` |
| `process` | `state/items`, lexicon, `public/markets.json` (optional) | `public/stories/*.json`, `public/latest.json`, `public/editions/*.json`, `state/clusters.json` |
| `markets` | config, network, `public/latest.json` (optional, for movers) | `public/markets.json`, `state/markets-cache.json` |
| `papers` | config, network | `public/weekend/<isoWeek>.json`, `public/weekend/index.json` |
| `claude` | config, network, `content/claude` | `public/claude/updates.json`, `public/claude/playbook.json` |
| `search` | all `public/` content, lexicon | `public/search/*` |
| `build` | `site/`, `data/public/` | `dist/`, `public/manifest.json`, `public/status.json` |
| `all` | — | runs fetch, markets, process, papers (only when due), claude, search, build |

`--now` overrides the clock (tests, backfills). `--offline` skips the network and reuses state. Every stage exits 0 unless its own output could not be written; partial source failure is not an error. Each stage appends its result to `state/run.json` (`{stage, ok, startedAt, durationSec, error, counts}`), which `build` folds into `status.json`.

## core/ API (shared by every stage)

```python
# net.py
fetch(url, *, timeout=20, retries=1, headers=None, cache=None, max_bytes=8_000_000) -> Response
#   Response: .status .body(bytes, already gunzipped) .headers .url(final) .not_modified(bool) .elapsed_ms
#   Follows 301/302/303/307/308. Sends Accept-Encoding: gzip. Raises NetError(kind, status, message) on failure.
#   cache: an HttpCache (state/http-cache.json) enabling ETag / Last-Modified conditional requests.
fetch_json(url, **kw) -> object
polite(host, min_interval_s)        # per-host spacing, thread-safe

# textutil.py
clean_text(html_or_text, limit=None) -> str      # strip tags, unescape (twice), collapse whitespace, trim boilerplate tails
truncate(text, limit) -> str                     # at a word boundary, with an ellipsis
norm_title(title) -> str                         # lowercase, strip " - Publisher" tails and punctuation
canonical_url(url) -> str                        # strip tracking params and fragments, https, no trailing slash
tokenize(text) -> list[str]                      # see "Tokens and stems"
stem(token) -> str
STOPWORDS: frozenset
stable_id(prefix, *parts) -> str                 # prefix + first 10 hex of sha1

# timeutil.py
parse_date(value, default_tz=None) -> datetime | None   # RFC 822, ISO 8601 (Z, fractions), date-only, naive
now_utc() -> datetime        # honours --now
iso(dt) -> "2026-11-11T06:02:00Z"
local_date(dt, tz) -> "2026-11-11"     iso_week(dt, tz) -> "2026-W46"

# jsonio.py
read_json(path, default=None)      write_json(path, obj)   # atomic (tmp + rename), utf-8, compact, sorted where it matters
# config.py
load(name) -> dict                 paths(data_dir) -> Paths(state, public, ...)
```

## Tokens and stems (must be identical in Python and JavaScript)

`tokenize`: NFKD-fold to ASCII, lowercase, split on anything that is not `[a-z0-9]` except keep `&`-joined (`s&p` → `s&p`), `+` suffix (`c++`), and inner `.`/`-` between alphanumerics in tokens that contain a digit (`gpt-5.5`, `3.5`); other hyphenated words split. Drop tokens of length 1 except digits. Stopwords are removed by callers, not by `tokenize`.

`stem` (deliberately light): if length ≤ 3 or the token contains a digit, return as is. Then apply the first matching rule: `ies`→`y` (len > 4); `sses`→`ss`; `xes|ches|shes|zes` drop `es`; `s` drop (not `ss`, `us`, `is`); then, on the result, the first of: `ing` drop (remaining length ≥ 4; undouble a final doubled consonant except `l s z`), `ed` drop (remaining ≥ 4; same undoubling), `ly` drop (remaining ≥ 4). Shared test vectors live in `tests/fixtures/stem-vectors.json` and are asserted by both the Python and the browser test suites.

## Sections

| id | Name | Notes |
|---|---|---|
| `world` | World | top international headlines |
| `india` | India | national headlines |
| `ai` | AI | industry, policy, products |
| `ml` | Machine Learning | research and engineering |
| `llm` | LLMs | models, tooling, evals, agents |
| `labs` | Frontier Labs | OpenAI, Anthropic, Google DeepMind, Meta, xAI, Mistral and others, first-party first |
| `companies` | Companies | Tesla, SpaceX, Nvidia, big tech, chips, space |
| `markets` | Markets | global markets and economy |
| `india-markets` | Dalal Street | NSE/BSE, RBI, SEBI, results, IPOs |
| `science` | Science | science and general technology |

A story has one primary `section` and a list `sections`. Order above is the canonical display order. Claude and papers are separate modules, not sections.

## State: items

`state/items/<local-date>.json` → `{"date", "items": {id: Item}}`; an item is filed under the local date of `publishedAt`. Retained 90 days.

```json
{"id":"i3fa9c2e1b0","url":"https://…","title":"…","summary":"… (≤ 300 chars, may be empty)",
 "source":"bbc-world","sourceName":"BBC News","publishedAt":"2026-11-11T04:10:00Z","firstSeenAt":"2026-11-11T05:00:12Z",
 "image":"https://…|null","section":"world","topics":["tesla"],"feedRank":3,
 "publisher":"Reuters|null","points":412,"comments":200,"alt":[{"title":"…","publisher":"…"}]}
```

`id = stable_id("i", canonical_url)`. `feedRank` is the 0-based position in a curated feed (null for firehoses). `publisher` is set by aggregators (Google News, Techmeme, Zerodha Pulse). `points`/`comments` come from Hacker News. `alt` holds other outlets' headlines when an aggregator item lists them.

`config/sources.json` → `{"sources":[{"id","name","url","kind":"rss|google-news|hn|json:<adapter>|html:<adapter>|sitemap-news","section","topics":[],"tier":1|2|3,"mode":"curated|firehose|official","maxItems":15,"maxAgeHours":48,"enabled":true,"homepage":"…"}]}`.
Tier 1 = wires, papers of record, first-party lab and exchange sources; 2 = established trade and national press; 3 = aggregators, blogs, firehoses.

## Public: stories

`public/stories/<local-date>.json` → `{"date","generatedAt","stories":[Story]}`. A story is one event as covered by one or more outlets. It is filed under the local date of its earliest item. The three most recent day files are rewritten each run; older ones are frozen. Retained 90 days.

```json
{"id":"s8c1d2e3f4a","title":"…","summary":"…","url":"https://… (best outlet's link)","image":"https://…|null",
 "section":"labs","sections":["labs","llm"],"entities":["openai","gpt"],"tickers":["MSFT"],
 "publishedAt":"…Z","updatedAt":"…Z","day":"2026-11-11",
 "sources":[{"id":"openai-news","name":"OpenAI","tier":1,"title":"…","url":"…","publishedAt":"…Z"}],
 "sourceCount":6,
 "score":78.4,
 "signals":{"breadth":0.8,"tier":1.0,"recency":0.9,"velocity":0.4,"attention":0.3,"editorial":0.7},
 "why":["6 outlets","first-party source","rising"],
 "thread":{"id":"t91ab…","day":3,"history":[{"date":"2026-11-09","id":"s…","title":"…"}]}}
```

- Story ids are stable across runs: `state/clusters.json` records item → story assignments; a new item joins an existing story (within 48 h) or starts a new one with `id = stable_id("s", seed item id)`.
- `title`, `summary`, `url`, `image` come from the best member (highest tier, then longest clean summary); `sources` lists every member, best first, one per outlet.
- `sourceCount` counts distinct outlets, including aggregator-reported publishers.
- `signals` are each 0–1; `score` is 0–100. The weights live in `config/site.json` → `ranking`.
- `why` is at most three short human-readable reasons derived from the signals.
- `thread` links a story to earlier days' stories about the same continuing event (entity overlap + title similarity over 14 days); `day` is 1-based; `history` is oldest first, at most 6. Null when the story is new.

`public/latest.json` — the hot set for the Wire and for "since you last visited":
`{"generatedAt","stories":[Story… last 48 h, score-desc, ≤ 500],"trending":[{"entity","name","count","baseline","ratio"}],"sectionCounts":{section:n}}`.

## Public: editions

`public/editions/<local-date>.json` — the frozen morning paper. Written by the first `process` run at or after `site.json → edition.hour` local time (default 06:00) and never rewritten that day (`--force-edition` overrides, for development). `public/editions/index.json` lists dates, newest first, with edition numbers.

```json
{"date":"2026-11-11","number":1,"generatedAt":"…Z","headline":"one-line banner built from the lead",
 "lead":Story,
 "front":[Story,Story,Story,Story],
 "briefs":[Story × ≤10],
 "sections":[{"id":"world","name":"World","stories":[Story × ≤3]}, …],
 "markets":{"asOf":"…Z","quotes":[Quote… the edition strip, ≤ 8]}|null,
 "claude":{"kind":"update|feature","update":ClaudeUpdate|null,"featureId":"…|null"},
 "weekend":{"isoWeek":"2026-W45","title":"…"}|null,
 "stats":{"storiesConsidered":412,"sourcesOk":140,"sourcesTotal":150,"readMinutes":6}}
```

No story appears twice in an edition and no two stories share a thread. `lead` is the highest-scoring story overall with `sourceCount ≥ 2` when one exists. `front` balances sections (at most 2 from one section). Stories are embedded in full so an edition renders without any other file.

## Public: markets

`public/markets.json`:

```json
{"generatedAt":"…Z","stale":false,
 "groups":[{"id":"india","name":"India","quotes":[Quote]},{"id":"us","name":"Wall Street",…},{"id":"world",…},
           {"id":"watch-in","name":"Indian stocks",…},{"id":"watch-us","name":"US stocks",…},
           {"id":"fx","name":"Currencies",…},{"id":"commodities",…},{"id":"crypto",…}],
 "strip":["^NSEI","^BSESN","^GSPC","^IXIC","USDINR=X","BZ=F","GC=F","BTC-USD"],
 "movers":[{"symbol":"TMPV.NS","name":"…","changePct":-4.2,"story":{"id":"s…","title":"…","sourceCount":5}|null}]}
```

`Quote = {"symbol","name","short","kind":"index|stock|fx|commodity|crypto","currency","price","change","changePct","spark":[closes ≤ 32],"asOf":"…Z","exchange","entity":"lexicon id|null","high52","low52","stale":false}`.
Day change uses the provider's `regularMarketChangePercent`. Data is end-of-day-ish and always labelled with `asOf`. `config/markets.json` holds groups and symbols.

## Public: weekend

`public/weekend/<isoWeek>.json` (built on Saturday's first run, or on demand with `papers --force`), `public/weekend/index.json` → `{"weeks":[{"isoWeek","from","to","title"}]}` newest first.

```json
{"isoWeek":"2026-W45","from":"2026-11-02","to":"2026-11-08","generatedAt":"…Z",
 "method":"one paragraph explaining the ranking in plain words",
 "papers":[Paper × 5],"runnersUp":[Paper × ≤10],
 "review":{"stories":[Story × ≤7],"markets":[{"symbol","name","weekPct"}],"claude":[ClaudeUpdate × ≤6]}}
```

`Paper = {"id":"2611.01234","title","authors":["…"],"primary":"cs.AR","categories":[…],"track":"cs|electronics","published":"…Z","abstract","digest":{"gist":"…","problem":"…","method":"…","result":"…"},"signals":{"hfUpvotes":0,"hnPoints":0,"citations":0,"githubStars":0,"mentions":0},"score":0-100,"why":["…"],"links":{"abs","pdf","code","hf","hn"},"rank":1}`. `digest` is extractive (sentences chosen from the abstract), never invented. At least two of the five are `electronics` track.

## Public: claude

`public/claude/updates.json` → `{"generatedAt","status":{"indicator","description"}|null,"entries":[ClaudeUpdate]}` (newest first, 180 days).
`ClaudeUpdate = {"id","date":"2026-11-10","surface":"apps|code|platform|cowork|models|news|learn","kind":"feature|release|article|video","title","summary","url","source","features":["playbook feature ids"]}`.

`public/claude/playbook.json` → `{"generatedAt","surfaces":[{"id","name"}],"jobs":[{"id","name"}],"features":[Feature],"recipes":[Recipe]}`, compiled from `content/claude/`.

Feature file `content/claude/features/<id>.md`:

```
---
id: projects
title: Projects
surface: apps            # apps | code | platform | cowork | integrations
group: Context           # free-text shelf within the surface
status: stable           # new | stable | beta
since: 2024-06           # optional
level: starter           # starter | intermediate | power
payoff: 3                # 1-3
effort: 1                # 1-3
jobs: [writing, research]
tags: [context, knowledge]
summary: One sentence, what it is.
when: One or two sentences, when to reach for it.
replaces: The manual habit this removes.
example_kind: prompt     # prompt | command | config
docs:
  - title: What are projects?
    url: https://support.claude.com/en/articles/9517075-what-are-projects
verified: 2026-11-11
---
## Try it in a minute
1. …
## Example
```text
…copyable prompt or command…
```
## At work
…
## Pitfalls
…
```

Recipe file `content/claude/recipes/<id>.md`: front matter `id, title, job, level, minutes_saved, features: [ids], prerequisites: […], fields: [{name, label, placeholder}], docs, verified`; body sections `## Steps`, `## Prompt` (a fenced template using `{{name}}` placeholders), `## Why it works`.

`Feature`/`Recipe` JSON mirror the front matter plus `html` (body rendered by `playbook.py`'s small markdown renderer: headings, paragraphs, lists, fenced code, inline code, bold, italic, links) and, for features, `example` (first fenced block under `## Example`) and, for recipes, `template`.
Front matter is a strict YAML subset parsed by `playbook.py`: scalars, inline lists `[a, b]`, and one level of `- key: value` object lists.

## Public: search

`public/search/manifest.json` → `{"generatedAt","shards":[{"month":"2026-11","file":"docs-2026-11.json","count":n}],"static":"docs-static.json"}`.
`docs-<month>.json` → array of compact docs: `{"i":id,"k":"story|paper|update","t":title,"s":summary ≤ 220,"c":section or surface,"e":[entity ids],"o":source name,"n":sourceCount,"d":"…Z","u":url,"x":score}`.
`docs-static.json` → the same shape for `feature`, `recipe` and `term` (glossary) docs.
`lexicon.json` → `{"aliases":{"llm":["large language model","foundation model"],…},"entities":{"openai":{"name":"OpenAI","type":"lab","aliases":[…],"related":["chatgpt","gpt"],"ticker":null}},"related":{"stem":[["stem",0.42],…]},"glossary":{"repo rate":"definition"}}`.
`related` is corpus-learned: positive PMI of stem co-occurrence within stories over 90 days, top 6 neighbours for stems with document frequency ≥ 5. The browser builds the inverted index in a Web Worker from the doc shards.

## Public: manifest and status

`public/manifest.json` → `{"schema":1,"builtAt","site":{"name","tagline","timezone"},"sections":[{"id","name"}],"edition":{"date","number"},"editions":[dates],"days":[dates],"weekends":[isoWeeks],"counts":{"stories","sources","sourcesOk"},"nextBuild":"…Z|null"}`.
`public/status.json` → `{"generatedAt","stages":[{"stage","ok","startedAt","durationSec","error","counts"}],"sources":[{"id","name","section","ok","items","newItems","ms","error","lastOkAt"}]}`.

## Frontend

- `site/index.html` is the only page; hash routes. `site/js/app.js` boots: it loads the manifest, sets up the shell and registers the routes.
- Modules are the `MODULES` list in `app.js`: `{id, routes: [[path, view]]}`. Adding a non-news module later means adding one entry there and its views under `site/js/views/`.
- A view is `async (el, params, ctx) => cleanup?`. `el` is a stage element that belongs to this render only. `ctx` carries `alive()`, `shown`, and the only ways a view may touch the shell: `setPage`, `setFrontPlate`, `setViewKeys`. They do nothing once the reader has moved on, so a slow view cannot write over the page that replaced it (`core/router.js`).
- `site/js/shell.js`: masthead, navigation, phone tab bar and desk sheet, footer, theme, global keys and the Cmd/Ctrl+K palette.
- `site/js/core/`: `router.js`, `store.js` (namespaced `localStorage`, with type-checked reads, export and import), `data.js` (fetch and cache `data/*.json` by relative URL, so the site works under any base path), `dom.js` (`h()` element helper), `time.js` (always the paper's timezone), `ui.js` (the shared typesetting: story cards, coverage marks, sparklines, filters).
- `site/js/search/`: `engine.js` (tokenizer and stemmer mirroring `pipeline/core/textutil.py`, BM25 index, query language, widening), `worker.js` (loads shards, answers queries), `client.js`.
- `site/css/bulletin.css` is the design system (see `docs/DESIGN.md`); `site/css/app.css` adds page furniture using its tokens only.
- All remote text is inserted as text nodes; there is no `innerHTML`. Every `href` passes `safeUrl` (http, https or `#/` only). Links out use `rel="noopener noreferrer"`.
- Local state keys: `fl.read`, `fl.saved`, `fl.prefs`, `fl.visit`, `fl.claude`, `fl.search`, `fl.seen`.

Routes: `#/` front page (today's edition) · `#/edition/<date>` · `#/wire` · `#/s/<section>` · `#/story/<id>?d=<day>` · `#/markets` · `#/weekend[/<isoWeek>]` · `#/claude` · `#/claude/updates` · `#/claude/playbook` · `#/claude/feature/<id>` · `#/claude/recipes` · `#/claude/recipe/<id>` · `#/search?q=` · `#/clippings` · `#/archive` · `#/settings` · `#/colophon`.

## Testing

- `python3 -m unittest discover -s tests/pipeline -t .` — parsers against saved fixtures, clustering, ranking, edition rules, search lexicon. No network.
- `python3 tests/e2e/run.py` — starts a local server on `dist/`, drives headless Chrome over the DevTools protocol (stdlib client in `tests/e2e/cdp.py`), runs the browser unit tests in `tests/js/` and the end-to-end scenarios, saves screenshots to `tests/e2e/artifacts/`.
