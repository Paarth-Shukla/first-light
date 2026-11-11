"""Google News sitemaps (kind ``sitemap-news``), used for Moneycontrol.

Moneycontrol's RSS is dead (HTML pages), but its news sitemap lists every
article of the last week with a title, an exact publication time and an
image. It covers the whole site (city news, sport...), so the source's
``urlPattern`` keeps the business paths. There is no summary text.
"""

from .. import feeds

SITEMAP = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
NEWS = "{http://www.google.com/schemas/sitemap-news/0.9}"
IMAGE = "{http://www.google.com/schemas/sitemap-image/1.1}"


def entries_from(body):
    """Raw entries from a ``<urlset>`` news sitemap."""
    root = feeds.xml_root(body)
    if root.tag != SITEMAP + "urlset":
        raise feeds.FeedError("not a sitemap <urlset>")
    entries = []
    for url in root.findall(SITEMAP + "url"):
        news = url.find(NEWS + "news")
        if news is None:
            continue
        entries.append({
            "title": news.findtext(NEWS + "title") or "",
            "link": (url.findtext(SITEMAP + "loc") or "").strip(),
            "published": (news.findtext(NEWS + "publication_date") or "").strip(),
            "image": (url.findtext(IMAGE + "image/" + IMAGE + "loc") or "").strip() or None,
        })
    if not entries:
        raise feeds.FeedError("sitemap has no news entries")
    return entries


def fetch_items(source, ctx):
    """Items from a news sitemap, filtered by the source's ``urlPattern``."""
    body = ctx.get(source["url"])
    if body is None:
        return []
    return feeds.build_items(entries_from(body), source, ctx.now)
