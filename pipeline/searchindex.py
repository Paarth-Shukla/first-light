"""Search stage: compact document shards, a static shard and the search lexicon for the browser.

The browser downloads ``public/search/*`` and builds its inverted index in a Web
Worker, so this stage only has to emit small, predictable files:

* ``docs-<YYYY-MM>.json`` – stories, weekend papers and Claude updates, bucketed
  by the month of the doc's date in the site timezone, so a browser can fetch
  only the months it needs.
* ``docs-static.json`` – playbook features, recipes and glossary terms.
* ``lexicon.json`` – the hand-made lexicon (aliases, entities, glossary) plus
  ``related``: neighbours learned from the story corpus, keyed by
  ``textutil.stem`` so the JavaScript twin of ``tokenize``/``stem`` finds them.
* ``manifest.json`` – what was written, with counts and byte sizes. It is
  written last, so it never names a shard that does not exist yet.

How ``related`` is learned (the constants below were tuned on live data):
each story is a set of stems from its title and summary, plus one term per
lexicon entity it carries: the entity's name when that is one word ("Nvidia"
is just ``nvidia``), otherwise ``@<entity-id>`` ("Google DeepMind" and
"DeepMind" are both ``@google-deepmind``). For terms in at least ``MIN_DF``
stories, every pair seen together in at least ``MIN_PAIR`` stories is scored
with positive PMI under context-distribution smoothing (the context's
frequency is raised to ``ALPHA``, which takes probability from frequent
contexts and gives it to rare ones), normalised to 0..1 the way NPMI is, and
shrunk by ``count / (count + SHRINK)`` so that a pair seen 3 times needs a far
stronger association than a pair seen 30 times. A neighbour that is only an
inflection or sub-token of the term or of a better neighbour ("chipmaker"
under "chip"), or another way of spelling the same entity ("reserve" and
"@federal-reserve" under "fed"), is dropped.
"""

import math
import os
import re
import urllib.parse
from collections import Counter
from datetime import timedelta
from itertools import combinations

from . import lexicon
from .core import config, jsonio, log, textutil, timeutil

SUMMARY_LIMIT = 220

MIN_TOKEN_LEN = 3       # shorter tokens ("ai", "us") are too ambiguous to learn from
MIN_DF = 5              # a stem needs this many stories before it gets neighbours
MIN_PAIR = 3            # and a pair this many stories together before it counts
VOCAB_CAP = 4000        # most frequent eligible stems kept
TOP_NEIGHBOURS = 6
ALPHA = 0.9             # context-distribution smoothing exponent; 0.75 (word2vec's) let filler words in
SHRINK = 4.0            # count-based shrinkage: weight *= n / (n + SHRINK)
MIN_WEIGHT = 0.05       # weaker links are noise a search box should not act on
SPELLS = 0.5            # a name word spells its entity when at least this share of its stories carry it
LEXICON_BUDGET = 400_000  # bytes; the least frequent terms' neighbours are dropped to fit

# News filler: words that appear across every desk and so attach weakly to everything
# ("year", "two", "show", "today"). They stay searchable; they are only kept out of
# ``related``, where tuning showed them filling the last slots of most lists.
GENERIC = frozenset(textutil.stem(word) for word in """
one two three four five six seven eight nine ten hundred thousand million billion crore lakh
first second third last next latest recent today tonight yesterday tomorrow day days week weeks month
months year years time times date ago early late soon long ahead
monday tuesday wednesday thursday friday saturday sunday january february march april june july
august september october november december jan feb mar apr jun jul aug sep sept oct nov dec
get gets got make makes made making take takes took taken see sees seen look looks find finds found
show shows turn turns use uses used using set sets run runs start starts end ends call calls want
wants need needs come comes came go goes going give gives bring brings keep keeps put puts help
helps follow follows remain remains reach reaches face faces lead leads hold holds move moves
like way thing things lot many key real top big small large largest level people man men woman
women part place point percent news story stories post posts accord according despite know
near available begin begins exist existing include includes including introduce introduces company
companies firm firms announce announces announced announcing introduced introducing began beginning
""".split())

ENTITY_PREFIX = "@"
STATIC_FILE = "docs-static.json"
LEXICON_FILE = "lexicon.json"
MANIFEST_FILE = "manifest.json"

_DAY_FILE = re.compile(r"\d{4}-\d{2}-\d{2}\.json\Z")
_WEEK_FILE = re.compile(r"\d{4}-W\d{2}\.json\Z")
_SHARD_FILE = re.compile(r"docs-\d{4}-\d{2}\.json\Z")
_ONLY_DIGITS = re.compile(r"[0-9.,\-]+\Z")
_SUBTOKEN_SPLIT = re.compile(r"[-.&+]")
_WHY_IT_WORKS = re.compile(r"<h2>\s*Why it works\s*</h2>(.*?)(?=<h2|\Z)", re.S | re.I)


class Report:
    """Problems met while reading inputs: logged as they happen and counted for run.json."""

    def __init__(self):
        self.skipped_files = []
        self.invalid_docs = 0

    def skip_file(self, path, why):
        log.warn("skipping %s: %s", path, why)
        self.skipped_files.append(os.path.basename(str(path)))

    def invalid(self, where, why, count=1):
        log.debug("invalid doc in %s: %s", where, why)
        self.invalid_docs += count


# ---------------------------------------------------------------- reading inputs


def _read_object(path, key, report):
    """Read a JSON file whose ``key`` must be a list; None (and a report entry) when it is not.

    A missing file is not a problem (every input is optional), so it is not reported.
    """
    if not os.path.exists(str(path)):
        return None
    data = jsonio.read_json(path)
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        report.skip_file(path, "unreadable, or no %r list" % key)
        return None
    return data


def story_days(stories_dir, today, keep_days, report):
    """``[(day, [story])]`` oldest first, for day files in the retention window ending ``today``.

    Files dated after ``today`` are ignored so that ``--now`` reproduces what the
    index looked like on that day.
    """
    first = (today - timedelta(days=keep_days - 1)).isoformat()
    last = today.isoformat()
    days = []
    for name in sorted(_list(stories_dir)):
        if not _DAY_FILE.match(name) or not first <= name[:10] <= last:
            continue
        data = _read_object(os.path.join(str(stories_dir), name), "stories", report)
        if data is not None:
            days.append((name[:10], data["stories"]))
    return days


def latest_stories(days, report):
    """One story per id, keeping the copy from the newest day file (then the latest ``updatedAt``)."""
    chosen = {}
    for day, stories in days:
        for story in stories:
            if not _valid_story(story, day, report):
                continue
            key = (day, story.get("updatedAt") or "")
            held = chosen.get(story["id"])
            if held is None or key >= held[0]:
                chosen[story["id"]] = (key, story)
    return [chosen[story_id][1] for story_id in sorted(chosen)]


def _named(entry):
    """True for a dict with a non-empty string ``id`` and ``title``: the least a doc needs."""
    return (isinstance(entry, dict) and isinstance(entry.get("id"), str) and isinstance(entry.get("title"), str)
            and bool(entry["id"]) and bool(entry["title"].strip()))


def _valid_story(story, day, report):
    """A story needs an id, a title and a parseable date to be indexed."""
    if not _named(story):
        report.invalid("stories/%s" % day, "missing id or title")
        return False
    if _date_of(story.get("updatedAt") or story.get("publishedAt")) is None:
        report.invalid("stories/%s" % day, "no usable date on %s" % story["id"])
        return False
    return True


def weekend_papers(weekend_dir, report):
    """Every pick and runner-up, one per arXiv id; the newest week's copy wins."""
    chosen = {}
    for name in sorted(_list(weekend_dir)):
        if not _WEEK_FILE.match(name):
            continue
        data = _read_object(os.path.join(str(weekend_dir), name), "papers", report)
        if data is None:
            continue
        for paper in data["papers"] + list(data.get("runnersUp") or []):
            if not _named(paper):
                report.invalid(name, "paper without id or title")
                continue
            chosen[paper["id"]] = paper
    return [chosen[paper_id] for paper_id in sorted(chosen)]


def _list(directory):
    """Directory entries, or nothing when the directory does not exist yet."""
    try:
        return os.listdir(str(directory))
    except FileNotFoundError:
        return []


def _date_of(value):
    """An aware datetime from an ISO timestamp or a date-only string, else None."""
    if not isinstance(value, str) or not value:
        return None
    return timeutil.parse_date(value)


# ---------------------------------------------------------------- compact docs


def _doc(doc_id, kind, title, summary, category, entities, source, count, date, url, score):
    """The one compact doc shape from docs/ARCHITECTURE.md; every key is always present."""
    return {
        "i": doc_id, "k": kind, "t": textutil.clean_text(title),
        "s": textutil.truncate(textutil.clean_text(summary), SUMMARY_LIMIT),
        "c": category, "e": list(entities or []), "o": source, "n": count,
        "d": date, "u": url, "x": score,
    }


def story_doc(story):
    """A story as a search doc; the best outlet is the first listed source."""
    sources = story.get("sources") or []
    best = sources[0].get("name") if sources and isinstance(sources[0], dict) else None
    when = _date_of(story.get("updatedAt") or story.get("publishedAt"))
    return _doc(story["id"], "story", story["title"], story.get("summary"), story.get("section"),
                story.get("entities"), best, story.get("sourceCount"), timeutil.iso(when),
                story.get("url"), story.get("score"))


def paper_doc(paper, match):
    """A weekend paper; the extractive gist reads better than the abstract's opening line."""
    gist = (paper.get("digest") or {}).get("gist") or paper.get("abstract") or ""
    when = _date_of(paper.get("published"))
    links = paper.get("links") or {}
    return _doc(paper["id"], "paper", paper["title"], gist, "weekend",
                match(paper["title"] + ". " + gist), paper.get("primary"), None,
                timeutil.iso(when) if when else None, links.get("abs"), paper.get("score"))


def update_doc(entry, tz, source_names, match):
    """A Claude update. Its date is a calendar day, read as midnight in the site timezone."""
    when = timeutil.parse_date(entry.get("date"), default_tz=tz)
    return _doc(entry["id"], "update", entry["title"], entry.get("summary"), entry.get("surface"),
                match(entry["title"] + ". " + (entry.get("summary") or "")),
                source_names.get(entry.get("source"), entry.get("source")), None,
                timeutil.iso(when), entry.get("url"), None)


def feature_doc(feature, match):
    """A playbook feature: what it is, then when to reach for it."""
    summary = " ".join(part for part in (feature.get("summary"), feature.get("when")) if part)
    return _doc("feature:" + feature["id"], "feature", feature["title"], summary, feature.get("surface"),
                match(feature["title"] + ". " + summary), None, None, None,
                "#/claude/feature/" + feature["id"], None)


def recipe_doc(recipe, match):
    """A recipe; "Why it works" is the closest thing it has to a summary, else its prompt."""
    found = _WHY_IT_WORKS.search(recipe.get("html") or "")
    summary = textutil.clean_text(found.group(1)) if found else recipe.get("template") or ""
    return _doc("recipe:" + recipe["id"], "recipe", recipe["title"], summary, recipe.get("job"),
                match(recipe["title"] + ". " + summary), None, None, None,
                "#/claude/recipe/" + recipe["id"], None)


def term_doc(term, definition):
    """A glossary term; following it runs a search for the term itself."""
    return _doc("term:" + term.lower(), "term", term, definition, "glossary", [], None, None, None,
                "#/search?q=" + urllib.parse.quote(term, safe=""), None)


def dated_docs(stories, papers, updates, tz, source_names, match, report):
    """Every doc that belongs in a monthly shard. Papers and updates without a usable date are skipped."""
    docs = [story_doc(story) for story in stories]
    for paper in papers:
        doc = paper_doc(paper, match)
        if doc["d"] is None:
            report.invalid("weekend", "paper %s has no published date" % paper["id"])
            continue
        docs.append(doc)
    seen = set()
    for entry in updates:
        if not _named(entry):
            report.invalid("claude/updates", "entry without id or title")
            continue
        if entry["id"] in seen or timeutil.parse_date(entry.get("date"), default_tz=tz) is None:
            report.invalid("claude/updates", "duplicate or undated entry %s" % entry["id"])
            continue
        seen.add(entry["id"])
        docs.append(update_doc(entry, tz, source_names, match))
    return docs


def static_docs(playbook, glossary, match, report):
    """Features, recipes and glossary terms, in that order, each sorted by id."""
    docs = []
    for key, build in (("features", feature_doc), ("recipes", recipe_doc)):
        entries = (playbook or {}).get(key) or []
        valid = [entry for entry in entries if _named(entry)]
        missing = len(entries) - len(valid)
        if missing:
            report.invalid("claude/playbook", "%d %s without id or title" % (missing, key), missing)
        docs.extend(build(entry, match) for entry in sorted(valid, key=lambda entry: entry["id"]))
    docs.extend(term_doc(term, glossary[term]) for term in sorted(glossary))
    return docs


def shard(docs, tz):
    """``{"YYYY-MM": [doc]}`` by the doc's date in the site timezone; each shard newest first."""
    months = {}
    for doc in docs:
        month = timeutil.local_date(timeutil.parse_date(doc["d"]), tz)[:7]
        months.setdefault(month, []).append(doc)
    for month_docs in months.values():
        month_docs.sort(key=lambda doc: doc["i"])
        month_docs.sort(key=lambda doc: doc["d"], reverse=True)
    return months


# ---------------------------------------------------------------- related terms


def entity_terms(entities):
    """``({entity id: term}, {term: {entity ids it spells}})`` from the exported lexicon.

    A one-word name ("Nvidia") is its own stem, so every alias of the entity
    counts as that word. Any other name ("Google DeepMind", or "AI", too short
    to learn from) becomes ``@id``, one token for every way of writing it.
    The second map ("families") records, for each such entity, the ``@id`` and
    the stems of its id, name and one-word aliases: the candidates for
    ``spelling`` to confirm against the corpus.
    """
    terms, families = {}, {}
    for entity_id, info in entities.items():
        name = info.get("name") or ""
        words = _stems(name)
        if len(textutil.tokenize(name)) == 1 and len(words) == 1:
            terms[entity_id] = words[0]
            continue
        terms[entity_id] = ENTITY_PREFIX + entity_id
        aliases = " ".join(a for a in info.get("aliases") or [] if len(textutil.tokenize(a)) == 1)
        spelled = set(words + _stems(entity_id.replace("-", " ") + " " + aliases))
        for term in spelled | {terms[entity_id]}:
            families.setdefault(term, set()).add(entity_id)
    return terms, families


def _pairs(text):
    """``(token, stem)`` for each eligible token of ``text``: no stopwords, short tokens or bare numbers."""
    for token in textutil.tokenize(text):
        if len(token) < MIN_TOKEN_LEN or token in textutil.STOPWORDS or _ONLY_DIGITS.match(token):
            continue
        stemmed = textutil.stem(token)
        if len(stemmed) >= MIN_TOKEN_LEN and stemmed not in textutil.STOPWORDS and stemmed not in GENERIC:
            yield token, stemmed


def _stems(text):
    """Eligible stems of ``text`` in order."""
    return [stemmed for _token, stemmed in _pairs(text)]


def _story_text(story):
    """The words of a story that count: its title and summary."""
    return "%s %s" % (story.get("title") or "", story.get("summary") or "")


def story_terms(story, entity_term):
    """The set of terms a story contributes to co-occurrence counts.

    Entities the lexicon does not know (an old story, a renamed id) add nothing.
    """
    terms = set(_stems(_story_text(story)))
    terms.update(entity_term[e] for e in story.get("entities") or [] if e in entity_term)
    return terms


def _is_variant(a, b):
    """True when one stem is an inflection, compound or sub-token of the other ("chip"/"chipmaker")."""
    if a.startswith(ENTITY_PREFIX) or b.startswith(ENTITY_PREFIX):
        return False
    short, long_ = sorted((a, b), key=len)
    if long_.startswith(short) or short in _SUBTOKEN_SPLIT.split(long_):
        return True
    shared = len(os.path.commonprefix((a, b)))
    return (shared >= 5 and shared >= 0.75 * len(short)) or (shared >= 4 and shared >= 0.8 * len(short))


def spelling(families, df, pairs):
    """The words that spell an entity: those whose stories mostly carry it (``{word: {entity ids}}``).

    Two such words co-occur only because they are one name, so neither is
    offered as the other's neighbour: no "jensen" under "huang". But "india" is
    also a word of "State Bank of India" and mostly appears without it, so it
    stays free to be a neighbour of "bank".
    """
    confirmed = {}
    for term, entity_ids in families.items():
        if term.startswith(ENTITY_PREFIX) or not df[term]:
            continue
        kept = {entity_id for entity_id in entity_ids
                if pairs[tuple(sorted((term, ENTITY_PREFIX + entity_id)))] >= SPELLS * df[term]}
        if kept:
            confirmed[term] = kept
    return confirmed


def _redundant(term, candidate, families, spelled):
    """A neighbour that adds nothing a reader would not already have from ``term``.

    An entity and any word of its name ("@federal-reserve" and "fed") always
    are; two plain words only when both spell one entity (see ``spelling``).
    """
    if _is_variant(term, candidate):
        return True
    names = families if ENTITY_PREFIX in (term[:1], candidate[:1]) else spelled
    return not names.get(term, set()).isdisjoint(names.get(candidate, ()))


def count_terms(term_sets, vocab_cap):
    """Document frequencies, the capped vocabulary and pair counts within it."""
    df = Counter()
    for terms in term_sets:
        df.update(terms)
    eligible = sorted((t for t, n in df.items() if n >= MIN_DF), key=lambda t: (-df[t], t))
    vocab = set(eligible[:vocab_cap])
    pairs = Counter()
    for terms in term_sets:
        pairs.update(combinations(sorted(terms & vocab), 2))
    return df, vocab, pairs


def _scores(df, vocab, pairs, docs):
    """``{term: [(weight, neighbour)]}`` for every pair seen at least ``MIN_PAIR`` times.

    The smoothed context probability is ``df**ALPHA`` rescaled to the same total
    mass as ``df / docs``, so ``ALPHA = 1`` is plain PMI and a smaller ALPHA only
    moves probability from frequent contexts to rare ones; it never shifts every
    score up (a story holds many terms, so ``df / docs`` sums to far more than 1).
    """
    if not vocab:
        return {}
    scale = sum(df[t] for t in vocab) / sum(df[t] ** ALPHA for t in vocab)
    scored = {}
    for (a, b), together in pairs.items():
        if together < MIN_PAIR:
            continue
        joint = together / docs
        if joint >= 1.0:
            continue  # in every story: no information either way
        for term, other in ((a, b), (b, a)):
            pmi = math.log(joint / ((df[term] / docs) * (df[other] ** ALPHA * scale / docs)))
            if pmi <= 0:
                continue
            weight = min(1.0, pmi / -math.log(joint)) * together / (together + SHRINK)
            scored.setdefault(term, []).append((weight, other))
    return scored


def learn_related(term_sets, families, vocab_cap=VOCAB_CAP, top=TOP_NEIGHBOURS):
    """``({term: [[neighbour, weight]]}, df)``: the corpus-learned half of ``lexicon.json``.

    Weights are rounded to two decimals (enough for ranking expansions, and half
    the bytes); neighbours below ``MIN_WEIGHT`` are not worth sending.
    """
    df, vocab, pairs = count_terms(term_sets, vocab_cap)
    spelled = spelling(families, df, pairs)
    related = {}
    for term, candidates in _scores(df, vocab, pairs, len(term_sets)).items():
        candidates.sort(key=lambda pair: (-pair[0], pair[1]))
        chosen = []
        for weight, other in candidates:
            if weight < MIN_WEIGHT:
                break  # candidates are sorted: the rest are weaker still
            if _redundant(term, other, families, spelled):
                continue
            if any(_redundant(kept, other, families, spelled) for kept, _ in chosen):
                continue
            chosen.append((other, round(weight, 2)))
            if len(chosen) == top:
                break
        if chosen:
            related[term] = [list(pair) for pair in chosen]
    return related, df


def surface_words(stories, related):
    """``{stem: the word readers saw most}`` for stems in ``related`` never seen as a word themselves.

    Stems such as "releas" are right for matching but wrong for a "related
    searches" chip, so the browser shows this word instead. Ties go to the
    alphabetically first word so the file is stable.
    """
    wanted = _mentioned(related)
    seen = {}
    for story in stories:
        for token, stemmed in _pairs(_story_text(story)):
            if stemmed in wanted:
                seen.setdefault(stemmed, Counter())[token] += 1
    words = {}
    for stemmed in sorted(seen):
        if stemmed not in seen[stemmed]:
            words[stemmed] = min(seen[stemmed], key=lambda token: (-seen[stemmed][token], token))
    return words


def fit_related(base, related, df, budget):
    """Drop the least frequent terms' neighbour lists until the lexicon file fits ``budget`` bytes.

    Returns ``(related, dropped)``; keys are sorted so the file is byte-stable.
    """
    # The empty file's size, less the comma the first entry will not need.
    size = len(jsonio.dumps(dict(base, related={})).encode("utf-8")) + 1 - 1
    kept, dropped = {}, 0
    for term in sorted(related, key=lambda t: (-df[t], t)):
        cost = len(jsonio.dumps({term: related[term]}).encode("utf-8")) - 1  # minus braces, plus comma
        if size + cost > budget:
            dropped += 1
            continue
        kept[term] = related[term]
        size += cost
    return {term: kept[term] for term in sorted(kept)}, dropped


def _mentioned(related):
    """Every term ``related`` uses, as a key or as a neighbour."""
    terms = set(related)
    for neighbours in related.values():
        terms.update(other for other, _weight in neighbours)
    return terms


# ---------------------------------------------------------------- writing


def _write(directory, name, obj):
    """Write one output file and return its size in bytes."""
    path = os.path.join(str(directory), name)
    jsonio.write_json(path, obj)
    return os.path.getsize(path)


def remove_stale_shards(directory, keep):
    """Delete ``docs-YYYY-MM.json`` files the new manifest no longer lists; returns how many."""
    removed = 0
    for name in sorted(_list(directory)):
        if _SHARD_FILE.match(name) and name not in keep:
            try:
                os.unlink(os.path.join(str(directory), name))
                removed += 1
            except OSError as err:
                log.warn("could not remove stale shard %s: %s", name, err)
    return removed


def write_index(search_dir, now, months, static, lexicon_doc):
    """Write shards, the static shard, the lexicon (unless None) and, last, the manifest."""
    shards = []
    for month in sorted(months, reverse=True):
        name = "docs-%s.json" % month
        size = _write(search_dir, name, months[month])
        shards.append({"month": month, "file": name, "count": len(months[month]), "bytes": size})
    manifest = {
        "generatedAt": timeutil.iso(now),
        "shards": shards,
        "static": STATIC_FILE,
        "staticCount": len(static),
        "staticBytes": _write(search_dir, STATIC_FILE, static),
        "lexicon": LEXICON_FILE,
        "lexiconBytes": None,
    }
    if lexicon_doc is not None:
        manifest["lexiconBytes"] = _write(search_dir, LEXICON_FILE, lexicon_doc)
    elif os.path.exists(os.path.join(str(search_dir), LEXICON_FILE)):
        manifest["lexiconBytes"] = os.path.getsize(os.path.join(str(search_dir), LEXICON_FILE))
    _write(search_dir, MANIFEST_FILE, manifest)
    removed = remove_stale_shards(search_dir, {entry["file"] for entry in shards})
    return manifest, removed


# ---------------------------------------------------------------- stage


def _load_lexicon():
    """The compiled lexicon, or ``(None, message)`` when config/lexicon.json is broken."""
    try:
        return lexicon.load(), None
    except config.ConfigError as err:
        log.error("lexicon unavailable, entity tags and lexicon.json skipped: %s", err)
        return None, str(err)


def _claude_source_names():
    """``{source id: display name}`` for Claude updates; ids are shown if config/claude.json is broken."""
    try:
        sources = config.load("claude").get("sources") or []
    except config.ConfigError as err:
        log.warn("config/claude.json unreadable, update sources shown by id: %s", err)
        return {}
    return {source["id"]: source["name"] for source in sources
            if isinstance(source, dict) and source.get("id") and source.get("name")}


def build(paths, tz, now, keep_days, lex, source_names):
    """Read every public input, write ``public/search/*`` and return counts for run.json.

    ``lex`` is a ``lexicon.Lexicon`` or None; without it docs carry no matched
    entities and ``lexicon.json`` is left as it was.
    """
    report = Report()
    exported = lex.export_public() if lex is not None else {"aliases": {}, "entities": {}, "glossary": {}}
    match = lex.match_entities if lex is not None else (lambda text: [])
    tz = timeutil.zone(tz)
    days = story_days(paths.stories_dir, now.astimezone(tz).date(), keep_days, report)
    stories = latest_stories(days, report)
    papers = weekend_papers(paths.weekend_dir, report)
    updates_file = _read_object(paths.claude_dir / "updates.json", "entries", report)
    playbook = _read_object(paths.claude_dir / "playbook.json", "features", report)

    months = shard(dated_docs(stories, papers, (updates_file or {}).get("entries", []), tz,
                              source_names, match, report), tz)
    static = static_docs(playbook, exported["glossary"], match, report)

    entity_term, families = entity_terms(exported["entities"])
    related, df = learn_related([story_terms(story, entity_term) for story in stories], families)
    words = surface_words(stories, related)
    related, trimmed = fit_related(dict(exported, words=words), related, df, LEXICON_BUDGET)
    if trimmed:
        log.warn("lexicon.json over %d bytes: dropped neighbours of %d rare terms", LEXICON_BUDGET, trimmed)
    words = {stemmed: word for stemmed, word in words.items() if stemmed in _mentioned(related)}
    lexicon_doc = dict(exported, related=related, words=words) if lex is not None else None

    if report.invalid_docs:
        log.warn("%d docs skipped as invalid (-v lists them)", report.invalid_docs)
    manifest, removed = write_index(paths.search_dir, now, months, static, lexicon_doc)
    kinds = Counter(doc["k"] for docs in months.values() for doc in docs)
    kinds.update(doc["k"] for doc in static)
    log.info("%d day files, %d stories, %d papers, %d updates, %d static docs in %d shards; %d related terms",
             len(days), kinds["story"], kinds["paper"], kinds["update"], len(static), len(months), len(related))
    return {
        "dayFiles": len(days), "stories": kinds["story"], "papers": kinds["paper"],
        "updates": kinds["update"], "features": kinds["feature"], "recipes": kinds["recipe"],
        "terms": kinds["term"], "shards": len(months), "staleShardsRemoved": removed,
        "relatedTerms": len(related), "relatedTrimmed": trimmed,
        "shardBytes": sum(entry["bytes"] for entry in manifest["shards"]),
        "lexiconBytes": manifest["lexiconBytes"],
        "skippedFiles": report.skipped_files, "invalidDocs": report.invalid_docs,
    }


def run(ctx):
    """Stage entry point. A broken lexicon still gets the docs written, then fails the stage."""
    lex, lexicon_error = _load_lexicon()
    counts = build(ctx.paths, ctx.tz, ctx.now, int(ctx.site.get("retentionDays", 90)), lex,
                   _claude_source_names())
    if lexicon_error:
        raise RuntimeError("lexicon unavailable; docs written, lexicon.json kept from the last run: %s"
                           % lexicon_error)
    return counts
