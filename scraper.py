#!/usr/bin/env python3
"""Backward-compatible entrypoint for the scraper.

The implementation now lives in ``comovoto.scraper``.
This file is intentionally small to preserve existing imports such as:

    from scraper import ConsolidatedDB, classify_bloc, VOTE_DECODE
"""

from comovoto.scraper import *  # noqa: F401,F403


if __name__ == "__main__":
    main()
