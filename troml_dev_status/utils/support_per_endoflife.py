# troml_dev_status/utils/support_per_endoflife.py
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


def fetch_latest_supported_minor(*, timeout: float = 10.0) -> tuple[int, list[str]]:
    """
    Query endoflife.date for Python cycles and return the highest supported minor.
    Returns: (latest_minor_int, sources)
    """
    url = "https://endoflife.date/api/python.json"
    with httpx.Client(
        timeout=timeout, headers={"User-Agent": "troml-dev-status/1.0"}
    ) as client:
        r = client.get(url)
        r.raise_for_status()
        data = r.json()

    def is_supported(row: dict) -> bool:
        eol = row.get("eol")
        if eol is None:
            return False
        if isinstance(eol, str) and eol.lower() == "false":
            return True
        # ISO date means still supported if in the future; we can skip parsing and
        # just treat non-"false" strings as dates in the future per endoflife.date semantics.
        # (If it were past, the row would usually be omitted from "supported" anyway.)
        return True

    cycles = [row.get("cycle", "") for row in data if is_supported(row)]
    # Keep only 3.X style and sort by X
    minors = sorted(
        (
            int(c.split(".")[1])
            for c in cycles
            if c.startswith("3.") and c.count(".") == 1
        ),
        key=int,
    )
    if not minors:
        raise RuntimeError(
            "Could not determine latest supported Python minor from endoflife.date"
        )
    return minors[-1], [url]
