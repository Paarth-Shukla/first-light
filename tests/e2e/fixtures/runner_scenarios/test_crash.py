"""Kills Chrome in the middle of a run, so the selfcheck can check the runner starts another."""

import os
import signal


def test_kills_chrome(page, base_url):
    page.goto(base_url + "/index.html")
    os.killpg(page.browser._process.pid, signal.SIGKILL)


def test_runs_in_a_new_chrome(page, base_url):
    page.goto(base_url + "/index.html")
    assert page.text("#title") == "Harness selfcheck"
