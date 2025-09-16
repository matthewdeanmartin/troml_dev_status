# troml_dev_status/analysis/pypi.py

from __future__ import annotations

import httpx
from packaging.version import InvalidVersion, Version


def get_project_data(project_name: str) -> dict | None:
    """Fetches the full JSON metadata for a project from PyPI."""
    url = f"https://pypi.org/pypi/{project_name}/json"
    try:
        with httpx.Client() as client:
            response = client.get(url, follow_redirects=True)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
    except httpx.RequestError:
        # Handle network-related errors
        return None


def get_sorted_versions(pypi_data: dict) -> list[Version]:
    """Extracts, validates, and sorts all release versions from PyPI data."""
    versions = []
    for v_str in pypi_data.get("releases", {}):
        try:
            versions.append(Version(v_str))
        except InvalidVersion:
            continue  # Ignore invalid versions
    return sorted(versions, reverse=True)
