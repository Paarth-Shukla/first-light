"""Entity, section and synonym knowledge: tagging and search expansion without a language model.

``config/lexicon.json`` is hand-edited and has four parts: ``entities`` (companies,
labs, people, products, indices, places, topics), ``synonyms`` (groups of
interchangeable search terms), ``sectionRules`` (phrases that file a story under a
section) and ``glossary``. This module validates it once, compiles it into token
tries and answers the questions other stages ask:

    match_entities(text)                      -> ["openai", "chatgpt"]
    sections_for(text, home, entity_ids)      -> ("labs", ["labs", "ai", "llm"])
    expand_term("llms")                       -> ["llms", "llm", "large language model", ...]
    entity(id), ticker_map(), export_public()

Matching rules (the "about" key in the config repeats them for editors):

* Text and aliases are split into the same word tokens (runs of letters and
  digits; ``&`` and ``+`` are tokens of their own), so a match can never start or
  end inside a word and "S&P 500" equals "S & P 500".
* Matching ignores case and accents, except that an all-capitals alias ("WHO",
  "US", "AMD") and any alias with a capital on an ambiguous entity must match
  exactly: "the WHO" is not "who", "Apple" is not "apple".
* A multi-word alias matches only across a space, a hyphen, a slash, an
  apostrophe, a dot with no space after it ("U.S.", "GPT-4o", "RISC-V") or a dot
  after an initial or short abbreviation ("C.C. Wei", "Dr. Reddy's"); never
  across a comma or a sentence end.
* A final "s" on the last word reads as a plural ("GPUs", "LLMs", "benchmarks"),
  except on the capitalised names of ambiguous entities ("Apples" are fruit).
  Possessives fall out of tokenising: "Tesla's" is "Tesla" followed by "s".
* The longest alias wins: "Bank Nifty" is not also "Nifty", "Google DeepMind"
  is not also "Google".
* A *gated* alias (a bare common word such as "Apple", "Gemini", "Claude",
  "Fed") counts only when the same text also has one of the entity's context
  words, an ungated mention of one of its related entities, or, for models and
  products, a version right after the name ("Llama 4", "Gemini 2.5", "Sora 2";
  never a year: "Gemini 2025 horoscope" stays a star sign).

Section rules: a strong phrase (or an entity whose ``sections`` lists the
section) files the story there; weak phrases count when two different ones
match, or when one matches and the source's home section is listed in the
rule's ``adjacent``. Words that are only part of a longer entity name are not
phrase evidence ("India" in "The Times of India"). The home section stays
primary unless it is a generic desk (world, india, science) and a specific desk
has more strong signals than the home desk, not counting mentions of people and
places.
"""

import copy
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from .core import config

ENTITY_TYPES = frozenset((
    "company", "lab", "person", "product", "model", "index", "org",
    "regulator", "agency", "topic", "place",
))
GENERIC_HOMES = frozenset(("world", "india", "science"))
# A gated model or product name followed by a version ("Llama 4") needs no other context.
VERSIONED_TYPES = frozenset(("model", "product"))
# Mentions of these add a story to their desks but never move its primary desk.
NON_STEERING_TYPES = frozenset(("person", "place"))

_ENTITY_KEYS = frozenset((
    "id", "name", "type", "aliases", "ticker", "sections", "related", "ambiguous", "context", "gated",
))
_RULE_KEYS = frozenset(("strong", "weak", "adjacent"))
_GLOSSARY_KEYS = frozenset(("term", "aliases", "definition", "section"))
_TOP_KEYS = frozenset(("about", "entities", "synonyms", "sectionRules", "glossary"))
_KEBAB = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_SPLIT = re.compile(r"([^\W_]+|[&+])")
# Gaps a multi-word alias may span. Anything else (", ", ". ", " - ", ": ") ends a phrase.
_SOFT_GAP = re.compile("\\s+|[-\u2010\u2011\u2013/.'\u2019]")  # hyphens, en dash, slash, dot, apostrophes
# ". " joins only after a token of one or two characters: an initial or "Dr", "US".
_ABBREVIATION_GAP = re.compile(r"\.\s+")
_VERSION = re.compile(r"[0-9]{1,3}[a-z]*\Z", re.I)  # "4", "2", "4o", "7B"; never "2025"
_END = ""  # trie key for "an alias ends here"; never a token
_MAX_REPORTED = 25


class _Tokens:
    """A text split once into the tokens every matcher walks.

    ``raw`` keeps the original spelling for exact (case-sensitive) checks,
    ``folded`` is lowercased and accent-free for trie lookups, and ``soft[i]``
    says whether token ``i`` may continue a phrase begun before it.
    """

    __slots__ = ("raw", "folded", "soft", "_words", "_joined")

    def __init__(self, text):
        parts = _SPLIT.split(text or "")
        self.raw = parts[1::2]
        self.folded = [_fold(token) for token in self.raw]
        gaps = parts[0:-1:2]
        self.soft = [_is_soft(gap, self.raw[index - 1] if index else "") for index, gap in enumerate(gaps)]
        self._words = None
        self._joined = None

    def has_word(self, words):
        """True if any of ``words`` (folded, singular) occurs, ignoring a plural "s"."""
        if self._words is None:
            folded = self.folded
            self._words = set(folded).union(word[:-1] for word in folded if word.endswith("s"))
        return not self._words.isdisjoint(words)

    def has_phrase(self, phrases):
        """True if any multi-word phrase (folded tokens joined by spaces) occurs."""
        if self._joined is None:
            self._joined = " %s " % " ".join(self.folded)
        joined = self._joined
        return any((" %s " % phrase) in joined or (" %ss " % phrase) in joined for phrase in phrases)


def _is_soft(gap, previous):
    """Whether the text between two tokens lets a multi-word alias continue (see the module docstring)."""
    if gap in ("", " ") or _SOFT_GAP.fullmatch(gap):
        return True
    return len(previous) <= 2 and _ABBREVIATION_GAP.fullmatch(gap) is not None


def _fold(token):
    """Lowercase and strip accents, so "Nestlé" and "NESTLE" share one trie key."""
    if token.isascii():
        return token.lower()
    decomposed = unicodedata.normalize("NFKD", token)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _alias_tokens(alias):
    """Split an alias exactly the way text is split; returns (raw, folded)."""
    tokens = _Tokens(alias)
    return tuple(tokens.raw), tuple(tokens.folded)


def _is_exact(alias, ambiguous):
    """Whether an alias must match with its exact capitalisation (see the module docstring)."""
    letters = [ch for ch in alias if ch.isalpha()]
    if len(letters) >= 2 and all(ch.isupper() for ch in letters):
        return True
    return ambiguous and any(ch.isupper() for ch in letters)


class _Trie:
    """Aliases keyed word by word: matching costs one dict lookup per token, not one regex per alias.

    Each terminal holds ``(payload, exact_tokens_or_None, plural_ok)`` entries;
    several entities may end at the same node (two ambiguous entities sharing a
    gated word such as "Congress").
    """

    def __init__(self):
        self.root = {}

    def add(self, alias, payload, exact, plural_ok):
        raw, folded = _alias_tokens(alias)
        node = self.root
        for word in folded:
            node = node.setdefault(word, {})
        node.setdefault(_END, []).append((payload, raw if exact else None, plural_ok))

    def scan(self, tokens, longest=True):
        """Return ``(start, end, payloads)`` matches, left to right.

        ``longest=True`` keeps only the longest acceptable match at a position
        and resumes after it (entities); ``longest=False`` reports every match
        at every position, overlapping (section phrases, where "AI" and
        "AI agents" are separate signals for different desks).
        """
        root, folded = self.root, tokens.folded
        matches = []
        start, count = 0, len(folded)
        while start < count:
            word = folded[start]
            if word not in root and not (word.endswith("s") and word[:-1] in root):
                start += 1
                continue
            found = self._walk(tokens, start)
            if not found:
                start += 1
            elif longest:
                matches.append(found[-1])
                start = found[-1][1]
            else:
                matches.extend(found)
                start += 1
        return matches

    def _walk(self, tokens, start):
        """Follow the trie from ``start``; return every acceptable match, shortest first."""
        folded, soft = tokens.folded, tokens.soft
        node, found = self.root, []
        position, count = start, len(folded)
        while position < count and (position == start or soft[position]):
            word = folded[position]
            if len(word) > 2 and word.endswith("s"):
                singular = node.get(word[:-1])
                if singular and _END in singular:
                    hits = _accept(singular[_END], tokens.raw, start, position + 1, True)
                    if hits:
                        found.append((start, position + 1, hits))
            node = node.get(word)
            if node is None:
                break
            if _END in node:
                hits = _accept(node[_END], tokens.raw, start, position + 1, False)
                if hits:
                    if found and found[-1][1] == position + 1:
                        found.pop()  # the exact word beats its plural reading at the same span
                    found.append((start, position + 1, hits))
            position += 1
        return found


def _accept(entries, raw, start, end, plural):
    """Filter a terminal's entries by plural permission and exact spelling."""
    hits = []
    for payload, exact, plural_ok in entries:
        if plural and not plural_ok:
            continue
        if exact is not None:
            words = raw[start:end]
            if plural:
                words = words[:-1] + [words[-1][:-1]]
            if tuple(words) != exact:
                continue
        hits.append(payload)
    return hits


def _steer(steering, section, position):
    """Count one primary-moving signal for ``section`` and remember the earliest position."""
    entry = steering.setdefault(section, [0, position])
    entry[0] += 1
    entry[1] = min(entry[1], position)


def _context_sets(words):
    """Split context words into single folded words (singular) and multi-word phrases."""
    singles, phrases = set(), []
    for word in words:
        folded = _alias_tokens(word)[1]
        if len(folded) == 1:
            single = folded[0]
            singles.add(single[:-1] if len(single) > 3 and single.endswith("s") else single)
        elif folded:
            phrases.append(" ".join(folded))
    return frozenset(singles), tuple(phrases)


# ---------------------------------------------------------------- validation


def validate(data, section_ids):
    """Return a list of human-readable problems in a lexicon object (empty when valid).

    Checked: known keys and types, unique kebab-case ids, known types and
    sections, related ids that exist, gated aliases that are real aliases with
    context words, unique tickers, no surface form shared by two entities
    unless it is gated on both, lowercase synonym groups, a rule for every
    section, and unique glossary terms.
    """
    problems = []
    if not isinstance(data, dict):
        return ["lexicon must be a JSON object"]
    unknown = sorted(set(data) - _TOP_KEYS)
    if unknown:
        problems.append("unknown top-level keys: %s" % ", ".join(unknown))
    sections = list(section_ids)
    entities = data.get("entities")
    if isinstance(entities, list):
        problems.extend(_check_entities(entities, sections))
    else:
        problems.append("entities must be a list")
    synonyms = data.get("synonyms")
    if isinstance(synonyms, list):
        problems.extend(_check_synonyms(synonyms))
    else:
        problems.append("synonyms must be a list of lists")
    rules = data.get("sectionRules")
    if isinstance(rules, dict):
        problems.extend(_check_rules(rules, sections))
    else:
        problems.append("sectionRules must be an object")
    glossary = data.get("glossary")
    if isinstance(glossary, list):
        problems.extend(_check_glossary(glossary, sections))
    else:
        problems.append("glossary must be a list")
    return problems


def _strings(value):
    """True for a list of non-empty strings."""
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def _check_entities(entities, sections):
    """Problems in the entity list, including cross-entity ones (related ids, tickers, aliases)."""
    problems, ids, tickers, surfaces = [], {}, {}, {}
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            problems.append("entities[%d] is not an object" % index)
            continue
        label = "entity %s" % entity.get("id", "#%d" % index)
        problems.extend(_check_entity_fields(entity, label, sections))
        entity_id = entity.get("id")
        if isinstance(entity_id, str):
            if entity_id in ids:
                problems.append("%s: duplicate id" % label)
            ids[entity_id] = entity
        ticker = entity.get("ticker")
        if isinstance(ticker, str):
            if ticker in tickers:
                problems.append("%s: ticker %s already used by %s" % (label, ticker, tickers[ticker]))
            tickers[ticker] = entity_id
        problems.extend(_collect_surfaces(entity, label, surfaces))
    for entity in entities:
        if isinstance(entity, dict) and _strings(entity.get("related", [])):
            for other in entity.get("related", []):
                if other not in ids:
                    problems.append("entity %s: related id %r does not exist" % (entity.get("id"), other))
                elif other == entity.get("id"):
                    problems.append("entity %s: related to itself" % other)
    return problems


def _check_entity_fields(entity, label, sections):
    """Problems inside one entity object."""
    problems = []
    unknown = sorted(set(entity) - _ENTITY_KEYS)
    if unknown:
        problems.append("%s: unknown keys %s" % (label, ", ".join(unknown)))
    if not isinstance(entity.get("id"), str) or not _KEBAB.match(entity["id"]):
        problems.append("%s: id must be kebab-case" % label)
    if not isinstance(entity.get("name"), str) or not entity["name"].strip():
        problems.append("%s: name must be a non-empty string" % label)
    if entity.get("type") not in ENTITY_TYPES:
        problems.append("%s: unknown type %r" % (label, entity.get("type")))
    aliases = entity.get("aliases")
    if not _strings(aliases) or not aliases:
        problems.append("%s: aliases must be a non-empty list of strings" % label)
        aliases = []
    for alias in aliases:
        if not _alias_tokens(alias)[1]:
            problems.append("%s: alias %r has no letters or digits" % (label, alias))
    if entity.get("ticker") is not None and not (isinstance(entity["ticker"], str) and entity["ticker"].strip()):
        problems.append("%s: ticker must be a string or null" % label)
    for field in ("sections", "related"):
        if not _strings(entity.get(field)):
            problems.append("%s: %s must be a list of strings" % (label, field))
    for section in entity.get("sections") or []:
        if section not in sections:
            problems.append("%s: unknown section %r" % (label, section))
    problems.extend(_check_gating(entity, label, aliases))
    return problems


def _check_gating(entity, label, aliases):
    """Ambiguity fields must be consistent: gated words are aliases and have context."""
    ambiguous = entity.get("ambiguous")
    if not isinstance(ambiguous, bool):
        return ["%s: ambiguous must be true or false" % label]
    gated, context = entity.get("gated", []), entity.get("context", [])
    if not ambiguous:
        return ["%s: only ambiguous entities take gated/context" % label] if gated or context else []
    problems = []
    if not _strings(gated) or not _strings(context):
        return ["%s: gated and context must be lists of strings" % label]
    for word in gated:
        if word not in aliases:
            problems.append("%s: gated %r is not one of its aliases" % (label, word))
    if gated and not context:
        problems.append("%s: gated aliases need context words" % label)
    for word in context:
        if not _alias_tokens(word)[1]:
            problems.append("%s: context word %r has no letters or digits" % (label, word))
    return problems


def _collect_surfaces(entity, label, surfaces):
    """Record each ungated surface form; report one already claimed by another entity.

    Gated forms may be shared ("Congress" for India's party and the US
    legislature) because context decides between them.
    """
    problems = []
    if not _strings(entity.get("aliases")):
        return problems
    gated = set(entity.get("gated") or [])
    for alias in entity["aliases"]:
        if alias in gated:
            continue
        key = _alias_tokens(alias)[1]
        owner = surfaces.get(key)
        if owner is not None and owner != entity.get("id"):
            problems.append("%s: alias %r already belongs to %s" % (label, alias, owner))
        surfaces[key] = entity.get("id")
    return problems


def _check_synonyms(groups):
    """Each group: two or more distinct lowercase terms."""
    problems = []
    for index, group in enumerate(groups):
        if not _strings(group) or len(group) < 2:
            problems.append("synonyms[%d] must list at least two terms" % index)
            continue
        for term in group:
            if term != _norm_term(term):
                problems.append("synonyms[%d]: %r must be lowercase with single spaces" % (index, term))
        if len(set(group)) != len(group):
            problems.append("synonyms[%d] repeats a term" % index)
    return problems


def _check_rules(rules, sections):
    """A rule per section, known keys, adjacent homes that exist, no phrase both strong and weak."""
    problems = []
    for section in sections:
        if section not in rules:
            problems.append("sectionRules: no rule for %r" % section)
    for section, rule in rules.items():
        if section not in sections:
            problems.append("sectionRules: unknown section %r" % section)
            continue
        if not isinstance(rule, dict) or set(rule) - _RULE_KEYS:
            problems.append("sectionRules.%s: only strong, weak and adjacent are allowed" % section)
            continue
        for key in _RULE_KEYS:
            if not _strings(rule.get(key, [])):
                problems.append("sectionRules.%s.%s must be a list of strings" % (section, key))
        for home in rule.get("adjacent", []):
            if home not in sections or home == section:
                problems.append("sectionRules.%s: bad adjacent section %r" % (section, home))
        both = set(rule.get("strong", [])) & set(rule.get("weak", []))
        if both:
            problems.append("sectionRules.%s: both strong and weak: %s" % (section, ", ".join(sorted(both))))
    return problems


def _check_glossary(entries, sections):
    """Entries need a unique term, a definition and a known section."""
    problems, seen = [], set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) - _GLOSSARY_KEYS:
            problems.append("glossary[%d]: must be an object with %s" % (index, ", ".join(sorted(_GLOSSARY_KEYS))))
            continue
        term = entry.get("term")
        if not isinstance(term, str) or not term.strip():
            problems.append("glossary[%d]: term must be a non-empty string" % index)
            continue
        key = _norm_term(term)
        if key in seen:
            problems.append("glossary: duplicate term %r" % term)
        seen.add(key)
        if not isinstance(entry.get("definition"), str) or len(entry["definition"].strip()) < 20:
            problems.append("glossary %r: definition must be a sentence" % term)
        if entry.get("section") not in sections:
            problems.append("glossary %r: unknown section %r" % (term, entry.get("section")))
        if not _strings(entry.get("aliases", [])):
            problems.append("glossary %r: aliases must be a list of strings" % term)
    return problems


def _norm_term(term):
    """Search-term key: lowercase, accents folded, single spaces."""
    return " ".join(_fold(str(term)).split())


# ---------------------------------------------------------------- the compiled lexicon


class Lexicon:
    """A validated, compiled lexicon.

    Build one with ``Lexicon(data, section_ids)`` (tests) or get the cached one from ``load()``.
    """

    def __init__(self, data, section_ids):
        problems = validate(data, section_ids)
        if problems:
            shown = problems[:_MAX_REPORTED]
            more = len(problems) - len(shown)
            raise config.ConfigError("config/lexicon.json has %d problem(s): %s%s" % (
                len(problems), "; ".join(shown), "; and %d more" % more if more else ""))
        self.sections = tuple(section_ids)
        self._data = data
        self._entities = {entity["id"]: entity for entity in data["entities"]}
        self._entity_trie = self._compile_entities()
        self._gates = self._compile_gates()
        self._rules, self._phrase_trie = self._compile_rules()
        self._synonyms = self._compile_synonyms()

    def _compile_entities(self):
        """One trie over every alias; the payload says which entity and whether it is gated."""
        trie = _Trie()
        for entity in self._data["entities"]:
            ambiguous, gated = entity["ambiguous"], set(entity.get("gated", []))
            for alias in entity["aliases"]:
                exact = _is_exact(alias, ambiguous)
                trie.add(alias, (entity["id"], alias in gated), exact, not (ambiguous and exact))
        return trie

    def _compile_gates(self):
        """For each entity with gated aliases: (context words, context phrases, related ids, versioned)."""
        gates = {}
        for entity in self._data["entities"]:
            if entity.get("gated"):
                singles, phrases = _context_sets(entity["context"])
                gates[entity["id"]] = (singles, phrases, frozenset(entity["related"]),
                                       entity["type"] in VERSIONED_TYPES)
        return gates

    def _compile_rules(self):
        """Section phrase trie (payload: (section, strong, phrase)) and the adjacency per section."""
        trie, adjacent = _Trie(), {}
        for section in self.sections:
            rule = self._data["sectionRules"][section]
            adjacent[section] = frozenset(rule.get("adjacent", []))
            for strength in ("strong", "weak"):
                for phrase in rule.get(strength, []):
                    trie.add(phrase, (section, strength == "strong", phrase), _is_exact(phrase, False), True)
        return adjacent, trie

    def _compile_synonyms(self):
        """Term -> every term it is interchangeable with, in group order, itself excluded."""
        index = {}
        for group in self._data["synonyms"]:
            for term in group:
                others = index.setdefault(term, [])
                others.extend(other for other in group if other != term and other not in others)
        return index

    # -------------------------------------------------- matching

    def match_entities(self, text):
        """Entity ids mentioned in ``text``, in order of first mention, each once."""
        found, _spans = self._scan_entities(_Tokens(text))
        return sorted(found, key=found.get)

    def _scan_entities(self, tokens):
        """Return ``({entity id: first token index}, [(start, end, entity ids) per accepted mention])``."""
        found, pending, spans = {}, [], []
        for start, end, hits in self._entity_trie.scan(tokens):
            accepted = []
            for entity_id, gated in hits:
                if gated:
                    pending.append((start, end, entity_id))
                else:
                    accepted.append(entity_id)
                    found.setdefault(entity_id, start)
            if accepted:
                spans.append((start, end, accepted))
        if pending:
            ungated = frozenset(found)
            for start, end, entity_id in pending:
                if entity_id in found or self._gate_open(entity_id, tokens, end, ungated):
                    found[entity_id] = min(found.get(entity_id, start), start)
                    spans.append((start, end, [entity_id]))
        return found, spans

    def _gate_open(self, entity_id, tokens, end, ungated):
        """Decide whether a gated word really names the entity (see the module docstring)."""
        singles, phrases, related, versioned = self._gates[entity_id]
        if not related.isdisjoint(ungated):
            return True
        if versioned and end < len(tokens.raw) and tokens.soft[end] and _VERSION.match(tokens.raw[end]):
            return True
        return tokens.has_word(singles) or (bool(phrases) and tokens.has_phrase(phrases))

    def sections_for(self, text, home_section, entity_ids=None):
        """Return ``(primary, sections)`` for a story; ``sections`` starts with ``primary``.

        ``entity_ids`` is normally the result of ``match_entities`` on the same
        text (pass it to avoid matching twice); ``None`` matches here.
        Raises ``ValueError`` for an unknown home section or entity id, which
        means the caller's config and the lexicon disagree.
        """
        if home_section not in self._rules:
            raise ValueError("unknown home section %r" % (home_section,))
        tokens = _Tokens(text)
        found, spans = self._scan_entities(tokens)
        ids = sorted(found, key=found.get) if entity_ids is None else entity_ids
        strong = {section: set() for section in self.sections}
        weak = {section: set() for section in self.sections}
        steering = {}  # section -> [strong signals that may move the primary desk, first token index]
        for entity_id in ids:
            entity = self._entities.get(entity_id)
            if entity is None:
                raise ValueError("unknown entity id %r" % (entity_id,))
            for section in entity["sections"]:
                strong[section].add("entity:" + entity_id)
                if entity["type"] not in NON_STEERING_TYPES:
                    _steer(steering, section, found.get(entity_id, len(tokens.raw)))
        for start, (section, is_strong, phrase) in self._phrase_hits(tokens, spans):
            if is_strong:
                strong[section].add(phrase)
                _steer(steering, section, start)
            else:
                weak[section].add(phrase)
        chosen = {home_section}
        for section in self.sections:
            if strong[section] or len(weak[section]) >= 2 or (
                    weak[section] and home_section in self._rules[section]):
                chosen.add(section)
        primary = self._primary(home_section, steering, len(strong[home_section]))
        return primary, [primary] + [s for s in self.sections if s in chosen and s != primary]

    def _phrase_hits(self, tokens, entity_spans):
        """``(token index, (section, strong, phrase))`` for each phrase that counts as evidence.

        A phrase that is only part of a longer entity name is not a topic
        ("India" in "The Times of India", "AI" in "Scale AI"), and a phrase that
        is exactly an entity mention already counted for the same desk is not
        counted twice. Phrases may overlap across desks ("AI" for ai, "AI agents"
        for llm), but a phrase inside a longer one of the same desk is the same
        evidence ("AI chips" counts once), and a weak phrase inside any longer
        phrase is not separate evidence ("equities" inside "Indian equities").
        """
        spans = [(start, end, payload)
                 for start, end, hits in self._phrase_trie.scan(tokens, longest=False)
                 for payload in hits
                 if not self._named(start, end, payload[0], entity_spans)]
        kept = []
        for start, end, payload in spans:
            inside = any(other_start <= start and end <= other_end and (other_start, other_end) != (start, end)
                         and (not payload[1] or (other[0] == payload[0] and other[1]))
                         for other_start, other_end, other in spans)
            if not inside:
                kept.append((start, payload))
        return kept

    def _named(self, start, end, section, entity_spans):
        """Whether a phrase at ``start:end`` is part of an entity name (see ``_phrase_hits``)."""
        for left, right, entity_ids in entity_spans:
            if left <= start and end <= right:
                if right - left > end - start:
                    return True
                if any(section in self._entities[entity_id]["sections"] for entity_id in entity_ids):
                    return True
        return False

    def _primary(self, home_section, steering, home_evidence):
        """The home desk, unless it is generic and a specific desk has stronger evidence.

        ``steering`` holds, per desk, the strong signals that may move a story
        (mentions of people and places do not: "Bessent moved to a military
        base" is still a World story) and where the first one appears.
        ``home_evidence`` is every strong signal for the home desk itself; a
        specific desk takes over only with more than that, so a NASA Moon plan
        that names SpaceX and Blue Origin stays on the Science desk. Among
        specific desks the one with the most signals wins; on a tie the one
        mentioned first, which is usually the headline's subject.
        """
        if home_section not in GENERIC_HOMES:
            return home_section
        candidates = [(-count, first, section) for section, (count, first) in steering.items()
                      if section not in GENERIC_HOMES and count > home_evidence]
        return min(candidates)[2] if candidates else home_section

    # -------------------------------------------------- lookups

    def expand_term(self, term):
        """The term (normalised) followed by its synonyms; a plural falls back to its singular."""
        key = _norm_term(term)
        if not key:
            return []
        others = self._synonyms.get(key)
        if others is None and key.endswith("s"):
            singular = key[:-1]
            others = self._synonyms.get(singular)
            if others is not None:
                others = [singular] + others
        return [key] + [other for other in (others or []) if other != key]

    def entity(self, entity_id):
        """A copy of one entity's config object, or None for an unknown id."""
        found = self._entities.get(entity_id)
        return copy.deepcopy(found) if found is not None else None

    def ticker_map(self):
        """Yahoo Finance symbol -> entity id, for joining quotes to stories."""
        return {entity["ticker"]: entity_id for entity_id, entity in self._entities.items() if entity["ticker"]}

    def export_public(self):
        """The ``aliases``, ``entities`` and ``glossary`` parts of ``public/search/lexicon.json``.

        Shapes follow docs/ARCHITECTURE.md exactly; the search stage adds ``related``.
        """
        return {
            "aliases": {term: list(others) for term, others in self._synonyms.items()},
            "entities": {
                entity_id: {
                    "name": entity["name"],
                    "type": entity["type"],
                    "aliases": list(entity["aliases"]),
                    "related": list(entity["related"]),
                    "ticker": entity["ticker"],
                }
                for entity_id, entity in self._entities.items()
            },
            "glossary": {entry["term"]: entry["definition"] for entry in self._data["glossary"]},
        }


_cache: Dict[str, Lexicon] = {}


def load():
    """The lexicon from ``config/lexicon.json``, validated and compiled once per process.

    Raises ``config.ConfigError`` if the file is missing, malformed or fails
    validation; the message lists the problems.
    """
    if "lexicon" not in _cache:
        site = config.load("site")
        section_ids = [section["id"] for section in site.get("sections", [])]
        _cache["lexicon"] = Lexicon(config.load("lexicon"), section_ids)
    return _cache["lexicon"]


def match_entities(text) -> List[str]:
    """See ``Lexicon.match_entities``."""
    return load().match_entities(text)


def sections_for(text, home_section, entity_ids=None) -> Tuple[str, List[str]]:
    """See ``Lexicon.sections_for``."""
    return load().sections_for(text, home_section, entity_ids)


def expand_term(term) -> List[str]:
    """See ``Lexicon.expand_term``."""
    return load().expand_term(term)


def entity(entity_id) -> Optional[dict]:
    """See ``Lexicon.entity``."""
    return load().entity(entity_id)


def ticker_map() -> Dict[str, str]:
    """See ``Lexicon.ticker_map``."""
    return load().ticker_map()


def export_public() -> dict:
    """See ``Lexicon.export_public``."""
    return load().export_public()
