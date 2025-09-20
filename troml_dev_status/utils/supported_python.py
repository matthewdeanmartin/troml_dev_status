# troml_dev_status/utils/supported_python.py
from __future__ import annotations

import datetime as _dt
import json as _json
import logging
import re as _re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SupportedBranch:
    branch: str  # e.g. "3.12"
    latest: str  # e.g. "3.12.7"
    eol_date: Optional[_dt.date]  # None means "not set" by source
    phase: Optional[str]  # "bugfix" | "security" | None (unknown)
    latest_release_date: Optional[_dt.date]


@dataclass(frozen=True)
class PythonSupportInfo:
    as_of: _dt.date
    latest_supported_branch: str  # e.g. "3.13"
    latest_supported_version: str  # e.g. "3.13.1"
    branches: List[SupportedBranch]  # all supported branches
    sources: List[str]  # URLs used


def _parse_iso_date(value: Optional[str]) -> Optional[_dt.date]:
    if not value:
        return None
    try:
        return _dt.date.fromisoformat(value)
    except Exception:
        return None


def _is_supported(eol_field: Optional[str], today: _dt.date) -> bool:
    """
    endoflife.date uses either an ISO date (YYYY-MM-DD) or 'false' to indicate
    not EOL yet. Treat 'false' or a date in the future as supported.
    """
    if eol_field is None:
        return False
    if isinstance(eol_field, str) and eol_field.lower() == "false":
        return True
    try:
        eol_date = _dt.date.fromisoformat(eol_field)
        return eol_date >= today
    except Exception:
        # If unparsable, be conservative: not supported
        return False


def _devguide_phase_map(client: httpx.Client) -> Dict[str, str]:
    """
    Best-effort parse of https://devguide.python.org/versions/ to map
    minor branches (e.g. '3.13') to 'bugfix' or 'security'. If the page format
    changes, we just return {} and keep going.
    """
    url = "https://devguide.python.org/versions/"
    try:
        r = client.get(url, timeout=10)
        r.raise_for_status()
        html = r.text

        # Rough parse: rows like:
        # <tr><td>3.13</td><td>...</td><td>bugfix</td>...</tr>
        # We'll look for branch and a status word nearby.
        phase_map: Dict[str, str] = {}

        # Collapse whitespace to simplify regex matching.
        compact = _re.sub(r"\s+", " ", html)

        # Find table rows that likely contain version info.
        for m in _re.finditer(r"<tr>(.*?)</tr>", compact, flags=_re.I):
            row = m.group(1)
            # Try to extract a branch like 3.12, 3.13, 3.14
            v = _re.search(r">\s*(3\.\d+)\s*<", row)
            if not v:
                continue
            branch = v.group(1)
            # Look for a status keyword in the row
            status_match = _re.search(
                r"(bugfix|security|pre-release|prerelease)", row, flags=_re.I
            )
            if status_match:
                phase = (
                    status_match.group(1).lower().replace("pre-release", "pre-release")
                )
                phase_map[branch] = (
                    "bugfix"
                    if "bugfix" in phase
                    else "security" if "security" in phase else "pre-release"
                )
        return phase_map
    except Exception:
        return {}


def get_supported_python_versions(
    *,
    http2: bool = True,
    timeout: float = 10.0,
) -> PythonSupportInfo:
    """
    Determine the currently supported Python branches and their latest patch versions.

    Strategy:
      1) Primary: endoflife.date JSON (authoritative for EOL dates and latest patch per cycle)
         https://endoflife.date/api/python.json
      2) Best-effort enrichment: devguide.python.org (to tag branch phase as bugfix/security)
         https://devguide.python.org/versions/

    Returns:
        PythonSupportInfo with a normalized, machine-friendly view.
    """
    today = _dt.date.today()
    sources: List[str] = ["https://endoflife.date/api/python.json"]

    with httpx.Client(
        http2=http2,
        headers={"User-Agent": "py-support-check/1.0"},
        follow_redirects=True,
        timeout=timeout,
    ) as client:
        # --- Primary source ---
        resp = client.get("https://endoflife.date/api/python.json")
        resp.raise_for_status()
        data = resp.json()

        # Filter to supported cycles
        supported_rows = []
        for row in data:
            # row keys (typical): cycle, releaseDate, eol, latest, latestReleaseDate, lts, link
            if _is_supported(row.get("eol"), today):
                supported_rows.append(row)

        if not supported_rows:
            raise RuntimeError("No supported Python branches found from endoflife.date")

        # Sort cycles numerically by (major, minor)
        def _cycle_key(cycle: str) -> Tuple[int, int]:
            # cycles are like "3.12", "3.13"
            try:
                major, minor = cycle.split(".")
                return int(major), int(minor)
            except Exception:
                return (0, 0)

        supported_rows.sort(key=lambda r: _cycle_key(r.get("cycle", "0.0")))

        # Latest supported branch is the highest cycle
        latest_row = supported_rows[-1]
        latest_supported_branch = latest_row["cycle"]
        latest_supported_version = latest_row.get("latest") or latest_supported_branch

        # Optional enrichment: map branch -> phase (bugfix/security)
        sources.append("https://devguide.python.org/versions/")
        phase_map = _devguide_phase_map(client)

        branches: List[SupportedBranch] = []
        for row in supported_rows:
            cycle = row["cycle"]
            eol_date = None
            if isinstance(row.get("eol"), str) and row["eol"].lower() != "false":
                eol_date = _parse_iso_date(row["eol"])

            branches.append(
                SupportedBranch(
                    branch=cycle,
                    latest=row.get("latest") or cycle,
                    eol_date=eol_date,
                    phase=phase_map.get(cycle),  # may be None if we couldn't determine
                    latest_release_date=_parse_iso_date(row.get("latestReleaseDate")),
                )
            )

    return PythonSupportInfo(
        as_of=today,
        latest_supported_branch=latest_supported_branch,
        latest_supported_version=latest_supported_version,
        branches=branches,
        sources=sources,
    )


# ----------- Example usage -----------
if __name__ == "__main__":
    info = get_supported_python_versions()
    print(
        _json.dumps(
            {
                "as_of": info.as_of.isoformat(),
                "latest_supported_branch": info.latest_supported_branch,
                "latest_supported_version": info.latest_supported_version,
                "branches": [
                    {
                        "branch": b.branch,
                        "latest": b.latest,
                        "phase": b.phase,
                        "eol_date": b.eol_date.isoformat() if b.eol_date else None,
                        "latest_release_date": (
                            b.latest_release_date.isoformat()
                            if b.latest_release_date
                            else None
                        ),
                    }
                    for b in info.branches
                ],
                "sources": info.sources,
            },
            indent=2,
        )
    )
