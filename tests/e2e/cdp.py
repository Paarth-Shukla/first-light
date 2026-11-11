"""A WebSocket client and a Chrome DevTools Protocol session, standard library only.

There is no Node and no Playwright in this project, so the browser tests talk to
Chrome directly. This module is the transport: `WebSocket` implements the client
side of RFC 6455 over a plain socket, and `CDPSession` layers request/response
matching and an event queue on top of it. `browser.py` builds the page API on
`CDPSession`; nothing here knows about pages.
"""

import base64
import hashlib
import json
import os
import socket
import struct
import threading
import time
import traceback
from urllib.parse import urlsplit

_HANDSHAKE_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_MAX_HANDSHAKE_BYTES = 16 * 1024
# A full-page screenshot arrives as one base64 message of a few megabytes. Anything
# near this limit is a corrupted length field, not a real message.
MAX_MESSAGE_BYTES = 512 * 1024 * 1024

OP_CONTINUATION = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA

CLOSE_NORMAL = 1000
CLOSE_PROTOCOL_ERROR = 1002
CLOSE_NO_STATUS = 1005
CLOSE_ABNORMAL = 1006
CLOSE_BAD_DATA = 1007
CLOSE_TOO_BIG = 1009


class WebSocketError(Exception):
    """Base class for every failure of the WebSocket transport."""


class HandshakeError(WebSocketError):
    """The server did not complete a valid HTTP upgrade to WebSocket."""


class ProtocolError(WebSocketError):
    """The peer sent bytes that RFC 6455 forbids; the connection is torn down."""


class ConnectionClosed(WebSocketError):
    """The connection ended. `code` is the close status (1006 if the socket just dropped)."""

    def __init__(self, code, reason):
        super().__init__("WebSocket closed ({0}){1}".format(code, ": " + reason if reason else ""))
        self.code = code
        self.reason = reason


def accept_key(key):
    """Return the Sec-WebSocket-Accept value a compliant server must send for `key`."""
    digest = hashlib.sha1((key + _HANDSHAKE_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def mask_payload(payload, key):
    """XOR `payload` with the repeating 4-byte `key` (RFC 6455 section 5.3).

    Done on big integers because a byte-by-byte loop in Python is far too slow for
    the occasional large message.
    """
    size = len(payload)
    if size == 0:
        return b""
    stream = (key * (size // 4 + 1))[:size]
    masked = int.from_bytes(payload, "big") ^ int.from_bytes(stream, "big")
    return masked.to_bytes(size, "big")


def encode_frame(opcode, payload, mask_key):
    """Build one final (FIN=1) client frame: masked, with the shortest legal length form."""
    size = len(payload)
    head = bytearray([0x80 | opcode])
    if size < 126:
        head.append(0x80 | size)
    elif size < 0x10000:
        head.append(0x80 | 126)
        head += struct.pack("!H", size)
    else:
        head.append(0x80 | 127)
        head += struct.pack("!Q", size)
    return bytes(head) + mask_key + mask_payload(payload, mask_key)


class WebSocket:
    """A blocking RFC 6455 client for `ws://` URLs.

    One thread may call `recv()` while other threads call `send_text()` and
    `close()`; writes are serialised by a lock. `recv()` answers pings and
    completes the closing handshake itself, so a caller only ever sees whole
    data messages or `ConnectionClosed`.
    """

    def __init__(self, url, timeout=10.0):
        parts = urlsplit(url)
        if parts.scheme != "ws":
            raise WebSocketError("only ws:// URLs are supported, got {0!r}".format(url))
        self.url = url
        self._send_lock = threading.Lock()
        self._close_sent = False
        self._buffer = b""
        port = parts.port or 80
        try:
            self._sock = socket.create_connection((parts.hostname, port), timeout=timeout)
        except OSError as exc:
            raise WebSocketError("cannot connect to {0}: {1}".format(url, exc)) from exc
        try:
            # DevTools traffic is many tiny request/response pairs; Nagle's algorithm
            # would add tens of milliseconds to each one.
            self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._handshake(parts, port)
            self._sock.settimeout(None)
        except Exception:
            self.abort()
            raise

    # -- opening handshake -------------------------------------------------

    def _handshake(self, parts, port):
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        request = (
            "GET {path} HTTP/1.1\r\n"
            "Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ).format(path=path, host=parts.hostname, port=port, key=key)
        try:
            self._sock.sendall(request.encode("ascii"))
            status_line, headers = self._read_http_response()
        except OSError as exc:
            raise HandshakeError("handshake with {0} failed: {1}".format(self.url, exc)) from exc
        self._check_upgrade(status_line, headers, key)

    def _read_http_response(self):
        """Read the HTTP response head; bytes after it stay in the buffer as frame data."""
        data = b""
        while b"\r\n\r\n" not in data:
            if len(data) > _MAX_HANDSHAKE_BYTES:
                raise HandshakeError("handshake response headers exceed 16 KiB")
            chunk = self._sock.recv(4096)
            if not chunk:
                raise HandshakeError(
                    "server closed the connection during the handshake: {0!r}".format(data[:200])
                )
            data += chunk
        head, _, self._buffer = data.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        headers = {}
        for line in lines[1:]:
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
        return lines[0], headers

    def _check_upgrade(self, status_line, headers, key):
        fields = status_line.split(" ", 2)
        if len(fields) < 2 or fields[1] != "101":
            raise HandshakeError("expected HTTP 101, server answered {0!r}".format(status_line))
        if headers.get("upgrade", "").lower() != "websocket":
            raise HandshakeError("missing 'Upgrade: websocket' in the handshake response")
        connection = [token.strip().lower() for token in headers.get("connection", "").split(",")]
        if "upgrade" not in connection:
            raise HandshakeError("missing 'Connection: Upgrade' in the handshake response")
        if headers.get("sec-websocket-accept") != accept_key(key):
            raise HandshakeError(
                "Sec-WebSocket-Accept does not match the key we sent; "
                "the peer is not a WebSocket server"
            )
        if headers.get("sec-websocket-extensions") or headers.get("sec-websocket-protocol"):
            raise HandshakeError("server selected an extension or subprotocol we never offered")

    # -- sending -----------------------------------------------------------

    def send_text(self, text):
        """Send one text message."""
        self._send_frame(OP_TEXT, text.encode("utf-8"))

    def _send_frame(self, opcode, payload):
        frame = encode_frame(opcode, payload, os.urandom(4))
        with self._send_lock:
            try:
                self._sock.sendall(frame)
            except OSError as exc:
                raise ConnectionClosed(CLOSE_ABNORMAL, "send failed: {0}".format(exc)) from exc

    def _send_close(self, code, reason=""):
        """Send our Close frame once; later calls are no-ops because only one is allowed."""
        with self._send_lock:
            if self._close_sent:
                return
            self._close_sent = True
            payload = struct.pack("!H", code) + reason.encode("utf-8")[:123]
            try:
                self._sock.sendall(encode_frame(OP_CLOSE, payload, os.urandom(4)))
            except OSError:
                # The peer is already gone; there is nobody left to tell.
                pass

    # -- receiving ---------------------------------------------------------

    def recv(self):
        """Return the next data message: `str` for text, `bytes` for binary.

        Control frames are handled here: pings are answered, pongs ignored, and a
        Close frame is echoed and raised as `ConnectionClosed`.
        """
        fragments = []
        kind = None
        size = 0
        while True:
            final, opcode, payload = self._read_frame()
            if opcode == OP_PING:
                self._send_frame(OP_PONG, payload)
                continue
            if opcode == OP_PONG:
                continue
            if opcode == OP_CLOSE:
                self._peer_closed(payload)
            if opcode == OP_CONTINUATION:
                if kind is None:
                    self._fail(CLOSE_PROTOCOL_ERROR, "continuation frame with no message to continue")
            elif opcode in (OP_TEXT, OP_BINARY):
                if kind is not None:
                    self._fail(CLOSE_PROTOCOL_ERROR, "new data frame before the previous message ended")
                kind = opcode
            else:
                self._fail(CLOSE_PROTOCOL_ERROR, "unknown opcode 0x{0:x}".format(opcode))
            fragments.append(payload)
            size += len(payload)
            if size > MAX_MESSAGE_BYTES:
                self._fail(CLOSE_TOO_BIG, "message larger than {0} bytes".format(MAX_MESSAGE_BYTES))
            if final:
                break
        data = b"".join(fragments)
        if kind == OP_BINARY:
            return data
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            self._fail(CLOSE_BAD_DATA, "text message is not valid UTF-8")

    def _read_frame(self):
        head = self._read_exact(2)
        final = bool(head[0] & 0x80)
        opcode = head[0] & 0x0F
        size = head[1] & 0x7F
        if head[0] & 0x70:
            self._fail(CLOSE_PROTOCOL_ERROR, "reserved bits set but no extension was negotiated")
        if head[1] & 0x80:
            self._fail(CLOSE_PROTOCOL_ERROR, "server frames must not be masked")
        if size == 126:
            size = struct.unpack("!H", self._read_exact(2))[0]
        elif size == 127:
            size = struct.unpack("!Q", self._read_exact(8))[0]
        if opcode >= OP_CLOSE and (not final or size > 125):
            self._fail(CLOSE_PROTOCOL_ERROR, "control frames must be final and at most 125 bytes")
        if size > MAX_MESSAGE_BYTES:
            self._fail(CLOSE_TOO_BIG, "frame of {0} bytes is over the limit".format(size))
        return final, opcode, self._read_exact(size)

    def _read_exact(self, size):
        """Return exactly `size` bytes, or raise `ConnectionClosed` if the socket ends first."""
        chunks = []
        remaining = size
        if self._buffer:
            chunks.append(self._buffer[:remaining])
            self._buffer = self._buffer[remaining:]
            remaining -= len(chunks[0])
        while remaining:
            try:
                chunk = self._sock.recv(min(remaining, 1 << 20))
            except OSError as exc:
                raise ConnectionClosed(CLOSE_ABNORMAL, "socket error: {0}".format(exc)) from exc
            if not chunk:
                raise ConnectionClosed(CLOSE_ABNORMAL, "connection dropped without a close frame")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _peer_closed(self, payload):
        """Finish the closing handshake the peer started (or answered) and raise."""
        if len(payload) == 1:
            self._fail(CLOSE_PROTOCOL_ERROR, "close frame with a one-byte body")
        code = struct.unpack("!H", payload[:2])[0] if payload else CLOSE_NO_STATUS
        reason = payload[2:].decode("utf-8", "replace")
        self._send_close(code if payload else CLOSE_NORMAL)
        self.abort()
        raise ConnectionClosed(code, reason)

    def _fail(self, code, message):
        """Tell the peer why, hang up, and raise `ProtocolError`."""
        self._send_close(code, message)
        self._hang_up()
        raise ProtocolError(message)

    def _hang_up(self):
        """Close without resetting the connection.

        Closing a socket that still has unread input makes TCP send a reset, which
        can destroy the Close frame just sent before the peer reads it. So: stop
        sending, discard what the peer still has to say (briefly), then close.
        """
        deadline = time.monotonic() + 1.0
        try:
            self._sock.shutdown(socket.SHUT_WR)
            self._sock.settimeout(0.2)
            while time.monotonic() < deadline and self._sock.recv(65536):
                pass
        except OSError:
            # Timed out or already disconnected: there is nothing left to wait for.
            pass
        self._sock.close()

    # -- closing -----------------------------------------------------------

    def close(self, code=CLOSE_NORMAL, reason=""):
        """Start the closing handshake.

        The peer's answering Close frame is consumed by whoever calls `recv()`,
        which then raises `ConnectionClosed`. Call `abort()` afterwards to release
        the socket if nobody is reading.
        """
        self._send_close(code, reason)

    def abort(self):
        """Drop the TCP connection now. Safe to call more than once and from any thread."""
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            # Already disconnected: shutdown has nothing to do.
            pass
        self._sock.close()


class CDPError(Exception):
    """Chrome answered a command with an error, or the command could not complete."""

    def __init__(self, method, message, code=None, data=None):
        text = "{0}: {1}".format(method, message)
        if code is not None:
            text += " (code {0})".format(code)
        if data:
            text += " [{0}]".format(data)
        super().__init__(text)
        self.method = method
        self.message = message
        self.code = code
        self.data = data


class CDPTimeout(CDPError):
    """No reply (or no matching event) arrived in time."""


class CDPClosed(CDPError):
    """The DevTools connection ended while it was still needed."""


class CDPSession:
    """One DevTools connection: commands with matched replies, plus an event queue.

    A single daemon thread reads the socket. Replies wake the caller blocked in
    `send()`; events are first handed to listeners registered with `on()` (on the
    reader thread, so they must be quick and must use `post()` rather than
    `send()`), then queued for `wait_for_event()`.
    """

    # Old events are dropped past this point so a chatty page cannot grow the queue
    # without bound; tests only ever wait for recent events.
    EVENT_BACKLOG = 20000

    def __init__(self, ws_url, timeout=30.0):
        self.timeout = timeout
        self.background_errors = []
        self._ws = WebSocket(ws_url)
        self._state = threading.Condition()
        self._next_id = 0
        self._replies = {}
        self._background_ids = {}
        self._abandoned_ids = set()
        self._events = []
        self._events_trimmed = 0
        self._listeners = {}
        self._closed_reason = None
        self._reader = threading.Thread(target=self._read_loop, name="cdp-reader", daemon=True)
        self._reader.start()

    # -- commands ----------------------------------------------------------

    def send(self, method, params=None, timeout=None):
        """Run a command and return its `result` object.

        Raises `CDPError` carrying Chrome's own message when the command fails,
        `CDPTimeout` when no reply arrives, `CDPClosed` when the connection is gone.
        """
        timeout = self.timeout if timeout is None else timeout
        message_id = self._write(method, params, background=False)
        deadline = time.monotonic() + timeout
        with self._state:
            while message_id not in self._replies:
                if self._closed_reason is not None:
                    raise CDPClosed(method, "connection closed: " + self._closed_reason)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._abandoned_ids.add(message_id)
                    raise CDPTimeout(method, "no reply within {0:g}s".format(timeout))
                self._state.wait(remaining)
            reply = self._replies.pop(message_id)
        if "error" in reply:
            error = reply["error"]
            raise CDPError(method, error.get("message", "unknown error"), error.get("code"), error.get("data"))
        return reply.get("result", {})

    def post(self, method, params=None):
        """Send a command without waiting for the reply.

        This is the only way to issue a command from an event listener, because the
        reader thread cannot wait for itself. A failed reply is appended to
        `background_errors` so it is still reported.
        """
        self._write(method, params, background=True)

    def _write(self, method, params, background):
        with self._state:
            if self._closed_reason is not None:
                raise CDPClosed(method, "connection closed: " + self._closed_reason)
            self._next_id += 1
            message_id = self._next_id
            if background:
                self._background_ids[message_id] = method
        payload = json.dumps({"id": message_id, "method": method, "params": params or {}})
        try:
            self._ws.send_text(payload)
        except WebSocketError as exc:
            raise CDPClosed(method, str(exc)) from exc
        return message_id

    # -- events ------------------------------------------------------------

    def on(self, event, listener):
        """Call `listener(params)` on the reader thread for every `event`."""
        with self._state:
            self._listeners.setdefault(event, []).append(listener)

    def wait_for_event(self, name, predicate=None, timeout=10.0):
        """Return the params of the first queued or future `name` event that matches.

        The matched event is removed from the queue; other events stay. `predicate`
        runs under the session lock, so it must only inspect its argument.
        """
        deadline = time.monotonic() + timeout
        with self._state:
            # Absolute position of the next unscanned event. It survives backlog
            # trimming, which shifts list indexes while this thread sleeps.
            position = self._events_trimmed
            while True:
                for index in range(max(0, position - self._events_trimmed), len(self._events)):
                    entry = self._events[index]
                    if entry is None or entry[0] != name:
                        continue
                    if predicate is None or predicate(entry[1]):
                        self._events[index] = None
                        return entry[1]
                position = self._events_trimmed + len(self._events)
                if self._closed_reason is not None:
                    raise CDPClosed(name, "connection closed while waiting for the event: " + self._closed_reason)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise CDPTimeout(name, "no matching event within {0:g}s".format(timeout))
                self._state.wait(remaining)

    def forget_events(self, name):
        """Discard queued `name` events, so a later wait only sees new ones."""
        with self._state:
            for index, entry in enumerate(self._events):
                if entry is not None and entry[0] == name:
                    self._events[index] = None

    # -- reader thread -----------------------------------------------------

    def _read_loop(self):
        try:
            while True:
                self._dispatch(json.loads(self._ws.recv()))
        except ConnectionClosed as exc:
            reason = str(exc)
        except Exception:
            # A malformed message or a listener bug: stop reading and make every
            # later call fail with the traceback instead of hanging.
            reason = "reader thread failed:\n" + traceback.format_exc()
            self._ws.abort()
        with self._state:
            self._closed_reason = reason
            self._state.notify_all()

    def _dispatch(self, message):
        if "id" in message:
            self._handle_reply(message)
            return
        name = message.get("method")
        params = message.get("params", {})
        with self._state:
            listeners = list(self._listeners.get(name, ()))
        for listener in listeners:
            listener(params)
        with self._state:
            self._events.append((name, params))
            if len(self._events) > self.EVENT_BACKLOG:
                dropped = self.EVENT_BACKLOG // 2
                del self._events[:dropped]
                self._events_trimmed += dropped
            self._state.notify_all()

    def _handle_reply(self, message):
        with self._state:
            if message["id"] in self._abandoned_ids:
                # The caller already gave up on this command and was told so.
                self._abandoned_ids.discard(message["id"])
                return
            method = self._background_ids.pop(message["id"], None)
            if method is None:
                self._replies[message["id"]] = message
                self._state.notify_all()
            elif "error" in message:
                self.background_errors.append(
                    "{0}: {1}".format(method, message["error"].get("message", "unknown error"))
                )

    # -- shutdown ----------------------------------------------------------

    @property
    def closed(self):
        """True once the connection has ended, for whatever reason."""
        return self._closed_reason is not None

    def close(self):
        """Close the connection and stop the reader thread."""
        self._ws.close()
        self._reader.join(2.0)
        # If Chrome never answered the Close frame the reader is still blocked in
        # recv(); dropping the socket unblocks it.
        self._ws.abort()
        self._reader.join(2.0)
