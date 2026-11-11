"""scripts/serve.py: MIME types, cache headers and quiet behaviour of the local server."""

import contextlib
import http.client
import importlib.util
import io
import socket
import tempfile
import threading
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("firstlight_serve", REPO / "scripts" / "serve.py")
serve = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(serve)

FILES = {
    "index.html": b"<!doctype html><title>First Light</title>",
    "sw.js": b"self.addEventListener('fetch', () => {});",
    "manifest.webmanifest": b'{"name": "First Light"}',
    "js/app.js": b"import './core/router.mjs';",
    "js/core/router.mjs": b"export const routes = [];",
    "css/site.css": b"body { margin: 0 }",
    "fonts/text.woff2": b"wOF2\x00\x01",
    "img/mark.svg": b"<svg xmlns='http://www.w3.org/2000/svg'/>",
    "data/latest.json": b'{"stories": []}',
    "data/search/docs-2026-11.json": b"[]",
    "notes/readme.txt": b"plain",
    "img/photo.png": b"\x89PNG\r\n",
}


class ServeTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.root = Path(cls.folder.name) / "dist"
        for name, content in FILES.items():
            path = cls.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (Path(cls.folder.name) / "secret.txt").write_text("outside the served directory", encoding="utf-8")
        cls.server = serve.make_server(cls.root, port=0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.folder.cleanup()

    def get(self, path, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(connection.close)
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            connection.request("GET", path, headers=headers or {})
            response = connection.getresponse()
            body = response.read()
        self.server_log = stderr.getvalue()
        return response, body


class Serving(ServeTestCase):
    def test_mime_types(self):
        expected = {
            "/index.html": "text/html; charset=utf-8",
            "/sw.js": "text/javascript; charset=utf-8",
            "/js/app.js": "text/javascript; charset=utf-8",
            "/js/core/router.mjs": "text/javascript; charset=utf-8",
            "/data/latest.json": "application/json; charset=utf-8",
            "/manifest.webmanifest": "application/manifest+json; charset=utf-8",
            "/fonts/text.woff2": "font/woff2",
            "/img/mark.svg": "image/svg+xml",
            "/css/site.css": "text/css; charset=utf-8",
            "/notes/readme.txt": "text/plain; charset=utf-8",
            "/img/photo.png": "image/png",
        }
        for path, content_type in expected.items():
            response, body = self.get(path)
            self.assertEqual(response.status, 200, path)
            self.assertEqual(response.getheader("Content-Type"), content_type, path)
            self.assertEqual(body, FILES[path.lstrip("/")], path)

    def test_data_and_service_worker_are_never_served_stale(self):
        for path in ("/data/latest.json", "/data/search/docs-2026-11.json", "/sw.js", "/index.html", "/js/app.js"):
            response, _ = self.get(path)
            self.assertEqual(response.getheader("Cache-Control"), "no-cache", path)

    def test_root_serves_index(self):
        response, body = self.get("/")
        self.assertEqual(response.status, 200)
        self.assertEqual(body, FILES["index.html"])
        self.assertEqual(response.getheader("Content-Type"), "text/html; charset=utf-8")

    def test_query_strings_are_ignored(self):
        response, body = self.get("/data/latest.json?v=12345")
        self.assertEqual((response.status, body), (200, FILES["data/latest.json"]))

    def test_revalidation_answers_304(self):
        first, _ = self.get("/data/latest.json")
        stamp = first.getheader("Last-Modified")
        self.assertTrue(stamp)
        second, body = self.get("/data/latest.json", headers={"If-Modified-Since": stamp})
        self.assertEqual((second.status, body), (304, b""))

    def test_missing_file_is_404(self):
        response, _ = self.get("/data/nope.json")
        self.assertEqual(response.status, 404)

    def test_directories_are_not_listed(self):
        for path in ("/data/", "/js/", "/data"):
            response, body = self.get(path)
            self.assertIn(response.status, (301, 404), path)
            self.assertNotIn(b"latest.json", body, path)
        response, _ = self.get("/js/")
        self.assertEqual(response.status, 404)

    def test_cannot_escape_the_served_directory(self):
        for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/js/../../secret.txt", "//etc/hosts"):
            response, body = self.get(path)
            self.assertNotEqual(response.status, 200, path)
            self.assertNotIn(b"outside the served directory", body, path)

    def test_successful_requests_are_not_logged_but_errors_are(self):
        self.get("/index.html")
        self.assertEqual(self.server_log, "")
        self.get("/missing.html")
        self.assertIn("404", self.server_log)

    def test_handles_parallel_requests(self):
        results = []

        def worker():
            connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
            try:
                connection.request("GET", "/data/latest.json")
                results.append(connection.getresponse().status)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(results, [200] * 20)

    def test_a_client_that_hangs_up_does_not_print_a_traceback(self):
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            with socket.create_connection(("127.0.0.1", self.port), timeout=5) as raw:
                raw.sendall(b"GET /data/latest.json HTTP/1.1\r\nHost: x\r\n")
            response, _ = self.get("/index.html")
        self.assertEqual(response.status, 200)
        self.assertNotIn("Traceback", stderr.getvalue())


class Main(unittest.TestCase):
    def run_main(self, argv):
        with contextlib.redirect_stderr(io.StringIO()) as stderr, contextlib.redirect_stdout(io.StringIO()):
            code = serve.main(argv)
        return code, stderr.getvalue()

    def test_missing_directory_is_explained(self):
        with tempfile.TemporaryDirectory() as folder:
            code, err = self.run_main(["--dir", str(Path(folder) / "dist")])
        self.assertEqual(code, 1)
        self.assertIn("python3 -m pipeline build", err)

    def test_busy_port_is_explained(self):
        with tempfile.TemporaryDirectory() as folder, socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen(1)
            code, err = self.run_main(["--dir", folder, "--port", str(busy.getsockname()[1])])
        self.assertEqual(code, 1)
        self.assertIn("cannot listen", err)

    def test_defaults(self):
        self.assertEqual(serve.ROOT, REPO)
        server = serve.make_server(REPO, port=0)
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            self.assertTrue(server.daemon_threads)
        finally:
            server.server_close()


if __name__ == "__main__":
    unittest.main()
