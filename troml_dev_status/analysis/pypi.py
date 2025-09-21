# troml_dev_status/analysis/pypi.py

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import httpx
from packaging.version import InvalidVersion, Version

logger = logging.getLogger(__name__)

INTEGRITY_ACCEPT = "application/vnd.pypi.integrity.v1+json"


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


def latest_release_files(pypi_json: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    # `info.version` is the latest release according to PyPI’s JSON API
    version = pypi_json["info"]["version"]
    files = pypi_json.get("releases", {}).get(version, [])
    return version, files


def file_has_attestations(
    project: str, version: str, filename: str
) -> Tuple[bool, Dict[str, Any] | None]:
    url = f"https://pypi.org/integrity/{project}/{version}/{filename}/provenance"
    headers = {"Accept": INTEGRITY_ACCEPT}
    try:
        with httpx.Client(timeout=20) as client:
            r = client.get(url, headers=headers)
            if r.status_code == 404:
                # No provenance (no attestations) for this file
                return False, None
            r.raise_for_status()
            data = r.json()
            # Heuristic: if there are any attestation bundles and any attestations within,
            # consider this file as having attestations.
            bundles = data.get("attestation_bundles", [])
            has = any(b.get("attestations") for b in bundles)
            return has, data
    except httpx.RequestError:
        return False, None


def latest_release_has_attestations(project: str) -> Dict[str, Any] | None:
    """
    Returns a dict like:
    {
      "project": "...",
      "version": "...",
      "files": [
        {"filename": "pkg-1.2.3-py3-none-any.whl", "has_attestations": True},
        {"filename": "pkg-1.2.3.tar.gz", "has_attestations": False},
      ],
      "any_file_attested": True,
      "all_files_attested": False
    }
    or None if project not found.
    """
    meta = get_project_data(project)
    if not meta:
        return None
    version, files = latest_release_files(meta)

    results = []
    any_attested = False
    all_attested = bool(files)

    for f in files:
        fname = f.get("filename")
        if not fname:
            continue
        has, _ = file_has_attestations(project, version, fname)
        results.append({"filename": fname, "has_attestations": has})
        any_attested = any_attested or has
        all_attested = all_attested and has

    return {
        "project": project,
        "version": version,
        "files": results,
        "any_file_attested": any_attested,
        "all_files_attested": all_attested,
    }


if __name__ == "__main__":
    print(get_project_data("troml-dev-status"))
    print(latest_release_has_attestations("troml-dev-status"))
