"""Turn feed documents into First Light items (``state/items`` shape, docs/ARCHITECTURE.md).

Three formats occur in the wild and the URL never tells you which: RSS 2.0
(``<rss><channel><item>``), Atom (``<feed><entry>``) and RDF / RSS 1.0
(``<rdf:RDF>`` with ``<item>`` as children of the *root*). The root tag
decides. Every quirk handled here was seen in a real feed during source
research (docs/research/sources-2026-11-11.json): BOMs, declared non-UTF-8
encodings, unescaped ampersands, a missing space between attributes
(science.nasa.gov), HTML pages served with status 200, ``media:description``
captions that must not be mistaken for ``description``, empty
``media:content`` elements, avatar and tracking-pixel images, future dates,
archive-sized feeds and evergreen promo items.

The module has two layers so that adapters can reuse the second one:

* ``xml_root`` / ``document`` / ``entry_elements`` / ``entry_fields`` read a
  document into plain *entries* (raw title, link, summary markup, date string,
  chosen image).
* ``build_items`` turns entries from any source (RSS or JSON adapters) into
  items: cleaned text, canonical URL and id, clamped date, age window,
  per-source ordering, ``feedRank`` and ``maxItems``.
"""

import codecs
import html
import html.entities
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import timedelta

from .core import textutil, timeutil

SUMMARY_LIMIT = 300
MIN_SUMMARY_CHARS = 30

ATOM = "{http://www.w3.org/2005/Atom}"
RSS1 = "{http://purl.org/rss/1.0/}"
MEDIA = "{http://search.yahoo.com/mrss/}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
DC = "{http://purl.org/dc/elements/1.1/}"


class FeedError(ValueError):
    """A body that is not a usable feed. ``str(err)`` is a short sentence for source health."""


# ---------------------------------------------------------------- documents

_HTML_START = re.compile(rb"^\s*(?:<!--.*?-->\s*)*<(?:!doctype\s+html|html[\s>])", re.I | re.S)
_ENTITY_DECL = re.compile(rb"<!ENTITY", re.I)
_ENCODING_DECL = re.compile(rb"^(\s*<\?xml[^>]*?)\sencoding=([\"'])([\w.:-]+)\2", re.I)
# Repairs, applied only after a strict parse fails, for damage seen in real feeds.
_GLUED_XMLNS = re.compile(rb'"(xmlns:)')                       # science.nasa.gov
_CONTROL_CHARS = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_BARE_AMPERSAND = re.compile(rb"&(?!#\d+;|#x[0-9a-fA-F]+;|[A-Za-z][A-Za-z0-9]{1,31};)")
_NAMED_ENTITY = re.compile(rb"&([A-Za-z][A-Za-z0-9]{1,31});")
_XML_ENTITIES = frozenset((b"amp", b"lt", b"gt", b"quot", b"apos"))


def _local(tag):
    """``{namespace}name`` -> ``name``."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _named_to_numeric(match):
    """HTML entities such as ``&nbsp;`` are undefined in XML; spell them as character references."""
    name = match.group(1)
    if name in _XML_ENTITIES:
        return match.group(0)
    codepoint = html.entities.name2codepoint.get(name.decode("ascii"))
    return b"&#%d;" % codepoint if codepoint else b"&amp;" + name + b";"


def _repair(body):
    """Fix the kinds of breakage feeds actually ship, so one bad byte does not cost the feed."""
    body = _GLUED_XMLNS.sub(b'" \\1', body)
    body = _CONTROL_CHARS.sub(b"", body)
    body = _BARE_AMPERSAND.sub(b"&amp;", body)
    return _NAMED_ENTITY.sub(_named_to_numeric, body)


def _transcode(body):
    """Re-encode a document that declares a non-UTF-8 encoding as UTF-8, declaration removed.

    expat handles UTF-8/16, Latin-1 and ASCII and Python adds single-byte
    codecs, but multi-byte ones (``gb2312``, ``shift_jis``) are refused, so
    those are decoded here instead. Returns None when there is nothing to do.
    """
    match = _ENCODING_DECL.match(body)
    if not match:
        return None
    try:
        codec = codecs.lookup(match.group(3).decode("ascii")).name
    except LookupError:
        return None
    if codec == "utf-8":
        return None
    text = body.decode(codec, errors="replace")
    return _ENCODING_DECL.sub(lambda m: m.group(1), text.encode("utf-8"), count=1)


def _strict(body):
    """``ET.fromstring`` with every way it fails reported as a FeedError."""
    try:
        return ET.fromstring(body)
    except ET.ParseError as err:
        raise FeedError("not well-formed XML (%s)" % err) from err
    except (ValueError, LookupError) as err:  # multi-byte or unknown declared encoding
        raise FeedError("unsupported encoding (%s)" % err) from err


def _parse_bytes(body):
    """Strict parse; on failure, transcode a non-UTF-8 document and/or repair it and retry."""
    try:
        return _strict(body)
    except FeedError as first:
        transcoded = _transcode(body)
        candidates = ([transcoded] if transcoded is not None else []) + [_repair(transcoded or body)]
        for candidate in candidates:
            try:
                return _strict(candidate)
            except FeedError:
                continue
        raise first


def xml_root(body):
    """Parse a feed or sitemap body into its root element, or raise FeedError.

    A 200 response is not proof of a feed: dead feeds often return an HTML
    page, and an empty body happens too. Documents that declare entities are
    refused outright; no feed needs them and they are how XML bombs work.
    """
    if not body or not body.strip():
        raise FeedError("empty response body")
    if body.startswith(b"\xef\xbb\xbf"):
        body = body[3:]
    body = body.lstrip()
    if _HTML_START.match(body[:2048]):
        raise FeedError("HTML page, not a feed")
    if _ENTITY_DECL.search(body[:4096]):
        raise FeedError("document declares XML entities; refused")
    root = _parse_bytes(body)
    if _local(root.tag).lower() == "html":
        raise FeedError("HTML page, not a feed")
    return root


def document(body):
    """Return ``(kind, root)`` where kind is ``rss``, ``atom`` or ``rdf``, from the root tag alone."""
    root = xml_root(body)
    name = _local(root.tag)
    if name == "rss" or (name == "channel" and root.find("item") is not None):
        return "rss", root
    if root.tag == ATOM + "feed":
        return "atom", root
    if name == "RDF":
        return "rdf", root
    raise FeedError("unrecognised feed root <%s>" % name)


def entry_elements(kind, root):
    """The item/entry elements in document order (RDF items sit outside <channel>)."""
    if kind == "atom":
        return root.findall(ATOM + "entry")
    if kind == "rdf":
        return [el for el in root.iter() if el.tag in (RSS1 + "item", "item")]
    return list(root.iter("item"))


# ---------------------------------------------------------------- entries

_TAG_PREFIX = re.compile(r"<(/?)[A-Za-z][\w.-]*:")


def _markup(element):
    """An element's content as text, keeping child markup when a feed left HTML unescaped
    (or used Atom ``type="xhtml"``). Namespace prefixes are dropped so ``<html:img>`` reads
    as ``<img>``."""
    if element is None:
        return ""
    if len(element) == 0:
        return element.text or ""
    parts = [element.text or ""]
    parts.extend(ET.tostring(child, encoding="unicode") for child in element)
    return _TAG_PREFIX.sub(r"<\1", "".join(parts))


def _child_text(element, *tags):
    """Stripped text of the first listed child that has any (CDATA padding is common)."""
    for tag in tags:
        child = element.find(tag)
        if child is not None:
            text = _markup(child).strip()
            if text:
                return text
    return ""


def _atom_link(entry):
    """The article link of an Atom entry: rel=alternate (or no rel), preferring HTML."""
    best = None
    for link in entry.findall(ATOM + "link"):
        rel = link.get("rel", "alternate")
        href = (link.get("href") or "").strip()
        if rel != "alternate" or not href:
            continue
        if link.get("type") in (None, "text/html"):
            return href
        best = best or href
    return best or ""


def _rss_link(item):
    """RSS <link>, else a permalink <guid>, else an atom:link (some feeds only have that)."""
    link = _child_text(item, "link", RSS1 + "link")
    if link:
        return link
    guid = item.find("guid")
    if guid is not None and guid.get("isPermaLink", "true") != "false":
        text = (guid.text or "").strip()
        if text.startswith(("http://", "https://")):
            return text
    return _atom_link(item)


def entry_fields(element, kind):
    """Read one item/entry into a raw entry dict (text still uncleaned, date still a string).

    ``description`` is matched by exact tag, never by local name, because
    ``media:description`` holds image captions in several feeds.
    """
    if kind == "atom":
        return {
            "title": _child_text(element, ATOM + "title"),
            "link": _atom_link(element),
            "summary": _child_text(element, ATOM + "summary"),
            "content": _child_text(element, ATOM + "content"),
            "published": _child_text(element, ATOM + "published", ATOM + "updated", DC + "date"),
            "image": image_of(element, kind),
        }
    return {
        "title": _child_text(element, "title", RSS1 + "title", DC + "title"),
        "link": _rss_link(element),
        "summary": _child_text(element, "description", RSS1 + "description"),
        "content": _child_text(element, CONTENT + "encoded"),
        "published": _child_text(element, "pubDate", DC + "date", ATOM + "published",
                                 ATOM + "updated", "date"),
        "image": image_of(element, kind),
    }


# ---------------------------------------------------------------- images

_IMG_SRC = re.compile(r"<img\b([^>]*)>", re.I)
_ATTR = re.compile(r"""([a-zA-Z-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""")
_REJECT_IMAGE = re.compile(
    r"/logo/|/logos?[._-]|/tracking/|rss-pixel|pixel\.(?:gif|png)|spacer\.gif|/1x1\.|"
    r"avatars\.githubusercontent\.com|gravatar\.com|s\.w\.org/images/core/emoji|"
    r"feeds\.feedburner\.com/~", re.I)
_IMAGE_EXTENSION = re.compile(r"\.(?:jpe?g|png|webp|gif|avif)(?:$|[?#])", re.I)
_BBC_THUMB = re.compile(r"^(https://ichef\.bbci\.co\.uk/.*?)/240/")


def usable_image(url, base=None):
    """An https image URL fit for the page, or None.

    Rejects what research found masquerading as article images: the literal
    "undefined", tracking pixels, site logos, GitHub/Gravatar avatars, emoji,
    and plain-http URLs (mixed content on an https page). BBC's 240 px
    thumbnails are swapped for the 976 px rendition of the same image.
    """
    text = html.unescape(str(url or "")).strip()
    if not text or text.lower() in ("undefined", "null", "none"):
        return None
    if text.startswith("//"):
        text = "https:" + text
    elif base and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", text):
        text = urllib.parse.urljoin(base, text)
    if not text.startswith("https://") or _REJECT_IMAGE.search(text):
        return None
    return _BBC_THUMB.sub(r"\1/976/", text, count=1)


def _width(element):
    """Declared pixel width, 0 when missing or junk."""
    value = (element.get("width") or "").strip()
    return int(value) if value.isdigit() else 0


def _widest(elements):
    """URL of the widest element that carries a usable url attribute (Guardian ships 140/460/700)."""
    best_url, best_width = None, -1
    for element in elements:
        url = usable_image(element.get("url"))
        if url and _width(element) > best_width:
            best_url, best_width = url, _width(element)
    return best_url


def _is_image_media(element):
    """media:content is often video; trust medium/type when given."""
    medium = (element.get("medium") or "").lower()
    kind = (element.get("type") or "").lower()
    if medium and medium != "image":
        return False
    return not kind or kind.startswith("image/")


def _is_image_enclosure(mime, url):
    """Enclosures are podcasts and videos as often as images; require an image type
    (or, when the type is missing, an image file extension)."""
    mime = (mime or "").lower()
    if mime:
        return mime.startswith("image/")
    return bool(_IMAGE_EXTENSION.search(url or ""))


def first_img(markup, base=None):
    """The first usable <img src> in an HTML fragment (tags may be UPPERCASE, quotes single)."""
    for match in _IMG_SRC.finditer(markup or ""):
        attrs = {}
        for name, double, single, bare in _ATTR.findall(match.group(1)):
            attrs[name.lower()] = double or single or bare
        if attrs.get("width") == "1" or attrs.get("height") == "1":
            continue
        url = usable_image(attrs.get("src"), base)
        if url:
            return url
    return None


def image_of(element, kind):
    """Pick an item's image in the order that covered every researched source:
    media:content (widest) > media:thumbnail (widest) > image enclosure >
    Atom link rel=enclosure > first <img> in the full content > first <img>
    in the description/summary."""
    url = _widest(el for el in element.iter(MEDIA + "content") if _is_image_media(el))
    url = url or _widest(element.iter(MEDIA + "thumbnail"))
    if url:
        return url
    for enclosure in element.findall("enclosure"):
        if _is_image_enclosure(enclosure.get("type"), enclosure.get("url")):
            url = usable_image(enclosure.get("url"))
            if url:
                return url
    for link in element.findall(ATOM + "link"):
        if link.get("rel") == "enclosure" and _is_image_enclosure(link.get("type"), link.get("href")):
            url = usable_image(link.get("href"))
            if url:
                return url
    if kind == "atom":
        bodies = (ATOM + "content", ATOM + "summary")
    else:
        bodies = (CONTENT + "encoded", "description", RSS1 + "description")
    for tag in bodies:
        url = first_img(_markup(element.find(tag)))
        if url:
            return url
    return None


# ---------------------------------------------------------------- items

_NATURE_PREFIX = re.compile(r"^[A-Z][^,]{1,60}, Published online: [^;]{4,40}; doi:\S+\s*")
# Newsletter plugs inside descriptions ("Get our breaking news email, free app or daily news podcast")
# and Reddit's footer ("submitted by /u/name to r/LocalLLaMA [link] [comments]").
_PLUG = re.compile(r"\s*(?:Get our|Sign up for our) [^.]{0,100}?\b(?:email|newsletter|app|podcast)s?\b[^.]*(?:\.|$)"
                   r"|\s*submitted by /?u/\S+ to /?r/\S+.*$")


def _is_navigation(text):
    """True for site navigation scraped into a description ("APOD Archive Submissions Index
    Search Calendar RSS"): almost every word capitalised, or mostly one- or two-word fragments.

    Prose, even dense with names ("Prime Minister Narendra Modi said on Tuesday..."), has
    enough lowercase words to stay well under the threshold.
    """
    words = [word for word in text.split()[:30] if word[:1].isalpha()]
    if len(words) >= 12 and sum(1 for word in words if word[0].isupper()) >= 0.8 * len(words):
        return True
    fragments = text.split(". ")[:8]
    return len(fragments) >= 5 and sum(1 for f in fragments if len(f.split()) <= 2) >= 4


def _repeats(summary, title):
    """True when a summary says nothing the headline does not (HT, India Today, Google News)."""
    s_key, t_key = textutil.norm_title(summary), textutil.norm_title(title)
    if not s_key or s_key == t_key or t_key.startswith(s_key):
        return True
    return s_key.startswith(t_key) and len(s_key) - len(t_key) < MIN_SUMMARY_CHARS


def _summary_text(markup, title):
    """Clean one summary candidate; '' when it is too short, only repeats the title or is
    scraped navigation. Boilerplate (newsletter plugs, Reddit's footer, Nature's citation line)
    is cut first, and a leading copy of the title is dropped."""
    text = _PLUG.sub("", _NATURE_PREFIX.sub("", textutil.clean_text(markup))).strip()
    if title and text.startswith(title) and not _repeats(text, title):
        text = text[len(title):].lstrip(" .:-–—|")
    if len(text) < MIN_SUMMARY_CHARS or _repeats(text, title) or _is_navigation(text):
        return ""
    return textutil.truncate(text, SUMMARY_LIMIT)


def summary_for(entry, title):
    """The description if it is useful, else the opening of the full content, else ''."""
    for key in ("summary", "content"):
        text = _summary_text(entry.get(key), title)
        if text:
            return text
    return ""


def _published(value, source, now):
    """Parse and clamp: undated items count as seen now, future dates become now."""
    parsed = timeutil.parse_date(value, source.get("timezone")) if value else None
    if parsed is None or parsed > now:
        return now
    return parsed


def _absolute(link, source):
    """Resolve a relative link against the feed URL; None when it is not a web link."""
    link = html.unescape(str(link or "")).strip()
    if not link:
        return None
    link = urllib.parse.urljoin(source["url"], link)
    if not link.startswith(("http://", "https://")):
        return None
    return textutil.canonical_url(link)


def _item(entry, source, now):
    """One entry -> one item dict, or None when it has no usable title or link."""
    title = textutil.clean_text(entry.get("title"))
    url = _absolute(entry.get("link"), source)
    if not title or not url:
        return None
    published = _published(entry.get("published"), source, now)
    return {
        "id": textutil.stable_id("i", url),
        "url": url,
        "title": title,
        "summary": summary_for(entry, title),
        "source": source["id"],
        "sourceName": source["name"],
        "publishedAt": timeutil.iso(published),
        "firstSeenAt": timeutil.iso(now),
        "image": usable_image(entry.get("image"), url),
        "section": source["section"],
        "topics": list(source.get("topics") or []),
        "feedRank": None,
        "publisher": entry.get("publisher") or None,
        "points": entry.get("points"),
        "comments": entry.get("comments"),
        "alt": list(entry.get("alt") or []),
    }


def _wanted(item, source, cutoff_iso):
    """Inside the source's age window and matching its optional ``urlPattern``."""
    if item["publishedAt"] < cutoff_iso:
        return False
    pattern = source.get("urlPattern")
    return not pattern or re.search(pattern, item["url"]) is not None


def build_items(entries, source, now):
    """Entries from any adapter -> the source's items, ready to store.

    Curated feeds keep their editorial order, which becomes ``feedRank``;
    firehose and official feeds are sorted newest first. ``maxItems`` is
    applied last, after filtering and ordering, so a stale pinned item at the
    top of a feed never costs a fresh one its slot.
    """
    cutoff = timeutil.iso(now - timedelta(hours=float(source.get("maxAgeHours", 48))))
    items, seen = [], set()
    for entry in entries:
        item = _item(entry, source, now)
        if item is None or item["id"] in seen or not _wanted(item, source, cutoff):
            continue
        seen.add(item["id"])
        items.append(item)
    if source.get("mode") == "curated":
        for rank, item in enumerate(items):
            item["feedRank"] = rank
    else:
        items.sort(key=lambda item: item["publishedAt"], reverse=True)
    return items[:int(source.get("maxItems", 15))]


def parse(body, source, now):
    """Parse a feed body for ``source`` into items; raises FeedError when it is not a usable feed.

    A document with no entries at all is a failure (dead feeds and unknown
    tag pages return valid, empty feeds). A feed whose entries are all older
    than the age window is fine and yields an empty list.
    """
    kind, root = document(body)
    entries = [entry_fields(element, kind) for element in entry_elements(kind, root)]
    if not entries:
        raise FeedError("feed has no items")
    return build_items(entries, source, now)
