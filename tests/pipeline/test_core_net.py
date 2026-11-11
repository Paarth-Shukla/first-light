"""pipeline.core.net against a local HTTP server (loopback only; never the real network)."""

import collections
import contextlib
import gzip
import http.client
import io
import json
import socket
import ssl
import tempfile
import threading
import time
import unittest
import urllib.error
from unittest import mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pipeline.core import net, timeutil

HELLO = b"hello, first light"
GZIPPED = gzip.compress(b"<rss>" + b"headline " * 200 + b"</rss>")
PLAIN = gzip.decompress(GZIPPED)
ETAG = '"v1"'
LAST_MODIFIED = "Wed, 11 Nov 2026 04:00:00 GMT"


class Handler(BaseHTTPRequestHandler):
    """One route per behaviour under test. ``server.hits`` counts requests per path."""

    def log_message(self, format, *args):
        pass

    def send_body(self, body, status=200, headers=(), length=True):
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        if length:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def hit(self):
        with self.server.lock:
            self.server.hits[self.path] += 1
            return self.server.hits[self.path]

    def do_GET(self):
        count = self.hit()
        parts = self.path.split("?")[0].strip("/").split("/")
        route = getattr(self, "route_" + parts[0].replace("-", "_"), None)
        if route is None:
            self.send_body(b"no such route", 404)
            return
        try:
            route(parts[1:], count)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the client gave up, which several tests do on purpose

    def route_hello(self, args, count):
        self.send_body(HELLO, headers=[("Content-Type", "text/plain; charset=utf-8")])

    def route_echo(self, args, count):
        body = json.dumps({"path": self.path, "headers": dict(self.headers.items())}).encode()
        self.send_body(body, headers=[("Content-Type", "application/json")])

    def route_gzip(self, args, count):
        self.send_body(GZIPPED, headers=[("Content-Encoding", "gzip")])

    def route_gzip_undeclared(self, args, count):
        self.send_body(GZIPPED)

    def route_gzip_two(self, args, count):
        self.send_body(gzip.compress(b"first,") + gzip.compress(b"second"),
                       headers=[("Content-Encoding", "gzip")])

    def route_gzip_truncated(self, args, count):
        self.send_body(GZIPPED[:len(GZIPPED) // 2], headers=[("Content-Encoding", "gzip")])

    def route_gzip_bad(self, args, count):
        self.send_body(b"\x1f\x8b" + b"definitely not deflate data", headers=[("Content-Encoding", "gzip")])

    def route_gzip_lookalike(self, args, count):
        self.send_body(b"\x1f\x8b" + b"definitely not deflate data")

    def route_gzip_bomb(self, args, count):
        self.send_body(gzip.compress(b"\0" * 5_000_000), headers=[("Content-Encoding", "gzip")])

    def route_gzip_claimed(self, args, count):
        self.send_body(b"plain text after all", headers=[("Content-Encoding", "gzip")])

    def route_redirect(self, args, count):
        self.send_body(b"", int(args[0]), headers=[("Location", "/hello")])

    def route_redirect_chain(self, args, count):
        self.send_body(b"", 301, headers=[("Location", "/redirect/308")])

    def route_redirect_loop(self, args, count):
        self.send_body(b"", 302, headers=[("Location", "/redirect-loop")])

    def route_redirect_file(self, args, count):
        self.send_body(b"", 302, headers=[("Location", "file:///etc/hosts")])

    def route_redirect_ftp(self, args, count):
        self.send_body(b"", 302, headers=[("Location", "ftp://127.0.0.1/pub/file")])

    def route_cached(self, args, count):
        if self.headers.get("If-None-Match") == ETAG:
            self.send_body(b"", 304, headers=[("ETag", ETAG)])
        else:
            self.send_body(HELLO, headers=[("ETag", ETAG), ("Last-Modified", LAST_MODIFIED)])

    def route_modified_only(self, args, count):
        if self.headers.get("If-Modified-Since") == LAST_MODIFIED:
            self.send_body(b"", 304)
        else:
            self.send_body(HELLO, headers=[("Last-Modified", LAST_MODIFIED)])

    def route_validators_once(self, args, count):
        headers = [("ETag", ETAG)] if count == 1 else []
        self.send_body(HELLO, headers=headers)

    def route_fail_then_ok(self, args, count):
        failures, status = int(args[1]), int(args[2])
        if count <= failures:
            self.send_body(b"try later", status)
        else:
            self.send_body(HELLO)

    def route_drop_then_ok(self, args, count):
        if count <= int(args[1]):
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)
        else:
            self.send_body(HELLO)

    def route_status(self, args, count):
        self.send_body(b"error page", int(args[0]))

    def route_big(self, args, count):
        self.send_body(b"x" * int(args[-1]))

    def route_big_stream(self, args, count):
        self.send_body(b"x" * int(args[-1]), length=False)

    def route_chunked(self, args, count):
        self.protocol_version = "HTTP/1.1"
        self.send_response(200)
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Connection", "close")
        self.end_headers()
        for piece in (b"alpha ", b"beta ", b"gamma"):
            self.wfile.write(b"%x\r\n%s\r\n" % (len(piece), piece))
        self.wfile.write(b"0\r\n\r\n")
        self.close_connection = True

    def route_short(self, args, count):
        self.send_response(200)
        self.send_header("Content-Length", "100")
        self.end_headers()
        self.wfile.write(b"only ten b")

    def route_slow_headers(self, args, count):
        time.sleep(float(args[-1]))
        self.send_body(HELLO)

    def route_drip(self, args, count):
        self.send_response(200)
        self.end_headers()
        for _ in range(100):
            self.wfile.write(b"x")
            self.wfile.flush()
            time.sleep(0.05)

    def route_json(self, args, count):
        self.send_body(b'{"ok": true, "items": [1, 2, 3]}', headers=[("Content-Type", "application/json")])

    def route_json_bom(self, args, count):
        self.send_body(b'\xef\xbb\xbf{"ok": true}')

    def route_not_json(self, args, count):
        self.send_body(b"Too Many Requests")

    def route_latin1(self, args, count):
        self.send_body("café".encode("latin-1"), headers=[("Content-Type", "text/plain; charset=ISO-8859-1")])

    def route_bogus_charset(self, args, count):
        self.send_body("café".encode("utf-8"), headers=[("Content-Type", "text/plain; charset=martian")])


class QuietServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass  # dropped connections are part of the tests


def setUpModule():
    """Start the server, bypass any system proxy, and shrink retry waits so tests are fast."""
    global SERVER, BASE, _saved
    SERVER = QuietServer(("127.0.0.1", 0), Handler)
    SERVER.hits = collections.Counter()
    SERVER.lock = threading.Lock()
    threading.Thread(target=SERVER.serve_forever, daemon=True).start()
    BASE = "http://127.0.0.1:%d" % SERVER.server_address[1]
    _saved = (net._opener, net._BACKOFF_S, net._RETRY_429_S)
    net._opener = net._build_opener(proxies={})
    net._BACKOFF_S = 0.01
    net._RETRY_429_S = 0.05


def tearDownModule():
    net._opener, net._BACKOFF_S, net._RETRY_429_S = _saved
    SERVER.shutdown()
    SERVER.server_close()


def hits(path):
    with SERVER.lock:
        return SERVER.hits[path]


def unique(prefix):
    """A path no other test uses, so hit counters start at zero."""
    unique.counter += 1
    return "%s/%d" % (prefix, unique.counter)


unique.counter = 0


class NetTestCase(unittest.TestCase):
    def setUp(self):
        net.set_offline(False)
        self.addCleanup(net.set_offline, False)

    def assertNetError(self, kind, path, status=None, **kw):
        with self.assertRaises(net.NetError) as caught:
            net.fetch(BASE + path if path.startswith("/") else path, **kw)
        self.assertEqual(caught.exception.kind, kind, repr(caught.exception))
        self.assertEqual(caught.exception.status, status, repr(caught.exception))
        return caught.exception


class FetchBasics(NetTestCase):
    def test_response_fields(self):
        response = net.fetch(BASE + "/hello")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, HELLO)
        self.assertEqual(response.url, BASE + "/hello")
        self.assertFalse(response.not_modified)
        self.assertIsInstance(response.elapsed_ms, int)
        self.assertGreaterEqual(response.elapsed_ms, 0)
        self.assertEqual(response.headers.get("content-type"), "text/plain; charset=utf-8")
        self.assertEqual(response.headers.get("Content-Type"), "text/plain; charset=utf-8")
        self.assertEqual(response.text(), HELLO.decode())

    def test_user_agent_is_the_contract_string(self):
        self.assertEqual(net.USER_AGENT, "Mozilla/5.0 (compatible; FirstLight/1.0; personal news digest)")

    def test_sends_honest_user_agent_and_accepts_gzip(self):
        sent = json.loads(net.fetch(BASE + "/echo").body)["headers"]
        self.assertEqual(sent["User-Agent"], net.USER_AGENT)
        self.assertEqual(sent["Accept-Encoding"], "gzip")
        self.assertEqual(sent["Accept"], "*/*")

    def test_caller_headers_are_merged_case_insensitively(self):
        sent = json.loads(net.fetch(BASE + "/echo", headers={"accept": "text/xml", "X-Test": "1"}).body)
        self.assertEqual(sent["headers"]["Accept"], "text/xml")
        self.assertEqual(sent["headers"]["X-Test"], "1")
        self.assertEqual(sent["headers"]["User-Agent"], net.USER_AGENT)

    def test_user_agent_cannot_be_overridden(self):
        for name in ("User-Agent", "user-agent", "USER-AGENT"):
            with self.assertRaises(ValueError):
                net.fetch(BASE + "/echo/ua-override", headers={name: "Mozilla/5.0 Chrome/130"})
        self.assertEqual(hits("/echo/ua-override"), 0)

    def test_restating_the_honest_user_agent_is_harmless(self):
        sent = json.loads(net.fetch(BASE + "/echo", headers={"user-agent": net.USER_AGENT}).body)
        self.assertEqual(sent["headers"]["User-Agent"], net.USER_AGENT)

    def test_url_is_trimmed_and_unsafe_characters_quoted(self):
        seen = json.loads(net.fetch("  " + BASE + "/echo/two words/ü?q=a b&s=^NSEI&k=%5E#frag \n").body)
        self.assertEqual(seen["path"], "/echo/two%20words/%C3%BC?q=a%20b&s=%5ENSEI&k=%5E")

    def test_non_http_urls_are_refused_without_touching_anything(self):
        for bad in ("file:///etc/hosts", "ftp://example.com/x", "example.com/feed", "", "http://", "data:text/plain,hi"):
            with self.assertRaises(net.NetError) as caught:
                net.fetch(bad)
            self.assertEqual(caught.exception.kind, "connection", bad)

    def test_chunked_response(self):
        self.assertEqual(net.fetch(BASE + "/chunked").body, b"alpha beta gamma")

    def test_text_uses_declared_charset(self):
        self.assertEqual(net.fetch(BASE + "/latin1").text(), "café")

    def test_text_falls_back_to_utf8_for_unknown_charset(self):
        self.assertEqual(net.fetch(BASE + "/bogus-charset").text(), "café")

    def test_text_strips_bom(self):
        self.assertEqual(net.fetch(BASE + "/json-bom").text(), '{"ok": true}')

    def test_response_text_works_with_plain_dict_headers(self):
        response = net.Response(status=200, body=b"caf\xe9", headers={"content-type": "text/plain; charset=latin-1"}, url="u")
        self.assertEqual(response.text(), "café")

    def test_error_string_is_short_and_has_no_url(self):
        err = self.assertNetError("http", "/status/403", status=403, retries=0)
        self.assertEqual(str(err), "HTTP 403 Forbidden")
        self.assertEqual(err.url, BASE + "/status/403")
        self.assertIn("403", repr(err))


class Gzip(NetTestCase):
    def test_declared_gzip_is_decompressed(self):
        self.assertEqual(net.fetch(BASE + "/gzip").body, PLAIN)

    def test_undeclared_gzip_is_detected_by_magic_bytes(self):
        self.assertEqual(net.fetch(BASE + "/gzip-undeclared").body, PLAIN)

    def test_multi_member_gzip(self):
        self.assertEqual(net.fetch(BASE + "/gzip-two").body, b"first,second")

    def test_truncated_gzip_is_a_retryable_connection_error(self):
        path = "/gzip-truncated"
        self.assertNetError("connection", path, retries=1)
        self.assertEqual(hits(path), 2)

    def test_corrupt_declared_gzip_is_an_error(self):
        err = self.assertNetError("connection", "/gzip-bad", retries=0)
        self.assertIn("gzip", str(err))

    def test_bytes_that_only_look_like_gzip_pass_through(self):
        self.assertEqual(net.fetch(BASE + "/gzip-lookalike").body, b"\x1f\x8b" + b"definitely not deflate data")

    def test_plain_body_with_a_false_gzip_header_passes_through(self):
        self.assertEqual(net.fetch(BASE + "/gzip-claimed").body, b"plain text after all")

    def test_gzip_bomb_is_stopped_at_max_bytes(self):
        err = self.assertNetError("too-large", "/gzip-bomb", max_bytes=1_000_000)
        self.assertIn("gunzip", str(err))

    def test_gzip_bomb_fits_when_allowed(self):
        self.assertEqual(len(net.fetch(BASE + "/gzip-bomb", max_bytes=5_000_000).body), 5_000_000)


class Redirects(NetTestCase):
    def test_follows_every_redirect_status(self):
        for code in (301, 302, 303, 307, 308):
            response = net.fetch(BASE + "/redirect/%d" % code)
            self.assertEqual((response.status, response.body), (200, HELLO), code)
            self.assertEqual(response.url, BASE + "/hello", code)

    def test_follows_a_chain_through_308(self):
        self.assertEqual(net.fetch(BASE + "/redirect-chain").url, BASE + "/hello")

    def test_redirect_loop_is_an_http_error_not_a_hang(self):
        started = time.monotonic()
        with self.assertRaises(net.NetError) as caught:
            net.fetch(BASE + "/redirect-loop", retries=0)
        self.assertEqual(caught.exception.kind, "http")
        self.assertEqual(caught.exception.status, 302)
        self.assertEqual(str(caught.exception), "HTTP 302 redirect not followed (loop, or no usable Location)")
        self.assertLess(time.monotonic() - started, 5)

    def test_redirect_to_file_or_ftp_is_refused(self):
        for path in ("/redirect-file", "/redirect-ftp"):
            with self.assertRaises(net.NetError):
                net.fetch(BASE + path, retries=0)


class Failures(NetTestCase):
    def test_4xx_is_never_retried(self):
        for status in (400, 403, 404, 410):
            path = unique("/status/%d" % status)
            self.assertNetError("http", path, status=status, retries=3)
            self.assertEqual(hits(path), 1, status)

    def test_5xx_is_retried_then_succeeds(self):
        path = unique("/fail-then-ok") + "/1/503"
        self.assertEqual(net.fetch(BASE + path, retries=1).body, HELLO)
        self.assertEqual(hits(path), 2)

    def test_5xx_gives_up_after_retries(self):
        path = unique("/fail-then-ok") + "/5/500"
        self.assertNetError("http", path, status=500, retries=2)
        self.assertEqual(hits(path), 3)

    def test_retries_zero_means_one_attempt(self):
        path = unique("/fail-then-ok") + "/1/502"
        self.assertNetError("http", path, status=502, retries=0)
        self.assertEqual(hits(path), 1)

    def test_429_gets_exactly_one_retry_after_a_pause(self):
        path = unique("/fail-then-ok") + "/1/429"
        started = time.monotonic()
        self.assertEqual(net.fetch(BASE + path, retries=1).body, HELLO)
        self.assertGreaterEqual(time.monotonic() - started, net._RETRY_429_S)
        self.assertEqual(hits(path), 2)

    def test_429_is_not_retried_twice_even_with_retries_left(self):
        path = unique("/status/429")
        self.assertNetError("http", path, status=429, retries=5)
        self.assertEqual(hits(path), 2)

    def test_429_is_not_retried_when_retries_is_zero(self):
        path = unique("/status/429")
        self.assertNetError("http", path, status=429, retries=0)
        self.assertEqual(hits(path), 1)

    def test_dropped_connection_is_retried(self):
        path = unique("/drop-then-ok") + "/1"
        self.assertEqual(net.fetch(BASE + path, retries=1).body, HELLO)
        self.assertEqual(hits(path), 2)

    def test_dropped_connection_reports_connection_kind(self):
        path = unique("/drop-then-ok") + "/9"
        self.assertNetError("connection", path, retries=1)
        self.assertEqual(hits(path), 2)

    def test_connection_refused(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        err = self.assertNetError("connection", "http://127.0.0.1:%d/" % port, retries=0)
        self.assertIn("refused", str(err).lower())

    def test_slow_headers_time_out_and_are_retried(self):
        path = unique("/slow-headers") + "/3"
        started = time.monotonic()
        err = self.assertNetError("timeout", path, timeout=0.3, retries=1)
        self.assertLess(time.monotonic() - started, 2.5)
        self.assertEqual(hits(path), 2)
        self.assertIn("timed out", str(err))

    def test_dripping_body_cannot_outlast_the_time_budget(self):
        started = time.monotonic()
        self.assertNetError("timeout", "/drip", timeout=0.4, retries=0)
        self.assertLess(time.monotonic() - started, 3)   # the server would drip for 5 s

    def test_declared_length_over_cap_fails_before_reading(self):
        self.assertNetError("too-large", "/big/50000", max_bytes=10_000)

    def test_streamed_body_over_cap(self):
        self.assertNetError("too-large", "/big-stream/300000", max_bytes=100_000)

    def test_too_large_is_not_retried(self):
        path = unique("/big") + "/50000"
        self.assertNetError("too-large", path, max_bytes=100, retries=3)
        self.assertEqual(hits(path), 1)

    def test_body_exactly_at_cap_is_fine(self):
        self.assertEqual(len(net.fetch(BASE + "/big/10000", max_bytes=10_000).body), 10_000)
        self.assertEqual(len(net.fetch(BASE + "/big-stream/10000", max_bytes=10_000).body), 10_000)

    def test_short_body_is_a_connection_error(self):
        err = self.assertNetError("connection", "/short", retries=0)
        self.assertIn("10 of 100", str(err))

    def test_tls_failure_has_kind_tls_and_is_not_retried(self):
        """An https:// URL answered in plain text: the handshake fails, and retrying cannot help."""
        connections = []
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(5)
        listener.settimeout(10)
        self.addCleanup(listener.close)

        def answer_in_plain_text():
            try:
                while True:
                    connection, _ = listener.accept()
                    connections.append(1)
                    with connection:
                        connection.settimeout(5)
                        connection.recv(65536)                       # the TLS ClientHello
                        connection.sendall(b"HTTP/1.0 400 Bad Request\r\n\r\nthis is not TLS\n")
                        connection.shutdown(socket.SHUT_WR)
                        connection.recv(65536)                       # wait for the client to hang up
            except OSError:
                return  # listener closed at the end of the test, or the client vanished

        threading.Thread(target=answer_in_plain_text, daemon=True).start()
        err = self.assertNetError("tls", "https://127.0.0.1:%d/feed" % listener.getsockname()[1],
                                  retries=3, timeout=10)
        self.assertTrue(str(err).startswith("TLS error"), str(err))
        self.assertEqual(len(connections), 1)

    def test_304_without_a_conditional_request_is_an_error(self):
        self.assertNetError("http", "/status/304", status=304, retries=0)


class Translate(unittest.TestCase):
    """Exception mapping for failures a loopback server cannot easily produce."""

    def kind(self, err):
        return net._translate(err, "https://example.com/", 20).kind

    def test_mapping(self):
        cases = [
            (urllib.error.URLError(socket.timeout("timed out")), "timeout"),
            (socket.timeout("The read operation timed out"), "timeout"),
            (TimeoutError("timed out"), "timeout"),
            (urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed")), "tls"),
            (ssl.SSLError(1, "[SSL: WRONG_VERSION_NUMBER] wrong version number"), "tls"),
            (urllib.error.URLError(socket.gaierror(8, "nodename nor servname provided")), "connection"),
            (urllib.error.URLError(ConnectionRefusedError(61, "Connection refused")), "connection"),
            (ConnectionResetError(54, "Connection reset by peer"), "connection"),
            (http.client.RemoteDisconnected("Remote end closed connection without response"), "connection"),
            (http.client.IncompleteRead(b"abc", 10), "connection"),
            (http.client.BadStatusLine("garbage"), "connection"),
            (urllib.error.URLError("unknown url type: ftp"), "connection"),
            (ValueError("bad host"), "connection"),
        ]
        for err, kind in cases:
            self.assertEqual(self.kind(err), kind, repr(err))

    def test_http_error_keeps_status(self):
        err = urllib.error.HTTPError("https://example.com/", 503, "Service Unavailable", {}, None)
        translated = net._translate(err, "https://example.com/", 20)
        self.assertEqual((translated.kind, translated.status), ("http", 503))
        self.assertEqual(str(translated), "HTTP 503 Service Unavailable")

    def test_http_messages_use_standard_phrases(self):
        self.assertEqual(net._http_message(404), "HTTP 404 Not Found")
        self.assertEqual(net._http_message(429), "HTTP 429 Too Many Requests")
        self.assertEqual(net._http_message(520), "HTTP 520")
        odd = urllib.error.HTTPError("https://example.com/", 403, "Blocked by\npolicy <b>x</b>", {}, None)
        self.assertEqual(str(net._translate(odd, "u", 20)), "HTTP 403 Forbidden")

    def test_messages_are_readable(self):
        timeout = net._translate(socket.timeout(), "u", 20)
        self.assertEqual(str(timeout), "timed out after 20 s")
        refused = net._translate(urllib.error.URLError(ConnectionRefusedError(61, "Connection refused")), "u", 20)
        self.assertEqual(str(refused), "connection failed: Connection refused")


class Offline(NetTestCase):
    def test_fetch_fails_fast_without_a_request(self):
        net.set_offline(True)
        self.assertTrue(net.is_offline())
        path = unique("/hello")
        started = time.monotonic()
        err = self.assertNetError("offline", path, timeout=30)
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(hits(path), 0)
        self.assertIn("offline", str(err))

    def test_fetch_json_is_offline_too(self):
        net.set_offline(True)
        with self.assertRaises(net.NetError) as caught:
            net.fetch_json(BASE + "/json")
        self.assertEqual(caught.exception.kind, "offline")

    def test_switching_back_on(self):
        net.set_offline(True)
        net.set_offline(False)
        self.assertEqual(net.fetch(BASE + "/hello").status, 200)


class FetchJson(NetTestCase):
    def test_parses_json(self):
        self.assertEqual(net.fetch_json(BASE + "/json"), {"ok": True, "items": [1, 2, 3]})

    def test_parses_json_with_bom(self):
        self.assertEqual(net.fetch_json(BASE + "/json-bom"), {"ok": True})

    def test_asks_for_json_but_caller_can_override(self):
        self.assertIn("application/json", net.fetch_json(BASE + "/echo")["headers"]["Accept"])
        self.assertEqual(net.fetch_json(BASE + "/echo", headers={"accept": "text/plain"})["headers"]["Accept"],
                         "text/plain")

    def test_text_body_is_a_net_error_not_a_crash(self):
        with self.assertRaises(net.NetError) as caught:
            net.fetch_json(BASE + "/not-json")
        self.assertEqual((caught.exception.kind, caught.exception.status), ("http", 200))
        self.assertIn("JSON", str(caught.exception))

    def test_passes_fetch_options_through(self):
        with self.assertRaises(net.NetError) as caught:
            net.fetch_json(BASE + "/big/5000", max_bytes=100)
        self.assertEqual(caught.exception.kind, "too-large")

    def test_not_modified_returns_none(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = net.HttpCache(Path(folder) / "http-cache.json")
            self.assertIsNotNone(net.fetch(BASE + "/cached", cache=cache))
            self.assertIsNone(net.fetch_json(BASE + "/cached", cache=cache))


class Cache(NetTestCase):
    def setUp(self):
        super().setUp()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "state" / "http-cache.json"
        self.addCleanup(timeutil.set_now, None)

    def test_second_fetch_is_conditional_and_not_modified(self):
        cache = net.HttpCache(self.path)
        first = net.fetch(BASE + "/cached", cache=cache)
        self.assertEqual((first.status, first.body, first.not_modified), (200, HELLO, False))
        second = net.fetch(BASE + "/cached", cache=cache)
        self.assertEqual((second.status, second.body, second.not_modified), (304, b"", True))
        self.assertEqual(second.url, BASE + "/cached")

    def test_last_modified_alone_works(self):
        cache = net.HttpCache(self.path)
        net.fetch(BASE + "/modified-only", cache=cache)
        self.assertTrue(net.fetch(BASE + "/modified-only", cache=cache).not_modified)

    def test_sends_both_validators(self):
        cache = net.HttpCache(self.path)
        net.fetch(BASE + "/cached", cache=cache)
        self.assertEqual(cache.headers_for(BASE + "/cached"),
                         {"If-None-Match": ETAG, "If-Modified-Since": LAST_MODIFIED})

    def test_without_cache_requests_are_unconditional(self):
        self.assertEqual(net.fetch(BASE + "/cached").status, 200)
        self.assertEqual(net.fetch(BASE + "/cached").status, 200)

    def test_nothing_is_persisted_until_save(self):
        cache = net.HttpCache(self.path)
        net.fetch(BASE + "/cached", cache=cache)
        self.assertFalse(self.path.exists())
        self.assertTrue(cache.save())
        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(list(stored), [BASE + "/cached"])
        entry = stored[BASE + "/cached"]
        self.assertEqual((entry["etag"], entry["lastModified"]), (ETAG, LAST_MODIFIED))
        self.assertRegex(entry["at"], r"^\d{4}-\d{2}-\d{2}$")

    def test_saved_cache_is_used_by_a_new_instance(self):
        cache = net.HttpCache(self.path)
        net.fetch(BASE + "/cached", cache=cache)
        cache.save()
        self.assertTrue(net.fetch(BASE + "/cached", cache=net.HttpCache(self.path)).not_modified)

    def test_forget_forces_a_full_download(self):
        cache = net.HttpCache(self.path)
        net.fetch(BASE + "/cached", cache=cache)
        cache.forget("  " + BASE + "/cached#fragment")
        self.assertEqual(net.fetch(BASE + "/cached", cache=cache).status, 200)

    def test_cache_methods_accept_any_spelling_of_the_url(self):
        cache = net.HttpCache(self.path)
        net.fetch(BASE + "/cached?q=a b", cache=cache)
        self.assertEqual(cache.headers_for("  " + BASE + "/cached?q=a b#x ")["If-None-Match"], ETAG)
        self.assertEqual(cache.headers_for(BASE + "/cached?q=a%20b")["If-None-Match"], ETAG)
        cache.forget("not a url")
        self.assertEqual(cache.headers_for("not a url"), {})

    def test_entry_is_dropped_when_the_server_stops_sending_validators(self):
        cache = net.HttpCache(self.path)
        url = BASE + unique("/validators-once")
        net.fetch(url, cache=cache)
        self.assertEqual(cache.headers_for(url), {"If-None-Match": ETAG})
        net.fetch(url, cache=cache)
        self.assertEqual(cache.headers_for(url), {})

    def test_unused_entries_are_pruned_after_thirty_days(self):
        timeutil.set_now("2026-10-01T00:00:00Z")
        cache = net.HttpCache(self.path)
        net.fetch(BASE + "/cached", cache=cache)
        timeutil.set_now("2026-10-20T00:00:00Z")
        net.fetch(BASE + "/modified-only", cache=cache)
        cache.save()
        timeutil.set_now("2026-11-11T00:00:00Z")
        reloaded = net.HttpCache(self.path)
        reloaded.save()
        self.assertEqual(list(json.loads(self.path.read_text(encoding="utf-8"))), [BASE + "/modified-only"])

    def test_a_304_keeps_the_entry_alive(self):
        timeutil.set_now("2026-10-01T00:00:00Z")
        cache = net.HttpCache(self.path)
        net.fetch(BASE + "/cached", cache=cache)
        timeutil.set_now("2026-11-10T00:00:00Z")
        net.fetch(BASE + "/cached", cache=cache)
        cache.save()
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))[BASE + "/cached"]["at"], "2026-11-10")

    def test_corrupt_cache_file_starts_empty(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            cache = net.HttpCache(self.path)
        self.assertIn("corrupt", stderr.getvalue())
        self.assertEqual(net.fetch(BASE + "/cached", cache=cache).status, 200)

    def test_wrong_shape_cache_file_starts_empty(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('["a list"]', encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            cache = net.HttpCache(self.path)
        self.assertEqual(cache.headers_for(BASE + "/cached"), {})

    def test_save_failure_is_reported_not_raised(self):
        blocker = self.path.parent
        blocker.parent.mkdir(parents=True, exist_ok=True)
        blocker.write_text("a file where the directory should be", encoding="utf-8")
        cache = net.HttpCache(self.path)
        net.fetch(BASE + "/cached", cache=cache)
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertFalse(cache.save())
        self.assertIn("could not save HTTP cache", stderr.getvalue())

    def test_failed_fetch_leaves_the_cache_alone(self):
        cache = net.HttpCache(self.path)
        with self.assertRaises(net.NetError):
            net.fetch(BASE + "/status/500", cache=cache, retries=0)
        self.assertTrue(cache.save())
        self.assertFalse(self.path.exists())

    def test_concurrent_fetches_share_one_cache(self):
        cache = net.HttpCache(self.path)
        errors = []

        def worker(index):
            try:
                for _ in range(5):
                    net.fetch(BASE + "/cached?n=%d" % index, cache=cache)
                    cache.save()
            except Exception as err:  # collected and asserted below
                errors.append(err)

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(len(stored), 8)


class FakeClock:
    """Stands in for the ``time`` module inside net: sleeping just moves the clock."""

    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(round(seconds, 6))
        self.now += seconds


class Polite(NetTestCase):
    def setUp(self):
        super().setUp()
        net._next_slot.clear()
        self.addCleanup(net._next_slot.clear)
        self.clock = FakeClock()
        patcher = mock.patch.object(net, "time", self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_first_call_does_not_wait(self):
        net.polite("first.example", 5)
        self.assertEqual(self.clock.sleeps, [])

    def test_calls_in_a_row_are_spaced_one_interval_apart(self):
        for _ in range(4):
            net.polite("export.arxiv.org", 3.2)
        self.assertEqual(self.clock.sleeps, [3.2, 3.2, 3.2])

    def test_only_the_remaining_time_is_waited(self):
        net.polite("partial.example", 3.0)
        self.clock.now += 2.0
        net.polite("partial.example", 3.0)
        self.assertEqual(self.clock.sleeps, [1.0])

    def test_no_wait_once_the_interval_has_passed(self):
        net.polite("idle.example", 3.0)
        self.clock.now += 10.0
        net.polite("idle.example", 3.0)
        self.assertEqual(self.clock.sleeps, [])

    def test_hosts_are_independent(self):
        net.polite("a.example", 5)
        net.polite("b.example", 5)
        self.assertEqual(self.clock.sleeps, [])

    def test_url_and_host_name_share_a_slot(self):
        net.polite("https://Export.ArXiv.org/api/query?x=1", 3.0)
        net.polite("export.arxiv.org", 3.0)
        net.polite("  EXPORT.arxiv.org ", 3.0)
        self.assertEqual(self.clock.sleeps, [3.0, 3.0])

    def test_zero_or_negative_interval_never_waits(self):
        for _ in range(10):
            net.polite("zero.example", 0)
            net.polite("zero.example", -1)
        self.assertEqual(self.clock.sleeps, [])

    def test_offline_never_waits(self):
        net.set_offline(True)
        net.polite("offline.example", 5)
        net.polite("offline.example", 5)
        self.assertEqual(self.clock.sleeps, [])


class PoliteThreads(NetTestCase):
    """Real clock: sleeps never return early, so only lower bounds are asserted."""

    def test_threads_are_queued_one_interval_apart(self):
        net._next_slot.clear()
        stamps = []

        def worker():
            net.polite("queue.example", 0.1)
            stamps.append(time.monotonic())

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        stamps.sort()
        gaps = [later - earlier for earlier, later in zip(stamps, stamps[1:])]
        self.assertEqual(len(stamps), 5)
        self.assertTrue(all(gap >= 0.08 for gap in gaps), gaps)
        self.assertGreaterEqual(stamps[-1] - stamps[0], 0.38)


class Concurrency(NetTestCase):
    def test_many_threads_can_fetch_at_once(self):
        results, errors = [], []

        def worker(index):
            try:
                path = ("/gzip", "/hello", "/redirect/308", "/chunked")[index % 4]
                results.append(net.fetch(BASE + path).status)
            except Exception as err:  # collected and asserted below
                errors.append(repr(err))

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(24)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(results, [200] * 24)


if __name__ == "__main__":
    unittest.main()
