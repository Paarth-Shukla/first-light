#!/usr/bin/env python3
"""Take a screenshot of a page in headless Chrome.

    python3 scripts/shot.py <url or path> <out.png> [--width 1440] [--height 900]
        [--full] [--dark] [--mobile] [--wait-for SELECTOR] [--delay MS] [--eval JS]

A local path is served through a temporary static server, because ES modules
and fetch() do not work from file:// URLs. A path may carry a route:
`dist/index.html#/wire`. Pages are served from the current directory when the
file is inside it (so `../` references keep working), otherwise from the file's
own directory; `--root` overrides that.

Anything the page logged as an error, and any request that failed, is listed on
stderr: a screenshot of a broken page should say that it is broken.
"""

import argparse
import os
import signal
import struct
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests.e2e.browser import Browser, BrowserError, JSError, LoadTimeout  # noqa: E402
from tests.e2e.cdp import CDPError  # noqa: E402
from tests.e2e.run import StaticServer, page_problems  # noqa: E402

DESKTOP = (1440, 900, 1)
PHONE = (390, 844, 2)


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description="Screenshot a URL or a local page in headless Chrome.")
    parser.add_argument("target", help="http(s) URL, or a local file or directory, optionally with #route")
    parser.add_argument("output", help="PNG file to write")
    parser.add_argument("--width", type=int, help="viewport width in CSS pixels (default 1440, or 390 with --mobile)")
    parser.add_argument("--height", type=int, help="viewport height in CSS pixels (default 900, or 844 with --mobile)")
    parser.add_argument("--scale", type=float, help="device pixel ratio (default 1, or 2 with --mobile)")
    parser.add_argument("--full", action="store_true", help="capture the whole scrollable page")
    parser.add_argument("--dark", action="store_true", help="emulate prefers-color-scheme: dark")
    parser.add_argument("--mobile", action="store_true", help="emulate a phone: narrow viewport, touch, 2x pixels")
    parser.add_argument("--wait-for", metavar="SELECTOR", help="wait until this element is visible")
    parser.add_argument("--delay", type=int, default=0, metavar="MS", help="extra wait before the capture")
    parser.add_argument("--eval", metavar="JS", help="run this in the page before the capture; its value is printed")
    parser.add_argument("--root", help="directory to serve for a local target")
    parser.add_argument("--timeout", type=float, default=20.0, help="seconds to wait for load and --wait-for")
    return parser.parse_args(argv)


def is_url(target):
    return target.startswith(("http://", "https://"))


def split_route(target):
    """Split `dist/index.html#/wire` into the path on disk and the `#/wire` (or `?x`) tail."""
    if os.path.exists(target):
        return target, ""
    for index, char in enumerate(target):
        if char in "#?":
            return target[:index], target[index:]
    return target, ""


def plan_local(target, root):
    """Return (directory to serve, URL path within it) for a local file or directory."""
    path, tail = split_route(target)
    if not os.path.exists(path):
        raise BrowserError("{0} does not exist".format(path))
    # realpath on both sides: on macOS /tmp is a symlink and getcwd() resolves it.
    path = os.path.realpath(path)
    if root is None:
        here = os.path.realpath(os.getcwd())
        inside = os.path.commonpath([here, path]) == here
        root = here if inside else (path if os.path.isdir(path) else os.path.dirname(path))
    root = os.path.realpath(root)
    if os.path.commonpath([root, path]) != root:
        raise BrowserError("{0} is not inside the served directory {1}".format(path, root))
    relative = os.path.relpath(path, root).replace(os.sep, "/")
    url_path = "/" if relative == "." else "/" + relative + ("/" if os.path.isdir(path) else "")
    return root, url_path + tail


def viewport(options):
    """Resolve width, height and scale, with phone defaults under --mobile."""
    width, height, scale = PHONE if options.mobile else DESKTOP
    return options.width or width, options.height or height, options.scale or scale


def capture(page, url, options):
    """Load `url`, apply the options, save the screenshot. Return False if a wait failed."""
    ok = True
    width, height, scale = viewport(options)
    page.set_viewport(width, height, mobile=options.mobile, scale=scale)
    page.emulate_dark(options.dark)
    try:
        page.goto(url, timeout=options.timeout)
    except LoadTimeout as exc:
        # Usually a slow remote image. The page is there; photograph what loaded.
        sys.stderr.write("warning: {0}; capturing anyway\n".format(exc))
    if options.wait_for:
        try:
            page.wait_for(options.wait_for, timeout=options.timeout, visible=True)
        except BrowserError as exc:
            sys.stderr.write("error: {0}; capturing the page as it is\n".format(exc))
            ok = False
    page.eval("document.fonts.ready.then(() => true)")
    if options.eval:
        print(page.eval(options.eval))
    if options.delay:
        time.sleep(options.delay / 1000.0)
    page.screenshot(options.output, full_page=options.full)
    page.sync()
    return ok


def report(page, output):
    """Print what was saved, and warn about anything the page got wrong."""
    with open(output, "rb") as handle:
        pixels = struct.unpack("!II", handle.read(24)[16:24])
    print("saved {0} ({1}x{2})".format(output, *pixels))
    for problem in page_problems(page):
        # A failed request is listed below with its status; skip Chrome's vaguer echo of it.
        if "Failed to load resource" not in problem:
            sys.stderr.write("warning: {0}\n".format(problem))
    for request in page.failed_requests:
        sys.stderr.write("warning: failed request: {0} {1}\n".format(request.status or request.error, request.url))


def shoot(url, options):
    # The internet stays reachable here: a person looking at a screenshot wants the
    # real images, unlike a test, which must not depend on them.
    with Browser(block_external=False) as browser:
        page = browser.new_page()
        ok = capture(page, url, options)
        report(page, options.output)
        page.close()
    return 0 if ok else 1


def main(argv=None):
    options = parse_arguments(argv)
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(128 + signum))
    try:
        if is_url(options.target):
            return shoot(options.target, options)
        root, url_path = plan_local(options.target, options.root)
        with StaticServer(root) as server:
            sys.stderr.write("serving {0} at {1}{2}\n".format(root, server.url, url_path))
            return shoot(server.url + url_path, options)
    except (BrowserError, JSError, CDPError, OSError) as exc:
        # Expected ways to fail (no Chrome, bad path, --eval threw): one line, not a traceback.
        sys.stderr.write("error: {0}: {1}\n".format(type(exc).__name__, exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
