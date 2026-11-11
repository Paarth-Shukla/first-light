"""HTTP for the pipeline: one honest client, used by every stage.

Why this exists instead of calling ``urllib`` directly:

* One User-Agent everywhere. A source that rejects it is disabled in config;
  nothing here (or anywhere) may send a different identity.
* Python 3.9's ``urllib`` raises on HTTP 308, some servers gzip without saying
  so, and feeds fail in a dozen different exception types. ``fetch`` hides all
  of that behind one ``Response`` and one ``NetError``.
* Limits that keep a bad source from hurting the run: a per-attempt time
  budget, a byte cap (also applied after gunzip), bounded retries.

    resp = net.fetch(url, cache=cache)        # raises NetError
    if not resp.not_modified:
        parse(resp.body)
"""

import codecs
import http.client
import json
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from . import jsonio, log, timeutil

USER_AGENT = "Mozilla/5.0 (compatible; FirstLight/1.0; personal news digest)"

_CHUNK = 65536
_BACKOFF_S = 0.5        # first retry waits this long, then doubles
_RETRY_429_S = 2.5      # the single retry a 429 gets
_CACHE_KEEP_DAYS = 30   # validators for URLs not fetched this long are dropped
_GZIP_MAGIC = b"\x1f\x8b"
_URL_SAFE = "%/:=&?~+!$,;'@()*[]"

_offline = {"on": False}


class NetError(Exception):
    """A fetch failed. ``str(err)`` is a short sentence fit for status.json.

    ``kind`` is one of ``http`` (a status, in ``status``), ``timeout``,
    ``connection``, ``tls``, ``too-large`` and ``offline``.
    """

    def __init__(self, kind, status=None, message="", url=None):
        super().__init__(message or kind)
        self.kind = kind
        self.status = status
        self.message = message or kind
        self.url = url

    def __str__(self):
        return self.message

    def __repr__(self):
        return "NetError(kind=%r, status=%r, message=%r, url=%r)" % (
            self.kind, self.status, self.message, self.url)


@dataclass
class Response:
    """The result of a fetch. ``headers`` is a case-insensitive mapping."""

    status: int
    body: bytes                 # already gunzipped
    headers: Any
    url: str                    # final URL after redirects
    not_modified: bool = False  # True on 304: body is empty, reuse what you have
    elapsed_ms: int = 0

    def text(self):
        """Decode the body using the declared charset, falling back to UTF-8.

        Bytes are what XML parsers want; this is for JSON and markdown, where a
        BOM or a wrong charset label must not break the read.
        """
        if self.body.startswith(codecs.BOM_UTF8):
            return self.body.decode("utf-8-sig", errors="replace")
        return self.body.decode(_charset(self.headers), errors="replace")


def _charset(headers):
    """Charset named in Content-Type if Python knows it, else utf-8."""
    content_type = headers.get("Content-Type") or headers.get("content-type") or ""
    match = re.search(r"charset=[\"']?([\w.:-]+)", content_type, re.I)
    if match:
        try:
            return codecs.lookup(match.group(1)).name
        except LookupError:
            pass  # an unknown label is the same as no label
    return "utf-8"


def set_offline(on):
    """Switch the network off (``--offline``): every fetch then fails fast with kind 'offline'."""
    _offline["on"] = bool(on)


def is_offline():
    """True when ``set_offline(True)`` is in effect."""
    return _offline["on"]


class _Redirects(urllib.request.HTTPRedirectHandler):
    """Follow 308 like 307. Python 3.9 raises on it; 3.11+ follows it natively."""

    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, 307, msg, headers)


def _build_opener(proxies=None):
    """An opener limited to http and https, so a redirect can never reach file:// or ftp://.

    ``proxies=None`` uses the system proxy settings; tests pass ``{}`` to stay local.
    """
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler(proxies),
        urllib.request.UnknownHandler(),
        urllib.request.HTTPHandler(),
        urllib.request.HTTPSHandler(),
        urllib.request.HTTPDefaultErrorHandler(),
        _Redirects(),
        urllib.request.HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    return opener


_opener = _build_opener()


class HttpCache:
    """Remembers ETag / Last-Modified per URL so unchanged feeds cost a 304.

    Only validators are stored, never bodies: on ``Response.not_modified`` the
    caller keeps what it already has. Call ``save()`` after your own output is
    safely written, not before; persisting validators for data you then failed
    to store would hide that data behind 304s on the next run. If a body turns
    out to be unusable (parse error), call ``forget(url)``.
    """

    def __init__(self, path):
        self._path = path
        self._lock = threading.Lock()
        stored = jsonio.read_json(path, default={})
        if not isinstance(stored, dict):
            log.warn("ignoring malformed HTTP cache %s", path)
            stored = {}
        self._entries = {url: entry for url, entry in stored.items() if isinstance(entry, dict)}
        self._dirty = False

    @staticmethod
    def _key(url):
        """Entries are keyed by the URL as ``fetch`` sends it, however the caller spelled it."""
        try:
            return _prepare_url(url)
        except NetError:
            return str(url).strip()  # never fetched, so never cached: any stable key will do

    def headers_for(self, url):
        """Conditional request headers for ``url`` (empty when nothing is known)."""
        with self._lock:
            entry = self._entries.get(self._key(url)) or {}
        headers = {}
        if entry.get("etag"):
            headers["If-None-Match"] = entry["etag"]
        if entry.get("lastModified"):
            headers["If-Modified-Since"] = entry["lastModified"]
        return headers

    def record(self, url, response):
        """Update the entry for ``url`` from a 200 (new validators) or a 304 (still in use)."""
        today = timeutil.now_utc().date().isoformat()
        url = self._key(url)
        with self._lock:
            if response.not_modified:
                entry = self._entries.get(url)
                if entry is not None and entry.get("at") != today:
                    entry["at"] = today
                    self._dirty = True
                return
            entry = {}
            if response.headers.get("ETag"):
                entry["etag"] = response.headers.get("ETag")
            if response.headers.get("Last-Modified"):
                entry["lastModified"] = response.headers.get("Last-Modified")
            if not entry:
                self._dirty = self._entries.pop(url, None) is not None or self._dirty
                return
            entry["at"] = today
            if self._entries.get(url) != entry:
                self._entries[url] = entry
                self._dirty = True

    def forget(self, url):
        """Drop validators for ``url`` so the next fetch downloads the body again."""
        with self._lock:
            if self._entries.pop(self._key(url), None) is not None:
                self._dirty = True

    def save(self):
        """Persist changes atomically, pruning long-unused URLs. Returns False if the write failed.

        A cache that cannot be saved only costs bandwidth next run, so the
        failure is logged rather than raised.
        """
        cutoff = (timeutil.now_utc() - timedelta(days=_CACHE_KEEP_DAYS)).date().isoformat()
        with self._lock:
            kept = {url: entry for url, entry in self._entries.items()
                    if str(entry.get("at", "")) >= cutoff}
            if not self._dirty and len(kept) == len(self._entries):
                return True
            try:
                jsonio.write_json(self._path, kept, sort_keys=True)
            except OSError as err:
                log.warn("could not save HTTP cache %s (%s)", self._path, err)
                return False
            self._entries = kept
            self._dirty = False
            return True


def _prepare_url(url):
    """Validate and normalise a URL for the wire: trimmed, http(s) only, unsafe characters quoted.

    Feeds hand us links with stray spaces and raw non-ASCII; quoting here means
    callers never have to. The fragment is dropped because it is never sent.
    """
    text = str(url).strip()
    try:
        parts = urllib.parse.urlsplit(text)
    except ValueError as err:
        raise NetError("connection", None, "bad URL: %s" % err, text) from err
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        raise NetError("connection", None, "not an http(s) URL", text)
    return urllib.parse.urlunsplit((
        parts.scheme.lower(),
        parts.netloc,
        urllib.parse.quote(parts.path, safe=_URL_SAFE),
        urllib.parse.quote(parts.query, safe=_URL_SAFE),
        "",
    ))


def _request_headers(extra, conditional):
    """Merge default, cache and caller headers; the User-Agent is not negotiable."""
    headers = {"User-agent": USER_AGENT, "Accept": "*/*", "Accept-encoding": "gzip"}
    for source in (conditional, extra or {}):
        for name, value in source.items():
            key = str(name).capitalize()
            if key == "User-agent" and str(value) != USER_AGENT:
                raise ValueError("the User-Agent is fixed; a source that rejects it gets disabled")
            headers[key] = str(value)
    return headers


def _gunzip(data, max_bytes, url):
    """Decompress a (possibly multi-member) gzip body without ever inflating past ``max_bytes``."""
    pieces, total = [], 0
    while True:
        inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
        piece = inflater.decompress(data, max_bytes + 1 - total)
        total += len(piece)
        if total > max_bytes:
            raise NetError("too-large", None, "response larger than %d bytes after gunzip" % max_bytes, url)
        if not inflater.eof:
            raise NetError("connection", None, "truncated gzip body", url)
        pieces.append(piece)
        data = inflater.unused_data
        if not data.startswith(_GZIP_MAGIC):
            return b"".join(pieces)


def _decode_body(body, headers, max_bytes, url):
    """Gunzip when the header says gzip or the bytes start with the gzip magic.

    Some servers (DeepMind, The Independent) compress without declaring it, so
    the magic bytes are checked too. Bytes that only look like gzip are passed
    through untouched unless the server declared the encoding.
    """
    if not body.startswith(_GZIP_MAGIC):
        return body
    try:
        return _gunzip(body, max_bytes, url)
    except zlib.error as err:
        if "gzip" in (headers.get("Content-Encoding") or "").lower():
            raise NetError("connection", None, "bad gzip body: %s" % err, url) from err
        return body


def _read_capped(raw, max_bytes, deadline, timeout, url):
    """Read the body in chunks, enforcing the byte cap and the attempt's time budget.

    ``read1`` returns as soon as any bytes arrive, so a server that drips data
    cannot stretch one attempt far beyond ``timeout`` the way a blocking
    ``read()`` would.
    """
    declared = raw.headers.get("Content-Length") or ""
    expected = int(declared) if declared.isdigit() else None
    too_large = NetError("too-large", None, "response larger than %d bytes" % max_bytes, url)
    if expected is not None and expected > max_bytes:
        raise too_large
    chunks, total = [], 0
    while True:
        if time.monotonic() > deadline:
            raise NetError("timeout", None, "timed out after %g s" % timeout, url)
        chunk = raw.read1(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise too_large
        chunks.append(chunk)
    if expected is not None and total < expected:
        raise NetError("connection", None,
                       "connection closed early (%d of %d bytes)" % (total, expected), url)
    return b"".join(chunks)


def _http_message(status):
    """"HTTP 403 Forbidden", using the standard phrase rather than whatever text the server sent.

    urllib only surfaces a 3xx when it refused to follow it, so say that.
    """
    if 300 <= status < 400:
        return "HTTP %d redirect not followed (loop, or no usable Location)" % status
    return ("HTTP %d %s" % (status, http.client.responses.get(status, ""))).strip()


def _translate(err, url, timeout):
    """Map every exception urllib, http.client, ssl and socket can raise onto one NetError."""
    if isinstance(err, urllib.error.HTTPError):
        return NetError("http", err.code, _http_message(err.code), url)
    reason = err.reason if isinstance(err, urllib.error.URLError) else err
    if isinstance(reason, (socket.timeout, TimeoutError)):
        return NetError("timeout", None, "timed out after %g s" % timeout, url)
    if isinstance(reason, ssl.SSLError):
        detail = getattr(reason, "verify_message", None) or getattr(reason, "reason", None) or str(reason)
        return NetError("tls", None, "TLS error: %s" % detail, url)
    if isinstance(reason, http.client.IncompleteRead):
        return NetError("connection", None, "connection closed early", url)
    if isinstance(reason, OSError):
        return NetError("connection", None, "connection failed: %s" % (reason.strerror or reason), url)
    return NetError("connection", None, "connection failed: %s" % (reason,), url)


def _attempt(url, headers, timeout, max_bytes):
    """One request/response cycle. Returns a Response or raises NetError."""
    deadline = time.monotonic() + timeout
    try:
        request = urllib.request.Request(url, headers=headers)
        with _opener.open(request, timeout=timeout) as raw:
            body = _read_capped(raw, max_bytes, deadline, timeout, url)
            return Response(
                status=raw.status,
                body=_decode_body(body, raw.headers, max_bytes, url),
                headers=raw.headers,
                url=raw.url,
            )
    except urllib.error.HTTPError as err:
        try:
            conditional = "If-none-match" in headers or "If-modified-since" in headers
            if err.code == 304 and conditional:
                return Response(status=304, body=b"", headers=err.headers, url=url, not_modified=True)
            raise _translate(err, url, timeout) from err
        finally:
            if err.fp is not None:
                err.close()  # the error object holds the open connection
    except NetError:
        raise
    except (OSError, http.client.HTTPException, ValueError) as err:
        # OSError covers URLError, socket.timeout, ssl errors and resets; ValueError covers
        # http.client.InvalidURL and host names that cannot be encoded.
        raise _translate(err, url, timeout) from err


def _retry_delay(err, failures, retries, throttled):
    """Seconds to wait before retrying, or None when this failure is final.

    Transient trouble (timeouts, resets, 5xx) backs off briefly. A 4xx is the
    server's answer and is never retried, except one polite retry on 429.
    """
    if failures >= retries:
        return None
    if err.kind == "http" and err.status == 429:
        return None if throttled else _RETRY_429_S
    if err.kind in ("timeout", "connection") or (err.kind == "http" and (err.status or 0) >= 500):
        return _BACKOFF_S * (2 ** failures)
    return None


def fetch(url, *, timeout=20, retries=1, headers=None, cache=None, max_bytes=8_000_000):
    """GET ``url`` and return a ``Response``; raise ``NetError`` on any failure.

    ``timeout`` is the budget for one attempt, connect to last byte (a read
    that stalls can overrun it by at most one more ``timeout``). ``retries`` is
    the number of extra attempts for transient failures. ``cache`` (an
    ``HttpCache``) turns the request conditional; a 304 comes back as
    ``Response.not_modified``. ``max_bytes`` caps the body, compressed and
    decompressed. Follows 301/302/303/307/308 and gunzips transparently.

    ``headers`` are added to the defaults; passing a different User-Agent is
    a programming error (``ValueError``), because there is exactly one.
    """
    target = _prepare_url(url)
    if is_offline():
        raise NetError("offline", None, "offline: network disabled", target)
    conditional = cache.headers_for(target) if cache is not None else {}
    request_headers = _request_headers(headers, conditional)
    started = time.monotonic()
    failures, throttled = 0, False
    while True:
        try:
            response = _attempt(target, request_headers, timeout, max_bytes)
            break
        except NetError as err:
            delay = _retry_delay(err, failures, retries, throttled)
            if delay is None:
                raise
            failures += 1
            throttled = throttled or err.status == 429
            log.debug("retry %d for %s in %.1f s (%s)", failures, target, delay, err)
            time.sleep(delay)
    response.elapsed_ms = int((time.monotonic() - started) * 1000)
    if cache is not None:
        cache.record(target, response)
    log.debug("GET %s -> %d, %d bytes, %d ms", target, response.status, len(response.body),
              response.elapsed_ms)
    return response


def fetch_json(url, **kw):
    """Fetch and parse JSON. Returns None on a 304; raises NetError if the body is not JSON.

    Error pages and rate-limit notices often arrive as text with a 200, so a
    parse failure is reported as a failed fetch (kind 'http'), not a crash.
    """
    headers = {"Accept": "application/json, */*;q=0.8"}
    headers.update(kw.pop("headers", None) or {})
    response = fetch(url, headers=headers, **kw)
    if response.not_modified:
        return None
    try:
        return json.loads(response.text())
    except ValueError as err:
        raise NetError("http", response.status, "response is not valid JSON", response.url) from err


_polite_lock = threading.Lock()
_next_slot = {}


def polite(host, min_interval_s):
    """Space out requests to one host: block until ``min_interval_s`` after the previous call.

    Thread-safe: concurrent callers are queued one interval apart. Accepts a
    host name or a full URL. Does nothing offline, when no request will follow.
    """
    if is_offline() or min_interval_s <= 0:
        return
    text = str(host).strip().lower()
    key = (urllib.parse.urlsplit(text).hostname or text) if "//" in text else text
    with _polite_lock:
        now = time.monotonic()
        slot = max(now, _next_slot.get(key, 0.0))
        _next_slot[key] = slot + min_interval_s
    if slot > now:
        time.sleep(slot - now)
