"""Deliberately good and bad tests, one per verdict the runner can give.

Not part of the real suite: the harness selfcheck runs the runner on this
directory in a subprocess and checks that every test gets the verdict in its name.
"""

from tests.e2e.run import allow_errors


def _open(page, base_url):
    page.goto(base_url + "/index.html")
    page.wait_for_text("#boot", "ready")


def _let_timers_run(page):
    page.eval("new Promise((resolve) => setTimeout(resolve, 30))")


def test_passes(page, base_url):
    _open(page, base_url)
    assert page.text("#title") == "Harness selfcheck"


def test_fails_on_assertion(page, base_url):
    _open(page, base_url)
    assert page.text("#title") == "Some other title", "the title was " + page.text("#title")


def test_fails_on_console_error(page, base_url):
    _open(page, base_url)
    page.click("#console-error")


def test_fails_on_uncaught_exception(page, base_url):
    _open(page, base_url)
    page.click("#throw")
    _let_timers_run(page)


@allow_errors
def test_passes_with_all_errors_allowed(page, base_url):
    _open(page, base_url)
    page.click("#console-error")
    page.click("#throw")
    _let_timers_run(page)


@allow_errors("deliberate console error")
def test_fails_on_error_outside_the_allow_list(page, base_url):
    _open(page, base_url)
    page.click("#console-error")
    page.click("#throw")
    _let_timers_run(page)
