"""Source adapters: one small module per source ``kind`` in config/sources.json.

Every adapter exposes ``fetch_items(source, ctx) -> list of items`` and raises
``feeds.FeedError`` (or lets ``net.NetError`` through) when the source gave
nothing usable. ``ctx`` is the fetch stage's per-source context:

    ctx.now            aware UTC datetime of the run
    ctx.get(url)       body bytes, or None when the server answered 304
    ctx.json(url)      decoded JSON, or None on 304

so adapters never touch the network, the HTTP cache or politeness themselves,
and tests can hand them a stub.
"""

from . import anthropic, google_news, hf_blog, hn, pulse, rss, sitemap_news, snapi, techmeme

ADAPTERS = {
    "rss": rss.fetch_items,
    "rss:techmeme": techmeme.fetch_items,
    "rss:pulse": pulse.fetch_items,
    "google-news": google_news.fetch_items,
    "hn": hn.fetch_items,
    "html:anthropic": anthropic.fetch_items,
    "json:snapi": snapi.fetch_items,
    "json:hf-blog": hf_blog.fetch_items,
    "sitemap-news": sitemap_news.fetch_items,
}
