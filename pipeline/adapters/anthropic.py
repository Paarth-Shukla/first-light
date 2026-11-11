"""Anthropic and Claude first-party listings (kind ``html:anthropic``).

anthropic.com (/news, /research, /engineering) and claude.com
(/resources/product-updates) publish no feed. Both are Next.js App Router
sites whose pages embed the CMS records as React Server Component chunks:
``self.__next_f.push([1,"<JSON string>"])``. Decoding and joining the chunks
gives a payload in which every record starts with ``{"_id":"``; each is
decoded in place and walked for article-shaped objects:

* anthropic.com: ``_type == "article"`` with ``publishedOn`` (YYYY-MM-DD),
  ``slug.current``, ``title``, ``articleType`` (the URL section), optional
  ``summary``/``seoDescription``, ``cardImage``/``hero`` and ``linkedUrl``;
* claude.com: ``_type == "blogPost"`` with ``date``, ``slug`` (a string),
  ``title``, ``excerpt``, optional ``externalUrl``; the article's Open Graph
  image is a raster rendition at a fixed path, unlike the SVG illustration.

This depends on build output, so any change in it must show up as a clear
failure in source health rather than as silently missing news.
"""

import json
import re

from .. import feeds

_CHUNK = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
_RECORD = re.compile(r'\{"_id":"')

ANTHROPIC = "https://www.anthropic.com/%s/%s"
CLAUDE_ARTICLE = "https://claude.com/resources/articles/%s"
CLAUDE_OG_IMAGE = "https://claude.com/resources/articles/%s/opengraph-image/og"


def rsc_payload(page):
    """Join the page's RSC string chunks; '' when the page has none."""
    parts = []
    for chunk in _CHUNK.findall(page):
        try:
            parts.append(json.loads('"' + chunk + '"'))
        except ValueError:
            continue  # one undecodable chunk only loses the records inside it
    return "".join(parts)


def records(payload):
    """Every dict reachable from a ``{"_id":...}`` record in the payload."""
    decoder = json.JSONDecoder()
    for match in _RECORD.finditer(payload):
        try:
            value, _ = decoder.raw_decode(payload, match.start())
        except ValueError:
            continue
        stack = [value]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                yield node
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)


def _image_url(*candidates):
    """The first candidate that is an object with a url."""
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate.get("url"):
            return candidate["url"]
    return None


def entry_for(record):
    """An article-shaped record as a raw entry, or None for anything else."""
    title = record.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    slug = record.get("slug")
    if record.get("_type") == "article" and isinstance(slug, dict) and record.get("publishedOn"):
        slug = slug.get("current")
        if not slug:
            return None
        return {
            "title": title,
            "link": record.get("linkedUrl") or ANTHROPIC % (record.get("articleType") or "news", slug),
            "summary": record.get("summary") or record.get("seoDescription") or "",
            "published": record["publishedOn"],
            "image": _image_url(record.get("cardImage"), record.get("hero")),
        }
    if record.get("_type") == "blogPost" and isinstance(slug, str) and slug and record.get("date"):
        return {
            "title": title,
            "link": record.get("externalUrl") or CLAUDE_ARTICLE % slug,
            "summary": record.get("excerpt") or "",
            "published": record["date"],
            "image": None if record.get("externalUrl") else CLAUDE_OG_IMAGE % slug,
        }
    return None


def entries_from(page):
    """Article entries from a listing page, one per link (the fullest record wins)."""
    payload = rsc_payload(page)
    if not payload:
        raise feeds.FeedError("no Next.js RSC payload in page (markup changed?)")
    best = {}
    for record in records(payload):
        entry = entry_for(record)
        if entry is None:
            continue
        richness = len(record)
        if entry["link"] not in best or richness > best[entry["link"]][0]:
            best[entry["link"]] = (richness, entry)
    if not best:
        raise feeds.FeedError("no articles found in the RSC payload (markup changed?)")
    return [entry for _, entry in best.values()]


def fetch_items(source, ctx):
    """Items from one anthropic.com or claude.com listing page."""
    body = ctx.get(source["url"])
    if body is None:
        return []
    return feeds.build_items(entries_from(body.decode("utf-8", errors="replace")), source, ctx.now)
