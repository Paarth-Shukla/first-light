"""Threads: which of today's stories continue an event from an earlier day.

A story stops taking new items after 48 hours, so a trial, a war or an IPO
shows up as a new story every day or two. A thread ties those together: the
reader sees "day 3" and the earlier headlines, and the edition never prints
two instalments of one event side by side.

Linking is deliberately strict, because a wrong link is worse than none:

* Stories are compared as wholes: the centroid of every outlet's headline for
  the story, under IDF weights, so "Trump" or "Nifty" alone weighs little.
* Two stories link when they share a lexicon entity, their centroids are
  similar, and a fair part of that similarity comes from ordinary words, not
  from the entities themselves. Two different Tesla stories share ``@tesla``
  and nothing else, and stay apart.
* Events about things the lexicon does not know (a strike in Spain) may still
  link, on word similarity alone, at a much higher bar and with at least
  three words in common ("wrote" and "book" are not an event).
* Two stories that each come from the same single outlet face a higher bar
  still: a newsroom's series ("Treasury Bills: Full Auction Result") repeats
  its wording without being one event.
* A story links only to stories filed on earlier days, within 14 days.

``state/threads.json`` records story -> thread and, per thread, each member's
date, title and score, so ids are stable and history survives the pruning of
old story files. A thread's id is ``stable_id("t", first story's id)``.
"""

from collections import defaultdict
from datetime import date, timedelta

from . import cluster, lexicon
from .core import log, textutil

WINDOW_DAYS = 14
# With a shared entity: minimum centroid similarity, and the least of it that words must carry.
LINK_THRESHOLD = 0.38
WORDS_THRESHOLD = 0.2
# Without a shared entity: minimum similarity of the words alone.
STRICT_THRESHOLD = 0.55
# Two single-outlet stories from one newsroom are usually instalments of a series, not one event.
SERIES_THRESHOLD = 0.6
HISTORY_MAX = 6
KEEP_DAYS = 45
# A token found in more stories than this proposes no candidates.
MAX_POSTINGS = 150


class Profile:
    """One story as the linker sees it: its day, entities and headline centroid."""

    __slots__ = ("story", "id", "day", "entities", "outlets", "tokens", "centroid", "words")

    def __init__(self, story):
        self.story = story
        self.id = story["id"]
        self.day = story["day"]
        self.entities = frozenset(story.get("entities") or [])
        self.outlets = frozenset(cluster.outlet_key(source.get("name")) for source in story.get("sources") or [])
        headlines = {story.get("title") or ""}
        headlines.update(source.get("title") or "" for source in story.get("sources") or [])
        headlines.discard("")
        counts = defaultdict(int)
        for headline in headlines:
            for token in cluster.text_tokens(headline, lexicon.match_entities(headline)):
                counts[token] += 1
        size = float(len(headlines) or 1)
        self.centroid = {token: count / size for token, count in counts.items()}
        self.words = {token: share for token, share in self.centroid.items()
                      if not token.startswith(cluster.ENTITY_PREFIX)}
        self.tokens = frozenset(counts)  # what cluster.Weights counts


def similarity(a, b, weights, link=LINK_THRESHOLD, words_share=WORDS_THRESHOLD, strict=STRICT_THRESHOLD):
    """How likely two stories are instalments of one event, 0..1; 0 when the rules forbid a link.

    The thresholds are parameters because the edition asks a looser question
    ("too alike to print side by side?") with the same measure.
    """
    full = cluster.centroid_cosine(a.centroid, b.centroid, weights)
    if len(a.outlets) == 1 and a.outlets == b.outlets:
        return full if full >= max(link, SERIES_THRESHOLD) and a.entities & b.entities else 0.0
    words = cluster.centroid_cosine(a.words, b.words, weights)
    if a.entities & b.entities and full >= link and words >= words_share:
        return full
    in_common = sum(1 for token in a.words if token in b.words)
    return words if words >= strict and in_common >= cluster.MIN_TOKENS else 0.0


def empty_state():
    """The shape of ``state/threads.json``."""
    return {"stories": {}, "threads": {}}


def _earliest(day):
    """The first day a story filed on ``day`` may link back to."""
    return (date.fromisoformat(day) - timedelta(days=WINDOW_DAYS)).isoformat()


def _best_earlier(profile, by_token, weights):
    """The most similar story from an earlier day within the window (the latest on a tie), or None."""
    earliest = _earliest(profile.day)
    seen, scored = set(), []
    for token in profile.tokens:
        postings = by_token.get(token, ())
        if len(postings) > MAX_POSTINGS:
            continue
        for other in postings:
            if other.id in seen or not earliest <= other.day < profile.day:
                continue
            seen.add(other.id)
            score = similarity(profile, other, weights)
            if score > 0.0:
                scored.append((score, other.day, other.id, other))
    return max(scored, key=lambda entry: entry[:3])[3] if scored else None


def _record(state, thread_id, story):
    """Add or refresh a story's entry in its thread (titles and scores move while a story is live)."""
    state["stories"][story["id"]] = thread_id
    state["threads"].setdefault(thread_id, {})[story["id"]] = {
        "date": story["day"], "title": story.get("title") or "", "score": story.get("score") or 0.0}


def _thread_field(state, story):
    """The public ``thread`` object for a story in a thread: id, 1-based day, earlier instalments."""
    thread_id = state["stories"][story["id"]]
    members = state["threads"][thread_id]
    first = min(member["date"] for member in members.values())
    per_day = {}
    for story_id, member in members.items():
        if member["date"] < story["day"]:
            kept = per_day.get(member["date"])
            if kept is None or (member["score"], story_id) > (kept[1]["score"], kept[0]):
                per_day[member["date"]] = (story_id, member)
    history = [{"date": day, "id": per_day[day][0], "title": per_day[day][1]["title"]}
               for day in sorted(per_day)][-HISTORY_MAX:]
    number = (date.fromisoformat(story["day"]) - date.fromisoformat(first)).days + 1
    return {"id": thread_id, "day": number, "history": history}


def prune(state, today):
    """Drop members older than ``KEEP_DAYS`` and threads left empty; returns how many stories went."""
    cutoff = (date.fromisoformat(today) - timedelta(days=KEEP_DAYS)).isoformat()
    gone = 0
    for thread_id in list(state["threads"]):
        members = state["threads"][thread_id]
        for story_id in [story_id for story_id, member in members.items() if member["date"] < cutoff]:
            del members[story_id]
            state["stories"].pop(story_id, None)
            gone += 1
        if not members:
            del state["threads"][thread_id]
    return gone


def link(live, archive, state):
    """Set ``story["thread"]`` on every live story, extending ``state``; returns how many are threaded.

    ``live`` are the stories being written this run; ``archive`` are stories
    from frozen day files of the last two weeks. A live story already in a
    thread keeps it. One that is not is linked to its best earlier story, if
    any passes the rules, joining that story's thread or starting one rooted
    at it; the root gets the thread too when its file is still live.
    """
    live_ids = {story["id"] for story in live}
    profiles = [Profile(story) for story in live]
    profiles += [Profile(story) for story in archive if story["id"] not in live_ids]
    weights = cluster.Weights(profiles)
    by_token = defaultdict(list)
    for profile in profiles:
        for token in profile.tokens:
            by_token[token].append(profile)
    by_id = {profile.id: profile for profile in profiles}
    linked = 0
    for story in sorted(live, key=lambda s: (s["day"], s.get("publishedAt") or "", s["id"])):
        if story["id"] in state["stories"]:
            continue
        earlier = _best_earlier(by_id[story["id"]], by_token, weights)
        if earlier is None:
            continue
        thread_id = state["stories"].get(earlier.id)
        if thread_id is None:
            thread_id = textutil.stable_id("t", earlier.id)
            _record(state, thread_id, earlier.story)
        _record(state, thread_id, story)
        linked += 1
    threaded = 0
    for story in live:
        thread_id = state["stories"].get(story["id"])
        if thread_id is not None and thread_id in state["threads"]:
            _record(state, thread_id, story)
            story["thread"] = _thread_field(state, story)
            threaded += 1
        else:
            story["thread"] = None
    log.debug("threads: %d live stories, %d newly linked, %d in a thread", len(live), linked, threaded)
    return threaded
