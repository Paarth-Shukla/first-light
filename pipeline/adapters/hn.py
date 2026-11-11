"""Hacker News through the Algolia API (kind ``hn``).

Two uses, both configured by the source URL alone:

* the front page (``search?tags=front_page``), whose points and comment
  counts are an attention signal for ranking;
* a keyword search (``search_by_date?query=Claude&tags=story&numericFilters=points>100``).
  Algolia matches author names and treats ``OR`` as a word, so each source
  queries one keyword and hits are kept only when the title contains it.

The link is the article; Ask HN and other text posts have no URL and link to
the HN thread instead.
"""

import re
import urllib.parse

from .. import feeds

THREAD = "https://news.ycombinator.com/item?id=%s"


def keyword_filter(url):
    """A title matcher for the URL's ``query`` parameter (whole word, plural allowed:
    "LLM" matches "LLMs" but not "LLMOps"), or None for the front page."""
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("query", [""])[0].strip()
    if not query:
        return None
    return re.compile(r"(?<![a-z0-9])" + re.escape(query.lower()) + r"s?(?![a-z0-9])")


def _count(value):
    """Algolia sends ints, but a null or a string must not break ranking."""
    return value if isinstance(value, int) and value >= 0 else None


def entries_from(payload, matcher=None):
    """Raw entries from an Algolia search response."""
    hits = payload.get("hits") if isinstance(payload, dict) else None
    if not isinstance(hits, list):
        raise feeds.FeedError("Algolia response has no hits list")
    entries = []
    for hit in hits:
        if not isinstance(hit, dict) or not hit.get("title") or not hit.get("objectID"):
            continue
        if "job" in (hit.get("_tags") or []):
            continue  # YC hiring posts sit on the front page but are ads, not news
        title = str(hit["title"])
        if matcher is not None and not matcher.search(title.lower()):
            continue
        entries.append({
            "title": title,
            "link": hit.get("url") or THREAD % hit["objectID"],
            "published": hit.get("created_at") or hit.get("created_at_i"),
            "points": _count(hit.get("points")),
            "comments": _count(hit.get("num_comments")),
        })
    return entries


def fetch_items(source, ctx):
    """Items from one Algolia query; an empty hit list is reported as a failure."""
    payload = ctx.json(source["url"])
    if payload is None:
        return []
    entries = entries_from(payload, keyword_filter(source["url"]))
    if not entries and not payload.get("hits"):
        raise feeds.FeedError("Algolia returned no hits")
    return feeds.build_items(entries, source, ctx.now)
