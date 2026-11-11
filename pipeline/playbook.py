"""Compile the hand-written Claude playbook (``content/claude``) into ``public/claude/playbook.json``.

Feature and recipe files are markdown with a front matter block (see
docs/ARCHITECTURE.md, "Public: claude"). Several people write them, so the
parser is strict and says exactly what is wrong and where: a bad file is
skipped and reported in ``state/playbook-errors.json`` and in the stage counts,
never fatal, and never published half-valid.

Two small parsers live here instead of a dependency:

* ``parse_front_matter`` reads the documented YAML subset: ``key: value``
  scalars (optionally quoted), inline lists ``[a, b]``, one level of
  ``- key: value`` object lists, and ``#`` comments. Anything else is an error
  rather than a guess.
* ``render_markdown`` turns the body into HTML. Every piece of text is
  HTML-escaped before any markup is added, raw HTML stays visible as text, and
  links are emitted only for http(s) URLs, so the output is safe to insert.
"""

import html
import re
import urllib.parse
from datetime import date

from .core import jsonio, log, timeutil

SURFACES = (
    ("apps", "Claude apps"),
    ("code", "Claude Code"),
    ("platform", "API and platform"),
    ("cowork", "Cowork"),
    ("integrations", "Claude in other tools"),
)
JOBS = (
    ("coding", "Coding"),
    ("review", "Review"),
    ("debugging", "Debugging"),
    ("writing", "Writing"),
    ("research", "Research"),
    ("analysis", "Analysis"),
    ("meetings", "Meetings"),
    ("planning", "Planning"),
    ("automation", "Automation"),
    ("learning", "Learning"),
)
SURFACE_IDS = tuple(sid for sid, _ in SURFACES)
JOB_IDS = tuple(jid for jid, _ in JOBS)
STATUSES = ("new", "stable", "beta")
LEVELS = ("starter", "intermediate", "power")
EXAMPLE_KINDS = ("prompt", "command", "config")

FEATURE_FIELDS = ("id", "title", "surface", "group", "status", "since", "level", "payoff", "effort",
                  "jobs", "tags", "summary", "when", "replaces", "example_kind", "docs", "verified")
RECIPE_FIELDS = ("id", "title", "job", "level", "minutes_saved", "features", "prerequisites",
                 "fields", "docs", "verified")

_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")


class ContentError(ValueError):
    """A problem in one content file. ``line`` is 1-based within the file, or None."""

    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line


# ---------------------------------------------------------------- front matter

_KEY_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(?:[ ]+(.*))?$")
_ITEM_LINE = re.compile(r"^  - ([A-Za-z_][A-Za-z0-9_]*):(?:[ ]+(.*))?$")
_MORE_LINE = re.compile(r"^    ([A-Za-z_][A-Za-z0-9_]*):(?:[ ]+(.*))?$")
_BARE_ITEM = re.compile(r"^\s*- (?![A-Za-z_][A-Za-z0-9_]*:)")
_INT = re.compile(r"^-?[0-9]+$")
# Characters YAML gives a meaning to at the start of a plain scalar; such values must be quoted.
_RESERVED_START = tuple("{}&*!|>%@`,")
_DQ_ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t", "/": "/"}


def split_document(text):
    """Split a content file into (front matter lines, body text, body's first line number).

    The file must start with a ``---`` line and the front matter ends at the
    next ``---`` line; anything else is reported, not guessed at.
    """
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        raise ContentError("file must start with a '---' front matter line", 1)
    for index in range(1, len(lines)):
        if lines[index].rstrip() == "---":
            return lines[1:index], "\n".join(lines[index + 1:]), index + 2
    raise ContentError("front matter is not closed with a '---' line", 1)


def _strip_comment(rest, line_no):
    """What may follow a closed value: nothing, or a comment. Anything else is an error."""
    rest = rest.strip()
    if rest and not rest.startswith("#"):
        raise ContentError("unexpected text after the value: %r" % rest, line_no)


def _double_quoted(text, line_no):
    """Read a double-quoted scalar at the start of ``text``; return (value, remainder)."""
    out, index = [], 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            escape = text[index + 1:index + 2]
            if escape not in _DQ_ESCAPES:
                raise ContentError("unsupported escape '\\%s' in a quoted value" % escape, line_no)
            out.append(_DQ_ESCAPES[escape])
            index += 2
            continue
        if char == '"':
            return "".join(out), text[index + 1:]
        out.append(char)
        index += 1
    raise ContentError("missing closing double quote", line_no)


def _single_quoted(text, line_no):
    """Read a single-quoted scalar (``''`` is a literal quote); return (value, remainder)."""
    out, index = [], 1
    while index < len(text):
        if text[index] == "'":
            if text[index + 1:index + 2] == "'":
                out.append("'")
                index += 2
                continue
            return "".join(out), text[index + 1:]
        out.append(text[index])
        index += 1
    raise ContentError("missing closing single quote", line_no)


def _plain(text, line_no):
    """An unquoted scalar: comment removed, digits become an int, YAML-special text refused."""
    value = re.split(r"\s#", text, maxsplit=1)[0].strip()
    if value.startswith(_RESERVED_START):
        raise ContentError("value %r starts with %r; wrap it in quotes" % (value, value[0]), line_no)
    if ": " in value or value.endswith(":"):
        raise ContentError("value %r contains ': '; wrap it in quotes" % value, line_no)
    if _INT.match(value):
        return int(value)
    return value


def _inline_list(text, line_no):
    """Parse ``[a, "b, c", 'd']`` into a list of strings; ``[]`` is an empty list."""
    items, rest = [], text[1:].lstrip()
    if rest.startswith("]"):
        _strip_comment(rest[1:], line_no)
        return items
    while True:
        rest = rest.lstrip()
        if rest.startswith('"'):
            item, rest = _double_quoted(rest, line_no)
        elif rest.startswith("'"):
            item, rest = _single_quoted(rest, line_no)
        else:
            match = re.match(r"[^,\]\[]*", rest)
            item, rest = match.group(0).strip(), rest[match.end():]
            if rest.startswith("["):
                raise ContentError("nested lists are not supported", line_no)
            if not item:
                raise ContentError("empty item in list", line_no)
            if item.startswith(_RESERVED_START) or item.startswith(("'", '"')):
                raise ContentError("list item %r must be quoted" % item, line_no)
        items.append(item)
        rest = rest.lstrip()
        if rest.startswith(","):
            rest = rest[1:]
            continue
        if rest.startswith("]"):
            _strip_comment(rest[1:], line_no)
            return items
        raise ContentError("list is not closed with ']'", line_no)


def parse_value(text, line_no):
    """Parse the text after ``key:`` into a str, int or list of str."""
    text = text.strip()
    if text.startswith('"'):
        value, rest = _double_quoted(text, line_no)
        _strip_comment(rest, line_no)
        return value
    if text.startswith("'"):
        value, rest = _single_quoted(text, line_no)
        _strip_comment(rest, line_no)
        return value
    if text.startswith("["):
        return _inline_list(text, line_no)
    return _plain(text, line_no)


def _check_new_key(store, key, line_no, what):
    """Duplicate keys silently overwrite in most YAML readers; here they are an error."""
    if key in store:
        raise ContentError("duplicate key %r in %s" % (key, what), line_no)


def parse_front_matter(lines, first_line=2):
    """Parse front matter lines into (values, key line numbers).

    ``first_line`` is the file line number of ``lines[0]`` so errors point at
    the real line. Object lists come back as lists of dicts of scalars.
    """
    values, key_lines = {}, {}
    items = None  # the list being filled while reading "  - key: value" lines
    for offset, raw in enumerate(lines):
        line_no = first_line + offset
        if "\t" in raw:
            raise ContentError("tab character; indent with spaces", line_no)
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top, item, more = _KEY_LINE.match(line), _ITEM_LINE.match(line), _MORE_LINE.match(line)
        if top:
            key, value = top.group(1), (top.group(2) or "").strip()
            _check_new_key(values, key, line_no, "front matter")
            key_lines[key] = line_no
            if value and not value.startswith("#"):
                values[key], items = parse_value(value, line_no), None
            else:
                values[key] = items = []
        elif (item or more) and items is None:
            raise ContentError("indented line does not belong to a list key", line_no)
        elif item:
            items.append({item.group(1): parse_value(item.group(2) or "", line_no)})
        elif more:
            if not items:
                raise ContentError("expected '  - key: value' to start a list item", line_no)
            _check_new_key(items[-1], more.group(1), line_no, "list item")
            items[-1][more.group(1)] = parse_value(more.group(2) or "", line_no)
        elif _BARE_ITEM.match(line):
            raise ContentError("'- value' lists are not supported; write an inline list [a, b] "
                               "or '  - key: value' items", line_no)
        else:
            raise ContentError("cannot read this line; expected 'key: value' (two-space indent "
                               "for '- key: value' items, four for their other keys)", line_no)
    for key, value in values.items():
        if value == [] and _opened_block(lines[key_lines[key] - first_line]):
            raise ContentError("%r has no value" % key, key_lines[key])
    return values, key_lines


def _opened_block(line):
    """True when a key line had no inline value, so an empty result means the value is missing.

    ``tags: []`` is an explicit empty list and is fine; ``tags:`` with nothing under it is not.
    """
    value = (_KEY_LINE.match(line.rstrip()).group(2) or "").strip()
    return not value or value.startswith("#")


# ---------------------------------------------------------------- markdown

# An opening fence may carry an info string ("```json title"); its first word is the language.
_FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})[ \t]*([^\s`]*)[^`]*$")
_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
_HR = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
_LIST_ITEM = re.compile(r"^( *)([-*+]|\d{1,9}[.)])[ \t]+(.*)$")
_QUOTE = re.compile(r"^ {0,3}> ?(.*)$")
_LANG = re.compile(r"^[A-Za-z0-9_+#.-]{1,24}$")

_CODE_SPAN = re.compile(r"(`+)(.+?)\1", re.S)
_ESCAPED = re.compile(r"\\([!-/:-@\[-`{-~])")
_LINK = re.compile(r"\[([^\[\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)")
_STRONG = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_EM_STAR = re.compile(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])")
_EM_UNDER = re.compile(r"(?<![\w])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\w])")
# Private-use characters mark spans already rendered, so later passes cannot touch them.
_HOLD_OPEN, _HOLD_CLOSE = "\ue000", "\ue001"
_HOLD = re.compile(_HOLD_OPEN + r"(\d+)" + _HOLD_CLOSE)


def safe_url(url):
    """True for an absolute http(s) URL; everything else (javascript:, data:, relative) is refused."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if re.search(r"[\s\x00-\x1f<>\"'`\\]", url):
        return False
    return parts.scheme.lower() in ("http", "https") and bool(parts.netloc)


def _escape(text):
    return html.escape(text, quote=True)


class _Inline:
    """Renders one run of inline markdown. Collects problems (unsafe links) in ``warnings``."""

    def __init__(self, warnings):
        self.warnings = warnings
        self.held = []

    def _hold(self, rendered):
        self.held.append(rendered)
        return "%s%d%s" % (_HOLD_OPEN, len(self.held) - 1, _HOLD_CLOSE)

    def _restore(self, text):
        while _HOLD.search(text):
            text = _HOLD.sub(lambda m: self.held[int(m.group(1))], text)
        return text

    def _code(self, match):
        body = match.group(2)
        if body.startswith(" ") and body.endswith(" ") and body.strip():
            body = body[1:-1]
        return self._hold("<code>%s</code>" % _escape(body))

    def _link(self, match):
        label, url = match.group(1), match.group(2)
        inner = self._emphasis(_escape(label))
        if not safe_url(url):
            self.warnings.append("link to %r is not an http(s) URL; it was rendered as text" % url)
            return self._hold(inner)
        return self._hold('<a href="%s" rel="noopener noreferrer">%s</a>' % (_escape(url), inner))

    @staticmethod
    def _emphasis(escaped):
        escaped = _STRONG.sub(r"<strong>\2</strong>", escaped)
        escaped = _EM_STAR.sub(r"<em>\1</em>", escaped)
        return _EM_UNDER.sub(r"<em>\1</em>", escaped)

    def render(self, text):
        text = text.replace(_HOLD_OPEN, "").replace(_HOLD_CLOSE, "")
        text = _CODE_SPAN.sub(self._code, text)
        text = _ESCAPED.sub(lambda m: self._hold(_escape(m.group(1))), text)
        text = _LINK.sub(self._link, text)
        return self._restore(self._emphasis(_escape(text)))


def render_inline(text, warnings=None):
    """Inline markdown (code, links, bold, italic) to safe HTML."""
    return _Inline(warnings if warnings is not None else []).render(text)


def _starts_block(line):
    """True when ``line`` begins a block, so it ends the paragraph before it."""
    return bool(_FENCE.match(line) or _HEADING.match(line) or _HR.match(line)
                or _QUOTE.match(line) or _LIST_ITEM.match(line))


def _dedent(lines):
    """Remove the common leading indentation of the non-blank lines."""
    widths = [len(line) - len(line.lstrip(" ")) for line in lines if line.strip()]
    cut = min(widths) if widths else 0
    return [line[cut:] for line in lines]


class _Blocks:
    """Splits markdown lines into blocks: heading, para, code, list, quote, hr."""

    def __init__(self, lines, first_line):
        self.lines = lines
        self.first_line = first_line
        self.index = 0

    def parse(self):
        blocks = []
        while self.index < len(self.lines):
            line = self.lines[self.index]
            if not line.strip():
                self.index += 1
                continue
            blocks.append(self._block(line))
        return blocks

    def _block(self, line):
        if _FENCE.match(line):
            return self._code()
        heading = _HEADING.match(line)
        if heading:
            self.index += 1
            return {"type": "heading", "level": len(heading.group(1)), "text": heading.group(2).strip(),
                    "line": self.first_line + self.index - 1}
        if _HR.match(line):
            self.index += 1
            return {"type": "hr"}
        if _QUOTE.match(line):
            return self._quote()
        if _LIST_ITEM.match(line):
            return self._list()
        return self._para()

    def _code(self):
        start = self.index
        opening = _FENCE.match(self.lines[start])
        marker = opening.group(2)
        lang = opening.group(3)
        if lang and not _LANG.match(lang):
            raise ContentError("unusual code fence language %r" % lang, self.first_line + start)
        body = []
        self.index += 1
        while self.index < len(self.lines):
            line = self.lines[self.index]
            self.index += 1
            fence = line.strip()
            if len(fence) >= len(marker) and fence == marker[0] * len(fence) and len(line) - len(line.lstrip()) < 4:
                indent = len(opening.group(1))
                body = [b[indent:] if b[:indent].strip() == "" else b.lstrip() for b in body]
                return {"type": "code", "lang": lang.lower(), "code": "\n".join(body),
                        "line": self.first_line + start}
            body.append(line)
        raise ContentError("code fence opened here is never closed", self.first_line + start)

    def _quote(self):
        start, inner = self.index, []
        while self.index < len(self.lines):
            match = _QUOTE.match(self.lines[self.index])
            if not match:
                break
            inner.append(match.group(1))
            self.index += 1
        return {"type": "quote", "blocks": _Blocks(inner, self.first_line + start).parse()}

    def _para(self):
        text = [self.lines[self.index].strip()]
        self.index += 1
        while self.index < len(self.lines):
            line = self.lines[self.index]
            if not line.strip() or _starts_block(line):
                break
            text.append(line.strip())
            self.index += 1
        return {"type": "para", "text": "\n".join(text)}

    def _list(self):
        first = _LIST_ITEM.match(self.lines[self.index])
        base = len(first.group(1))
        ordered = first.group(2)[0].isdigit()
        start = int(first.group(2)[:-1]) if ordered else 1
        items = []
        while self.index < len(self.lines):
            line = self.lines[self.index]
            match = _LIST_ITEM.match(line)
            indent = len(line) - len(line.lstrip(" "))
            if match and indent <= base + 1:
                if match.group(2)[0].isdigit() != ordered:
                    break
                items.append({"text": [match.group(3).strip()], "children": [],
                              "line": self.first_line + self.index})
                self.index += 1
                continue
            if not line.strip():
                if self._list_continues(base, ordered):
                    items[-1]["children"].append("")
                    self.index += 1
                    continue
                break
            item = items[-1]
            if indent >= base + 2:
                if item["children"] or _starts_block(line.strip()):
                    item["children"].append(line)
                else:
                    item["text"].append(line.strip())
                self.index += 1
                continue
            if not _starts_block(line) and not item["children"]:
                item["text"].append(line.strip())  # lazy continuation of the item's paragraph
                self.index += 1
                continue
            break
        for item in items:
            children = _dedent(item.pop("children"))
            item["blocks"] = _Blocks(children, item["line"] + 1).parse() if any(children) else []
            item["text"] = "\n".join(item["text"])
        return {"type": "list", "ordered": ordered, "start": start, "items": items}

    def _list_continues(self, base, ordered):
        """After a blank line: does the next non-blank line still belong to this list?"""
        ahead = self.index + 1
        while ahead < len(self.lines) and not self.lines[ahead].strip():
            ahead += 1
        if ahead >= len(self.lines):
            return False
        line = self.lines[ahead]
        indent = len(line) - len(line.lstrip(" "))
        if indent >= base + 2:
            return True
        match = _LIST_ITEM.match(line)
        return bool(match and indent <= base + 1 and match.group(2)[0].isdigit() == ordered)


def parse_markdown(text, first_line=1):
    """Markdown text to a list of block dicts (raises ContentError on an unclosed fence)."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return _Blocks(lines, first_line).parse()


def render_blocks(blocks, warnings=None):
    """Blocks to an HTML string. Unsafe links are dropped to text and noted in ``warnings``."""
    warnings = warnings if warnings is not None else []
    out = []
    for block in blocks:
        kind = block["type"]
        if kind == "heading":
            out.append("<h%d>%s</h%d>" % (block["level"], render_inline(block["text"], warnings),
                                          block["level"]))
        elif kind == "para":
            out.append("<p>%s</p>" % render_inline(block["text"], warnings))
        elif kind == "code":
            css = ' class="language-%s"' % _escape(block["lang"]) if block["lang"] else ""
            out.append("<pre><code%s>%s</code></pre>" % (css, _escape(block["code"])))
        elif kind == "hr":
            out.append("<hr>")
        elif kind == "quote":
            out.append("<blockquote>%s</blockquote>" % render_blocks(block["blocks"], warnings))
        elif kind == "list":
            out.append(_render_list(block, warnings))
    return "\n".join(out)


def _render_list(block, warnings):
    tag = "ol" if block["ordered"] else "ul"
    start = ' start="%d"' % block["start"] if block["ordered"] and block["start"] != 1 else ""
    items = []
    for item in block["items"]:
        inner = render_inline(item["text"], warnings)
        if item["blocks"]:
            inner += "\n" + render_blocks(item["blocks"], warnings)
        items.append("<li>%s</li>" % inner)
    return "<%s%s>\n%s\n</%s>" % (tag, start, "\n".join(items), tag)


def render_markdown(text, warnings=None):
    """Markdown to safe HTML in one call."""
    return render_blocks(parse_markdown(text), warnings)


def first_code_under(blocks, heading):
    """The first fenced block in the ``## <heading>`` section, or None.

    The section runs to the next heading of level 2 or higher.
    """
    inside = False
    for block in blocks:
        if block["type"] == "heading" and block["level"] <= 2:
            inside = block["level"] == 2 and block["text"].strip().lower() == heading.lower()
            continue
        if inside and block["type"] == "code":
            return block
    return None


# ---------------------------------------------------------------- validation

_PLACEHOLDER = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")


def template_fields(template):
    """Placeholder names used in a template, in order of first use; bad names raise ContentError."""
    names = []
    for match in _PLACEHOLDER.finditer(template):
        name = match.group(1)
        if not _FIELD_NAME.match(name):
            raise ContentError("placeholder {{%s}} is not a valid field name" % name)
        if name not in names:
            names.append(name)
    leftover = _PLACEHOLDER.sub("", template)
    if "{{" in leftover or "}}" in leftover:
        raise ContentError("unbalanced '{{' or '}}' in the prompt template")
    return names


class _Checker:
    """Collects every validation problem in one file, so an author fixes them in one pass."""

    def __init__(self, values, key_lines):
        self.values = values
        self.key_lines = key_lines
        self.errors = []

    def fail(self, key, message):
        self.errors.append(ContentError("%s: %s" % (key, message), self.key_lines.get(key)))

    def text(self, key):
        value = self.values.get(key)
        if not isinstance(value, str) or not value.strip():
            self.fail(key, "must be non-empty text")
            return None
        return value.strip()

    def choice(self, key, allowed):
        value = self.values.get(key)
        if value not in allowed:
            self.fail(key, "%r is not one of %s" % (value, ", ".join(allowed)))
            return None
        return value

    def number(self, key, low, high=None):
        """A whole number in [low, high]; ``high=None`` means no upper bound."""
        value = self.values.get(key)
        in_range = isinstance(value, int) and value >= low and (high is None or value <= high)
        if not in_range:
            limit = "%d-%d" % (low, high) if high is not None else "of at least %d" % low
            self.fail(key, "must be a whole number %s, got %r" % (limit, value))
            return None
        return value

    def strings(self, key, allowed=None, non_empty=True):
        value = self.values.get(key)
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
            self.fail(key, "must be an inline list like [a, b]")
            return None
        if non_empty and not value:
            self.fail(key, "must list at least one value")
            return None
        if len(set(value)) != len(value):
            self.fail(key, "lists the same value twice")
        if allowed is not None:
            unknown = [v for v in value if v not in allowed]
            if unknown:
                self.fail(key, "unknown value(s) %s; use %s" % (", ".join(unknown), ", ".join(allowed)))
                return None
        return [v.strip() for v in value]

    def day(self, key, optional=False):
        value = self.values.get(key)
        if value is None and optional:
            return None
        if isinstance(value, str) and (_DAY.match(value) or (optional and _MONTH.match(value))):
            parts = [int(p) for p in value.split("-")] + [1]
            try:
                date(parts[0], parts[1], parts[2])
                return value
            except ValueError:
                pass
        shape = "YYYY-MM or YYYY-MM-DD" if optional else "YYYY-MM-DD"
        self.fail(key, "%r is not a valid date (%s)" % (value, shape))
        return None

    def objects(self, key, keys):
        value = self.values.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(v, dict) for v in value):
            self.fail(key, "must be a list of '  - %s: ...' items" % keys[0])
            return None
        out = []
        for position, entry in enumerate(value, 1):
            extra, missing = set(entry) - set(keys), [k for k in keys if not str(entry.get(k, "")).strip()]
            if extra or missing:
                self.fail(key, "item %d needs exactly %s (missing: %s; unknown: %s)" % (
                    position, ", ".join(keys), ", ".join(missing) or "none", ", ".join(sorted(extra)) or "none"))
                return None
            out.append({k: str(entry[k]).strip() for k in keys})
        return out

    def docs(self):
        docs = self.objects("docs", ("title", "url"))
        for doc in docs or []:
            if not doc["url"].startswith("https://") or not safe_url(doc["url"]):
                self.fail("docs", "%r is not an https URL" % doc["url"])
                return None
        return docs

    def unknown_keys(self, known):
        for key in self.values:
            if key not in known:
                self.fail(key, "unknown field (expected one of %s)" % ", ".join(known))


def _check_feature(values, key_lines, stem):
    check = _Checker(values, key_lines)
    check.unknown_keys(FEATURE_FIELDS)
    feature = {
        "id": check.text("id"),
        "title": check.text("title"),
        "surface": check.choice("surface", SURFACE_IDS),
        "group": check.text("group"),
        "status": check.choice("status", STATUSES),
        "since": check.day("since", optional=True),
        "level": check.choice("level", LEVELS),
        "payoff": check.number("payoff", 1, 3),
        "effort": check.number("effort", 1, 3),
        "jobs": check.strings("jobs", JOB_IDS),
        "tags": check.strings("tags"),
        "summary": check.text("summary"),
        "when": check.text("when"),
        "replaces": check.text("replaces"),
        "example_kind": check.choice("example_kind", EXAMPLE_KINDS),
        "docs": check.docs(),
        "verified": check.day("verified"),
    }
    _check_id(check, feature["id"], stem)
    return feature, check.errors


def _check_recipe(values, key_lines, stem, feature_ids):
    check = _Checker(values, key_lines)
    check.unknown_keys(RECIPE_FIELDS)
    recipe = {
        "id": check.text("id"),
        "title": check.text("title"),
        "job": check.choice("job", JOB_IDS),
        "level": check.choice("level", LEVELS),
        "minutes_saved": check.number("minutes_saved", 1),
        "features": check.strings("features"),
        "prerequisites": check.strings("prerequisites", non_empty=False),
        "fields": check.objects("fields", ("name", "label", "placeholder")),
        "docs": check.docs(),
        "verified": check.day("verified"),
    }
    _check_id(check, recipe["id"], stem)
    unknown = [f for f in recipe["features"] or [] if f not in feature_ids]
    if unknown:
        check.fail("features", "unknown or invalid feature id(s): %s" % ", ".join(unknown))
    names = [field["name"] for field in recipe["fields"] or []]
    bad = [n for n in names if not _FIELD_NAME.match(n)]
    if bad:
        check.fail("fields", "field names must be lowercase words with underscores: %s" % ", ".join(bad))
    if len(set(names)) != len(names):
        check.fail("fields", "two fields share a name")
    return recipe, check.errors


def _check_id(check, value, stem):
    if value is None:
        return
    if not _ID.match(value):
        check.fail("id", "%r must be lowercase words joined by '-'" % value)
    elif value != stem:
        check.fail("id", "%r does not match the file name %s.md" % (value, stem))


def _check_template(recipe, template_block):
    """Every {{placeholder}} needs a field and every field must be used."""
    if template_block is None:
        return [ContentError("'## Prompt' has no fenced code block for the template")]
    try:
        used = template_fields(template_block["code"])
    except ContentError as err:
        return [ContentError(err.message, template_block["line"])]
    declared = [field["name"] for field in recipe["fields"] or []]
    errors = []
    missing = [n for n in used if n not in declared]
    unused = [n for n in declared if n not in used]
    if missing:
        errors.append(ContentError("template uses {{%s}} with no matching entry in fields"
                                   % "}}, {{".join(missing), template_block["line"]))
    if unused:
        errors.append(ContentError("fields %s are never used in the template" % ", ".join(unused),
                                   template_block["line"]))
    return errors


def _compile_body(body, body_line):
    """(blocks, html, warnings as errors) for a body; raises ContentError on a broken fence."""
    blocks = parse_markdown(body, body_line)
    warnings = []
    rendered = render_blocks(blocks, warnings)
    return blocks, rendered, [ContentError(w) for w in warnings]


def compile_feature(text, stem):
    """One feature file to (feature dict or None, [ContentError])."""
    try:
        fm_lines, body, body_line = split_document(text)
        values, key_lines = parse_front_matter(fm_lines)
        feature, errors = _check_feature(values, key_lines, stem)
        blocks, rendered, warnings = _compile_body(body, body_line)
    except ContentError as err:
        return None, [err]
    errors += warnings
    example = first_code_under(blocks, "Example")
    if example is None:
        errors.append(ContentError("'## Example' has no fenced code block"))
    if errors:
        return None, errors
    feature["example"] = example["code"]
    feature["html"] = rendered
    return feature, []


def compile_recipe(text, stem, feature_ids):
    """One recipe file to (recipe dict or None, [ContentError])."""
    try:
        fm_lines, body, body_line = split_document(text)
        values, key_lines = parse_front_matter(fm_lines)
        recipe, errors = _check_recipe(values, key_lines, stem, feature_ids)
        blocks, rendered, warnings = _compile_body(body, body_line)
    except ContentError as err:
        return None, [err]
    template = first_code_under(blocks, "Prompt")
    errors += warnings + _check_template(recipe, template)
    if errors:
        return None, errors
    recipe["template"] = template["code"]
    recipe["html"] = rendered
    return recipe, []


# ---------------------------------------------------------------- the whole playbook

def _read(path):
    """File text, or a ContentError naming why it could not be read."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        raise ContentError("cannot read file: %s" % err) from err


def _compile_kind(directory, root, compile_one, seen_ids, report):
    """Compile every ``*.md`` in ``directory``; bad files go to ``report`` and are skipped."""
    compiled = []
    if not directory.is_dir():
        return compiled
    for path in sorted(directory.glob("*.md")):
        rel = path.relative_to(root).as_posix() if root in path.parents else str(path)
        try:
            item, errors = compile_one(_read(path), path.stem)
        except ContentError as err:
            item, errors = None, [err]
        if item is not None and item["id"] in seen_ids:
            item, errors = None, [ContentError("duplicate id %r (also used by %s)"
                                               % (item["id"], seen_ids[item["id"]]))]
        for err in errors:
            report.append({"file": rel, "line": err.line, "message": err.message})
        if item is not None:
            seen_ids[item["id"]] = rel
            compiled.append(item)
    return compiled


def compile_playbook(content_dir, root):
    """Compile ``content_dir/features`` and ``content_dir/recipes``.

    Returns (features, recipes, errors); ``errors`` are dicts with file, line
    and message. Recipes are checked against the features that compiled.
    """
    errors, seen = [], {}
    features = _compile_kind(content_dir / "features", root, compile_feature, seen, errors)
    feature_ids = {feature["id"] for feature in features}
    recipes = _compile_kind(content_dir / "recipes", root,
                            lambda text, stem: compile_recipe(text, stem, feature_ids), seen, errors)
    surface_rank = {sid: rank for rank, sid in enumerate(SURFACE_IDS)}
    features.sort(key=lambda f: (surface_rank[f["surface"]], f["group"].lower(), f["title"].lower()))
    recipes.sort(key=lambda r: r["title"].lower())
    return features, recipes, errors


def build(ctx):
    """Compile the playbook, write playbook.json and state/playbook-errors.json, return (features, counts).

    Raises OSError if playbook.json cannot be written: that is this stage's own output.
    """
    content_dir = ctx.paths.root / "content" / "claude"
    if not content_dir.is_dir():
        log.warn("no playbook content at %s; writing an empty playbook", content_dir)
    features, recipes, errors = compile_playbook(content_dir, ctx.paths.root)
    for err in errors:
        log.warn("%s%s: %s", err["file"], ":%d" % err["line"] if err["line"] else "", err["message"])
    generated = timeutil.iso(ctx.now)
    playbook = {
        "generatedAt": generated,
        "surfaces": [{"id": sid, "name": name} for sid, name in SURFACES],
        "jobs": [{"id": jid, "name": name} for jid, name in JOBS],
        "features": features,
        "recipes": recipes,
    }
    jsonio.write_json(ctx.paths.claude_dir / "playbook.json", playbook)
    try:
        jsonio.write_json(ctx.paths.state / "playbook-errors.json", {"generatedAt": generated, "errors": errors})
    except OSError as err:
        log.error("could not write playbook-errors.json: %s", err)
    files_with_errors = len({err["file"] for err in errors})
    log.info("playbook: %d features, %d recipes, %d content errors in %d files",
             len(features), len(recipes), len(errors), files_with_errors)
    counts = {"features": len(features), "recipes": len(recipes), "contentErrors": len(errors),
              "contentFilesSkipped": files_with_errors}
    return features, counts
