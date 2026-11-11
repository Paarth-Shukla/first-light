# First Light

A personal daily newspaper. A scheduled Python pipeline reads public news feeds, groups reports of the same event from different outlets into one story, ranks stories mostly by how widely they were covered, and publishes a static site.

- **Front Page**: one finite edition each morning. Headline size is the number of outlets that carried the story.
- **The Wire**: everything from the last 48 hours, one line each, keyboard-first.
- **Desks**: World, India, AI, Machine Learning, LLMs, Frontier Labs, Companies, Markets, Dalal Street, Science.
- **Markets**: end-of-day indices, a watchlist, and movers joined to the stories that explain them.
- **Weekend Review**: the five most-noticed computer-science and electronics papers of the week, with an extractive digest of each.
- **Claude Desk**: what is new in Claude, a playbook of features with how to use each, and workplace recipes with fill-in prompts.
- **Search**: across everything, widened with names, tickers, synonyms and terms the news itself links, with every widening shown.

No server, no accounts, no tracking, no paid APIs, no dependencies. The pipeline is Python standard library only (3.9 or newer). The site is plain HTML, CSS and ES modules.

## Run it locally

```sh
python3 -m pipeline all        # fetch, rank, set today's edition, build dist/
python3 scripts/serve.py       # http://localhost:8080
```

The first run takes a few minutes. Later runs are faster because feeds that have not changed are skipped.

To update automatically on this Mac every three hours and keep the site served at http://localhost:8080:

```sh
scripts/install-local-schedule.sh               # install two launchd agents
scripts/install-local-schedule.sh --uninstall   # remove them
```

## Publish it with GitHub Pages (free)

1. Create a repository on GitHub and push this one to it (`main` branch).
2. In the repository settings, under **Pages**, set **Source** to **GitHub Actions**.
3. In the **Actions** tab, run **Update and publish** once by hand. After that it runs every three hours.

The workflow keeps the pipeline's state on a separate `data` branch as a single squashed commit, so `main` holds only code. The published site is public on a free GitHub plan; it carries a `noindex` tag and contains nothing personal. GitHub disables scheduled workflows after 60 days without repository activity; running the workflow by hand turns it back on.

## Useful commands

| Command | What it does |
|---|---|
| `python3 -m pipeline <stage> -v` | Run one stage: `fetch`, `markets`, `process`, `papers`, `claude`, `search`, `build` |
| `python3 -m pipeline process --force-edition` | Re-set today's edition (it is otherwise frozen once set) |
| `python3 -m pipeline papers --force` | Build a Weekend Review now instead of waiting for Saturday |
| `python3 -m pipeline all --offline` | Rebuild from stored data without touching the network |
| `python3 -m unittest discover -s tests/pipeline -t .` | Pipeline unit tests (no network) |
| `python3 tests/e2e/run.py` | Browser tests in headless Chrome |

## Make it yours

| File | What it controls |
|---|---|
| `config/sources.json` | The feeds each desk reads, and how much each outlet counts |
| `config/markets.json` | Indices and the stock watchlist |
| `config/lexicon.json` | Names, tickers, synonyms and the glossary used by tagging and search |
| `config/site.json` | Timezone, edition hour, ranking weights, retention |
| `config/papers.json` | arXiv categories and the paper-ranking weights |
| `content/claude/` | The Claude Desk playbook and recipes (Markdown with front matter) |

What you read, clip and try is stored only in your browser. **Settings** in the site exports and imports it.

## How it is put together

`docs/ARCHITECTURE.md` is the contract: the pipeline stages, every JSON shape, and the frontend's structure. `docs/DESIGN.md` records the design system. `docs/research/` holds the live-tested list of sources, including the ones that do not work.

```
config/     what to read and how to rank it
content/    hand-written Claude Desk material
pipeline/   the Python pipeline (python3 -m pipeline)
site/       the static frontend
data/       pipeline state and published JSON (not in git)
dist/       the built site (not in git)
tests/      pipeline unit tests, browser unit tests, end-to-end tests
```

Market figures come from unofficial public endpoints and are end-of-day. They are information, not advice.
