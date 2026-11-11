"""Same-story clustering: which headlines are one event, with ids that never change.

The front page is only as good as this step. Merge too little and one event
fills five slots; merge too much and "Tesla recalls Cybertruck" swallows
"Tesla opens Mumbai showroom". So the rules are deliberately conservative and
each one exists because of a failure seen in real feeds:

* An item is compared with *stories*, never with every other item: an inverted
  index over informative title tokens (and exact headlines) proposes the few
  stories worth scoring.
* Similarity starts from an IDF-weighted cosine over stemmed title tokens. A
  matched lexicon entity becomes one token of its own ("U.S.", "US" and
  "United States" all turn into ``@united-states``), which is what lets
  differently worded headlines about one event meet. The score is lifted when
  most of one headline is found in the other's headline and standfirst.
* The same headline is the same story. A headline that an aggregator lists as
  another outlet's version of its story (``alt``) is strong evidence, added to
  the text score: aggregator groups are too loose to be trusted alone.
* Recurring templates ("Sensex, Nifty close higher", "Stocks to watch", live
  blogs, dated bulletins) look identical every day, so they may only merge
  within one local day and a few hours. Opposite market directions ("ends
  higher" / "ends lower") and disjoint named subjects pull the score down, and
  two items from one outlet need nearly the same headline: a newsroom does
  not write one story twice, but it does run series.
* A story is also judged as a whole, by the centroid of its headlines, which
  forgets each outlet's turn of phrase. Stories seeded in the current run are
  merged when their centroids agree, so a breaking story that two outlets
  worded differently does not stay split in two.
* Assignments are recorded in ``state/clusters.json``. Once a story has been
  published its id (``stable_id("s", seed item id)``) is stable for good: a
  later run can add items to it but never moves, splits or absorbs it.

A story stays open to new items while it is on one of the live day files and
its newest item is at most 48 hours from the candidate's. After that the same
event starts a new story, which ``threads.py`` links back to the old one.
"""

import math
import re
from collections import Counter, defaultdict
from functools import lru_cache

from . import lexicon, rank
from .core import log, textutil, timeutil

WINDOW_HOURS = 48.0
# Minimum similarity to a story's closest members for an item to join it (tuned on the live
# store; see the tests).
JOIN_THRESHOLD = 0.44
# A token must be at least this informative (IDF) to propose a candidate story.
INDEX_MIN_IDF = 2.2
# Recurring templates merge only inside one local day and this many hours.
ROUTINE_MAX_HOURS = 8.0
# How much the best-matching member counts against the average of the next two.
BEST_WEIGHT = 0.7
# Minimum centroid similarity for two small stories, one seeded in this run, to be merged.
MERGE_THRESHOLD = 0.45
# A story with this many members has a centroid worth trusting; against one, an item or a
# story needs only this much centroid similarity.
CENTROID_MIN_DOCS = 3
CENTROID_THRESHOLD = 0.40
# A token found in more stories than this proposes no merge pairs (it would propose all of them).
MERGE_MAX_POSTINGS = 80
NUMBER_WEIGHT = 0.5
# Share of the blended score given to "one headline is contained in the other's headline and standfirst".
CONTAINMENT_WEIGHT = 0.4
# Two items from one outlet are rarely one story unless the headlines nearly coincide.
SAME_OUTLET_FACTOR = 0.8
# Both headlines name someone and share no name ("TCS Q2 results" / "Infosys Q2 results").
DIFFERENT_SUBJECT_FACTOR = 0.5
# One headline only goes up, the other only down ("ends higher" / "ends lower").
OPPOSITE_DIRECTION_FACTOR = 0.6
# A headline with fewer tokens than this ("Red Flags") cannot be matched on its words, and two
# headlines with fewer tokens in common than this get no lift and a discount: two rare words
# shared ("trade", "ties") are a coincidence more often than an event.
MIN_TOKENS = 3
FEW_SHARED_FACTOR = 0.85
# An aggregator listing two headlines under one story is strong evidence, but its groups are
# loose ("Russia" news), so it adds to the text score instead of replacing it.
ALT_BONUS = 0.3
# An identical headline shorter than this ("Markets wrap") is not evidence of anything.
MIN_HEADLINE_WORDS = 4
ENTITY_PREFIX = "@"
# Entity types that say what a headline is about; places and topics are too broad for that.
ANCHOR_TYPES = frozenset(("company", "lab", "person", "product", "model", "org", "regulator", "agency", "index"))

_UP = frozenset("rise rose gain jump surge rally climb soar higher up rebound advance spike zoom".split())
_DOWN = frozenset(
    "fall fell drop slip tumble plunge sink sank slump lower down decline crash slide slid dip shed lose".split())
_MAGNITUDE = re.compile(r"^(\d+(?:\.\d+)?)(k|m|mn|b|bn|tn|trn)$")
_MAGNITUDE_WORDS = {"k": "thousand", "m": "million", "mn": "million", "b": "billion", "bn": "billion",
                    "tn": "trillion", "trn": "trillion"}
# Adjective -> the country word headlines also use ("Italian schools" / "schools in Italy").
_DEMONYMS = {
    "american": "us", "british": "uk", "chinese": "china", "russian": "russia",
    "ukrainian": "ukraine", "indian": "india", "pakistani": "pakistan", "israeli": "israel",
    "iranian": "iran", "french": "france", "german": "germany", "italian": "italy", "spanish": "spain",
    "japanese": "japan", "korean": "korea", "canadian": "canada", "australian": "australia",
    "brazilian": "brazil", "mexican": "mexico", "turkish": "turkey", "polish": "poland", "dutch": "netherlands",
    "swedish": "sweden", "norwegian": "norway", "danish": "denmark", "finnish": "finland", "greek": "greece",
    "irish": "ireland", "scottish": "scotland", "swiss": "switzerland", "belgian": "belgium",
    "bulgarian": "bulgaria", "hungarian": "hungary", "romanian": "romania", "syrian": "syria",
    "lebanese": "lebanon", "iraqi": "iraq", "saudi": "saudi", "egyptian": "egypt", "nigerian": "nigeria",
    "kenyan": "kenya", "argentine": "argentina", "argentinian": "argentina", "venezuelan": "venezuela",
    "colombian": "colombia", "peruvian": "peru", "afghan": "afghanistan", "bangladeshi": "bangladesh",
    "nepali": "nepal", "nepalese": "nepal", "taiwanese": "taiwan", "vietnamese": "vietnam",
    "indonesian": "indonesia", "thai": "thailand", "european": "europe", "african": "africa",
    "palestinian": "palestine", "cuban": "cuba", "sudanese": "sudan", "ethiopian": "ethiopia",
}
_OUTLET_SUFFIX = re.compile(r"\.(?:com|in|org|net|eu|co\.uk|co\.in)$", re.I)
_OUTLET_TAIL = re.compile(r"\s+[-|–—:]\s.*$")
# Different spellings aggregators use for one newsroom.
_OUTLET_ALIASES = {
    "wsj": "wall street journal", "nyt": "new york times", "bbc": "bbc news", "ap": "ap news",
    "associated press": "ap news", "et": "economic times", "toi": "times of india", "ht": "hindustan times",
    "livemint": "mint", "cnbc tv18": "cnbc-tv18", "cnbctv18": "cnbc-tv18", "hindu businessline": "businessline",
    "ft": "financial times", "wapo": "washington post",
}


def outlet_label(name):
    """An outlet's name as shown to readers: no tagline, no domain suffix.

    Aggregators report "ABC News - Breaking News, Latest News and Videos" and
    "Moneycontrol.com"; the paper prints "ABC News" and "Moneycontrol".
    """
    text = _OUTLET_TAIL.sub("", str(name or "").strip())
    return _OUTLET_SUFFIX.sub("", text) if " " not in text else text


def outlet_key(name):
    """One key per newsroom, however a feed or an aggregator spells it.

    "The Times of India", "Times of India" and "TOI" are one outlet; so are
    "Moneycontrol.com" and "Moneycontrol". Breadth counts these keys.
    """
    text = outlet_label(name).lower()
    if text.startswith("the "):
        text = text[4:]
    return _OUTLET_ALIASES.get(text, text)


@lru_cache(maxsize=None)
def _entity_facts(entity_id):
    """(is anchor, word keys of every alias) for an entity; no keys for an unknown id."""
    found = lexicon.entity(entity_id)
    if found is None:
        return False, frozenset()
    keys = {key for alias in found["aliases"] for token in textutil.tokenize(alias) for key in _word_keys(token)}
    return found["type"] in ANCHOR_TYPES, frozenset(keys)


def _direction(raw_tokens):
    """+1 for a headline that only talks of going up, -1 only down, 0 mixed or neither."""
    stems = {textutil.stem(token) for token in raw_tokens}
    up, down = not stems.isdisjoint(_UP), not stems.isdisjoint(_DOWN)
    return (1 if up else 0) - (1 if down else 0)


@lru_cache(maxsize=None)
def _country_key(country):
    """The token for a country word: the lexicon's place entity when it has one, else the word."""
    found = lexicon.match_entities(country.upper() if len(country) <= 2 else country.capitalize())
    return ENTITY_PREFIX + found[0] if found else country


def _word_keys(token):
    """The comparison key(s) of one word token.

    The shared stemmer is deliberately light, so three things it leaves apart
    are joined here: "exposes"/"exposed" (a final "e" is dropped), "Italian"/
    "Italy" (demonyms), and "$1.4tn"/"$1.4 trillion" (magnitude suffixes).
    """
    magnitude = _MAGNITUDE.match(token)
    if magnitude:
        return (magnitude.group(1), _MAGNITUDE_WORDS[magnitude.group(2)])
    if token in _DEMONYMS:
        return (_country_key(_DEMONYMS[token]),)
    stem = textutil.stem(token)
    return (stem[:-1] if len(stem) > 4 and stem.endswith("e") else stem,)


def text_tokens(text, entity_ids):
    """The comparison tokens of a text: word keys minus stopwords, entities as single tokens.

    The words of a matched entity's aliases are dropped in favour of one
    ``@id`` token, so an entity is counted once however it is spelt.
    """
    alias_keys = set()
    for entity_id in entity_ids:
        alias_keys.update(_entity_facts(entity_id)[1])
    tokens = set()
    for token in textutil.tokenize(text):
        if token not in textutil.STOPWORDS:
            tokens.update(key for key in _word_keys(token) if key not in alias_keys)
    tokens.update(ENTITY_PREFIX + entity_id for entity_id in entity_ids)
    return frozenset(tokens)


class Doc:
    """What clustering needs to know about one item."""

    __slots__ = ("id", "time", "day", "outlet", "norm", "tokens", "full", "alts", "anchors", "routine",
                 "direction")

    def __init__(self, item, title_entities, text_entities, tz):
        """``title_entities`` are the lexicon ids in the headline, ``text_entities`` those in
        headline plus summary (a superset)."""
        self.id = item["id"]
        self.time = timeutil.parse_date(item.get("publishedAt"))
        if self.time is None:
            raise ValueError("item %s has no usable publishedAt" % item.get("id"))
        self.day = timeutil.local_date(self.time, tz)
        self.outlet = outlet_key(item.get("publisher") or item.get("sourceName") or item.get("source"))
        title = item.get("title") or ""
        self.norm = textutil.norm_title(title)
        self.tokens = text_tokens(title, title_entities)
        self.full = self.tokens | text_tokens(item.get("summary") or "", text_entities)
        self.alts = frozenset(textutil.norm_title(alt.get("title") or "") for alt in item.get("alt") or []) - {""}
        self.anchors = frozenset(e for e in title_entities if _entity_facts(e)[0])
        self.routine = rank.template(title) in rank.RECURRING_TEMPLATES
        self.direction = _direction(textutil.tokenize(title))


class Weights:
    """IDF weights from the headlines in play; rare words say more than "India" or "shares"."""

    def __init__(self, docs):
        frequency = Counter(token for doc in docs for token in doc.tokens)
        self._count = len(docs)
        self._idf = {token: self._formula(seen) for token, seen in frequency.items()}
        self._unseen = self._formula(0)

    def _formula(self, seen):
        return math.log((self._count + 1.0) / (seen + 1.0)) + 0.5

    def idf(self, token):
        """Raw informativeness of a token (higher is rarer)."""
        return self._idf.get(token, self._unseen)

    def weight(self, token):
        """IDF, halved for bare numbers: "12" and "a dozen" should not decide a match."""
        value = self.idf(token)
        return value * NUMBER_WEIGHT if token[0].isdigit() else value

    def norm(self, tokens):
        """Euclidean length of a token set under these weights."""
        return math.sqrt(sum(self.weight(token) ** 2 for token in tokens))


def cosine(a_tokens, b_tokens, weights):
    """IDF-weighted cosine of two token sets, 0..1."""
    shared = a_tokens & b_tokens
    if not shared:
        return 0.0
    dot = sum(weights.weight(token) ** 2 for token in shared)
    return dot / (weights.norm(a_tokens) * weights.norm(b_tokens))


def centroid_cosine(a, b, weights):
    """IDF-weighted cosine of two centroids, each ``{token: share of headlines using it}``.

    A centroid keeps what several headlines about one event agree on and
    plays down each outlet's turn of phrase.
    """
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    dot = sum(weights.weight(token) ** 2 * share * large[token]
              for token, share in small.items() if token in large)
    if not dot:
        return 0.0
    a_norm = math.sqrt(sum((weights.weight(token) * share) ** 2 for token, share in a.items()))
    b_norm = math.sqrt(sum((weights.weight(token) * share) ** 2 for token, share in b.items()))
    return dot / (a_norm * b_norm)


def containment(a, b, weights):
    """How much of headline ``a`` is found in ``b``'s headline and standfirst, 0..1.

    Outlets word one event differently, but the key words of one headline
    usually turn up in the other's first sentence. Measured both by weight and
    by count, taking the lower: two rare words out of four are not "most of
    the headline". A headline of fewer than four tokens is contained in almost
    anything and counts for nothing.
    """
    if len(a.tokens) < 4:
        return 0.0
    found = a.tokens & b.full
    by_weight = sum(weights.weight(token) ** 2 for token in found) / (weights.norm(a.tokens) ** 2)
    return min(by_weight, len(found) / float(len(a.tokens)))


def _text_score(a, b, weights):
    """Headline cosine, lifted when one headline is largely contained in the other's text.

    The lift needs three shared headline tokens to stand on (a shared name plus
    a coincidence in a long summary is not evidence) and is not given to two
    items from one outlet: a newsroom does not write one story twice, but it
    does run series ("Broker's Call: X", "Curiosity Blog, Sols N") whose
    instalments look alike.
    """
    if min(len(a.tokens), len(b.tokens)) < MIN_TOKENS:
        return 0.0
    direct = cosine(a.tokens, b.tokens, weights)
    if a.outlet == b.outlet:
        return direct * SAME_OUTLET_FACTOR
    if len(a.tokens & b.tokens) < MIN_TOKENS:
        return direct * FEW_SHARED_FACTOR
    contained = max(containment(a, b, weights), containment(b, a, weights))
    return max(direct, (1.0 - CONTAINMENT_WEIGHT) * direct + CONTAINMENT_WEIGHT * contained)


def _listed_together(a, b):
    """True when an aggregator lists one item's headline among the other outlets' versions of the other."""
    return a.norm in b.alts or b.norm in a.alts


def _same_series(a, b):
    """True for two instalments of one outlet's series: the same words, different numbers.

    "Money Market Operations as on November 09" and "... November 10" are two
    days of one bulletin, not one story told twice.
    """
    if a.outlet != b.outlet or a.norm == b.norm:
        return False
    a_words = {token for token in a.tokens if not token[0].isdigit()}
    b_words = {token for token in b.tokens if not token[0].isdigit()}
    return a_words == b_words


def _time_factor(hours):
    """1.0 within half a day, easing to 0.6 at the 48 hour edge: old stories need a closer match."""
    if hours <= 12.0:
        return 1.0
    return max(0.6, 1.0 - 0.4 * (hours - 12.0) / (WINDOW_HOURS - 12.0))


def similarity(a, b, weights):
    """How likely two items are the same story, 0..1 (see the module docstring for the rules)."""
    hours = abs(timeutil.hours_between(a.time, b.time))
    if hours > WINDOW_HOURS:
        return 0.0
    if (a.routine or b.routine) and (a.day != b.day or hours > ROUTINE_MAX_HOURS):
        return 0.0
    if _same_series(a, b):
        return 0.0
    if a.norm == b.norm and len(a.norm.split()) >= MIN_HEADLINE_WORDS:
        score = 1.0
    else:
        score = _text_score(a, b, weights)
        if _listed_together(a, b):
            score = min(1.0, score + ALT_BONUS)
    if a.direction * b.direction < 0:
        score *= OPPOSITE_DIRECTION_FACTOR
    if a.anchors and b.anchors and a.anchors.isdisjoint(b.anchors):
        score *= DIFFERENT_SUBJECT_FACTOR
    return score * _time_factor(hours)


class _Story:
    """A story being built: its members, the time span they cover and their token centroid."""

    __slots__ = ("id", "docs", "first", "last", "counts", "fresh", "_centroid")

    def __init__(self, story_id, fresh):
        self.id = story_id
        self.docs = []
        self.first = None
        self.last = None
        self.counts = Counter()   # token -> number of members whose headline has it
        self.fresh = fresh        # created in this run, so its id has never been published
        self._centroid = None

    def add(self, doc):
        self.docs.append(doc)
        self.first = doc.time if self.first is None else min(self.first, doc.time)
        self.last = doc.time if self.last is None else max(self.last, doc.time)
        self.counts.update(doc.tokens)
        self._centroid = None

    def open_to(self, doc):
        """Whether ``doc`` falls within the window around this story's span."""
        return (timeutil.hours_between(self.last, doc.time) <= WINDOW_HOURS
                and timeutil.hours_between(doc.time, self.first) <= WINDOW_HOURS)

    @property
    def routine(self):
        """True when most members follow a recurring template (a market wrap, a live blog)."""
        return 2 * sum(1 for doc in self.docs if doc.routine) > len(self.docs)

    @property
    def direction(self):
        """Net market direction of the members' headlines: positive up, negative down."""
        return sum(doc.direction for doc in self.docs)

    @property
    def outlets(self):
        """The newsrooms that carry this story."""
        return frozenset(doc.outlet for doc in self.docs)

    @property
    def anchors(self):
        """Every named subject in any member's headline."""
        return frozenset(anchor for doc in self.docs for anchor in doc.anchors)

    def centroid(self):
        """{token: share of members whose headline has it}: what the story's headlines agree on."""
        if self._centroid is None:
            size = float(len(self.docs))
            self._centroid = {token: count / size for token, count in self.counts.items()}
        return self._centroid

    def member_score(self, doc, weights):
        """Best member match, tempered by the next two so one stray member cannot pull in a stranger."""
        scores = sorted((similarity(doc, member, weights) for member in self.docs), reverse=True)
        support = scores[1:3] or scores[:1]
        return BEST_WEIGHT * scores[0] + (1.0 - BEST_WEIGHT) * sum(support) / len(support)


def _gap_hours(a, b):
    """Hours between two stories' time spans; 0 when they overlap."""
    if a.first > b.last:
        return timeutil.hours_between(b.last, a.first)
    if b.first > a.last:
        return timeutil.hours_between(a.last, b.first)
    return 0.0


def story_similarity(a, b, weights):
    """How likely two stories are one event, 0..1, judged on their centroids.

    A centroid keeps what a story's headlines agree on and forgets each
    outlet's turn of phrase, so it is a far better judge than any single pair
    of headlines. The same guards apply as between items: recurring templates
    only within one day, opposite market directions and disjoint named
    subjects count against, distance in time costs.
    """
    gap = _gap_hours(a, b)
    if gap > WINDOW_HOURS / 2 or min(len(a.counts), len(b.counts)) < MIN_TOKENS:
        return 0.0
    if (a.routine or b.routine) and (
            a.docs[0].day != b.docs[0].day or abs(timeutil.hours_between(a.first, b.first)) > ROUTINE_MAX_HOURS):
        return 0.0
    if a.outlets == b.outlets and len(a.outlets) == 1:
        # One newsroom on both sides: series instalments look alike, so compare headline by headline.
        return max(similarity(x, y, weights) for x in a.docs for y in b.docs)
    score = centroid_cosine(a.centroid(), b.centroid(), weights)
    if a.direction * b.direction < 0:
        score *= OPPOSITE_DIRECTION_FACTOR
    a_anchors, b_anchors = a.anchors, b.anchors
    if a_anchors and b_anchors and a_anchors.isdisjoint(b_anchors):
        score *= DIFFERENT_SUBJECT_FACTOR
    return score * _time_factor(gap)


def _join_margin(doc, story, weights):
    """By how much ``doc`` clears the bar for joining ``story`` (negative: it does not).

    Two views, each with its own bar: the closest members, and, once a story
    has enough members for a centroid to mean something, the story as a whole.
    """
    margin = story.member_score(doc, weights) - JOIN_THRESHOLD
    if len(story.docs) >= CENTROID_MIN_DOCS:
        alone = _Story(None, True)
        alone.add(doc)
        margin = max(margin, story_similarity(alone, story, weights) - CENTROID_THRESHOLD)
    return margin


def _merge_threshold(a, b):
    """The centroid similarity two stories need to be merged: lower when one has a real centroid."""
    established = max(len(a.docs), len(b.docs)) >= CENTROID_MIN_DOCS
    return CENTROID_THRESHOLD if established else MERGE_THRESHOLD


class _Index:
    """Informative token or exact headline -> stories that contain it."""

    def __init__(self, weights):
        self._weights = weights
        self._by_key = defaultdict(set)

    def _keys(self, doc):
        keys = {token for token in doc.tokens if self._weights.idf(token) >= INDEX_MIN_IDF}
        keys.add("=" + doc.norm)
        keys.update("=" + alt for alt in doc.alts)
        return keys

    def add(self, doc, story_id):
        for key in self._keys(doc):
            self._by_key[key].add(story_id)

    def candidates(self, doc):
        found = set()
        for key in self._keys(doc):
            found |= self._by_key.get(key, set())
        return found


def empty_state():
    """The shape of ``state/clusters.json``: item -> story, and each story's fixed day."""
    return {"items": {}, "stories": {}}


def _load_stories(docs, state, live_days, index):
    """Rebuild the live stories from recorded assignments; returns (stories, unassigned docs in time order)."""
    stories, pending = {}, []
    for doc in sorted(docs, key=lambda d: (d.time, d.id)):
        story_id = state["items"].get(doc.id)
        if story_id is None:
            pending.append(doc)
        elif state["stories"].get(story_id, {}).get("day") in live_days:
            stories.setdefault(story_id, _Story(story_id, False)).add(doc)
            index.add(doc, story_id)
    return stories, pending


def _place(doc, stories, index, state, weights):
    """Put one doc into its best story above the threshold, or seed a new story with it."""
    best_id, best_margin = None, 0.0
    for story_id in sorted(index.candidates(doc)):
        story = stories[story_id]
        if story.open_to(doc):
            margin = _join_margin(doc, story, weights)
            if margin > best_margin:
                best_id, best_margin = story_id, margin
    if best_id is None:
        best_id = textutil.stable_id("s", doc.id)
        state["stories"][best_id] = {"day": doc.day}
        stories[best_id] = _Story(best_id, True)
    state["items"][doc.id] = best_id
    stories[best_id].add(doc)
    index.add(doc, best_id)


def _merge_pairs(stories, weights):
    """(margin, kept id, absorbed id) for every pair worth merging in which a story is fresh.

    A published story always survives; between two fresh stories the one seeded
    first does. Pairs are found through shared centroid tokens, skipping tokens
    so common that they would pair everything with everything.
    """
    by_token = defaultdict(list)
    for story_id, story in stories.items():
        for token in story.counts:
            by_token[token].append(story_id)
    seen, pairs = set(), []
    for token, ids in by_token.items():
        if len(ids) < 2 or len(ids) > MERGE_MAX_POSTINGS:
            continue
        for index, first_id in enumerate(ids):
            for second_id in ids[index + 1:]:
                pair = (first_id, second_id) if first_id < second_id else (second_id, first_id)
                if pair in seen:
                    continue
                seen.add(pair)
                a, b = stories[pair[0]], stories[pair[1]]
                if not (a.fresh or b.fresh):
                    continue
                margin = story_similarity(a, b, weights) - _merge_threshold(a, b)
                if margin >= 0.0:
                    keep, gone = sorted((a, b), key=lambda story: (story.fresh, story.first, story.id))
                    pairs.append((margin, keep.id, gone.id))
    return pairs


def _merge_fresh(stories, state, weights):
    """Fold stories created in this run into the story they turned out to belong to.

    Taking items one at a time fragments a breaking story: two outlets word it
    differently, each seeds a story, and later items split between them. Once
    both halves have a few members their centroids agree, and since a fresh
    story's id has never been published, merging it breaks no promise.
    Returns the number of stories absorbed.
    """
    absorbed = 0
    while True:
        pairs = sorted(_merge_pairs(stories, weights), reverse=True)
        touched = set()
        for _margin, keep_id, gone_id in pairs:
            if keep_id in touched or gone_id in touched:
                continue
            touched.update((keep_id, gone_id))
            gone = stories.pop(gone_id)
            for doc in gone.docs:
                stories[keep_id].add(doc)
                state["items"][doc.id] = keep_id
            del state["stories"][gone_id]
            absorbed += 1
        if not touched:
            return absorbed


def assign(docs, state, live_days, weights=None):
    """Give every unassigned doc a story, mutating ``state``; returns the number of new stories.

    ``docs`` are all items in play (assigned or not); ``live_days`` are the
    local dates whose story files are still rewritten. A doc may join only a
    story filed on a live day; a recorded assignment is never changed. Docs
    are taken in time order so that a story's seed is its earliest item, then
    the stories seeded in this run are merged where they belong together.
    """
    weights = weights or Weights(docs)
    index = _Index(weights)
    stories, pending = _load_stories(docs, state, set(live_days), index)
    known = len(stories)
    for doc in pending:
        _place(doc, stories, index, state, weights)
    seeded = len(stories) - known
    absorbed = _merge_fresh(stories, state, weights)
    log.debug("clustering: %d docs, %d unassigned, %d stories seeded, %d of them merged away",
              len(docs), len(pending), seeded, absorbed)
    return seeded - absorbed


def prune(state, keep_from_day):
    """Forget stories filed before ``keep_from_day`` and their items, so the state file stays small."""
    gone = {story_id for story_id, meta in state["stories"].items() if meta.get("day", "") < keep_from_day}
    if not gone:
        return 0
    state["stories"] = {story_id: meta for story_id, meta in state["stories"].items() if story_id not in gone}
    state["items"] = {item_id: story_id for item_id, story_id in state["items"].items() if story_id not in gone}
    return len(gone)
