"""A test that never finishes on its own, so the selfcheck can interrupt the runner mid-test."""

import time


def test_sleeps_until_interrupted(page, base_url):
    page.goto(base_url + "/index.html")
    time.sleep(60)
