"""Plain RSS 2.0, Atom and RDF feeds (kind ``rss``): fetch the URL, parse with ``feeds``."""

from .. import feeds


def fetch_items(source, ctx):
    """Items from one feed URL; an unchanged feed (304) yields nothing new."""
    body = ctx.get(source["url"])
    if body is None:
        return []
    return feeds.parse(body, source, ctx.now)
