"""Ranking: six signals per story, a 0-100 score, and the reasons shown to the reader.

Every signal is 0..1 and means one thing:

* ``breadth``   how many newsrooms carry the story beyond the first, weighted by tier
                (three papers of record beat six blogs) and log-scaled; outlets known
                only through an aggregator count for less.
* ``tier``      the standing of the best outlet carrying it.
* ``recency``   exponential decay on the newest item (half-life in ``site.json``).
* ``velocity``  how many newsrooms picked it up within six hours of the first.
* ``attention`` Hacker News points and comments, log-scaled.
* ``editorial`` where editors put it: its position in curated front pages, best two averaged.

``score = 100 x (weighted sum) x quality``. ``quality`` is 1 for news and lower for
things that are not: promotions, live-blog shells, recurring bulletins, headlines with
nothing behind them. A first-party announcement (a lab's own post) has no second
outlet by nature, so it gets a floor on breadth and editorial instead of sinking.

``why`` turns the dominant signals into at most three short reasons.
"""

import math
import re

from .core import timeutil

VELOCITY_HOURS = 6.0
TIER_VALUE = {1: 1.0, 2: 0.6, 3: 0.3}
# What one more outlet adds to breadth, by tier.
OUTLET_WEIGHT = {1: 1.0, 2: 0.6, 3: 0.35}
# How much an outlet counts by how we know of it: "direct" from its own feed, "relayed" as the
# publisher of an aggregator's item (a headline and a link), "listed" in an aggregator's list of
# other coverage (a name only).
VIA_FACTOR = {"direct": 1.0, "relayed": 0.75, "listed": 0.5}
# Extra outlet weight at which breadth saturates (about nine good outlets).
BREADTH_FULL = 7.0
VELOCITY_FULL = 6.0
ATTENTION_FULL = 1000.0
# How fast an editorial slot loses value with its position in the feed, and what a slot is worth by tier.
EDITORIAL_DECAY = 0.9
EDITORIAL_TIER = {1: 1.0, 2: 0.8, 3: 0.6}
# Floors for a first-party post: together worth about what three more small outlets would add,
# so an uncovered announcement tops the single-source items without burying covered stories.
FIRST_PARTY_BREADTH = 0.1
FIRST_PARTY_EDITORIAL = 0.2
QUALITY = {"promo": 0.35, "live": 0.6, "recurring": 0.4, "thin": 0.6, "foreign": 0.3}
RISING_MAX_AGE_HOURS = 12.0

_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
# A full date in a headline marks a dated bulletin ("Money Market Operations as on November 10, 2026").
_DATE = (r"(?:\d{1,2}(?:st|nd|rd|th)? " + _MONTH + r",? 20\d\d|" + _MONTH + r" \d{1,2}(?:st|nd|rd|th)?,? 20\d\d"
         r"|20\d\d " + _MONTH + r" \d{1,2}|\d{1,2}/\d{1,2}/20\d\d)")

# Headline templates. Order matters: the first match names the template.
_TEMPLATES = (
    ("promo", re.compile(
        r"\b(?:best|top|early|flash|app|holiday|weekend|today['’]?s)\b[^.;:]{0,50}\bdeals\b"
        r"|\bdeals? (?:event|roundup|of the (?:day|week))\b|\bblack friday\b|\bcyber monday\b|\bprime day\b"
        r"|\b\d+% off\b|\bcoupons?\b|\bpromo codes?\b|\bgift guide\b|\bhow to watch\b|\bwhere to watch\b"
        r"|\bsponsored\b|\bgiveaway\b|\bfreebies\b|\bpartner content\b", re.I)),
    ("live", re.compile(
        r"\blive (?:updates?|blog|news|coverage)\b|\b(?:live|highlights)\s*[:|]|[-–—:|]\s*(?:\w+ )?live$"
        r"|^live\b|\bas it happened\b", re.I)),
    ("recurring", re.compile(
        r"\bhoroscope\b|\bstocks? to (?:watch|buy|sell)\b|\bbuy or sell\b|\bstocks? in (?:news|focus)\b"
        r"|\btrade setup\b|\b(?:daily|morning|evening|weekly) (?:briefing|brief|digest|roundup|wrap|newswrap)\b"
        r"|\bnews ?wrap\b|\bnewsletter\b|\bpodcast\b|\bquiz\b|\bwordle\b|\bquordle\b|\bcrossword\b"
        r"|\blottery\b|\bresults? today\b|\b(?:gold|silver|petrol|diesel) (?:rate|price)s? today\b"
        r"|\bweather (?:today|update|forecast)\b|\baqi today\b|^apod\b|\bblog review\b|\bthings to (?:know|watch)\b"
        r"|\bwhat to watch\b|\bin pictures\b|\bphotos of the (?:day|week)\b|\b9to5\w+ daily\b"
        r"|\bscores?,? (?:&|and)? ?(?:daily )?(?:news|stats)\b|\bnews,? stats,? (?:&|and) scores\b"
        r"|\bshare price highlights\b|\bbroker['’]?s call\b|^firstft\b|\bblog, sols?\b"
        # Routine notices from central banks and regulators.
        r"|\bauction results?\b|\bauction of (?:government|state)\b|\bmoney market operations\b"
        r"|\bconversion/switch\b|\breserve money\b|\bcertificate of registration\b"
        r"|\bapproval of (?:two |three )?applications?\b|\b" + _DATE + r"\b", re.I)),
    ("wrap", re.compile(
        r"\b(?:closing|opening) bell\b|\bmarket (?:wrap|today|live|highlights|update|recap|outlook|close)\b"
        r"|\b(?:stock|share) markets? (?:today|live|highlights|updates?|close|end)\b|\bpre-?market\b"
        r"|\b(?:sensex|nifty|gift nifty|dow|nasdaq|s&p 500|wall street|d-street|dalal street|stocks|markets"
        r"|ftse|nikkei|hang seng|asian shares|european shares)\b.{0,60}\b(?:clos\w+|ends?|ended|settles?|settled"
        r"|opens?|opened|today|futures)\b", re.I)),
)
# Templates that repeat every day with near-identical wording; clustering keeps them inside one day.
RECURRING_TEMPLATES = frozenset(("live", "recurring", "wrap"))
_LETTER = re.compile(r"[^\W\d_]")


def template(title):
    """The recurring shape a headline follows: "promo", "live", "recurring", "wrap", or None for news."""
    for name, pattern in _TEMPLATES:
        if pattern.search(title or ""):
            return name
    return None


def is_market_wrap(story):
    """True for the daily "markets closed higher" story, which should not lead the paper on a news day."""
    return template(story.get("title")) == "wrap"


def _mostly_foreign(title):
    """True when most letters of a headline are outside Latin script: not readable in an English paper."""
    letters = _LETTER.findall(title or "")
    return bool(letters) and 2 * sum(1 for letter in letters if ord(letter) > 0x24F) > len(letters)


def quality(title, summary):
    """(multiplier 0..1, reason or None): how much of a real news story this headline is.

    Promotions, bulletins that recur daily, live-blog shells and headlines in
    another script are marked down; so is a very short headline with no
    summary, which gives a reader nothing to go on. Market wraps are news.
    """
    if _mostly_foreign(title):
        return QUALITY["foreign"], "foreign"
    name = template(title)
    if name in QUALITY:
        return QUALITY[name], name
    if not (summary or "").strip() and len((title or "").split()) < 5:
        return QUALITY["thin"], "thin"
    return 1.0, None


# ---------------------------------------------------------------- signals

def _log_scale(value, full):
    """0 at 0, 1 at ``full``, logarithmic in between and capped."""
    if value <= 0:
        return 0.0
    return min(1.0, math.log1p(value) / math.log1p(full))


def breadth(outlets):
    """Corroboration: tier-weighted outlets beyond the strongest one, log-scaled.

    ``outlets`` is a list of ``{"tier", "via"}`` (see ``VIA_FACTOR``). One
    outlet alone scores 0 however good it is: breadth is about who else is
    reporting it.
    """
    weights = sorted((OUTLET_WEIGHT.get(outlet["tier"], OUTLET_WEIGHT[3])
                      * VIA_FACTOR.get(outlet.get("via"), 1.0) for outlet in outlets), reverse=True)
    return _log_scale(sum(weights[1:]), BREADTH_FULL)


def recency(updated_at, now, half_life_hours):
    """Exponential decay on the newest item; a timestamp in the future counts as now."""
    age = max(0.0, timeutil.hours_between(updated_at, now))
    return 0.5 ** (age / float(half_life_hours))


def velocity(arrivals):
    """Outlets gained within six hours of the first one, log-scaled.

    ``arrivals`` holds each outlet's first publication time. Measured from the
    story's own start, so it describes how fast it broke, not how old it is.
    """
    if not arrivals:
        return 0.0
    start = min(arrivals)
    early = sum(1 for when in arrivals if timeutil.hours_between(start, when) <= VELOCITY_HOURS)
    return _log_scale(early - 1, VELOCITY_FULL)


def attention(points, comments):
    """Hacker News interest: points plus half the comments, log-scaled to 1000."""
    return _log_scale((points or 0) + 0.5 * (comments or 0), ATTENTION_FULL)


def editorial(placements):
    """Editors' judgment: the best two curated-feed slots, averaged.

    ``placements`` is a list of ``(tier, feedRank)``, one per outlet. Slot 0 of
    a tier-1 front page is worth 1.0 and decays 10% per position; one slot
    alone therefore tops out at 0.5, two front pages agreeing reach 1.0.
    """
    values = sorted((EDITORIAL_TIER.get(tier, EDITORIAL_TIER[3]) * EDITORIAL_DECAY ** rank
                     for tier, rank in placements), reverse=True)
    return sum(values[:2]) / 2.0


def signals(facts, now, half_life_hours):
    """The six signals for one story, each rounded to three places.

    ``facts`` is what ``process`` gathered from the members:
    ``outlets`` [{"tier", "via"}], ``bestTier``, ``updatedAt`` (datetime),
    ``arrivals`` [datetime per outlet], ``points``, ``comments``,
    ``placements`` [(tier, feedRank)], ``firstParty`` (bool).
    """
    values = {
        "breadth": breadth(facts["outlets"]),
        "tier": TIER_VALUE.get(facts["bestTier"], TIER_VALUE[3]),
        "recency": recency(facts["updatedAt"], now, half_life_hours),
        "velocity": velocity(facts["arrivals"]),
        "attention": attention(facts.get("points"), facts.get("comments")),
        "editorial": editorial(facts["placements"]),
    }
    if facts.get("firstParty"):
        values["breadth"] = max(values["breadth"], FIRST_PARTY_BREADTH)
        values["editorial"] = max(values["editorial"], FIRST_PARTY_EDITORIAL)
    return {name: round(value, 3) for name, value in values.items()}


def score(signal_values, weights, quality_factor=1.0):
    """0..100: the weighted sum of the signals (weights normalised), times the quality factor."""
    total = sum(max(0.0, float(weight)) for weight in weights.values())
    if total <= 0:
        raise ValueError("ranking weights must sum to a positive number")
    blended = sum(max(0.0, float(weight)) * signal_values.get(name, 0.0) for name, weight in weights.items())
    return round(100.0 * blended / total * quality_factor, 1)


def by_score(stories):
    """Stories best first: by score, then the more recently updated, then id, so order is deterministic."""
    ordered = sorted(stories, key=lambda story: story["id"])
    ordered.sort(key=lambda story: story["updatedAt"], reverse=True)
    ordered.sort(key=lambda story: -story["score"])
    return ordered


# ---------------------------------------------------------------- reasons

def _join_names(names):
    """"BBC", "BBC and NYT", "BBC, NYT and DW"."""
    if len(names) <= 1:
        return "".join(names)
    return "%s and %s" % (", ".join(names[:-1]), names[-1])


def why(facts, signal_values, now):
    """At most three short reasons, strongest signal first.

    ``facts`` additionally carries ``sourceCount``, ``topSlots`` (names of
    outlets that put the story in their top three), ``firstAt`` (datetime) and
    ``threadDay`` (int or None).
    """
    reasons = []
    if facts.get("sourceCount", 1) >= 2:
        reasons.append((signal_values["breadth"] + 0.3, "%d outlets" % facts["sourceCount"]))
    if facts.get("topSlots"):
        reasons.append((signal_values["editorial"] + 0.2, "top of %s" % _join_names(facts["topSlots"][:2])))
    if facts.get("firstParty"):
        reasons.append((0.75, "first-party source"))
    if (facts.get("points") or 0) >= 50:
        reasons.append((signal_values["attention"], "%d points on Hacker News" % facts["points"]))
    age = timeutil.hours_between(facts["firstAt"], now)
    if signal_values["velocity"] >= 0.5 and age <= RISING_MAX_AGE_HOURS:
        reasons.append((signal_values["velocity"] - 0.1, "rising"))
    if (facts.get("threadDay") or 1) >= 2:
        reasons.append((0.45, "day %d" % facts["threadDay"]))
    reasons.sort(key=lambda reason: -reason[0])
    return [text for _strength, text in reasons[:3]]
