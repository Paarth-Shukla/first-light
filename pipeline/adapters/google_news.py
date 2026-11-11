"""Google News RSS (kind ``google-news``): top stories, topic pages and searches.

Google News is the only route to Reuters and AP, and its top/topic items are
already clustered: each description lists other outlets covering the same
story, which becomes ``alt`` (a coverage signal for ranking). Quirks handled:

* the title ends in `` - Publisher``; the publisher is also in ``<source>``,
  so the tail is cut using that text rather than guessed;
* links are opaque news.google.com tokens that cannot be resolved without
  JavaScript, so they are kept exactly as given;
* there is no real summary (the description is the outlet list) and no image;
* finance searches are flooded by ticker-spam sites, which are dropped.
"""

import re

from .. import feeds
from ..core import textutil

# Seen dominating entity and market searches with machine-written ticker notes or
# "1 unstoppable stock to buy" promotion. Compared after _publisher_key().
SPAM_PUBLISHERS = frozenset((
    "tradingview", "benzinga", "marketscreener", "biggo finance", "marketbeat",
    "stocktitan", "stock titan", "gurufocus", "ainvest", "simply wall st",
    "zacks investment research", "zacks", "stocktwits", "moomoo", "tipranks",
    "intellectia ai", "kalkine media", "trefis", "insider monkey", "the motley fool",
    "motley fool", "chartmill", "24/7 wall st", "seeking alpha", "fourweekmba",
))
_DOMAIN_SUFFIX = re.compile(r"\.(?:com|net|org|co|io|in)$")
# SEO pieces that searches for a company or a market pull in from any publisher.
_SPAM_TITLE = re.compile(r"\bprice predictions?\b|\b(?:stocks?|shares) to buy\b", re.I)
MAX_ALT = 8

_OUTLET = re.compile(r"<a\b[^>]*>(.*?)</a>(?:\s|&nbsp;|\xa0)*<font\b[^>]*>(.*?)</font>", re.I | re.S)
_DASH_TAIL = re.compile(r"\s+[-–—]\s+([^-–—]{1,60})$")
# Publishers put a desk name before their own: "Headline | India News - Hindustan Times".
_SECTION_TAIL = re.compile(r"\s+\|\s+([A-Z][^|]{0,30})$")


def _without_section(title):
    """Drop a trailing `` | Desk`` (at most four words) from a headline of four or more words."""
    match = _SECTION_TAIL.search(title)
    if match and len(match.group(1).split()) <= 4 and len(title[:match.start()].split()) >= 4:
        return title[:match.start()].rstrip()
    return title


def split_title(title, publisher):
    """``"Headline | Desk - Publisher"`` -> ``("Headline", "Publisher")``.

    The ``<source>`` text is trusted when present; otherwise a short tail after
    the last dash is taken as the publisher.
    """
    if publisher:
        for dash in (" - ", " – ", " — "):
            suffix = dash + publisher
            if title.lower().endswith(suffix.lower()) and len(title) > len(suffix):
                return _without_section(title[:-len(suffix)].rstrip()), publisher
        return _without_section(title), publisher
    match = _DASH_TAIL.search(title)
    if match and len(match.group(1).split()) <= 5 and len(title[:match.start()].split()) >= 3:
        return _without_section(title[:match.start()].rstrip()), match.group(1).strip()
    return _without_section(title), None


def _publisher_key(publisher):
    """"MarketScreener.com", "www.marketscreener.com" and "24/7 Wall St." compare alike."""
    key = (publisher or "").strip().lower().rstrip(".")
    if key.startswith("www."):
        key = key[4:]
    return _DOMAIN_SUFFIX.sub("", key)


def is_spam(publisher):
    """True for the ticker-note mills that drown out real finance coverage."""
    return _publisher_key(publisher) in SPAM_PUBLISHERS


def alternatives(description, title, publisher):
    """Other outlets' headlines from the clustered description, without the item itself."""
    alt, seen = [], {textutil.norm_title(title) + "|" + (publisher or "").lower()}
    for raw_title, raw_publisher in _OUTLET.findall(description or ""):
        other_title = textutil.clean_text(raw_title)
        other_publisher = textutil.clean_text(raw_publisher)
        key = textutil.norm_title(other_title) + "|" + other_publisher.lower()
        if not other_title or not other_publisher or key in seen or is_spam(other_publisher):
            continue
        seen.add(key)
        alt.append({"title": other_title, "publisher": other_publisher})
    return alt[:MAX_ALT]


def _entry(element, kind):
    """One Google News item as a raw entry, or None for a spam publisher or headline."""
    entry = feeds.entry_fields(element, kind)
    publisher = textutil.clean_text(element.findtext("source")) or None
    title, publisher = split_title(textutil.clean_text(entry["title"]), publisher)
    if is_spam(publisher) or _SPAM_TITLE.search(title):
        return None
    entry.update({
        "title": title,
        "publisher": publisher,
        "alt": alternatives(entry["summary"], title, publisher),
        "summary": "",
        "content": "",
        "image": None,
    })
    return entry


def fetch_items(source, ctx):
    """Items from one Google News RSS URL."""
    body = ctx.get(source["url"])
    if body is None:
        return []
    kind, root = feeds.document(body)
    elements = feeds.entry_elements(kind, root)
    if not elements:
        raise feeds.FeedError("feed has no items")
    entries = [entry for entry in (_entry(element, kind) for element in elements) if entry]
    return feeds.build_items(entries, source, ctx.now)
