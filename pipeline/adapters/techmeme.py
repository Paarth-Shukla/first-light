"""Techmeme (kind ``rss:techmeme``): an editor-curated list of the day's top tech stories.

The feed is RSS, but every useful field is in the wrong place: ``<link>`` is a
techmeme.com permalink and the article URL is the first ``<A HREF>`` in the
description; the title ends in ``(Author/Publisher)``; the description is
UPPERCASE HTML holding ``Author / <A>Publisher</A>:`` then the headline then
`` — `` and a teaser; the only image is plain http (unusable on https).
"""

import re

from .. import feeds
from ..core import textutil

_FIRST_HREF = re.compile(r"<a\b[^>]*\bhref\s*=\s*[\"']([^\"']+)[\"']", re.I)
_PUBLISHER_ANCHOR = re.compile(r"<a\b[^>]*>([^<]{1,80})</a>\s*:\s*<br", re.I)
_BYLINE_TAIL = re.compile(r"\s*\(([^()]{1,80})\)\s*$")
_TEASER = re.compile(r"</span>(.*)$", re.I | re.S)


def article_url(description):
    """The real article URL: the first href in the description."""
    match = _FIRST_HREF.search(description or "")
    return match.group(1).strip() if match else ""


def split_title(title):
    """``"Headline (Author/Publisher)"`` -> ``("Headline", "Publisher")``."""
    match = _BYLINE_TAIL.search(title)
    if not match:
        return title, None
    byline = match.group(1)
    return title[:match.start()].rstrip(), byline.rsplit("/", 1)[-1].strip() or None


def teaser(description):
    """The publisher's teaser that follows the bold headline, without the leading dash."""
    match = _TEASER.search(description or "")
    if not match:
        return ""
    return textutil.clean_text(match.group(1)).lstrip(" —–-").strip()


def _entry(element, kind):
    """One Techmeme item, re-pointed at the article it is about."""
    entry = feeds.entry_fields(element, kind)
    description = entry["summary"]
    title, publisher = split_title(textutil.clean_text(entry["title"]))
    anchor = _PUBLISHER_ANCHOR.search(description or "")
    entry.update({
        "title": title,
        "link": article_url(description) or entry["link"],
        "publisher": textutil.clean_text(anchor.group(1)) if anchor else publisher,
        "summary": teaser(description),
        "content": "",
    })
    return entry


def fetch_items(source, ctx):
    """Items from the Techmeme feed."""
    body = ctx.get(source["url"])
    if body is None:
        return []
    kind, root = feeds.document(body)
    elements = feeds.entry_elements(kind, root)
    if not elements:
        raise feeds.FeedError("feed has no items")
    return feeds.build_items([_entry(element, kind) for element in elements], source, ctx.now)
