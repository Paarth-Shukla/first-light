# Shortcuts for the commands in README.md. The pipeline needs only Python 3.9+.
PYTHON ?= /usr/bin/env python3

.PHONY: update fetch build serve test e2e clean-dist

# Full run: fetch, markets, process, papers (when due), claude, search, build dist/.
update:
	$(PYTHON) -m pipeline all

fetch:
	$(PYTHON) -m pipeline fetch

build:
	$(PYTHON) -m pipeline build

# http://localhost:8080 from dist/
serve:
	$(PYTHON) scripts/serve.py

# Pipeline unit tests; no network.
test:
	$(PYTHON) -m unittest discover -s tests/pipeline -t .

# Browser unit tests and end-to-end checks in headless Chrome, against dist/.
e2e:
	$(PYTHON) tests/e2e/run.py

clean-dist:
	rm -rf dist dist.tmp dist.old
