# readme_rater/main.py
"""Allows the package to be run as a script via `python -m readme_rater`."""

from __future__ import annotations

import sys

from readme_rater.cli import main

if __name__ == "__main__":
    sys.exit(main())
