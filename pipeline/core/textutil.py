"""Text helpers shared by every stage: cleaning feed text, URLs, ids, tokens and stems.

``tokenize`` and ``stem`` have a JavaScript twin in the site's search worker.
Both are asserted against ``tests/fixtures/stem-vectors.json``; if you change
one, change the other and the vectors in the same commit. To make the twin a
straight port, the exact algorithm is:

tokenize(text)
  1. ``text.normalize("NFKD")``, delete U+0300..U+036F (combining accents), lowercase.
  2. Scan left to right for matches of
     ``[a-z0-9]+(?:[&.\\-][a-z0-9]+)*(?:\\++(?![a-z0-9+]))?``
     (words joined by single ``&``, ``.`` or ``-``, plus a trailing run of ``+``
     that ends the word). Every other character is a separator.
  3. A match containing a digit is one token as is (``gpt-5.5``, ``s&p-500``).
     Otherwise split it on ``.`` and ``-`` (``&`` joins and the ``+`` suffix stay).
  4. Drop tokens of length 1 unless that character is a digit.

stem(token)
  1. Length <= 3 or contains a digit: return unchanged.
  2. First match only: ``ies`` -> ``y`` if length > 4; ``sses`` -> ``ss``;
     ``xes`` / ``ches`` / ``shes`` / ``zes`` drop ``es``; a final ``s`` is dropped
     unless the word ends ``ss``, ``us`` or ``is``.
  3. On that result, first match only, each requiring at least 4 characters to
     remain: drop ``ing``; drop ``ed``; drop ``ly``. After ``ing`` or ``ed``, if
     the result ends in a doubled consonant other than ``l``, ``s`` or ``z``,
     drop one of the pair.
"""

import hashlib
import html
import re
import unicodedata
import urllib.parse

# ---------------------------------------------------------------- clean_text

_CDATA = re.compile(r"<!\[CDATA\[|\]\]>")
# Content that is never prose. An unclosed <script> (a feed cut mid-tag) hides everything after it.
_HIDDEN = re.compile(
    r"<(script|style|noscript|iframe|svg|template)\b[^>]*>.*?(?:</\1\s*>|$)|<!--.*?(?:-->|$)", re.S | re.I)
# Inline tags vanish without a trace, so "H<sub>2</sub>O" stays one word.
_INLINE_TAG = re.compile(
    r"</?(?:a|abbr|b|bdi|bdo|big|cite|code|del|em|font|i|ins|kbd|mark|nobr|q|s|samp|small|span"
    r"|strike|strong|sub|sup|time|tt|u|var|wbr)(?![a-zA-Z0-9])[^<>]*>", re.I)
# Paragraph-level tags mark a break, so a standfirst and the body after it do not run together.
_BLOCK_TAG = re.compile(
    r"</?(?:p|div|br|li|ul|ol|h[1-6]|tr|table|blockquote|section|article|header|footer|figure"
    r"|figcaption|pre|hr|dd|dt|dl)(?![a-zA-Z0-9])[^<>]*>", re.I)
_ANY_TAG = re.compile(r"<(?:[/!?]?[a-zA-Z]|!)[^<>]*>")
_BREAK = "\x1e"  # stands for a paragraph break until _join_blocks resolves it
_UNCLOSED_TAG = re.compile(r"<[/!]?[a-zA-Z][^<>]*$")
# Zero-width space, word joiner, BOM, soft hyphen, direction marks, control characters, and
# lone surrogates (JSON APIs can emit half an emoji; it cannot be stored as UTF-8).
# ZWJ/ZWNJ are kept: emoji sequences and Indic scripts need them.
_INVISIBLE = re.compile(
    "[\u200b\u2060\ufeff\u00ad\u200e\u200f\u202a-\u202e\u2066-\u2069\x00-\x08\x0e-\x1d\x1f\x7f\ud800-\udfff]")
_SPACE = re.compile(r"\s+")

_ELLIPSIS_TAIL = re.compile(r"\s*\[\s*(?:\.{2,}|…)\s*\]$")
_BOUNDARY = r"(?:(?<=[.!?…\]\)\"”’»>])|\s[-–—|·])\s*"
_LINK_PUNCT = r"[\s.…»→›>:]*$"
_LINK_PHRASE = (
    r"(?:(?:Read|READ) (?:[Mm]ore|MORE|(?:the )?[Ff]ull (?:[Ss]tory|[Aa]rticle|[Pp]ost))"
    r"|(?:Continue|CONTINUE|Keep) (?:[Rr]eading|READING))")
# A "Read more" link is only cut after a sentence boundary: "Why Kids Should Read More" is a headline.
_LINK_TAIL = re.compile(
    r"(?:^|" + _BOUNDARY + r")(?:" + _LINK_PHRASE + r"|\(?[Mm]ore ?(?:\.{3}|…)\)?)" + _LINK_PUNCT)
# ...unless the phrase carries its own ellipsis ("Continue reading..."), which no headline ends with.
_LINK_ELLIPSIS_TAIL = re.compile(r"\s" + _LINK_PHRASE + r" ?(?:\.{3}|…)[\s»→›>]*$")
_CONTINUE_TAIL = re.compile(_BOUNDARY + r"Continue reading [^.!?]{1,80}?" + _LINK_PUNCT)
_POST_MARKER = " appeared first on "
_POST_OPENER = re.compile(r"The (?:post|article|story|entry) ")


def _strip_tags(text):
    """Remove markup: hidden blocks go entirely, inline tags close up, block tags leave a
    paragraph break and anything else a space."""
    text = _HIDDEN.sub(" ", _CDATA.sub("", text))
    text = _INLINE_TAG.sub("", text)
    text = _BLOCK_TAG.sub(_BREAK, text)
    text = _ANY_TAG.sub(" ", text)
    return _UNCLOSED_TAG.sub("", text)


def _join_blocks(text):
    """Collapse whitespace and join paragraphs into one line.

    A paragraph that ends in a letter or digit (a heading, a standfirst, a list
    item) gets a full stop so it does not read as one sentence with the next.
    """
    line = ""
    for block in text.split(_BREAK):
        block = _SPACE.sub(" ", block).strip()
        if not block:
            continue
        if line:
            line += ". " if line[-1].isalnum() else " "
        line += block
    return line


def _drop_post_footer(text):
    """Cut WordPress's "The post <title> appeared first on <site>." footer.

    The footer starts at the last "The post" (or "The article") that opens a
    sentence before the marker, so neither body text nor a title containing
    those words moves the cut.
    """
    marker = text.rfind(_POST_MARKER)
    if marker == -1 or len(text) - marker > 160:
        return text
    starts = [match.start() for match in _POST_OPENER.finditer(text, 0, marker)]
    if not starts:
        return text
    at_sentence_start = [start for start in starts
                         if not text[:start].rstrip() or text[:start].rstrip()[-1] in ".!?…]\"”’)"]
    return text[:(at_sentence_start or starts)[-1]].rstrip()


def _drop_ellipsis_tail(text):
    """Replace a trailing "[...]" with a real ellipsis, or nothing after a finished sentence."""
    match = _ELLIPSIS_TAIL.search(text)
    if not match:
        return text
    head = text[:match.start()].rstrip()
    return head if not head or head[-1] in ".!?…" else head + "…"


def _trim_tails(text):
    """Strip feed boilerplate from the end until nothing more comes off."""
    while True:
        trimmed = _drop_post_footer(text)
        trimmed = _LINK_TAIL.sub("", trimmed)
        trimmed = _LINK_ELLIPSIS_TAIL.sub("", trimmed)
        trimmed = _CONTINUE_TAIL.sub("", trimmed)
        trimmed = _drop_ellipsis_tail(trimmed).rstrip()
        if trimmed == text:
            return text
        text = trimmed


def clean_text(html_or_text, limit=None):
    """Turn whatever a feed put in a title or description into one clean line of text.

    Feeds mix raw HTML, escaped HTML, double-escaped entities and CDATA
    leftovers, so tags are stripped and entities unescaped twice. Paragraphs
    are joined into one line, whitespace (including non-breaking and
    zero-width) is collapsed, and trailing boilerplate ("[...]", "Read more",
    "Continue reading", "The post X appeared first on Y") is removed. With
    ``limit`` the result is then truncated at a word boundary.
    """
    if html_or_text is None:
        return ""
    text = str(html_or_text).replace(_BREAK, "")
    for _ in range(2):
        text = html.unescape(_strip_tags(text))
    text = _join_blocks(_INVISIBLE.sub("", _strip_tags(text)))
    text = _trim_tails(text)
    return truncate(text, limit)


def truncate(text, limit):
    """Shorten ``text`` to at most ``limit`` characters, ending on a whole word plus an ellipsis.

    If the only word boundary is in the first half (one very long word), the
    text is cut hard instead, so the result never collapses to a few
    characters. ``limit=None`` means no limit.
    """
    text = text or ""
    if limit is None or len(text) <= limit:
        return text
    if limit <= 1:
        return "…" if limit == 1 else ""
    cut = text[:limit - 1]
    if not text[limit - 1].isspace():
        space = cut.rfind(" ")
        if space >= limit // 2:
            cut = cut[:space]
    return cut.rstrip(" .,;:-–—([\"'“‘") + "…"


# ---------------------------------------------------------------- titles and URLs

_TITLE_SEPARATOR = re.compile(r"\s+[-–—|]\s+")
_SECTION_SEPARATOR = re.compile(r"\s+\|\s+")
_APOSTROPHES = re.compile(r"['’‘`]")
_NOT_WORD = re.compile(r"[^\w\s]|_")


def _strip_tail(title, separator):
    """Drop what follows the last ``separator`` when it looks like a publisher or section name.

    Only a short tail that looks like a name (capitalised, or a domain) after a
    headline of four or more words is removed; "Sensex up - live updates" keeps
    its tail.
    """
    matches = list(separator.finditer(title))
    if not matches:
        return title
    head, tail = title[:matches[-1].start()], title[matches[-1].end():]
    name_like = tail[:1].isupper() or tail[:1].isdigit() or ("." in tail and " " not in tail)
    if name_like and len(tail) <= 40 and len(tail.split()) <= 5 and len(head.split()) >= 4:
        return head
    return title


def _strip_publisher(title):
    """Drop a trailing " - Publisher" (Google News and many feeds append one), then a
    " | Section" left in front of it ("Headline | India News - Hindustan Times")."""
    return _strip_tail(_strip_tail(title, _TITLE_SEPARATOR), _SECTION_SEPARATOR)


def norm_title(title):
    """A comparison key for headlines: the same story from two feeds should normalise alike.

    Lowercased, accents folded, publisher tail and punctuation removed. Not for display.
    """
    text = _strip_publisher(clean_text(title))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = _NOT_WORD.sub(" ", _APOSTROPHES.sub("", text))
    return _SPACE.sub(" ", text).strip()


_TRACKING_PREFIXES = ("utm_", "at_")
_TRACKING_PARAMS = frozenset((
    "traffic_source", "maca", "ref", "ref_src", "fbclid", "gclid", "dclid", "msclkid",
    "igshid", "mc_cid", "mc_eid", "oc", "cmpid", "ncid", "ocid",
))


def _is_tracking(pair):
    """True for a query pair whose name only identifies where the click came from."""
    name = pair.split("=", 1)[0].lower()
    return name in _TRACKING_PARAMS or name.startswith(_TRACKING_PREFIXES)


def canonical_url(url):
    """One spelling per article, so the same link from two feeds dedupes and gets one id.

    Strips tracking parameters and the fragment, lowercases the host, upgrades
    http to https and drops a trailing slash. Google News article links are
    opaque tokens that must be used exactly as given, so they pass through
    untouched. Anything that is not an http(s) URL is returned trimmed.
    """
    text = str(url or "").strip()
    for entity in ("&amp;", "&#038;", "&#38;"):
        text = text.replace(entity, "&")
    if text.startswith("//"):
        text = "https:" + text
    try:
        parts = urllib.parse.urlsplit(text)
        host, port = parts.hostname, parts.port
    except ValueError:
        return text
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https") or not host:
        return text
    if host == "news.google.com":
        return text
    if port in (None, 80, 443):
        scheme, port = "https", None
    netloc = "[%s]" % host if ":" in host else host
    if port is not None:
        netloc += ":%d" % port
    userinfo = parts.netloc.rpartition("@")[0]
    if userinfo:
        netloc = userinfo + "@" + netloc
    query = "&".join(pair for pair in parts.query.split("&") if pair and not _is_tracking(pair))
    return urllib.parse.urlunsplit((scheme, netloc, parts.path.rstrip("/"), query, ""))


def stable_id(prefix, *parts):
    """``prefix`` + the first 10 hex digits of sha1 over the parts: short, stable across runs."""
    joined = "\x1f".join(str(part) for part in parts)
    return prefix + hashlib.sha1(joined.encode("utf-8", "surrogatepass")).hexdigest()[:10]


# ---------------------------------------------------------------- tokens and stems

_ACCENTS = re.compile("[\u0300-\u036f]")
_CANDIDATE = re.compile(r"[a-z0-9]+(?:[&.\-][a-z0-9]+)*(?:\++(?![a-z0-9+]))?")
_INNER_JOIN = re.compile(r"[.\-]")
_DIGIT = re.compile(r"[0-9]")


def tokenize(text):
    """Split text into search tokens (see the module docstring for the exact rules).

    Model names and tickers keep their punctuation when they contain a digit
    (``gpt-5.5``, ``3.5-turbo``); ``s&p`` and ``c++`` stay whole. Stopwords are
    left in: callers decide whether to drop them.
    """
    folded = _ACCENTS.sub("", unicodedata.normalize("NFKD", text or "")).lower()
    tokens = []
    for match in _CANDIDATE.finditer(folded):
        candidate = match.group()
        parts = [candidate] if _DIGIT.search(candidate) else _INNER_JOIN.split(candidate)
        tokens.extend(part for part in parts if len(part) > 1 or "0" <= part <= "9")
    return tokens


def _strip_plural(word):
    """Step 2 of ``stem``: undo the common plural endings, first match only."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("sses"):
        return word[:-2]
    if word.endswith(("xes", "ches", "shes", "zes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def _undouble(word):
    """"runn" -> "run": drop one of a final doubled consonant, except l, s and z."""
    last = word[-1]
    if word[-2] == last and "a" <= last <= "z" and last not in "aeioulsz":
        return word[:-1]
    return word


def stem(token):
    """A deliberately light stemmer: enough to match plurals and -ing/-ed/-ly, never clever.

    Expects a token from ``tokenize``. Short tokens and anything with a digit
    (tickers, versions) are returned unchanged.
    """
    if len(token) <= 3 or _DIGIT.search(token):
        return token
    word = _strip_plural(token)
    for suffix, undouble in (("ing", True), ("ed", True), ("ly", False)):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            base = word[:-len(suffix)]
            return _undouble(base) if undouble else base
    return word


STOPWORDS = frozenset("""
a about above across after again against all almost also although always am among an and
another any are aren around as at be because been before being below between both but by can
cannot could couldn did didn do does doesn doing don down during each either even ever every
few for from further had hadn has hasn have haven having he her here hers herself him himself
his how however i if in into is isn it its itself just ll may me might more most much must my
myself neither no nor not now of off often on once only or other our ours ourselves out over
own per rather re same shall she should shouldn since so some still such than that the their
theirs them themselves then there these they this those though through to too toward towards
under until up upon ve very was wasn we were weren what when where whether which while who
whom whose why will with within without won would wouldn yet you your yours yourself yourselves
says said new report reports amid via video watch live update updates
""".split())
