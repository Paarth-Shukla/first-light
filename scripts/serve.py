#!/usr/bin/env python3
"""Serve the built site locally: ``python3 scripts/serve.py`` -> http://localhost:8080

Python's stock ``http.server`` is almost enough, but on Python 3.9 it serves
``.mjs``, ``.webmanifest`` and ``.woff2`` with types browsers reject for
modules, manifests and fonts, it lets the browser cache yesterday's data and
service worker, and it logs every request. This wrapper fixes those three
things and nothing else. It is a development and personal-use server; the
published site is plain static hosting.
"""

import argparse
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}


class Handler(SimpleHTTPRequestHandler):
    """Static file handler with correct types, revalidation on every load, and quiet logs."""

    extensions_map = dict(SimpleHTTPRequestHandler.extensions_map, **MIME_TYPES)
    server_version = "FirstLightServe"

    def end_headers(self):
        # "no-cache" means "revalidate before use", not "do not store": data/ and sw.js
        # must never be stale, and applying it to every file also stops the browser from
        # running an old script after a rebuild. Unchanged files still answer 304.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def list_directory(self, path):
        """Static hosts do not list directories, so neither does this."""
        self.send_error(404, "File not found")
        return None

    def log_request(self, code="-", size="-"):
        """Successful requests are not interesting; errors still go through log_error."""

    def log_message(self, format, *args):
        sys.stderr.write("serve: %s\n" % (format % args))


class Server(ThreadingHTTPServer):
    """Threaded so a slow request (or the service worker's parallel fetches) never blocks the page."""

    daemon_threads = True

    def handle_error(self, request, client_address):
        """A browser closing a connection early is normal; anything else is worth a traceback."""
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def make_server(directory, port=8080, host="127.0.0.1"):
    """Build (but do not start) a server for ``directory``; port 0 picks a free port."""
    return Server((host, port), partial(Handler, directory=str(directory)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serve the built First Light site.")
    parser.add_argument("--port", type=int, default=8080, help="port to listen on (default 8080)")
    parser.add_argument("--dir", default=str(ROOT / "dist"), help="directory to serve (default dist/)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="address to bind (default 127.0.0.1; use 0.0.0.0 to reach it from your phone)")
    args = parser.parse_args(argv)

    directory = Path(args.dir).expanduser().resolve()
    if not directory.is_dir():
        print("serve: %s does not exist. Build the site first: python3 -m pipeline build" % directory,
              file=sys.stderr)
        return 1
    if not (directory / "index.html").is_file():
        print("serve: warning: no index.html in %s" % directory, file=sys.stderr)
    try:
        server = make_server(directory, args.port, args.host)
    except OSError as err:
        print("serve: cannot listen on %s:%d (%s)" % (args.host, args.port, err.strerror or err),
              file=sys.stderr)
        return 1
    shown_host = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
    print("Serving %s at http://%s:%d/  (Ctrl-C to stop)" % (directory, shown_host, server.server_address[1]),
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nserve: stopped", file=sys.stderr)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
