"""Hugging Face blog JSON (kind ``json:hf-blog``).

The RSS feed has no descriptions or images; ``/api/blog`` has thumbnails and
marks Hugging Face's own posts (``canonical: true``, one path segment) apart
from organisation posts (``/blog/<org>/<slug>``), which are kept out because
they are vendor marketing more often than news.
"""

from .. import feeds

BASE = "https://huggingface.co"


def is_official(post):
    """Hugging Face's own posts: ``/blog/<slug>``, not ``/blog/<org>/<slug>``."""
    url = str(post.get("url") or "")
    return url.startswith("/blog/") and url.count("/") == 2


def entries_from(payload):
    """Raw entries for the official posts in an ``/api/blog`` response."""
    posts = payload.get("allBlogs") if isinstance(payload, dict) else None
    if not isinstance(posts, list):
        raise feeds.FeedError("Hugging Face blog response has no allBlogs list")
    return [{
        "title": post.get("title"),
        "link": BASE + post["url"],
        "published": post.get("publishedAt"),
        "image": feeds.usable_image(post.get("thumbnail"), BASE + "/"),
    } for post in posts if isinstance(post, dict) and is_official(post)]


def fetch_items(source, ctx):
    """Recent official Hugging Face blog posts."""
    payload = ctx.json(source["url"])
    if payload is None:
        return []
    return feeds.build_items(entries_from(payload), source, ctx.now)
