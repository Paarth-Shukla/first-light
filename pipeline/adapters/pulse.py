"""Zerodha Pulse (kind ``rss:pulse``): an aggregator of Indian business news.

Its links go straight to the original publishers (NDTV Profit, The Hindu,
Business Standard, ...), which makes it the best route to outlets that block
scripted clients themselves. The feed names no publisher, so it is derived
from the link's host.
"""

import urllib.parse

from .. import feeds

PUBLISHERS = {
    "ndtvprofit.com": "NDTV Profit",
    "thehindu.com": "The Hindu",
    "thehindubusinessline.com": "BusinessLine",
    "business-standard.com": "Business Standard",
    "economictimes.indiatimes.com": "The Economic Times",
    "timesofindia.indiatimes.com": "The Times of India",
    "livemint.com": "Mint",
    "moneycontrol.com": "Moneycontrol",
    "financialexpress.com": "Financial Express",
    "cnbctv18.com": "CNBC-TV18",
    "businesstoday.in": "Business Today",
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "indianexpress.com": "The Indian Express",
    "hindustantimes.com": "Hindustan Times",
}


def publisher_for(url):
    """A readable outlet name for a link: known hosts by name, others by bare domain."""
    host = (urllib.parse.urlsplit(url or "").hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    for domain, name in PUBLISHERS.items():
        if host == domain or host.endswith("." + domain):
            return name
    return host or None


def fetch_items(source, ctx):
    """Items from the Pulse feed, each credited to its original publisher."""
    body = ctx.get(source["url"])
    if body is None:
        return []
    kind, root = feeds.document(body)
    entries = [feeds.entry_fields(element, kind) for element in feeds.entry_elements(kind, root)]
    if not entries:
        raise feeds.FeedError("feed has no items")
    for entry in entries:
        entry["publisher"] = publisher_for(entry["link"])
    return feeds.build_items(entries, source, ctx.now)
