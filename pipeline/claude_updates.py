"""The ``claude`` stage: what is new in Claude (``public/claude/updates.json``) plus the playbook.

Eight first-party sources, each fetched and parsed in isolation so one markup
change costs only that source (see docs/ARCHITECTURE.md, "Public: claude"):
the apps, platform, Claude Code and Desktop/Cowork release notes, the claude.com
product-updates blog, the Anthropic news and engineering listings, and the
Claude YouTube channel, plus the status page summary.

Entries accumulate. A source that fails keeps all of its previous entries, and
a source that works replaces only the dates its feed still covers, so a short
feed (the Claude Code RSS holds three weeks) still fills the 180-day window.
A source that parses to nothing at all is treated as failed, not as empty.
"""

import json
import re
import traceback
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import timedelta
from html.parser import HTMLParser

from . import playbook
from .core import config, jsonio, log, net, textutil, timeutil

SURFACES = ("apps", "code", "platform", "cowork", "models", "news", "learn")
KINDS = ("feature", "release", "article", "video")
STATUS_INDICATORS = ("none", "minor", "major", "critical", "maintenance")
TITLE_CHARS = 160
MAX_FEATURES = 3

_ATOM = "{http://www.w3.org/2005/Atom}"
_MEDIA = "{http://search.yahoo.com/mrss/}"
_CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"


class ParseError(ValueError):
    """A source's body did not have the shape we expect (its markup probably changed)."""


# ---------------------------------------------------------------- text helpers

_HOLD = re.compile("\ue000(\\d+)\ue001")
_MD_CODE = re.compile(r"(`+)(.+?)\1", re.S)
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\((?:[^()\s]|\([^()\s]*\))+\)")
_MD_LINK = re.compile(r"\[([^\[\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)")
_MD_STRONG = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_MD_EM = re.compile(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])")
_MD_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")
_MD_BULLET = re.compile(r"(?m)^[ \t]*(?:[-*+]|\d+\.)[ \t]+")
_JSX_TAG = re.compile(r"</?[A-Z][A-Za-z]*(?:\s[^<>]*)?/?>")
_SPACE = re.compile(r"\s+")


def squash(text):
    """Collapse all whitespace to single spaces and trim."""
    return _SPACE.sub(" ", text or "").strip()


def md_text(markdown):
    """Markdown to one line of plain text: links keep their words, markers go.

    Code spans are set aside first so ``**kwargs`` or ``a_b_c`` inside them
    survive, and text such as ``<file>`` is kept: callers insert our strings as
    text, so angle brackets are content, not markup. Only MDX components
    (capitalised tags like ``<Tip>``) are removed.
    """
    held = []

    def hold(value):
        held.append(value)
        return "\ue000%d\ue001" % (len(held) - 1)

    text = (markdown or "").replace("\ue000", "").replace("\ue001", "")
    text = _MD_CODE.sub(lambda m: hold(m.group(2).strip()), text)
    text = _MD_ESCAPE.sub(lambda m: hold(m.group(1)), text)
    text = _MD_IMAGE.sub(r"\1", text)
    text = _MD_LINK.sub(r"\1", text)
    for _ in range(2):  # bold around a link, or italics inside bold
        text = _MD_STRONG.sub(r"\2", text)
        text = _MD_EM.sub(r"\1", text)
    text = _JSX_TAG.sub(" ", _MD_BULLET.sub("", text))
    text = _HOLD.sub(lambda m: held[int(m.group(1))], text)
    return squash(text)


def first_link(markdown):
    """The first http(s) link target in a markdown snippet, or None."""
    for match in _MD_LINK.finditer(markdown or ""):
        if playbook.safe_url(match.group(2)):
            return match.group(2)
    return None


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“\"‘'(\[])")


def split_first_sentence(text):
    """(first sentence, rest). Sentences end at . ! ? followed by a capitalised word."""
    parts = _SENTENCE_END.split(text, maxsplit=1)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")


def _date_text(value):
    """A ``YYYY-MM-DD`` UTC date for any date shape, or raise ParseError."""
    parsed = timeutil.parse_date(value)
    if parsed is None:
        raise ParseError("unreadable date %r" % (value,))
    return parsed.date().isoformat()


def _entry(source, date, title, summary, url, kind, surface=None):
    """A ClaudeUpdate with clean, length-limited text. ``features`` is filled in later."""
    title = textutil.truncate(squash(title), TITLE_CHARS)
    return {
        "id": textutil.stable_id("u", source["id"], date, title),
        "date": date,
        "surface": surface or source["surface"],
        "kind": kind,
        "title": title,
        "summary": textutil.truncate(squash(summary), source["summaryChars"]),
        "url": url,
        "source": source["id"],
        "features": [],
    }


# ---------------------------------------------------------------- dated markdown notes

_DAY_HEADING = re.compile(r"(?m)^### ([A-Z][a-z]+ \d{1,2}, \d{4})[ \t]*$")
_BOLD_LINE = re.compile(r"(?m)^\*\*(.+?)\*\*[ \t]*$")
# Notes end their paragraphs with a pointer: "For more information, see our blog post:
# **[Title](url)**." or "See **[Title](url)** for more information." From such a sentence to
# the end of the line is a pointer, not news; the link itself becomes the entry's URL.
# Only a sentence that starts with the phrase counts, so "you can see the logs" survives.
_POINTER = re.compile(
    r"(?:^|(?<=[.!?:*]\s))(?:(?:For more information|Learn more|Read more|Read our|Refer to)\b"
    r"|See\s+(?=\*{0,2}\[|(?:our|the|these|this|updates)\b)).*$")
_LINK_ONLY = re.compile(r"^\s*(?:[-*+]\s+)?(?:\*\*)?\[[^\]]*\]\([^)]*\)(?:\*\*)?[\s.]*$")
# What is left of a line after its pointer is cut: an empty bullet, or a lead-in like "**Note:**".
_LEAD_IN_ONLY = re.compile(r"^\s*(?:[-*+]\s*)?(?:(?:\*\*)?[\w ]{0,20}(?::\*\*|\*\*:|:))?\s*$")
_RULE = re.compile(r"(?m)^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")


def dated_sections(text):
    """Split notes into (date, body) pairs at ``### Month D, YYYY`` headings.

    A body ends at the next heading of any level, so a ``## Month`` heading
    never leaks into the last day of the month before it.
    """
    parts = _DAY_HEADING.split(text)
    sections = []
    for index in range(1, len(parts), 2):
        body = re.split(r"(?m)^#{1,3} ", parts[index + 1])[0]
        sections.append((_date_text(parts[index]), body))
    return sections


def _apps_summary(markdown):
    """Plain text of an apps note without its pointers to further reading.

    A horizontal rule ends a month's notes, so nothing after one belongs to
    the item. Lines that are only a link, or only a lead-in such as "Note:"
    once the pointer is cut, are dropped.
    """
    kept = []
    for line in _RULE.split(markdown)[0].split("\n"):
        if _LINK_ONLY.match(line):
            continue
        line = _POINTER.sub("", line)
        if line.strip() and not _LEAD_IN_ONLY.match(line):
            kept.append(line)
    return md_text("\n".join(kept))


def parse_apps_notes(text, source):
    """Help Center release notes: ``### date`` sections of ``**Title**`` + paragraphs."""
    entries = []
    for day, body in dated_sections(text):
        pieces = _BOLD_LINE.split(body)
        for index in range(1, len(pieces), 2):
            title, details = md_text(pieces[index]), pieces[index + 1]
            if not title:
                continue
            url = first_link(details) or source["page"]
            entries.append(_entry(source, day, title, _apps_summary(details), url, "feature"))
    if not entries:
        raise ParseError("no dated notes found")
    return entries


_LEADING_BOLD = re.compile(r"^\*\*(.+?)\*\*[:.]?\s*")
# "We've launched Claude Haiku 5.5", "We announced the deprecation of the Claude Sonnet 4.5 model":
# the model must be the object of the verb, so "We've launched fast mode for Claude X" stays platform.
_MODEL_NEWS = re.compile(
    r"^We(?:[’']ve| have)? (?:launched|released|deprecated|retired|announced the (?:deprecation|retirement) of)"
    r" (?:the )?Claude [A-Z][a-z]+ \d")


def _platform_entry(bullet, day, source):
    """One platform bullet: headline from a leading bold span, else the first sentence.

    A trailing "See [guide](url) for ..." pointer is cut unless it is all there
    is. When the first sentence is too long for a headline, the summary
    repeats the whole text so the clipped part is not lost.
    """
    bullet = _POINTER.sub("", bullet).strip() or bullet
    lead = _LEADING_BOLD.match(bullet)
    if lead:
        title, summary = md_text(lead.group(1)).rstrip(".:"), md_text(bullet[lead.end():])
    else:
        title, summary = split_first_sentence(md_text(bullet))
        if len(title) > TITLE_CHARS:
            summary = md_text(bullet)
    surface = "models" if _MODEL_NEWS.match(title) else None
    return _entry(source, day, title, summary, source["page"], "feature", surface)


def parse_platform_notes(text, source):
    """Platform release notes: ``### date`` sections of ``* `` bullets (some span several lines)."""
    text = re.sub(r"<Tip>.*?</Tip>", "", text, flags=re.S)
    entries = []
    for day, body in dated_sections(text):
        for bullet in re.split(r"(?m)^\* ", body)[1:]:
            if bullet.strip():
                entries.append(_platform_entry(bullet.strip(), day, source))
    if not entries:
        raise ParseError("no dated notes found")
    return entries


# ---------------------------------------------------------------- Mintlify changelog RSS

class _ChangelogHTML(HTMLParser):
    """Collects (section label, item text) from a release body.

    Bodies look like ``<p><strong>Added</strong></p><ul><li>...</li></ul>``.
    A paragraph that is only bold text is a section label; other paragraphs
    (such as "Bundled Claude Code version") are ignored. Nested list text is
    folded into its parent item.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.section = ""
        self._depth = 0      # <li> nesting
        self._item = []
        self._para = None    # text of the open top-level <p>, or None
        self._bold = []      # the part of it inside <strong>/<b>
        self._bold_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self._depth += 1
            if self._depth == 1:
                self._item = []
        if self._depth and tag in ("li", "p", "br", "ul", "ol"):
            self._item.append(" ")  # block boundaries inside an item separate words
        elif tag == "p" and not self._depth:
            self._para, self._bold, self._bold_depth = [], [], 0
        elif tag in ("strong", "b") and self._para is not None:
            self._bold_depth += 1

    def handle_endtag(self, tag):
        if tag == "li" and self._depth:
            self._depth -= 1
            if not self._depth:
                self.items.append((self.section, squash("".join(self._item))))
        elif tag in ("strong", "b") and self._bold_depth:
            self._bold_depth -= 1
        elif tag == "p" and self._para is not None:
            text, bold = squash("".join(self._para)), squash("".join(self._bold))
            if text and text == bold:
                self.section = text
            self._para = None

    def handle_data(self, data):
        if self._depth:
            self._item.append(data)
        elif self._para is not None:
            self._para.append(data)
            if self._bold_depth:
                self._bold.append(data)


_ITEM_PREFIX = re.compile(r"^(?:\[[^\]]{1,30}\]\s*|\([^)]{1,30}\)\s*|[A-Z][\w ./-]{0,30}:\s+)+")
_NO_CHANGES = re.compile(r"^no user-facing changes\.?$", re.I)


def added_items(body_html):
    """The "Added" items of one release, in order.

    An item counts when it sits under a bold "Added" label, or when its text
    starts with "Added" after prefixes such as "[VSCode]" or "Windows:".
    """
    reader = _ChangelogHTML()
    reader.feed(body_html or "")
    reader.close()
    added = []
    for section, text in reader.items:
        if not text or _NO_CHANGES.match(text):
            continue
        if section.lower() == "added" or _ITEM_PREFIX.sub("", text).startswith("Added "):
            added.append(text)
    return added


def _join_items(items):
    """Items as sentences: "Added X. Added Y." """
    return " ".join(item.rstrip(" .;") + "." for item in items)


def parse_changelog_rss(body, source):
    """Mintlify changelog RSS (Claude Code, Desktop/Cowork): one entry per release that adds something."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError as err:
        raise ParseError("not valid XML: %s" % err) from err
    releases = root.findall("./channel/item")
    if not releases:
        raise ParseError("no <item> elements in the feed")
    entries = []
    for release in releases:
        version = squash(release.findtext("title"))
        content = release.find(_CONTENT)
        items = added_items(content.text if content is not None else "")
        if not version or not items:
            continue
        day = _date_text(release.findtext("pubDate"))
        title = "%s %s" % (source["titlePrefix"], version)
        summary = _join_items(items[:source["maxItemsPerRelease"]])
        url = squash(release.findtext("link")) or source["url"]
        entries.append(_entry(source, day, title, summary, url, "release"))
    return entries


# ---------------------------------------------------------------- Next.js RSC listings

_RSC_CHUNK = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
_OBJECT_START = re.compile(r'\{"_id":\s*"')


def rsc_objects(page):
    """Every JSON object starting ``{"_id":"`` in a Next.js App Router page's RSC payload.

    The listing data lives in ``self.__next_f.push([1,"..."])`` script chunks:
    each is a JSON string, their concatenation is the payload, and objects can
    span chunks, so the payload is joined before decoding.
    """
    chunks = _RSC_CHUNK.findall(page)
    if not chunks:
        raise ParseError("no Next.js data chunks in the page")
    decoded = []
    for chunk in chunks:
        try:
            decoded.append(json.loads('"%s"' % chunk))
        except ValueError:
            log.debug("skipping an undecodable RSC chunk (%d chars)", len(chunk))
    payload = "".join(decoded)
    decoder, objects = json.JSONDecoder(), []
    for match in _OBJECT_START.finditer(payload):
        try:
            obj, _ = decoder.raw_decode(payload, match.start())
        except ValueError:
            continue
        objects.append(obj)
    return objects


def _richest_by(objects, key):
    """One object per key value, keeping the one with the most fields (listing card over stub)."""
    best, order = {}, []
    for obj in objects:
        value = key(obj)
        if not value:
            continue
        if value not in best:
            order.append(value)
            best[value] = obj
        elif len(obj) > len(best[value]):
            best[value] = obj
    return [best[value] for value in order]


def _slug(obj):
    slug = obj.get("slug")
    return slug.get("current") if isinstance(slug, dict) else slug


def parse_anthropic_listing(page, source):
    """anthropic.com /news or /engineering: the listing cards (objects with a summary).

    Related-article stubs elsewhere in the payload have no summary and reach
    back years, so they are left out.
    """
    cards = [obj for obj in rsc_objects(page)
             if obj.get("_type") == "article" and obj.get("publishedOn") and obj.get("title")
             and "summary" in obj and _slug(obj)]
    entries = []
    for card in _richest_by(cards, _slug):
        slug, kind = _slug(card), card.get("articleType") or "news"
        url = card.get("linkedUrl") or "https://www.anthropic.com/%s/%s" % (kind, slug)
        url = urllib.parse.urljoin("https://www.anthropic.com/", url)
        surface = "models" if "models" in (card.get("newsCategories") or []) else None
        summary = card.get("summary") or card.get("seoDescription") or ""
        entries.append(_entry(source, _date_text(card["publishedOn"]), card["title"], summary,
                              url, "article", surface))
    if not entries:
        raise ParseError("no article cards found in the page data")
    return entries


def parse_claude_blog(page, source):
    """claude.com/resources listing: blogPost objects; surface from the first known product tag."""
    posts = [obj for obj in rsc_objects(page)
             if obj.get("_type") == "blogPost" and obj.get("title") and obj.get("date")
             and (obj.get("slug") or obj.get("externalUrl"))]
    entries = []
    for post in _richest_by(posts, lambda obj: obj.get("slug") or obj.get("externalUrl")):
        url = post.get("externalUrl") or "https://claude.com/resources/articles/%s" % post["slug"]
        products = [p.get("name") for p in post.get("products") or [] if isinstance(p, dict)]
        surface = next((source["productSurfaces"][p] for p in products if p in source["productSurfaces"]),
                       None)
        entries.append(_entry(source, _date_text(post["date"]), post["title"], post.get("excerpt") or "",
                              url, "article", surface))
    if not entries:
        raise ParseError("no blog posts found in the page data")
    return entries


# ---------------------------------------------------------------- YouTube and status

def parse_youtube(body, source):
    """YouTube channel Atom feed: published date, title, link and the description's first paragraph."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError as err:
        raise ParseError("not valid XML: %s" % err) from err
    videos = root.findall(_ATOM + "entry")
    if not videos:
        raise ParseError("no <entry> elements in the feed")
    entries = []
    for video in videos:
        link = video.find(_ATOM + "link")
        title, url = video.findtext(_ATOM + "title"), link.get("href") if link is not None else None
        if not title or not url:
            continue
        description = video.findtext(_MEDIA + "group/" + _MEDIA + "description") or ""
        summary = re.split(r"\n\s*\n", description.strip(), maxsplit=1)[0]
        entries.append(_entry(source, _date_text(video.findtext(_ATOM + "published")), title, summary,
                              url, "video"))
    return entries


def parse_status(data):
    """Statuspage summary.json to ``{"indicator", "description"}``."""
    status = data.get("status") if isinstance(data, dict) else None
    if not isinstance(status, dict):
        raise ParseError("no 'status' object in summary.json")
    indicator, description = status.get("indicator"), squash(status.get("description"))
    if indicator not in STATUS_INDICATORS or not description:
        raise ParseError("unexpected status %r" % (status,))
    return {"indicator": indicator, "description": description}


# kind -> (parser, how to hand it the body)
PARSERS = {
    "apps-notes": (parse_apps_notes, "text"),
    "platform-notes": (parse_platform_notes, "text"),
    "changelog-rss": (parse_changelog_rss, "bytes"),
    "anthropic-listing": (parse_anthropic_listing, "text"),
    "claude-blog": (parse_claude_blog, "text"),
    "youtube": (parse_youtube, "bytes"),
}
_REQUIRED = {
    "apps-notes": ("page",),
    "platform-notes": ("page",),
    "changelog-rss": ("titlePrefix", "maxItemsPerRelease"),
    "claude-blog": ("productSurfaces",),
}


# ---------------------------------------------------------------- fetching

def check_source(source, defaults):
    """Validate one config entry and fill defaults; raise ValueError naming the problem."""
    for key in ("id", "name", "kind", "url", "surface"):
        if not isinstance(source.get(key), str) or not source[key]:
            raise ValueError("source needs a %r" % key)
    if source["kind"] not in PARSERS:
        raise ValueError("unknown kind %r" % source["kind"])
    if source["surface"] not in SURFACES:
        raise ValueError("unknown surface %r" % source["surface"])
    for key in _REQUIRED.get(source["kind"], ()):
        if key not in source:
            raise ValueError("kind %s needs %r" % (source["kind"], key))
    unknown = set(source.get("productSurfaces", {}).values()) - set(SURFACES)
    if unknown:
        raise ValueError("productSurfaces maps to unknown surface(s) %s" % ", ".join(sorted(unknown)))
    merged = dict(defaults)
    merged.update(source)
    return merged


def fetch_source(source):
    """Fetch and parse one source. Raises NetError or ParseError (or ValueError) on failure."""
    parser, shape = PARSERS[source["kind"]]
    net.polite(source["url"], 1.0)
    response = net.fetch(source["url"], timeout=30, retries=2)
    return parser(response.text() if shape == "text" else response.body, source)


def fetch_status(status_config):
    """The status page summary, or raise."""
    return parse_status(net.fetch_json(status_config["url"], timeout=20, retries=1))


def _describe(err):
    """A short reason for status.json; the type name helps when it is not a network error."""
    if isinstance(err, net.NetError):
        return str(err)
    return " ".join(("%s: %s" % (type(err).__name__, err)).split())[:200]


# ---------------------------------------------------------------- merging

def _valid_previous(entry):
    """True for an entry from the previous file that still has the ClaudeUpdate shape."""
    if not isinstance(entry, dict):
        return False
    text_keys = ("id", "date", "title", "url", "source")
    if not all(isinstance(entry.get(k), str) and entry[k] for k in text_keys):
        return False
    return (entry.get("surface") in SURFACES and entry.get("kind") in KINDS
            and re.match(r"^\d{4}-\d{2}-\d{2}$", entry["date"]) is not None)


def previous_entries(path):
    """Entries of the existing updates.json grouped by source id (bad rows dropped, with a warning)."""
    data = jsonio.read_json(path, default={})
    rows = data.get("entries") if isinstance(data, dict) else None
    grouped, dropped = {}, 0
    for row in rows if isinstance(rows, list) else []:
        if _valid_previous(row):
            grouped.setdefault(row["source"], []).append(row)
        else:
            dropped += 1
    if dropped:
        log.warn("ignored %d malformed entries in %s", dropped, path)
    return grouped


def merge_source(fresh, previous):
    """Combine one source's fresh entries (or None when it failed) with its previous ones.

    A fresh feed is the authority for the dates it covers; previous entries
    older than its oldest entry are kept, so short feeds accumulate history.
    """
    previous = previous or []
    if not fresh:
        return list(previous)
    oldest = min(entry["date"] for entry in fresh)
    fresh_ids = {entry["id"] for entry in fresh}
    return fresh + [e for e in previous if e["date"] < oldest and e["id"] not in fresh_ids]


def _unique_urls(entries):
    """(source, canonical URL) pairs that identify exactly one entry within their source.

    Platform notes all link to one page and changelog anchors canonicalise to
    one page; such shared URLs say nothing about duplicates and are skipped.
    """
    seen = {}
    for entry in entries:
        key = (entry["source"], textutil.canonical_url(entry["url"]))
        seen[key] = seen.get(key, 0) + 1
    return {key for key, count in seen.items() if count == 1}


def dedupe(entries):
    """Drop repeats by normalised title or by a URL unique to one entry; the first one wins.

    Entries arrive in source priority order, so a first-party release note beats
    the blog post, video or news item about the same thing.
    """
    unique = _unique_urls(entries)
    seen, kept = set(), []
    for entry in entries:
        keys = {"t:" + textutil.norm_title(entry["title"])}
        url = textutil.canonical_url(entry["url"])
        if (entry["source"], url) in unique:
            keys.add("u:" + url)
        if keys & seen:
            continue
        seen |= keys
        kept.append(entry)
    return kept


def in_window(entries, now, days):
    """Entries dated within the last ``days`` days, and not after tomorrow (webinars, bad clocks)."""
    oldest = (now - timedelta(days=days)).date().isoformat()
    newest = (now + timedelta(days=1)).date().isoformat()
    return [entry for entry in entries if oldest <= entry["date"] <= newest]


# ---------------------------------------------------------------- feature links

_CROSS_SURFACE = ("models", "news", "learn")
_COMPATIBLE = {"apps": ("apps", "integrations"), "code": ("code",), "platform": ("platform",),
               "cowork": ("cowork", "apps")}
# Release-stage wording that contains a feature's one-word title ("Research") without meaning it.
_NOT_FEATURE_PHRASES = re.compile(r"\bresearch preview\b", re.I)
_TITLE_SEGMENTS = re.compile(r",\s*|\s+and\s+")
TAG_ONLY_SCORE = 3


def _phrase_pattern(phrase):
    """Word-bounded, case-insensitive pattern for a phrase.

    Space, '-' and '_' are interchangeable ("web fetch" matches ``web_fetch``)
    and the last word may be plural or singular.
    """
    words = [re.escape(word) for word in re.split(r"[\s_-]+", phrase.strip().lower()) if word]
    if not words:
        return None
    last = words[-1]
    words[-1] = (last[:-1] + "s?") if last.endswith("s") and len(last) > 3 else last + "s?"
    return re.compile(r"(?<![\w-])" + r"[\s_-]+".join(words) + r"(?![\w-])", re.I)


def _title_phrases(title):
    """(pattern, one_word) for a title and its multi-word parts.

    "Model, effort level and fast mode" also yields "effort level" and "fast
    mode"; one-word parts ("Model") are too vague and are left out, but a
    one-word title ("Hooks") is kept and flagged. A parenthesised part
    ("Thinking (adaptive)") is dropped first.
    """
    title = re.sub(r"\s*\([^)]*\)", "", title).strip()
    phrases = [(title, len(title.split()) == 1)]
    phrases += [(part, False) for part in _TITLE_SEGMENTS.split(title)
                if len(part.split()) > 1 and part != title]
    return [(_phrase_pattern(text), one_word) for text, one_word in phrases if _phrase_pattern(text)]


def _feature_terms(features):
    """Per feature: (feature, title phrases, tag patterns).

    Tags that three or more features share ("context", "cost") are too
    generic to count, and a tag that repeats a title phrase is not counted twice.
    """
    usage = {}
    for feature in features:
        for tag in set(feature["tags"]):
            usage[tag] = usage.get(tag, 0) + 1
    terms = []
    for feature in features:
        title_key = re.sub(r"\s*\([^)]*\)", "", feature["title"]).strip().lower()
        tags = [_phrase_pattern(tag) for tag in feature["tags"]
                if usage[tag] < 3 and tag.lower().replace("-", " ") != title_key]
        terms.append((feature, _title_phrases(feature["title"]), [t for t in tags if t]))
    return terms


def _score(text, surface, feature, phrases, tags):
    """How strongly an entry's text points at a feature; 0 means no link.

    A title phrase links on its own (2 points); a one-word title only within
    the entry's own product surface. Tags add a point each, and without a
    title match need TAG_ONLY_SCORE points and a product-surface entry.
    """
    cross = surface in _CROSS_SURFACE
    if not cross and feature["surface"] not in _COMPATIBLE.get(surface, ()):
        return 0
    titled = any(pattern.search(text) for pattern, one_word in phrases if not (one_word and cross))
    tag_points = sum(1 for pattern in tags if pattern.search(text))
    if titled:
        return 2 + tag_points
    return tag_points if not cross and tag_points >= TAG_ONLY_SCORE else 0


def link_features(entries, features, source_surfaces):
    """Set each entry's ``features`` to at most three playbook feature ids it plainly mentions.

    Surface compatibility uses the surface of the entry's source
    (``source_surfaces``: source id -> configured surface), so a model launch
    from the platform notes still links only to platform features.
    Deliberately conservative: a missed link costs little; a wrong one sends
    a reader to the wrong page.
    """
    terms = _feature_terms(features)
    for entry in entries:
        text = _NOT_FEATURE_PHRASES.sub(" ", "%s. %s" % (entry["title"], entry["summary"]))
        surface = source_surfaces.get(entry["source"], entry["surface"])
        scored = []
        for feature, phrases, tags in terms:
            score = _score(text, surface, feature, phrases, tags)
            if score:
                scored.append((-score, feature["id"]))
        entry["features"] = [feature_id for _, feature_id in sorted(scored)[:MAX_FEATURES]]
    return entries


# ---------------------------------------------------------------- the stage

def _load_sources(settings):
    """(valid sources, [(id, error)]) from config; a bad entry is reported, not fatal."""
    defaults = {"summaryChars": int(settings.get("summaryChars", 300)), "maxEntries": 100}
    sources, problems = [], []
    for raw in settings.get("sources", []):
        if not isinstance(raw, dict):
            problems.append(("?", "config entry is not an object"))
            continue
        if raw.get("enabled", True) is False:
            continue
        try:
            sources.append(check_source(raw, defaults))
        except ValueError as err:
            problems.append((str(raw.get("id", "?")), "bad config: %s" % err))
    return sources, problems


def collect(sources, previous, now, days):
    """Fetch every source in turn; returns (entries in source priority order, failures).

    Each source's merged entries are windowed and then capped at its
    ``maxEntries``, so accumulated history cannot crowd out other sources.
    """
    entries, failures = [], []
    for source in sources:
        try:
            fresh = fetch_source(source)
            log.info("%s: %d entries", source["id"], len(fresh))
        except Exception as err:  # isolation boundary: one source must never stop the others
            fresh = None
            failures.append((source["id"], _describe(err)))
            log.warn("%s failed, keeping %d previous entries: %s", source["id"],
                     len(previous.get(source["id"], [])), _describe(err))
            if not isinstance(err, (net.NetError, ParseError)):
                log.debug("%s", traceback.format_exc().rstrip())
        merged = in_window(merge_source(fresh, previous.get(source["id"])), now, days)
        entries += merged[:source["maxEntries"]]
    return entries, failures


def _status(settings, failures):
    """The status chip, or None (a stale "all operational" would be worse than none)."""
    status_config = settings.get("status") or {}
    if not status_config.get("enabled", False) or not status_config.get("url"):
        return None
    try:
        return fetch_status(status_config)
    except Exception as err:  # same isolation as a source
        failures.append(("claude-status", _describe(err)))
        log.warn("status failed: %s", _describe(err))
        return None


def build_updates(ctx, settings, features):
    """Fetch, merge, dedupe, window, link and write updates.json; return counts."""
    path = ctx.paths.claude_dir / "updates.json"
    previous = previous_entries(path)
    sources, failures = _load_sources(settings)
    for source_id, problem in failures:
        log.error("%s: %s", source_id, problem)
    entries, fetch_failures = collect(sources, previous, ctx.now, int(settings.get("windowDays", 180)))
    failures += fetch_failures
    status = _status(settings, failures)
    entries = dedupe(entries)
    entries.sort(key=lambda entry: entry["date"], reverse=True)  # stable: priority order within a day
    entries = link_features(entries[:int(settings.get("maxEntries", 400))], features,
                            {source["id"]: source["surface"] for source in sources})
    jsonio.write_json(path, {"generatedAt": timeutil.iso(ctx.now), "status": status, "entries": entries})
    known = {row["id"] for rows in previous.values() for row in rows}
    return {
        "entries": len(entries),
        "newEntries": sum(1 for entry in entries if entry["id"] not in known),
        "linkedEntries": sum(1 for entry in entries if entry["features"]),
        "sourcesOk": len(sources) - len(fetch_failures),
        "sourcesFailed": len(failures),
        "failed": ["%s: %s" % failure for failure in failures],
    }


def run(ctx):
    """Stage entry point: compile the playbook, then build the updates feed."""
    settings = config.load("claude")
    features, playbook_counts = playbook.build(ctx)
    counts = build_updates(ctx, settings, features)
    counts.update(playbook_counts)
    return counts
