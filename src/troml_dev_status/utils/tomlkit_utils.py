from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import tomlkit

# Use tomllib for Python 3.11+, fallback to tomli for older versions
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef,import-not-found]


logger = logging.getLogger(__name__)


def load_pyproject_toml(
    repo_path: Path,
) -> dict[str, Any] | tomlkit.TOMLDocument | None:
    """Load pyproject.toml using tomlkit if available, else tomllib."""
    pyproject_path = repo_path / "pyproject.toml"
    if not pyproject_path.is_file():
        return None

    content = pyproject_path.read_text(encoding="utf-8")
    if tomlkit:  # pylint: disable=using-constant-test
        try:
            return tomlkit.parse(content)
        except Exception:  # nosec # noqa
            return None

    return tomllib.loads(content)


def dump_pyproject_toml(
    repo_path: Path, doc: dict[str, Any] | tomlkit.TOMLDocument
) -> None:
    """Dump document to pyproject.toml, requiring tomlkit to preserve styles."""
    pyproject_path = repo_path / "pyproject.toml"
    pyproject_path.write_text(tomlkit.dumps(doc), encoding="utf-8")
