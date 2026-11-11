"""First Light pipeline: fetches headlines and writes the JSON the static site reads.

Run a stage with ``python3 -m pipeline <stage>``. Stages talk to each other only
through files under ``data/``; the one thing they share in code is ``pipeline.core``.
"""
