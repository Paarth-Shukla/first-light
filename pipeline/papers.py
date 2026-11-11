"""Weekend Review: the week's five most-noticed CS and electronics papers, plus the week in review.

Runs on the first pipeline run of the site's weekend day (``site.json`` weekend.weekday)
or on demand with ``papers --force``. The issue covers the ``lookbackDays`` local days
ending yesterday and is filed under the ISO week that contains the window's last day.

Why it is built this way:

* Candidates come from the arXiv API, one query per category for the window, plus any
  recent paper a signal provider names that those queries missed. arXiv asks for 3 s
  between requests and a week is several thousand papers, so parsed responses are
  cached for the day under ``state/papers-cache/``; a re-run the same day is offline.
* Attention comes from free providers (Hugging Face daily papers, alphaXiv, Hacker
  News, OpenAlex citations) and from our own news item store. Any of them can be down,
  so each is collected on its own and the score is renormalised over the signals that
  arrived. Signals are scaled per track, because a busy hardware paper gets a tenth of
  the votes of a busy ML paper.
* Electronics papers get almost no online votes, so that track also earns credit from
  facts in the paper record: an accepted-venue comment, a code link, cross-listing,
  and measured numbers in the abstract.
* The digest is extractive: every field is one verbatim sentence of the abstract
  (after LaTeX is turned into readable text) or empty. Nothing is paraphrased.
"""

import json
import math
import re
import shutil
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, time, timedelta

from .core import config, jsonio, log, net, textutil, timeutil

# ------------------------------------------------------------------ window and due logic


def issue_window(now, tz, lookback_days):
    """(first, last) local dates covered: the ``lookback_days`` days ending yesterday.

    Ending yesterday means a Saturday run reviews Saturday to Friday, and a forced
    mid-week run reviews the latest complete days rather than a half-finished one.
    """
    last = date.fromisoformat(timeutil.local_date(now, tz)) - timedelta(days=1)
    return last - timedelta(days=lookback_days - 1), last


def window_bounds(first, last, tz):
    """UTC [start, end) instants of the local-date window, for date filters and API queries."""
    start = datetime.combine(first, time(0), tzinfo=tz).astimezone(timeutil.UTC)
    end = datetime.combine(last + timedelta(days=1), time(0), tzinfo=tz).astimezone(timeutil.UTC)
    return start, end


def week_of(day):
    """ISO week label (``2026-W46``) of a calendar date."""
    year, week, _ = day.isocalendar()
    return "%04d-W%02d" % (year, week)


def is_due(now, tz, weekday, issue_path, force, window_last=None):
    """True when the issue should be built now.

    Due on the configured local weekday until that week's file exists and
    covers this window (it ends on ``window_last``); ``force`` rebuilds on any
    day (development, backfills) and overwrites the file. Without
    ``window_last`` any existing file counts as built.
    """
    if force:
        return True
    local = now.astimezone(tz)
    return local.weekday() == weekday and not _covers(issue_path, window_last)


def _covers(issue_path, window_last):
    """Whether the stored issue already reviews the window ending ``window_last``.

    A mid-week ``--force`` build is named for the same ISO week as that
    Saturday's issue but ends days earlier, so it must not stand in for it. A
    file whose end date cannot be read is left alone rather than overwritten.
    """
    if not issue_path.exists():
        return False
    stored = jsonio.read_json(issue_path, default=None)
    ends = stored.get("to") if isinstance(stored, dict) else None
    return window_last is None or not isinstance(ends, str) or ends >= window_last.isoformat()


# ------------------------------------------------------------------ cache and fetching


class ProviderError(Exception):
    """A provider answered, but with something we cannot use (bad XML, unexpected JSON)."""


class DayCache:
    """Parsed responses fetched today, keyed by URL, so a same-day re-run does not refetch.

    One directory per local run date. Older directories are removed when the cache
    opens: yesterday's vote counts are stale by definition, and arXiv listings are
    cheap to refetch once a week.
    """

    def __init__(self, root, day):
        self.dir = root / day
        self._prune(root, day)

    @staticmethod
    def _prune(root, keep):
        """Delete every day directory except ``keep``; a failure only costs disk space."""
        if not root.is_dir():
            return
        for child in root.iterdir():
            if child.name == keep:
                continue
            try:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            except OSError as err:
                log.warn("could not prune %s (%s)", child, err)

    def _path(self, url):
        """A short stable file name per URL; the stored URL guards against collisions."""
        return self.dir / (textutil.stable_id("c", url) + ".json")

    def get(self, url):
        """(True, data) when today's cache holds ``url``, else (False, None)."""
        entry = jsonio.read_json(self._path(url))
        if isinstance(entry, dict) and entry.get("url") == url and "data" in entry:
            return True, entry["data"]
        return False, None

    def put(self, url, data):
        """Store parsed data; a cache that cannot be written only costs a refetch."""
        try:
            jsonio.write_json(self._path(url), {"url": url, "data": data})
        except (OSError, TypeError, ValueError) as err:
            log.warn("could not cache %s (%s)", url, err)


def cached_get(cache, url, parse, interval, timeout=30, retries=1, keep=None):
    """Fetch ``url`` once per day and return ``parse(body)``.

    ``keep(data)`` may veto caching (an empty arXiv answer is often a transient
    glitch and must not stick for the rest of the day). Raises ``net.NetError`` or
    ``ProviderError``; callers decide what a failure costs.
    """
    found, data = cache.get(url)
    if found:
        log.debug("cache hit %s", url)
        return data
    net.polite(url, interval)
    response = net.fetch(url, timeout=timeout, retries=retries)
    try:
        data = parse(response.body)
    except (ValueError, KeyError, TypeError, AttributeError, ET.ParseError) as err:
        raise ProviderError("unusable response from %s (%s)" % (urllib.parse.urlsplit(url).hostname, err)) from err
    if keep is None or keep(data):
        cache.put(url, data)
    return data


# ------------------------------------------------------------------ LaTeX to readable text

_ACCENTS = {'"': "\u0308", "'": "\u0301", "`": "\u0300", "^": "\u0302", "~": "\u0303",
            "=": "\u0304", ".": "\u0307", "c": "\u0327", "v": "\u030c", "u": "\u0306", "H": "\u030b"}
_ACCENT = re.compile(r"\\([\"'`^~=.]|[cvuH](?=[{ ]))\s*(?:\{\s*([A-Za-z])\s*\}|([A-Za-z]))")
_BRACED_ACCENT = re.compile(r"\{(\\[\"'`^~=.][A-Za-z])\}")
_SYMBOLS = {
    "times": "\u00d7", "sim": "~", "approx": "\u2248", "simeq": "\u2243", "le": "\u2264", "leq": "\u2264",
    "ge": "\u2265", "geq": "\u2265", "neq": "\u2260", "ne": "\u2260", "ll": "\u226a", "gg": "\u226b",
    "pm": "\u00b1", "mp": "\u2213", "cdot": "\u00b7", "cdots": "\u2026", "ldots": "\u2026", "dots": "\u2026",
    "to": "\u2192", "rightarrow": "\u2192", "leftarrow": "\u2190", "Rightarrow": "\u21d2",
    "leftrightarrow": "\u2194", "mapsto": "\u21a6", "infty": "\u221e", "propto": "\u221d", "in": "\u2208",
    "notin": "\u2209", "subset": "\u2282", "subseteq": "\u2286", "cup": "\u222a", "cap": "\u2229",
    "partial": "\u2202", "nabla": "\u2207", "sum": "\u03a3", "prod": "\u03a0", "int": "\u222b",
    "forall": "\u2200", "exists": "\u2203", "ell": "\u2113", "hbar": "\u0127", "circ": "\u00b0",
    "degree": "\u00b0", "textdegree": "\u00b0", "dagger": "\u2020", "star": "*", "ast": "*", "mid": "|",
    "vert": "|", "lvert": "|", "rvert": "|", "langle": "\u27e8", "rangle": "\u27e9", "prime": "\u2032",
    "checkmark": "\u2713", "S": "\u00a7", "textasciitilde": "~", "textbar": "|", "textendash": "\u2013",
    "textemdash": "\u2014", "textless": "<", "textgreater": ">", "AA": "\u00c5", "aa": "\u00e5",
    "o": "\u00f8", "O": "\u00d8", "ss": "\u00df", "ae": "\u00e6",
    "wedge": "\u2227", "land": "\u2227", "vee": "\u2228", "lor": "\u2228", "neg": "\u00ac", "lnot": "\u00ac",
    "oplus": "\u2295", "otimes": "\u2297", "odot": "\u2299", "div": "\u00f7", "equiv": "\u2261",
    "cong": "\u2245", "perp": "\u22a5", "parallel": "\u2225", "bullet": "\u2022", "setminus": "\u2216",
    "emptyset": "\u2205", "varnothing": "\u2205", "uparrow": "\u2191", "downarrow": "\u2193",
    "iff": "\u21d4", "implies": "\u21d2", "lceil": "\u2308", "rceil": "\u2309", "lfloor": "\u230a",
    "rfloor": "\u230b", "top": "\u22a4", "bot": "\u22a5", "textmu": "\u00b5", "micro": "\u00b5",
}
# In Unicode order from U+03B1 / U+0391; "-" holds the slot of final sigma, which has no capital.
_GREEK = ("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho - sigma "
          "tau upsilon phi chi psi omega").split()
for _index, _name in enumerate(_GREEK):
    if _name != "-":
        _SYMBOLS[_name] = chr(0x03b1 + _index)
        _SYMBOLS[_name.capitalize()] = chr(0x0391 + _index)
_SYMBOLS.update({"varepsilon": "\u03b5", "vartheta": "\u03d1", "varphi": "\u03c6", "varrho": "\u03f1",
                 "varsigma": "\u03c2", "Alpha": "A", "Beta": "B", "Epsilon": "E", "Zeta": "Z", "Eta": "H",
                 "Iota": "I", "Kappa": "K", "Mu": "M", "Nu": "N", "Rho": "P", "Tau": "T", "Chi": "X"})
_FUNCTIONS = frozenset("log ln exp max min sin cos tan arg sup inf lim det dim mod Pr gcd deg".split())
# Commands whose last braced argument is the visible text.
_KEEP_ARG = frozenset((
    "textbf textit textsl textsc texttt textrm textsf textup textnormal text emph mathrm mathbf mathit "
    "mathsf mathtt mathcal mathbb mathfrak mathscr boldsymbol bm operatorname mbox hbox fbox underline "
    "overline hat bar tilde vec widehat widetilde dot ddot check breve acute grave textsuperscript "
    "textsubscript url textcolor color uline"
).split())
_DROP_WITH_ARG = frozenset("cite citep citet ref eqref label footnote vspace hspace".split())
_SPACING = {",": " ", ";": " ", ":": " ", ">": " ", "!": "", " ": " ", "quad": " ", "qquad": " ",
            "enspace": " ", "thinspace": " ", "newline": " ", "left": "", "right": "", "big": "",
            "Big": "", "bigg": "", "Bigg": "", "displaystyle": "", "textstyle": "", "limits": "",
            "nolimits": "", "noindent": "", "centering": "", "small": "", "footnotesize": "", "tiny": "",
            "large": "", "Large": "", "normalsize": "", "bf": "", "it": "", "rm": "", "sc": "", "em": "",
            "tt": "", "sf": "", "protect": "", "relax": ""}
_SUPERSCRIPT_CHARS, _SUBSCRIPT_CHARS = "0123456789+-=()n", "0123456789+-=()"
_SUPERSCRIPT = str.maketrans(_SUPERSCRIPT_CHARS, "\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079\u207a\u207b\u207c\u207d\u207e\u207f")
_SUBSCRIPT = str.maketrans(_SUBSCRIPT_CHARS, "\u2080\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089\u208a\u208b\u208c\u208d\u208e")
_MATH = re.compile(r"\$\$(.+?)\$\$|\$(?!\s)([^$]+?)(?<!\s)\$|\\\((.+?)\\\)|\\\[(.+?)\\\]", re.S)
_COMMAND = re.compile(r"\\([A-Za-z]+)\*?\s*|\\([,;:!> ])")
_SCRIPT = re.compile(r"([\^_])\s*(\{([^{}]*)\}|\\[A-Za-z]+|[^\s{}\\])")
_PROTECT = {"\\$": "\x01", "\\%": "%", "\\&": "&", "\\#": "#", "\\_": "\x02", "\\{": "\x03", "\\}": "\x04"}
_RESTORE = {"\x01": "$", "\x02": "_", "\x03": "{", "\x04": "}"}


def _brace_group(text, start):
    """(content, end) of the braced group opening at ``text[start]``, honouring nesting."""
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
    return text[start + 1:], len(text)


def _skip_space(text, index):
    """Index of the first non-space at or after ``index`` (TeX allows "\\frac {a} {b}")."""
    while index < len(text) and text[index] == " ":
        index += 1
    return index


def _commands(text):
    """Replace every backslash command with readable text, recursing into arguments."""
    out, index = [], 0
    while index < len(text):
        match = _COMMAND.search(text, index)
        if not match:
            out.append(text[index:])
            break
        out.append(text[index:match.start()])
        index = match.end()
        if match.group(2):
            out.append(_SPACING.get(match.group(2), " "))
            continue
        name = match.group(1)
        args = []
        if name in _KEEP_ARG or name in _DROP_WITH_ARG or name in ("frac", "dfrac", "tfrac", "sqrt", "href", "unicode"):
            want = 2 if name in ("frac", "dfrac", "tfrac", "href", "textcolor") else 1
            if name == "sqrt" and text[index:index + 1] == "[":
                index = text.find("]", index) + 1 or len(text)
            while len(args) < want:
                position = _skip_space(text, index)
                if text[position:position + 1] != "{":
                    break
                content, index = _brace_group(text, position)
                args.append(content)
        if name in _DROP_WITH_ARG:
            continue
        if name in ("frac", "dfrac", "tfrac") and len(args) == 2:
            out.append("%s/%s" % (_wrap(_commands(args[0])), _wrap(_commands(args[1]))))
        elif name == "sqrt":
            out.append("\u221a" + _wrap(_commands(args[0])) if args else "\u221a")
        elif name == "href" and args:
            out.append(_commands(args[-1]))
        elif name == "unicode" and args:
            out.append(_codepoint(args[0]))
        elif name in ("textcolor", "color"):
            out.append(_commands(args[-1]) if len(args) == 2 else "")
        elif name in _KEEP_ARG:
            out.append(_commands(args[0]) if args else "")
        elif name in _SYMBOLS:
            out.append(_SYMBOLS[name])
        elif name in _FUNCTIONS:
            out.append(name)
        elif name in _SPACING:
            out.append(_SPACING[name])
        # Any other command is formatting we cannot render; its braced text survives below.
    return "".join(out)


def _codepoint(spec):
    """MathJax's \\unicode{x2014} / \\unicode{8212}: the character, or nothing if the number is bad."""
    spec = spec.strip().lower()
    try:
        number = int(spec[1:], 16) if spec.startswith("x") else int(spec)
        return chr(number) if 0 < number < 0x110000 else ""
    except ValueError:
        return ""


def _wrap(text):
    """Parenthesise a fraction or root operand that is more than one simple token."""
    text = text.strip()
    return text if re.fullmatch(r"[\w.\u0370-\u03ff]+", text) else "(%s)" % text


def _scripts(math):
    """Turn ^{..} and _{..} into Unicode super/subscripts when every character has one."""
    def replace(match):
        marker, body = match.group(1), match.group(3) if match.group(3) is not None else match.group(2)
        body = _commands(body).strip()
        chars, table = (_SUPERSCRIPT_CHARS, _SUPERSCRIPT) if marker == "^" else (_SUBSCRIPT_CHARS, _SUBSCRIPT)
        if body and all(char in chars for char in body):
            return body.translate(table)
        if marker == "^" and body in ("\u00b0", "\u2032", "*", "\u2020"):
            return body
        return marker + (body if len(body) == 1 else "(%s)" % body)
    return _SCRIPT.sub(replace, math)


def _math(segment):
    """Readable text for the inside of one $...$ span."""
    return _commands(_scripts(segment))


def _accents(text):
    """\\"o and {\\"o} become ö; done before anything else touches the backslashes."""
    text = _BRACED_ACCENT.sub(r"\1", text)

    def replace(match):
        letter = match.group(2) or match.group(3)
        return unicodedata.normalize("NFC", letter + _ACCENTS[match.group(1)])
    return _ACCENT.sub(replace, text)


def clean_latex(text):
    """Turn arXiv's LaTeX-flavoured title or abstract into plain readable text.

    ``$\\times$`` becomes ×, ``$O(n^2)$`` becomes O(n²), ``MoS$_2$`` becomes MoS₂,
    ``\\textbf{X}`` becomes X, TeX quotes become typographic ones. A lone ``$``
    (a price) is left alone. Whitespace is collapsed.
    """
    if not text:
        return ""
    text = " ".join(str(text).split())
    for raw, placeholder in _PROTECT.items():
        text = text.replace(raw, placeholder)
    text = _accents(text)
    text = re.sub(r"(?<=[^\s\\/])~(?=\S)", " ", text)  # TeX tie "Fig.~3"; not a URL's "/~user"
    text = text.replace("``", "\u201c").replace("''", "\u201d")
    text = text.replace("---", "\u2014").replace("--", "\u2013")

    def math(match):
        inner = next(group for group in match.groups() if group is not None)
        return _math(inner)
    text = _MATH.sub(math, text)
    text = _commands(text)
    text = text.replace("{", "").replace("}", "")
    for placeholder, char in _RESTORE.items():
        text = text.replace(placeholder, char)
    text = text.replace("\\", "")
    text = " ".join(text.split())
    text = re.sub(r"\s+([,.;:!?%)\]])", r"\1", text)
    return re.sub(r"([(\[])\s+", r"\1", text)


# ------------------------------------------------------------------ sentences

_END = re.compile(r"(?:[.!?]+|\u2026)[\"'\u201d\u2019)\]]*(?=\s)")
_ABBREVIATIONS = frozenset((
    "al approx apr assoc aug ca cf ch chap co col conf corp dec dept dr ed eds eg eq eqn eqs esp est "
    "ex feb fig figs ie inc incl jan jr jul jun lem ltd mr mrs ms mt no nos nov oct op pp proc prof "
    "prop ref refs resp sec secs sect sep sept sr st tab tabs thm trans univ viz vol vols vs wrt alg "
    "app appx cor def nr"
).split())
_DOTTED = re.compile(r"(?:[A-Za-z]{1,2}\.)+[A-Za-z]{1,2}")
_CAMEL_START = re.compile(r"[a-z]+[A-Z]")


_LIST_MARKER = re.compile(r"\((?:[ivx]{1,4}|\d{1,2}|[a-h])\)$")


def _starts_sentence(token):
    """Whether the next token can open a sentence: capital, digit, quote+capital, a name like mHC,
    or a list marker like "(ii)" (abstracts enumerate contributions as separate sentences)."""
    if _LIST_MARKER.match(token):
        return True
    if token[:1] in "([{":
        return False
    token = token.lstrip("\"'\u201c\u2018")
    return bool(token) and (token[0].isupper() or token[0].isdigit() or bool(_CAMEL_START.match(token)))


def _is_boundary(text, start, match):
    """Decide whether the punctuation in ``match`` ends a sentence (abbreviations, initials, lists)."""
    following = text[match.end():].split(None, 1)
    if not following or not _starts_sentence(following[0]):
        return False
    if match.group()[0] in "!?\u2026":
        return True
    before = text[start:match.start()].split()
    if not before:
        return False
    raw_word = before[-1]
    word = raw_word.lstrip("([{\"'\u201c\u2018")
    if not word:
        return False
    previous = before[-2] if len(before) > 1 else ""
    if word.lower() in _ABBREVIATIONS or _DOTTED.fullmatch(word):
        return False
    # "J. Smith" is an initial; "draws 3 W. The" is a unit after a number.
    if len(word) == 1 and word.isalpha() and not _NUMBER.fullmatch(previous):
        return False
    # "Our contributions: 1. We ..." is an enumeration marker, not the end of a sentence.
    if re.fullmatch(r"\d{1,2}", raw_word) and (not previous or previous[-1] in ":;."):
        return False
    return True


def split_sentences(text):
    """Split prose into sentences, treating abbreviations, initials, decimals and lists correctly.

    A missed split only makes a sentence longer; a wrong split makes a fragment the
    digest might then show, so every rule errs toward not splitting.
    """
    text = " ".join((text or "").split())
    sentences, start = [], 0
    for match in _END.finditer(text):
        if _is_boundary(text, start, match):
            sentence = text[start:match.end()].strip()
            if sentence:
                sentences.append(sentence)
            start = match.end()
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


# ------------------------------------------------------------------ extractive digest

_METHOD_CUE = re.compile(
    r"\b(?:we (?:propose|present|introduce|develop|design|describe|report|build|construct|devise|"
    r"formulate|demonstrate|implement|release|create|contribute|show how|offer|put forward|unveil)\w*"
    r"|(?:this|the present|our) (?:paper|work|article|study|letter|thesis|survey|report) "
    r"(?:propose|present|introduce|develop|describe|report|investigat|stud|explor|address|tackle|"
    r"examin|provid|offer|demonstrat)\w*|in this (?:paper|work|article|letter|study)"
    r"|our (?:approach|method|framework|system|design|technique|model|solution)|here,? we|we call)\b", re.I)
_PROBLEM_CUE = re.compile(
    r"\b(?:however|but|challeng\w*|remain\w*|limit\w*|suffer\w*|bottleneck\w*|costly|expensive|"
    r"lack\w*|difficult\w*|problem\w*|struggl\w*|fail\w*|despite|inefficien\w*|unclear|"
    r"open question|hinder\w*|prohibitive\w*|scarce|obstacle\w*|unexplored|overlook\w*|"
    r"underexplored|insufficient|degrad\w*|vulnerab\w*|constrain\w*|demand\w*|crucial|critical|yet|"
    r"not been|unknown|little is known|understudied|unaddressed)\b", re.I)
_RESULT_CUE = re.compile(
    r"(?:\b(?:achiev|outperform|improv|reduc|speed|accelerat|lower|higher|increas|gain|surpass|"
    r"exceed|sav|boost|cut|yield|attain|deliver|consum|beat|match|enabl|decreas|shrink|"
    r"state-of-the-art|sota|faster|better|fewer|less|pass|scor|reach|success|accura|throughput|"
    r"latency|win|solv)\w*|%|\u00d7|\b\d+(?:\.\d+)?x\b)", re.I)
_STRONG_RESULT = re.compile(r"\b(?:outperform|surpass|state-of-the-art|achiev|exceed)\w*|"
                            r"\b(?:experiments|results|evaluations?) (?:show|demonstrate|indicate)", re.I)
_FIRST_PERSON = re.compile(r"\b(?:we|our)\b", re.I)
_HEDGE = re.compile(r"^(?:we|i) (?:believe|hope|envision|anticipate|expect|argue|speculate|think)\b", re.I)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_ANAPHORA = re.compile(
    r"^(?:this|these|it|its|they|their|such|however|moreover|furthermore|additionally|finally|"
    r"in addition|also|thus|hence|therefore|meanwhile|then|both|those)\b(?! (?:paper|work|article|"
    r"study|letter|survey)\b)", re.I)
GIST_MAX = 240


def title_names(title):
    """{name: weight} for what a title calls its work.

    The one-word prefix of "Name: subtitle" is the work itself (1.0); other tokens
    that look like names (FP8, MI355X, NVLink) often describe the setting, so they
    count for less (0.5).
    """
    names = {}
    for token in re.findall(r"[A-Za-z0-9][\w-]*", title):
        capitals = sum(1 for char in token if char.isupper())
        if len(token) >= 3 and (capitals >= 2 or (capitals and any(char.isdigit() for char in token))):
            names[token] = 0.5
    head = title.split(":", 1)[0].strip() if ":" in title else ""
    if re.fullmatch(r"[A-Za-z][\w-]{2,}", head):
        names[head] = 1.0
    return names


def _name_weight(sentence, names):
    """The weight of the strongest title name the sentence mentions (0 when none)."""
    found = [weight for name, weight in names.items()
             if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(name), sentence)]
    return max(found or [0.0])


def _pick_method(sentences, names):
    """The first sentence saying what the authors did; failing that, one that opens with the work's name."""
    for index, sentence in enumerate(sentences):
        if _METHOD_CUE.search(sentence) and not _HEDGE.match(sentence):
            return index
    for index, sentence in enumerate(sentences):
        first = sentence.split(None, 1)[0].rstrip(",:;'s\u2019") if sentence.split() else ""
        if first in names:
            return index
    return None


def _pick_problem(sentences, method_index):
    """The first sentence with a problem cue before the method; else the opening sentence."""
    stop = method_index if method_index is not None else min(3, len(sentences))
    for index in range(stop):
        if _PROBLEM_CUE.search(sentences[index]):
            return index
    if stop > 0:
        return 0
    for index, sentence in enumerate(sentences):
        if index != method_index and _PROBLEM_CUE.search(sentence) and not _RESULT_CUE.search(sentence):
            return index
    return None


def _pick_result(sentences, used, method_index, names):
    """The headline finding: a sentence with numbers and result cues.

    Background sentences are number-heavy too ("the vendor's kernels reach 39% of
    peak"), so a sentence earns more for following the method, for naming the work
    or speaking as the authors, and for a strong cue ("outperforms", "results show").
    The earlier sentence wins a tie: abstracts state the headline result first.
    """
    best, best_score = None, None
    for index, sentence in enumerate(sentences):
        if index in used or not _NUMBER.search(sentence):
            continue
        cues = len(_RESULT_CUE.findall(sentence))
        if not cues:
            continue
        score = min(cues, 3) + 0.5 * min(len(_NUMBER.findall(sentence)), 3)
        if method_index is not None and index > method_index:
            score += 2
        named = _name_weight(sentence, names)
        if named:
            score += 2 * named
        elif _FIRST_PERSON.search(sentence):
            score += 1
        if _STRONG_RESULT.search(sentence):
            score += 1
        if best_score is None or score > best_score:
            best, best_score = index, score
    if best is not None:
        return best
    for index in range(len(sentences) - 1, -1, -1):
        if index not in used and _STRONG_RESULT.search(sentences[index]):
            return index
    return None


def _pick_gist(sentences, names):
    """The single most informative sentence that fits in GIST_MAX characters.

    Credits saying what the paper does and what it found, naming the thing the
    title names, and standing alone (no "This"/"However" opener that needs context,
    no "We believe" hedge).
    """
    best, best_score = None, None
    for index, sentence in enumerate(sentences):
        if len(sentence) > GIST_MAX or len(sentence) < 40 or _HEDGE.match(sentence):
            continue
        score = 0.0
        if _METHOD_CUE.search(sentence):
            score += 3
        if _NUMBER.search(sentence) and _RESULT_CUE.search(sentence):
            score += 2
        score += 0.5 * min(len(_NUMBER.findall(sentence)), 2)
        score += 2 * _name_weight(sentence, names)
        if _ANAPHORA.match(sentence):
            score -= 2
        if len(sentence) < 70:
            score -= 1
        if best_score is None or score > best_score:
            best, best_score = index, score
    return best


def digest(abstract, title=""):
    """{"gist","problem","method","result"}, each a verbatim sentence of ``abstract`` or ""."""
    sentences = split_sentences(abstract)
    names = title_names(title)
    method = _pick_method(sentences, names)
    problem = _pick_problem(sentences, method)
    if method is None and problem is not None and problem + 1 < len(sentences):
        follow = sentences[problem + 1]
        if re.search(r"\b(?:we|our)\b", follow, re.I) and not _RESULT_CUE.search(follow):
            method = problem + 1
    used = {index for index in (problem, method) if index is not None}
    result = _pick_result(sentences, used, method, names)
    gist = _pick_gist(sentences, names)

    def at(index):
        return sentences[index] if index is not None else ""
    return {"gist": at(gist), "problem": at(problem), "method": at(method), "result": at(result)}


# ------------------------------------------------------------------ arXiv

_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"
_OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"
_ENTRY_ID = re.compile(r"(\d{4}\.\d{4,5})(?:v(\d+))?$")
BARE_ID = re.compile(r"^\d{4}\.\d{4,5}$")
_ID_IN_URL = re.compile(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})", re.I)
_ID_IN_TEXT = re.compile(r"(?:arxiv\.org/(?:abs|pdf|html)/|\barXiv:\s?)(\d{4}\.\d{4,5})", re.I)
_MAX_AUTHORS = 30


def _text(element, tag):
    """Child text with arXiv's hard line wrapping collapsed."""
    return " ".join((element.findtext(tag) or "").split())


def parse_arxiv(body):
    """Parse an arXiv API Atom response into {"total", "entries": [paper record]}.

    Ids lose their version suffix; title and abstract go through ``clean_latex``.
    Entries without a new-style id or a parseable date are skipped.
    """
    root = ET.fromstring(body)
    if root.tag != _ATOM + "feed":
        raise ProviderError("not an Atom feed")
    total_text = root.findtext(_OPENSEARCH + "totalResults") or "0"
    entries = []
    for entry in root.findall(_ATOM + "entry"):
        match = _ENTRY_ID.search(_text(entry, _ATOM + "id"))
        published = timeutil.parse_date(_text(entry, _ATOM + "published"))
        if not match or published is None:
            continue  # old-style ids (math/0601001) cannot be in a recent window
        primary = entry.find(_ARXIV_NS + "primary_category")
        categories = [element.get("term") for element in entry.findall(_ATOM + "category") if element.get("term")]
        entries.append({
            "id": match.group(1),
            "version": int(match.group(2) or 1),
            "title": clean_latex(_text(entry, _ATOM + "title")),
            "abstract": clean_latex(_text(entry, _ATOM + "summary")),
            "authors": [_text(author, _ATOM + "name") for author in entry.findall(_ATOM + "author")][:_MAX_AUTHORS],
            "published": timeutil.iso(published),
            "primary": primary.get("term") if primary is not None else (categories[0] if categories else ""),
            "categories": categories,
            "comment": _text(entry, _ARXIV_NS + "comment"),
            "journalRef": _text(entry, _ARXIV_NS + "journal_ref"),
        })
    return {"total": int(total_text.strip() or 0), "entries": entries}


def arxiv_category_url(api, category, start, end, max_results):
    """Query URL for one category's submissions in [start, end) UTC, newest first."""
    span = "%s TO %s" % (start.strftime("%Y%m%d%H%M"), (end - timedelta(minutes=1)).strftime("%Y%m%d%H%M"))
    query = "cat:%s AND submittedDate:[%s]" % (category, span)
    return api + "?" + urllib.parse.urlencode({
        "search_query": query, "sortBy": "submittedDate", "sortOrder": "descending",
        "start": 0, "max_results": max_results})


def arxiv_ids_url(api, ids):
    """Query URL resolving up to 100 ids at once (arXiv returns them in no particular order)."""
    return api + "?" + urllib.parse.urlencode({"id_list": ",".join(ids), "max_results": len(ids)})


def _arxiv_get(cache, url, provider):
    """One arXiv request; an empty answer is retried once and never cached."""
    def keep(data):
        return bool(data["entries"])
    data = cached_get(cache, url, parse_arxiv, provider["intervalSec"], timeout=provider["timeoutSec"],
                      retries=2, keep=keep)
    if not data["entries"]:
        log.debug("arXiv returned nothing for %s; retrying once", url)
        data = cached_get(cache, url, parse_arxiv, provider["intervalSec"], timeout=provider["timeoutSec"],
                          retries=1, keep=keep)
    return data


def gather_candidates(cache, cfg, start, end, report):
    """All papers submitted in the window to the configured categories, keyed by id.

    Each category is fetched on its own; a failed one is reported and skipped.
    """
    provider = cfg["providers"]["arxiv"]
    papers, failures = {}, []
    categories = []
    for track in ("cs", "electronics"):
        categories.extend(category for category in cfg["tracks"][track]["categories"] if category not in categories)
    for category in categories:
        url = arxiv_category_url(provider["api"], category, start, end, cfg["candidatesPerCategory"])
        try:
            data = _arxiv_get(cache, url, provider)
        except (net.NetError, ProviderError) as err:
            log.warn("arXiv %s: %s", category, err)
            failures.append(category)
            continue
        if data["total"] > len(data["entries"]):
            log.info("arXiv %s: %d of %d submissions kept (candidatesPerCategory)",
                     category, len(data["entries"]), data["total"])
        for entry in data["entries"]:
            papers.setdefault(entry["id"], entry)
    report["arxiv"] = {"ok": len(failures) < len(categories), "count": len(papers),
                       "error": ("failed: " + ", ".join(failures)) if failures else None}
    return papers


def resolve_ids(cache, cfg, ids, report):
    """Fetch arXiv records for ids the signal providers named but the category queries missed."""
    provider = cfg["providers"]["arxiv"]
    found, failed = {}, 0
    ids = sorted(ids)
    for offset in range(0, len(ids), 100):
        chunk = ids[offset:offset + 100]
        try:
            data = _arxiv_get(cache, arxiv_ids_url(provider["api"], chunk), provider)
        except (net.NetError, ProviderError) as err:
            log.warn("arXiv id lookup (%d ids): %s", len(chunk), err)
            failed += len(chunk)
            continue
        for entry in data["entries"]:
            found[entry["id"]] = entry
    if failed:
        report["arxiv"]["error"] = ((report["arxiv"].get("error") or "") + " %d id lookups failed" % failed).strip()
    return found


# ------------------------------------------------------------------ signal providers


def _int(value):
    """Counts from JSON APIs arrive as int, float, numeric string or null."""
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def parse_hf(body):
    """Hugging Face daily_papers -> {"rows": n, "papers": {id: signals}} (rows tells the pager to stop)."""
    rows = json.loads(body)
    if not isinstance(rows, list):
        raise ProviderError("expected a JSON array")
    papers = {}
    for row in rows:
        paper = row.get("paper") if isinstance(row, dict) else None
        if not isinstance(paper, dict) or not BARE_ID.match(str(paper.get("id") or "")):
            continue
        papers[paper["id"]] = {"hfUpvotes": _int(paper.get("upvotes")),
                               "githubStars": _int(paper.get("githubStars")),
                               "codeUrl": paper.get("githubRepo") or None}
    return {"rows": len(rows), "papers": papers}


def parse_alphaxiv(body):
    """alphaXiv feed -> {id: signals}. Slug ids ("2611.flashstate") are not arXiv papers and are skipped."""
    data = json.loads(body)
    rows = data.get("papers") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ProviderError("expected {papers: [...]}")
    papers = {}
    for row in rows:
        pid = str(row.get("universal_paper_id") or "") if isinstance(row, dict) else ""
        if not BARE_ID.match(pid):
            continue
        metrics = row.get("metrics") or {}
        visits = metrics.get("visits_count") or {}
        papers[pid] = {"alphaxivVotes": _int(metrics.get("public_total_votes")),
                       "alphaxivViews": _int(visits.get("last_7_days")),
                       "githubStars": _int(row.get("github_stars")),
                       "codeUrl": row.get("github_url") or None}
    return papers


def parse_hn(body):
    """HN Algolia search -> {id: {"hnPoints","hnComments","hnUrl"}}, summed over every story linking the paper.

    The link kept is the discussion with the most points.
    """
    data = json.loads(body)
    hits = data.get("hits") if isinstance(data, dict) else None
    if not isinstance(hits, list):
        raise ProviderError("expected {hits: [...]}")
    papers, best = {}, {}
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        match = _ID_IN_URL.search(str(hit.get("url") or ""))
        if not match:
            continue
        pid, points = match.group(1), _int(hit.get("points"))
        entry = papers.setdefault(pid, {"hnPoints": 0, "hnComments": 0, "hnUrl": None})
        entry["hnPoints"] += points
        entry["hnComments"] += _int(hit.get("num_comments"))
        if hit.get("objectID") and points >= best.get(pid, -1):
            best[pid] = points
            entry["hnUrl"] = "https://news.ycombinator.com/item?id=%s" % hit["objectID"]
    return papers


def parse_openalex(body):
    """OpenAlex works filtered by arXiv DOI -> {id: citation count}."""
    data = json.loads(body)
    rows = data.get("results") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ProviderError("expected {results: [...]}")
    counts = {}
    for row in rows:
        match = re.search(r"10\.48550/arxiv\.(\d{4}\.\d{4,5})", str((row or {}).get("doi") or ""), re.I)
        if match:
            counts[match.group(1)] = max(counts.get(match.group(1), 0), _int(row.get("cited_by_count")))
    return counts


def _merge_signals(entry, signals):
    """Fold one provider's signals for a paper into ``entry``: counts keep their maximum, links the first seen."""
    for key, value in signals.items():
        if isinstance(value, int):
            entry[key] = max(entry.get(key, 0), value)
        elif value and not entry.get(key):
            entry[key] = value


def _merge(target, source):
    """Fold one provider page ({id: signals}) into the running map."""
    for pid, signals in source.items():
        _merge_signals(target.setdefault(pid, {}), signals)


def collect_hf(cache, cfg, first, last, today):
    """Upvotes for every paper Hugging Face curated on a day of the window (weekend days are empty)."""
    provider = cfg["providers"]["hf"]
    found, errors, day = {}, [], first
    while day <= last and day < today:
        for page in range(provider["maxPages"]):
            url = provider["url"] + "?" + urllib.parse.urlencode(
                {"date": day.isoformat(), "limit": provider["pageSize"], "p": page})
            try:
                data = cached_get(cache, url, parse_hf, provider["intervalSec"], retries=2)
            except (net.NetError, ProviderError) as err:
                errors.append("%s: %s" % (day.isoformat(), err))
                break
            _merge(found, data["papers"])
            if data["rows"] < provider["pageSize"]:
                break
        day += timedelta(days=1)
    return found, errors


def collect_alphaxiv(cache, cfg):
    """Seven-day views and votes: the global list plus one list per hardware topic."""
    provider = cfg["providers"]["alphaxiv"]
    requests = [{"pageNum": 0, "pageSize": provider["globalPageSize"], "sort": "Views",
                 "interval": provider["interval"]}]
    requests += [{"pageNum": 0, "pageSize": provider["topicPageSize"], "sort": "Views",
                  "interval": provider["interval"], "topics": json.dumps([topic])} for topic in provider["topics"]]
    found, errors = {}, []
    for params in requests:
        url = provider["url"] + "?" + urllib.parse.urlencode(params)
        try:
            _merge(found, cached_get(cache, url, parse_alphaxiv, provider["intervalSec"], retries=2))
        except (net.NetError, ProviderError) as err:
            errors.append("%s: %s" % (params.get("topics", "global"), err))
    return found, errors


def collect_hn(cache, cfg, start, until):
    """Points on Hacker News stories linking an arXiv paper, posted from the window start until ``until``.

    ``until`` is the end of the run's local day rather than the current instant, so
    the URL (the cache key) stays the same for every run that day.
    """
    provider = cfg["providers"]["hn"]
    url = provider["url"] + "?" + urllib.parse.urlencode({
        "query": "arxiv.org", "restrictSearchableAttributes": "url", "tags": "story",
        "numericFilters": "created_at_i>%d,created_at_i<%d" % (start.timestamp(), until.timestamp()),
        "hitsPerPage": provider["hitsPerPage"]})
    try:
        return cached_get(cache, url, parse_hn, 0, retries=2), []
    except (net.NetError, ProviderError) as err:
        return {}, [str(err)]


def collect_citations(cache, cfg, ids):
    """OpenAlex citation counts for a shortlist (they are near zero for week-old papers, but real)."""
    provider = cfg["providers"]["openalex"]
    found, errors = {}, []
    for offset in range(0, len(ids), provider["batch"]):
        chunk = ids[offset:offset + provider["batch"]]
        url = provider["url"] + "?" + urllib.parse.urlencode({
            "filter": "doi:" + "|".join("10.48550/arxiv.%s" % pid for pid in chunk),
            "select": "doi,cited_by_count", "per_page": provider["batch"]})
        try:
            found.update(cached_get(cache, url, parse_openalex, provider["intervalSec"], retries=2))
        except (net.NetError, ProviderError) as err:
            errors.append(str(err))
    return found, errors


def _provider(report, name, result, missing):
    """Record a provider's outcome; it counts as present if it produced any answer at all."""
    data, errors = result
    ok = not errors or bool(data)
    report[name] = {"ok": ok, "count": len(data), "error": "; ".join(errors)[:300] if errors else None}
    for error in errors:
        log.warn("%s: %s", name, error)
    if not ok:
        missing.append(name)
    return data if ok else None


# ------------------------------------------------------------------ mentions in the news item store

_MENTION_STOP = textutil.STOPWORDS | frozenset("paper new via using based toward towards".split())


def _title_tokens(text):
    """Content-word stems of a title, the unit of the title-match rule."""
    return {textutil.stem(token) for token in textutil.tokenize(text) if token not in _MENTION_STOP}


def load_items(items_dir, first, last):
    """News items filed under the window's dates (missing days are simply absent)."""
    items, day = [], first
    while day <= last:
        stored = jsonio.read_json(items_dir / ("%s.json" % day.isoformat()), default=None)
        if isinstance(stored, dict) and isinstance(stored.get("items"), dict):
            items.extend(item for item in stored["items"].values() if isinstance(item, dict))
        day += timedelta(days=1)
    return items


def count_mentions(papers, items):
    """{paper id: number of distinct news sources that mention it}.

    A mention is an item whose title or summary cites the arXiv id, or whose title
    shares at least 80% of a paper title's content words (and at least four). Items
    that link to arxiv.org itself are link posts (HN, arXiv feeds) and are skipped:
    Hacker News is already its own signal.
    """
    by_token, item_tokens = {}, []
    sources = {pid: set() for pid in papers}
    for index, item in enumerate(items):
        url = str(item.get("url") or "")
        if "arxiv.org" in url:
            item_tokens.append(set())
            continue
        text = "%s %s" % (item.get("title") or "", item.get("summary") or "")
        for match in _ID_IN_TEXT.finditer(text):
            if match.group(1) in sources:
                sources[match.group(1)].add(item.get("source") or item.get("id"))
        tokens = _title_tokens(item.get("title") or "")
        item_tokens.append(tokens)
        for token in tokens:
            by_token.setdefault(token, []).append(index)
    for pid, paper in papers.items():
        wanted = _title_tokens(paper["title"])
        if len(wanted) < 4:
            continue
        hits = Counter(index for token in wanted for index in by_token.get(token, ()))
        for index, shared in hits.items():
            if shared >= 4 and shared >= 0.8 * len(wanted):
                sources[pid].add(items[index].get("source") or items[index].get("id"))
    return {pid: len(found) for pid, found in sources.items() if found}


# ------------------------------------------------------------------ content signals (no network)

_ACCEPT_CUES = (
    (re.compile(r"\baccepted\b|\bcamera[- ]ready\b", re.I), "accepted at"),
    (re.compile(r"\bto appear\b|\bforthcoming\b|\bin press\b", re.I), "to appear at"),
    (re.compile(r"\bpublished\b|\bproceedings of\b|\bin proceedings\b", re.I), "published in"),
    (re.compile(r"\bpresented\b", re.I), "presented at"),
)
_NEGATIVE_CUE = re.compile(r"\b(?:submitted|under review|in submission|under submission|rejected)\b", re.I)
_GENERIC_VENUE = re.compile(r"\b(?:conference|symposium|journal|transactions|workshop|proceedings|letters|"
                            r"peer[- ]review\w*)\b", re.I)
_YEAR_AFTER = re.compile(r"\s?(?:'|\u2019)?(\d{4}|\d{2})\b")
_CODE_URL = re.compile(
    r"(?:https?://)?(?:www\.)?(github\.com|gitlab\.com|bitbucket\.org|codeberg\.org|huggingface\.co|"
    r"zenodo\.org|doi\.org/10\.5281)/[^\s,;)\]>]+", re.I)
_PROMISE = re.compile(r"\b(?:will be|to be|upon|after) (?:publicly )?(?:released|available|made|open|acceptance|"
                      r"publication)|coming soon", re.I)
_MEASURE = re.compile(
    r"\d+(?:\.\d+)?\s?(?:%|\u00d7|x\b|times\b|[kMGTP]?(?:Hz|W|Wh|J|V|A|B/s|b/s|bps|FLOPS|OPS)\b|"
    r"[m\u00b5unpf](?:W|J|V|A|s|m|F|H)\b|(?:nm|mm|cm|\u00b5m)(?:2|\u00b2)?\b|dB[mi]?\b|[TGM]OPS(?:/W)?|"
    r"fps\b|\u00b0C|K\b|Gb/s|Mb/s|ppm\b)")


def _venue_pattern(venue):
    """Case-sensitive whole-name match, so "DATE" is a venue and "date" is not, and DAC does not match ASP-DAC."""
    return re.compile(r"(?<![A-Za-z0-9-])" + re.escape(venue) + r"(?![A-Za-z-])")


def _journal_label(journal_ref, venue_patterns, authors):
    """"published in <venue>" from a journal reference, without echoing an author list as a venue.

    The reference's first segment is used only when it names no author; otherwise the
    label stays generic.
    """
    for venue, pattern in venue_patterns:
        if pattern.search(journal_ref):
            return "published in %s" % venue
    head = re.split(r"[,(;]|\d", journal_ref, 1)[0].strip(" .")
    surnames = {name.split()[-1].lower() for name in authors if name.split()}
    if 6 <= len(head) <= 60 and not any(word.lower().strip(".") in surnames for word in head.split()):
        return "published in %s" % head
    return "published, with a journal reference"


def venue_signal(comment, journal_ref, venue_patterns, authors=(), current_year=None):
    """(value, label) from the arXiv comment and journal reference.

    1.0 for a named venue that the comment says accepted or published the paper (or
    names with its year, "ASP-DAC'27 Invited Paper"); 0.5 for a workshop or an unnamed
    peer-reviewed venue; 0 for "submitted to" or nothing. Cues only count inside the
    same clause as the venue, so "accepted at X; extended version submitted" works.
    A venue more than a year before ``current_year`` is an old paper being re-posted
    and earns nothing.
    """
    if journal_ref:
        years = [int(year) for year in re.findall(r"\b(?:19|20)\d{2}\b", journal_ref)]
        if years and current_year and max(years) < current_year - 1:
            return 0.0, None
        workshop = "workshop" in journal_ref.lower()
        return (0.5 if workshop else 1.0), _journal_label(journal_ref, venue_patterns, authors)
    best = (0.0, None)
    for clause in re.split(r";|\.\s+|\|", comment or ""):
        cue = None
        for pattern, verb in _ACCEPT_CUES:
            found = pattern.search(clause)
            if found and (cue is None or found.start() < cue[0]):
                cue = (found.start(), verb)
        negative = _NEGATIVE_CUE.search(clause)
        workshop = "workshop" in clause.lower()
        for venue, pattern in venue_patterns:
            found = pattern.search(clause)
            if not found:
                continue
            year = _YEAR_AFTER.match(clause, found.end())
            year_text = ""
            if year:
                year_text = year.group(1) if len(year.group(1)) == 4 else "20" + year.group(1)
            cued = cue is not None and cue[0] < found.start()
            if not cued and (negative or not year_text):
                continue
            if year_text and current_year and int(year_text) < current_year - 1:
                return 0.0, None
            name = venue + (" " + year_text if year_text else "") + (" workshop" if workshop else "")
            label = "%s %s" % (cue[1], name) if cued else "%s paper" % name
            return (0.5 if workshop else 1.0), label
        if cue is not None and not negative and _GENERIC_VENUE.search(clause) and best[0] == 0:
            best = (0.5, "accepted at a workshop" if workshop else "accepted for publication")
    return best


def code_signal(abstract, comment, provider_url):
    """(url, kind) of released code or artifacts, or (None, None).

    A provider's repository link wins; otherwise the first code-host URL in the
    comment or abstract, unless the surrounding text only promises a future release.
    """
    if provider_url:
        return provider_url, "code"
    for text in (comment or "", abstract or ""):
        for match in _CODE_URL.finditer(text):
            context = text[max(0, match.start() - 80):match.start()]
            if _PROMISE.search(context):
                continue
            url = match.group(0).rstrip(".")
            if not url.lower().startswith("http"):
                url = "https://" + url
            host = match.group(1).lower()
            artifacts = host.startswith(("zenodo", "doi.org")) or "/datasets/" in url
            return url, ("artifacts" if artifacts else "code")
    return None, None


def measured_count(abstract):
    """How many quantities with units or ratios the abstract reports (e.g. 4.2 TOPS/W, 31%, 2.1x)."""
    return len(_MEASURE.findall(abstract or ""))


# ------------------------------------------------------------------ tracks

# Terms that mark machine learning. Counted as distinct terms, so one ambiguous word (a power
# engineer's "transformer", a modem's "training sequence") never decides alone.
_ML_FLAVOUR = re.compile(
    r"\b(?:LLMs?|large language models?|language models?|transformers?|\w*(?:ro|con)formers?|neural|"
    r"deep learning|deep|diffusion|reinforcement learning|foundation models?|agents?|agentic|generative|"
    r"GPT|VLAs?|VLMs?|in-context|self-supervised|semi-supervised|supervised|contrastive|fine-tun\w*|"
    r"prompt\w*|CNNs?|GANs?|VAEs?|LoRA|attention|learned|learning|pre-?train\w*|trained|training|"
    r"embeddings?|text-to-\w+|AI|datasets?|benchmarks?|corpus|corpora|reward models?|"
    r"(?:speech|music|audio|image|video|text) generation)\b", re.I)
_HARDWARE = re.compile(
    r"\b(?:GPUs?|FPGAs?|ASICs?|accelerators?|chips?|chiplets?|silicon|SoCs?|RISC-V|DRAM|HBM|SRAM|CXL|"
    r"NoCs?|interconnects?|processors?|CPUs?|microarchitectur\w*|hardware|SmartNICs?|DPUs?|TPUs?|NPUs?|"
    r"CUDA|ROCm|CDNA\d*|Hopper|Blackwell|in-memory computing|PIM|RDMA|NVLink|cache coherence)\b")


def ml_flavoured(paper):
    """An ML paper in disguise: an ML term in the title, or two distinct ones in the abstract."""
    if _ML_FLAVOUR.search(paper["title"]):
        return True
    return len({term.lower() for term in _ML_FLAVOUR.findall(paper["abstract"])}) >= 2


def classify_track(paper, tracks):
    """"electronics", "cs" or None, decided by the paper's primary category.

    Core hardware categories are always electronics; signal processing, systems,
    imaging and audio count only when the paper is not machine learning applied to
    them; distributed computing counts when the title is about hardware. Cross-listing
    alone never makes an ML paper electronics.
    """
    electronics, primary = tracks["electronics"], paper.get("primary") or ""
    if primary in electronics["alwaysPrimary"]:
        return "electronics"
    if primary in electronics["unlessMlFlavouredPrimary"]:
        return "cs" if ml_flavoured(paper) else "electronics"
    if primary in electronics["hardwareTitlePrimary"] and _HARDWARE.search(paper["title"]):
        return "electronics"
    if any(primary.startswith(prefix) for prefix in tracks["cs"]["eligiblePrimaryPrefixes"]):
        return "cs"
    return None


# ------------------------------------------------------------------ scoring

# Signal -> provider that must have answered for it to count. None: derived from the
# paper record, always present.
SIGNAL_PROVIDERS = {
    "hfUpvotes": ("hf",), "alphaxivVotes": ("alphaxiv",), "alphaxivViews": ("alphaxiv",),
    "hnPoints": ("hn",), "githubStars": ("hf", "alphaxiv"), "citations": ("openalex",),
    "mentions": ("items",), "venue": None, "code": None, "crossLists": None, "measured": None,
}
_LINEAR = {"crossLists": 3.0, "measured": 3.0}  # counted signals that saturate at this many
_SOCIAL = ("hfUpvotes", "alphaxivVotes", "hnPoints", "alphaxivViews", "mentions")


def present_signals(available):
    """The signals whose provider answered this run, given the set of providers that did."""
    return {signal for signal, needs in SIGNAL_PROVIDERS.items()
            if needs is None or any(name in available for name in needs)}


def normalise(signal, value, track_max, floors, caps):
    """Map a raw signal onto 0..1.

    Counts are log-scaled against the track's highest value this week (never below a
    floor, so three views do not look like a landslide); venue and code are already
    0..1; cross-listing and measured numbers saturate at three.
    """
    if signal in _LINEAR:
        return min(1.0, value / _LINEAR[signal])
    if signal in ("venue", "code"):
        return float(value)
    cap = caps.get(signal)
    value = min(value, cap) if cap else value
    top = max(min(track_max, cap) if cap else track_max, floors.get(signal, 1))
    return min(1.0, math.log1p(value) / math.log1p(top)) if value > 0 else 0.0


def score_track(papers, weights, floors, caps, present):
    """Give each paper of one track ``score`` (0-100) and ``parts`` (signal -> weight x normalised value).

    Signals combine like independent chances of being noticed: score = 1 - prod(1 - part).
    Strong attention from any one community counts on its own and agreement between
    communities counts more, which a weighted average would not allow (a paper huge on
    alphaXiv but never posted to Hugging Face would be dragged down by the zero).
    The result is divided by the best score possible from the signals present this
    run, so a provider outage renormalises instead of lowering every paper.
    """
    active = [signal for signal, weight in weights.items() if weight > 0 and signal in present]
    best = 1.0 - math.prod(1.0 - weights[signal] for signal in active)
    maxima = {signal: max([paper["signals"].get(signal, 0) for paper in papers] or [0]) for signal in active}
    for paper in papers:
        parts = {}
        for signal in active:
            share = weights[signal] * normalise(signal, paper["signals"].get(signal, 0), maxima[signal], floors, caps)
            if share > 0:
                parts[signal] = share
        missed = math.prod(1.0 - share for share in parts.values())
        paper["parts"] = parts
        paper["score"] = round(100.0 * (1.0 - missed) / best, 1) if best > 0 else 0.0


def rank_key(paper):
    """Highest score first; ties go to more social attention, then the newer paper, then the id."""
    social = sum(paper["signals"].get(signal, 0) for signal in _SOCIAL)
    return (-paper["score"], -social, _neg_time(paper["published"]), paper["id"])


def _neg_time(iso_text):
    """Sort key putting newer papers first."""
    parsed = timeutil.parse_date(iso_text)
    return -parsed.timestamp() if parsed else 0.0


def select(papers, picks, quotas, max_per_primary, runners_up, exclude=()):
    """(top, runners) chosen from scored papers.

    Quotas are filled first from the best papers of each quota track, from different
    primary categories while that is possible; then the rest by score. No more than
    ``max_per_primary`` picks share a primary category, and papers in ``exclude``
    (featured in an earlier week) or with no score are skipped.
    """
    ranked = sorted((paper for paper in papers if paper["score"] > 0 and paper["id"] not in exclude), key=rank_key)
    chosen, per_primary = [], Counter()

    def take(paper):
        chosen.append(paper)
        per_primary[paper["primary"]] += 1

    def allowed(paper):
        return paper not in chosen and per_primary[paper["primary"]] < max_per_primary

    for track, need in quotas.items():
        for distinct in (True, False):
            for paper in ranked:
                if len(chosen) >= picks or sum(1 for item in chosen if item["track"] == track) >= need:
                    break
                fresh = not any(item["primary"] == paper["primary"] for item in chosen if item["track"] == track)
                if paper["track"] == track and allowed(paper) and (fresh or not distinct):
                    take(paper)
    for paper in ranked:
        if len(chosen) >= picks:
            break
        if allowed(paper):
            take(paper)
    chosen.sort(key=rank_key)
    rest = [paper for paper in ranked if paper not in chosen][:runners_up]
    return chosen, rest


# ------------------------------------------------------------------ why chips


def _count(value, one, many):
    """Singular or plural chip text with thousands separators."""
    return one if value == 1 else many % "{:,}".format(value)


def why_chips(paper, limit=4):
    """Short reasons, strongest contribution first, each stating a real signal value."""
    signals, labels = paper["signals"], paper.get("labels", {})
    text = {
        "hfUpvotes": lambda v: _count(v, "1 upvote on Hugging Face", "%s upvotes on Hugging Face"),
        "alphaxivVotes": lambda v: _count(v, "1 vote on alphaXiv", "%s votes on alphaXiv"),
        "alphaxivViews": lambda v: _count(v, "1 view on alphaXiv", "%s views on alphaXiv this week"),
        "hnPoints": lambda v: _count(v, "1 point on Hacker News", "%s points on Hacker News"),
        "githubStars": lambda v: _count(v, "1 GitHub star", "%s GitHub stars"),
        "citations": lambda v: _count(v, "cited once", "cited %s times"),
        "mentions": lambda v: _count(v, "mentioned in 1 of our feeds", "mentioned in %s of our feeds"),
        "venue": lambda v: labels.get("venue") or "",
        "code": lambda v: "artifacts available" if labels.get("code") == "artifacts" else "code available",
        "crossLists": lambda v: "cross-listed in %d categories" % (v + 1),
        "measured": lambda v: "reports measured results",
    }
    order = sorted(paper.get("parts", {}).items(), key=lambda pair: -pair[1])
    chips = []
    for signal, _ in order:
        value = signals.get(signal, 0)
        if not value or (signal == "crossLists" and value < 2) or (signal == "measured" and value < 2):
            continue
        chip = text[signal](value)
        if chip and chip not in chips:
            chips.append(chip)
        if len(chips) >= limit:
            break
    return chips


# ------------------------------------------------------------------ papers


def build_paper(record, track, social, venue_patterns):
    """Merge an arXiv record with its provider signals and content signals into a Paper draft."""
    year = int(record["published"][:4])
    venue_value, venue_label = venue_signal(record["comment"], record["journalRef"], venue_patterns,
                                            record["authors"], year)
    code_url, code_kind = code_signal(record["abstract"], record["comment"], social.get("codeUrl"))
    return {
        "id": record["id"],
        "title": record["title"],
        "authors": record["authors"],
        "primary": record["primary"],
        "categories": record["categories"],
        "track": track,
        "published": record["published"],
        "abstract": record["abstract"],
        "comment": record["comment"],
        "signals": {
            "hfUpvotes": social.get("hfUpvotes", 0), "hnPoints": social.get("hnPoints", 0),
            "citations": social.get("citations", 0), "githubStars": social.get("githubStars", 0),
            "mentions": social.get("mentions", 0), "alphaxivVotes": social.get("alphaxivVotes", 0),
            "alphaxivViews": social.get("alphaxivViews", 0), "venue": venue_value,
            "code": 1 if code_url else 0, "crossLists": max(0, len(set(record["categories"])) - 1),
            "measured": measured_count(record["abstract"]),
        },
        "labels": {"venue": venue_label, "code": code_kind},
        "links": {
            "abs": "https://arxiv.org/abs/%s" % record["id"],
            "pdf": "https://arxiv.org/pdf/%s" % record["id"],
            "code": code_url,
            "hf": "https://huggingface.co/papers/%s" % record["id"] if social.get("onHf") else None,
            "hn": social.get("hnUrl"),
        },
    }


def public_paper(paper, rank):
    """The contract's Paper object: drops working fields, adds digest, why and rank."""
    return {
        "id": paper["id"], "title": paper["title"], "authors": paper["authors"], "primary": paper["primary"],
        "categories": paper["categories"], "track": paper["track"], "published": paper["published"],
        "abstract": paper["abstract"], "digest": digest(paper["abstract"], paper["title"]),
        "signals": paper["signals"], "score": paper["score"], "why": why_chips(paper),
        "links": paper["links"], "rank": rank,
    }


def in_window(record, start, end, grace_days):
    """Published in [start - grace, end): late-curated papers from just before the window still count."""
    published = timeutil.parse_date(record["published"])
    return published is not None and start - timedelta(days=grace_days) <= published < end


def _id_month_floor(start, grace_days):
    """Smallest YYMM an arXiv id can carry for a paper submitted in the window (ids encode the month)."""
    earliest = start - timedelta(days=grace_days + 31)
    return "%02d%02d" % (earliest.year % 100, earliest.month)


# ------------------------------------------------------------------ week in review


def review_stories(stories_dir, first, last, limit=7):
    """The week's biggest stories: each thread's peak-scoring day, highest first."""
    peaks, day, seen_file = {}, first, False
    while day <= last:
        stored = jsonio.read_json(stories_dir / ("%s.json" % day.isoformat()), default=None)
        if isinstance(stored, dict) and isinstance(stored.get("stories"), list):
            seen_file = True
            for story in stored["stories"]:
                if not isinstance(story, dict) or not isinstance(story.get("score"), (int, float)):
                    continue
                key = (story.get("thread") or {}).get("id") or story.get("id")
                if key and (key not in peaks or story["score"] > peaks[key]["score"]):
                    peaks[key] = story
        day += timedelta(days=1)
    if not seen_file:
        return None
    return sorted(peaks.values(), key=lambda story: -story["score"])[:limit]


def review_markets(markets_path, sessions=5):
    """Week moves for the headline strip: last close against the close ``sessions`` earlier."""
    markets = jsonio.read_json(markets_path, default=None)
    if not isinstance(markets, dict):
        return None
    quotes = {}
    for group in markets.get("groups") or []:
        for quote in (group or {}).get("quotes") or []:
            if isinstance(quote, dict) and quote.get("symbol"):
                quotes.setdefault(quote["symbol"], quote)
    moves = []
    for symbol in markets.get("strip") or list(quotes):
        quote = quotes.get(symbol)
        spark = [value for value in (quote or {}).get("spark") or [] if isinstance(value, (int, float))]
        if len(spark) < 2:
            continue
        base = spark[-(sessions + 1)] if len(spark) > sessions else spark[0]
        if base:
            moves.append({"symbol": symbol, "name": quote.get("name") or symbol,
                          "weekPct": round((spark[-1] / base - 1.0) * 100.0, 2)})
    return moves


def review_claude(updates_path, first, last, limit=6):
    """Claude updates dated inside the window, newest first."""
    updates = jsonio.read_json(updates_path, default=None)
    if not isinstance(updates, dict) or not isinstance(updates.get("entries"), list):
        return None
    window = [entry for entry in updates["entries"]
              if isinstance(entry, dict) and first.isoformat() <= str(entry.get("date") or "") <= last.isoformat()]
    return sorted(window, key=lambda entry: entry["date"], reverse=True)[:limit]


def build_review(paths, first, last):
    """The review block; each part appears only when its input exists and has something to show."""
    review = {}
    parts = (("stories", review_stories(paths.stories_dir, first, last)),
             ("markets", review_markets(paths.public / "markets.json")),
             ("claude", review_claude(paths.claude_dir / "updates.json", first, last)))
    for name, value in parts:
        if value:
            review[name] = value
    return review


# ------------------------------------------------------------------ method text and index

_PROVIDER_NAMES = {"hf": "Hugging Face upvotes", "alphaxiv": "alphaXiv views and votes",
                   "hn": "Hacker News points", "openalex": "OpenAlex citations",
                   "items": "coverage in our own news feeds"}


def _day(day):
    """"4 November": strftime's no-padding flag is not portable."""
    return "%d %s" % (day.day, day.strftime("%B"))


def method_text(considered, categories, first, last, available, missing):
    """The one honest paragraph shown with the issue: what was ranked, on what, and what it is not."""
    used = [_PROVIDER_NAMES[name] for name in ("hf", "alphaxiv", "hn", "openalex", "items") if name in available]
    lost = [_PROVIDER_NAMES[name] for name in ("hf", "alphaxiv", "hn", "openalex", "items") if name in missing]
    text = ("These are the papers that were most noticed this week, not a judgement of which are best. "
            "We took the %s new arXiv papers submitted %s to %s in %d computer-science and electronics "
            "categories and scored each on free public signals: %s. Each signal is put on a log scale "
            "against the week's highest value in its own track, so hardware papers compete with hardware "
            "papers. Strong attention from any one community counts on its own and agreement between "
            "communities counts more; scores are scaled to the signals that were available. "
            % ("{:,}".format(considered), _day(first), _day(last) + " %d" % last.year, categories,
               ", ".join(used) if used else "none were reachable"))
    if lost:
        text += "Unavailable this week: %s. " % ", ".join(lost)
    text += ("Few people vote on electronics papers online, so that track also credits acceptance at a named "
             "venue, released code, cross-listing and measured results stated in the abstract. At least two "
             "picks are electronics, at most two share an arXiv category, and papers featured in an earlier "
             "week are skipped. Digest lines are sentences copied from each abstract, not written by us.")
    return text


def featured_before(weekend_dir, iso_week, weeks):
    """Ids already in the top five of the ``weeks`` most recent earlier issues."""
    index = jsonio.read_json(weekend_dir / "index.json", default={}) or {}
    ids = set()
    earlier = [entry.get("isoWeek") for entry in index.get("weeks") or [] if isinstance(entry, dict)]
    for week in [week for week in earlier if week and week < iso_week][:weeks]:
        issue = jsonio.read_json(weekend_dir / ("%s.json" % week), default={}) or {}
        ids.update(paper.get("id") for paper in issue.get("papers") or [] if isinstance(paper, dict))
    return ids


def update_index(weekend_dir, entry):
    """Insert or replace this week's line in index.json, newest week first."""
    path = weekend_dir / "index.json"
    index = jsonio.read_json(path, default={}) or {}
    weeks = [week for week in index.get("weeks") or []
             if isinstance(week, dict) and week.get("isoWeek") and week.get("isoWeek") != entry["isoWeek"]]
    weeks.append(entry)
    weeks.sort(key=lambda week: week["isoWeek"], reverse=True)
    jsonio.write_json(path, {"weeks": weeks})


# ------------------------------------------------------------------ the stage


class Window:
    """The issue's dates: local ``first``..``last``, their UTC [start, end), the run's local ``today`` and its end."""

    def __init__(self, now, tz, lookback_days):
        self.first, self.last = issue_window(now, tz, lookback_days)
        self.start, self.end = window_bounds(self.first, self.last, tz)
        self.today = date.fromisoformat(timeutil.local_date(now, tz))
        self.today_end = window_bounds(self.today, self.today, tz)[1]
        self.iso_week = week_of(self.last)


def check_config(cfg):
    """Fail early, naming the key, when hand-edited config would make scores meaningless."""
    for track, weights in cfg["weights"].items():
        if track not in cfg["tracks"]:
            raise config.ConfigError("config/papers.json: weights for unknown track %r" % track)
        for signal, weight in weights.items():
            if signal not in SIGNAL_PROVIDERS:
                raise config.ConfigError("config/papers.json: unknown signal %r in weights.%s" % (signal, track))
            if not isinstance(weight, (int, float)) or not 0 <= weight <= 1:
                raise config.ConfigError("config/papers.json: weights.%s.%s must be between 0 and 1" % (track, signal))
    for track in cfg["quotas"]:
        if track not in cfg["tracks"]:
            raise config.ConfigError("config/papers.json: quota for unknown track %r" % track)


def collect_signals(cache, cfg, window, report, missing):
    """Every network provider, each on its own; {provider: {id: signals}} for those that answered."""
    maps = {}
    for name, result in (("hf", collect_hf(cache, cfg, window.first, window.last, window.today)),
                         ("alphaxiv", collect_alphaxiv(cache, cfg)),
                         ("hn", collect_hn(cache, cfg, window.start, window.today_end))):
        data = _provider(report, name, result, missing)
        if data is not None:
            maps[name] = data
    return maps


def _social(pid, maps, mentions):
    """One paper's provider signals merged into a flat dict."""
    merged = {}
    for name in ("hf", "alphaxiv", "hn"):
        _merge_signals(merged, maps.get(name, {}).get(pid, {}))
    merged["onHf"] = pid in maps.get("hf", {})
    if pid in mentions:
        merged["mentions"] = mentions[pid]
    return merged


def build_candidates(records, maps, mentions, cfg, window):
    """Eligible Paper drafts: a track, published inside the window (plus grace), signals attached."""
    venue_patterns = [(venue, _venue_pattern(venue)) for venue in sorted(cfg["venues"], key=len, reverse=True)]
    papers = []
    for pid, record in records.items():
        track = classify_track(record, cfg["tracks"])
        if track and in_window(record, window.start, window.end, int(cfg["graceDays"])):
            papers.append(build_paper(record, track, _social(pid, maps, mentions), venue_patterns))
    return papers


def score_all(papers, cfg, available):
    """Score every track separately over the signals whose providers answered."""
    present = present_signals(available)
    for track in cfg["weights"]:
        members = [paper for paper in papers if paper["track"] == track]
        score_track(members, cfg["weights"][track], cfg["floors"], cfg["caps"], present)


def add_citations(cache, cfg, papers, available, report, missing):
    """OpenAlex citations for each track's shortlist, then a rescore if OpenAlex answered."""
    shortlist = []
    for track in cfg["weights"]:
        members = sorted((paper for paper in papers if paper["track"] == track), key=rank_key)
        shortlist.extend(paper["id"] for paper in members[:int(cfg["citationLookups"])])
    citations = _provider(report, "openalex", collect_citations(cache, cfg, shortlist), missing)
    if citations is None:
        return
    available.add("openalex")
    for paper in papers:
        paper["signals"]["citations"] = citations.get(paper["id"], 0)
    score_all(papers, cfg, available)


def write_issue(paths, cfg, window, papers, top, rest, available, missing):
    """Write the week's file and its index line; returns the issue."""
    categories = len({category for track in cfg["tracks"].values() for category in track["categories"]})
    issue = {
        "isoWeek": window.iso_week, "from": window.first.isoformat(), "to": window.last.isoformat(),
        "generatedAt": timeutil.iso(timeutil.now_utc()),
        "title": top[0]["title"],
        "method": method_text(len(papers), categories, window.first, window.last, available, missing),
        "papers": [public_paper(paper, rank) for rank, paper in enumerate(top, 1)],
        "runnersUp": [public_paper(paper, rank) for rank, paper in enumerate(rest, len(top) + 1)],
        "review": build_review(paths, window.first, window.last),
    }
    jsonio.write_json(paths.weekend_dir / ("%s.json" % window.iso_week), issue)
    update_index(paths.weekend_dir, {"isoWeek": window.iso_week, "from": issue["from"], "to": issue["to"],
                                     "title": issue["title"]})
    return issue


def run(ctx):
    """Build the Weekend Review when it is due; returns counts for run.json."""
    cfg = config.load("papers")
    check_config(cfg)
    weekday = int((ctx.site.get("weekend") or {}).get("weekday", 5))
    window = Window(ctx.now, ctx.tz, int(cfg["lookbackDays"]))
    if not is_due(ctx.now, ctx.tz, weekday, ctx.paths.weekend_dir / ("%s.json" % window.iso_week), ctx.force,
                  window.last):
        log.info("not due: builds on weekday %d unless %s.json already covers the week to %s, or with --force",
                 weekday, window.iso_week, window.last)
        return {"skipped": True}
    log.info("Weekend Review %s: papers submitted %s to %s", window.iso_week, window.first, window.last)
    cache = DayCache(ctx.paths.state / "papers-cache", window.today.isoformat())
    report, missing = {}, []
    grace = int(cfg["graceDays"])

    records = gather_candidates(cache, cfg, window.start, window.end, report)
    maps = collect_signals(cache, cfg, window, report, missing)
    floor = _id_month_floor(window.start, grace)
    named = {pid for data in maps.values() for pid in data if pid[:4] >= floor and pid not in records}
    records.update(resolve_ids(cache, cfg, named, report))
    if not records:
        raise RuntimeError("no candidate papers: arXiv returned nothing (%s)" % report["arxiv"]["error"])

    items = load_items(ctx.paths.items_dir, window.first - timedelta(days=grace), window.today)
    available = set(maps) | ({"items"} if items else set())
    if not items:
        missing.append("items")
    papers = build_candidates(records, maps, count_mentions(records, items) if items else {}, cfg, window)
    score_all(papers, cfg, available)
    add_citations(cache, cfg, papers, available, report, missing)

    exclude = featured_before(ctx.paths.weekend_dir, window.iso_week, int(cfg["excludeFeaturedWeeks"]))
    top, rest = select(papers, int(cfg["picks"]), cfg["quotas"], int(cfg["maxPerPrimaryCategory"]),
                       int(cfg["runnersUp"]), exclude)
    if not top:
        raise RuntimeError("no paper had any signal this week; previous issues are untouched")
    for track, need in cfg["quotas"].items():
        have = sum(1 for paper in top if paper["track"] == track)
        if have < need:
            log.warn("quota not met: %d of %d %s papers", have, need, track)

    issue = write_issue(ctx.paths, cfg, window, papers, top, rest, available, missing)
    for paper in issue["papers"]:
        log.info("#%d [%s %s] %.1f %s | %s", paper["rank"], paper["track"], paper["primary"], paper["score"],
                 paper["title"][:80], "; ".join(paper["why"]))
    return {
        "isoWeek": window.iso_week, "candidates": len(records), "considered": len(papers),
        "papers": len(top), "electronics": sum(1 for paper in top if paper["track"] == "electronics"),
        "runnersUp": len(rest), "reviewParts": sorted(issue["review"]),
        "signalsMissing": sorted(set(missing)),
        "providerErrors": {name: info["error"] for name, info in report.items() if info.get("error")},
    }
