"""Spaceflight News API v4 (kind ``json:snapi``).

One call covers NASA, SpaceNews, NASASpaceflight, Spaceflight Now, ESA, Ars
and more; ``news_site`` names the outlet, so it becomes ``publisher``. The
request asks only for the source's age window (``published_at_gte``).
"""

import urllib.parse
from datetime import timedelta

from .. import feeds
from ..core import timeutil


def request_url(source, now):
    """The source URL with the age window added as ``published_at_gte``."""
    since = now - timedelta(hours=float(source.get("maxAgeHours", 48)))
    parts = urllib.parse.urlsplit(source["url"])
    query = [pair for pair in urllib.parse.parse_qsl(parts.query) if pair[0] != "published_at_gte"]
    query.append(("published_at_gte", timeutil.iso(since)))
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def entries_from(payload):
    """Raw entries from a SNAPI ``articles`` response."""
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        raise feeds.FeedError("SNAPI response has no results list")
    return [{
        "title": article.get("title"),
        "link": article.get("url"),
        "summary": article.get("summary") or "",
        "published": article.get("published_at"),
        "image": article.get("image_url"),
        "publisher": article.get("news_site"),
    } for article in results if isinstance(article, dict)]


def fetch_items(source, ctx):
    """Recent spaceflight articles; an empty window is not an error (quiet days happen)."""
    payload = ctx.json(request_url(source, ctx.now))
    if payload is None:
        return []
    return feeds.build_items(entries_from(payload), source, ctx.now)
