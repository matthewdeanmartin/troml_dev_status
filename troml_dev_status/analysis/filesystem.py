# troml_dev_status/analysis/filesystem.py
"""
Filesystem analysis utility to read and modify Python project metadata.

This module provides functions to inspect and update project configuration files
such as pyproject.toml (for both PEP 621 and Poetry) and setup.cfg. It also
includes utilities for analyzing source code, test files, and CI configurations.

NEW:
- venv_mode flag on readers. When True, prefer importlib.metadata (or backport)
  to fetch name, classifiers, and dependencies from the installed distribution.
- Even when venv_mode=False, we now fall back to importlib.metadata if config
  files are missing or unparseable.
"""
from __future__ import annotations

import ast
import configparser
import logging
import os
import re
from pathlib import Path
from typing import Any, Iterable, Optional

import tomlkit
from tomlkit.items import Table

from troml_dev_status.utils.tomlkit_utils import (
    dump_pyproject_toml,
    load_pyproject_toml,
)

try:
    # Preferred: follows PEP 503
    from packaging.utils import canonicalize_name as _canonicalize_name  # type: ignore
except Exception:  # packaging not installed
    _canonicalize_name = None  # type: ignore

# importlib.metadata with backport support
try:
    from importlib import metadata as _im
except Exception:  # pragma: no cover
    import importlib_metadata as _im  # type: ignore

logger = logging.getLogger(__name__)

# --- Constants ---
DEV_STATUS_PREFIX = "Development Status :: "
VALID_ANALYSIS_MODES = ["library", "application"]
DEFAULT_ANALYSIS_MODE = "library"


# --- Importlib.metadata helpers ------------------------------------------------


def _pep503_normalize(name: str) -> str:
    """PEP 503 normalization: lowercase and collapse runs of [-_.] to a single '-'."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _canon(name: str) -> str:
    """Canonicalize a distribution name using packaging if available; else PEP 503."""
    if _canonicalize_name is not None:  # pragma: no cover - trivial branch
        return _canonicalize_name(name)
    return _pep503_normalize(name)


def _unique(iterable: Iterable[str]) -> list[str]:
    """Preserve order while removing duplicates (case-sensitive)."""
    seen: set[str] = set()
    out: list[str] = []
    for s in iterable:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _candidate_dist_names(
    repo_path: Path, pyproject_doc: dict[str, Any] | None
) -> list[str]:
    """
    Build a small set of likely distribution names to look up via importlib.metadata.
    Priority:
      1) [project].name
      2) [tool.poetry].name
      3) folder name (hyphen/underscore variants)
    Returns raw and normalized variants (PEP 503/canonical), de-duplicated.
    """
    cands: list[str] = []

    # pyproject sources
    if pyproject_doc:
        proj_name = (pyproject_doc.get("project") or {}).get("name")
        if proj_name:
            cands.append(str(proj_name))

        poetry_name = ((pyproject_doc.get("tool") or {}).get("poetry") or {}).get(
            "name"
        )
        if poetry_name:
            cands.append(str(poetry_name))

    # folder name & simple swaps
    folder = repo_path.name
    cands.append(folder)
    cands.append(folder.replace("-", "_"))
    cands.append(folder.replace("_", "-"))

    # Build variants per candidate
    variants: list[str] = []
    for n in _unique(cands):
        variants.extend(
            [
                n,  # as-is
                n.lower(),  # lowercase
                n.replace("-", "_"),
                n.replace("_", "-"),
                _pep503_normalize(n),
                _canon(n),  # packaging canonical (same as PEP 503, but future-proof)
            ]
        )

    return _unique(variants)


# def _candidate_dist_names(repo_path: Path, pyproject_doc: dict[str, Any] | None) -> list[str]:
#     """
#     Build a small set of likely distribution names to look up via importlib.metadata.
#     Priority:
#       1) [project].name
#       2) [tool.poetry].name
#       3) folder name (hyphen and underscore variants)
#     """
#     cands: list[str] = []
#     if pyproject_doc:
#         name = pyproject_doc.get("project", {}).get("name")
#         if name:
#             cands.append(str(name))
#         poetry_name = pyproject_doc.get("tool", {}).get("poetry", {}).get("name")
#         if poetry_name and poetry_name not in cands:
#             cands.append(str(poetry_name))
#     folder = repo_path.name
#     if folder not in cands:
#         cands.append(folder)
#     u = folder.replace("-", "_")
#     h = folder.replace("_", "-")
#     for n in (u, h):
#         if n not in cands:
#             cands.append(n)
#     # Normalize names per PEP 503 (importlib.metadata uses normalized names internally)
#     normed = list(dict.fromkeys(_im._meta._normalize_name(n) if hasattr(_im, "_meta") else n.lower().replace("-", "").replace("_", "") for n in cands))  # type: ignore[attr-defined]
#     # Keep both raw and normalized to maximize hit chance
#     return list(dict.fromkeys(cands + normed))


def _find_distribution_by_candidates(
    candidates: Iterable[str],
) -> Optional[_im.Distribution]:
    """
    Return the first importlib.metadata Distribution whose name matches any candidate
    (case-insensitive, normalized).
    """
    for cand in candidates:
        try:
            dist = _im.distribution(cand)
            if dist:
                return dist
        except _im.PackageNotFoundError:
            continue
        except Exception:  # nosec
            continue
    # Last-ditch: try scanning all dists and match normalized names
    try:
        all_dists = list(_im.distributions())
        normalized = {
            cand.lower().replace("-", "").replace("_", "") for cand in candidates
        }
        for dist in all_dists:
            nm = dist.metadata.get("Name", "") or ""
            nm_norm = nm.lower().replace("-", "").replace("_", "")
            if nm_norm in normalized:
                return dist
    except Exception:  # nosec
        pass
    return None


def _get_metadata_list(dist: _im.Distribution, key: str) -> list[str]:
    """
    Collect all repeated metadata headers, e.g., Classifier / Requires-Dist.
    """
    # EmailMessage-like interface; get_all returns a list or None
    vals = dist.metadata.get_all(key) if hasattr(dist.metadata, "get_all") else None
    if not vals:
        # Some implementations expose a single string joined by newlines
        raw = dist.metadata.get(key)
        if not raw:
            return []
        if isinstance(raw, str):
            return [line.strip() for line in raw.splitlines() if line.strip()]
        return []
    return [v.strip() for v in vals if isinstance(v, str) and v.strip()]


# --- setup.cfg I/O -------------------------------------------------------------


def _load_setup_cfg(repo_path: Path) -> configparser.ConfigParser | None:
    """Load setup.cfg if it exists."""
    setup_cfg_path = repo_path / "setup.cfg"
    if not setup_cfg_path.is_file():
        return None
    config = configparser.ConfigParser()
    config.read(setup_cfg_path)
    return config


def _dump_setup_cfg(repo_path: Path, config: configparser.ConfigParser) -> None:
    """Dump ConfigParser object to setup.cfg."""
    setup_cfg_path = repo_path / "setup.cfg"
    with setup_cfg_path.open("w", encoding="utf-8") as f:
        config.write(f)


# --- Private Helper Functions: Classifier Manipulation ------------------------


def _get_classifiers_from_toml_table(table: dict[str, Any] | None) -> list[str]:
    """Extract classifiers list from a TOML table ([project] or [tool.poetry])."""
    if not table:
        return []
    classifiers = table.get("classifiers", [])
    return list(classifiers) if classifiers else []


def _update_classifiers_in_toml_table(table: Table, new_classifier: str) -> None:
    """Update a TOML table's classifiers list in-place."""
    if "classifiers" not in table or table.get("classifiers") is None:
        if not tomlkit:
            raise RuntimeError("tomlkit is required to create a 'classifiers' array.")
        table["classifiers"] = tomlkit.array().multiline(True)

    classifiers = table["classifiers"]

    # Filter out existing dev status classifiers
    to_keep = [
        item
        for item in classifiers  # type: ignore[attr-defined]
        if not (isinstance(item, str) and item.startswith(DEV_STATUS_PREFIX))
    ]

    # Rebuild the list with the new classifier at the front
    if hasattr(classifiers, "clear"):
        classifiers.clear()
        for item in reversed(to_keep):
            classifiers.insert(0, item)  # type: ignore[attr-defined]
        classifiers.insert(0, new_classifier)  # type: ignore[attr-defined]
    else:  # Fallback for plain list
        table["classifiers"] = [new_classifier] + to_keep


# --- Public API ----------------------------------------------------------------


def get_dev_status_classifier(
    repo_path: Path, *, venv_mode: bool = False
) -> str | None:
    """
    Return the first Development Status classifier from config files, or from the
    installed distribution when venv_mode=True, or as a final fallback.
    """
    if os.environ.get("TROML_DEV_STATUS_VENV_MODE"):
        venv_mode = True
    doc = load_pyproject_toml(repo_path)

    # venv_mode prefers installed metadata first
    if venv_mode:
        dist = _find_distribution_by_candidates(_candidate_dist_names(repo_path, doc))
        if dist:
            for c in _get_metadata_list(dist, "Classifier"):
                if c.startswith(DEV_STATUS_PREFIX):
                    return c

    # 1. Try pyproject.toml
    if doc:
        # PEP 621 [project] table
        project_table = doc.get("project")
        classifiers = _get_classifiers_from_toml_table(project_table)  # type: ignore

        # Poetry [tool.poetry] table
        if not classifiers:
            poetry_table = doc.get("tool", {}).get("poetry")  # type: ignore
            classifiers = _get_classifiers_from_toml_table(poetry_table)

        for c in classifiers:
            if c.startswith(DEV_STATUS_PREFIX):
                return c

    # 2. Try setup.cfg
    config = _load_setup_cfg(repo_path)
    if config and config.has_option("metadata", "classifiers"):
        raw_classifiers = config.get("metadata", "classifiers", fallback="")
        classifiers = [c.strip() for c in raw_classifiers.split("\n") if c.strip()]
        for c in classifiers:
            if c.startswith(DEV_STATUS_PREFIX):
                return c

    # Final fallback: try installed distribution metadata
    dist = _find_distribution_by_candidates(_candidate_dist_names(repo_path, doc))
    if dist:
        for c in _get_metadata_list(dist, "Classifier"):
            if c.startswith(DEV_STATUS_PREFIX):
                return c

    return None


def set_dev_status_classifier(
    repo_path: Path, new_classifier: str, *, venv_mode: bool = False
) -> bool:
    """
    Set/replace the Development Status classifier, prioritizing pyproject.toml.
    NOTE: We only *write* to files. venv_mode is accepted for API symmetry but
    does not write to installed metadata (not possible); it still writes files.
    """
    pyproject_path = repo_path / "pyproject.toml"
    setup_cfg_path = repo_path / "setup.cfg"

    if pyproject_path.is_file():
        doc = load_pyproject_toml(repo_path)
        if not doc:
            raise IOError(f"Could not parse {pyproject_path}")
        if not tomlkit:
            raise RuntimeError("tomlkit is required to safely update pyproject.toml.")

        # If poetry table exists, update it as the more specific tool config.
        if doc.get("tool", {}).get("poetry"):  # type: ignore
            table = doc["tool"]["poetry"]  # type: ignore
        else:  # Otherwise, update standard [project] table
            if "project" not in doc:
                doc["project"] = tomlkit.table()  # type: ignore
            table = doc["project"]  # type: ignore

        _update_classifiers_in_toml_table(table, new_classifier)  # type: ignore[arg-type]
        dump_pyproject_toml(repo_path, doc)
        return True

    if setup_cfg_path.is_file():
        config = _load_setup_cfg(repo_path)
        if not config:
            raise IOError(f"Could not parse {setup_cfg_path}")

        if not config.has_section("metadata"):
            config.add_section("metadata")

        raw_classifiers = config.get("metadata", "classifiers", fallback="").strip()
        classifiers = [c.strip() for c in raw_classifiers.split("\n") if c.strip()]

        to_keep = [c for c in classifiers if not c.startswith(DEV_STATUS_PREFIX)]
        new_list = [new_classifier] + to_keep

        # setup.cfg expects a newline-separated string
        config.set("metadata", "classifiers", "\n" + "\n".join(new_list))
        _dump_setup_cfg(repo_path, config)
        return True

    # If there are no files to write, we cannot persist it.
    raise FileNotFoundError("No pyproject.toml or setup.cfg found in the repository.")


def get_project_name(repo_path: Path, *, venv_mode: bool = False) -> str | None:
    """Get project name from pyproject.toml/setup.cfg, or from installed dist."""
    doc = load_pyproject_toml(repo_path)

    if venv_mode:
        dist = _find_distribution_by_candidates(_candidate_dist_names(repo_path, doc))
        if dist:
            name = dist.metadata.get("Name")
            if name:
                return str(name)

    # 1. Try pyproject.toml (PEP 621 and Poetry)
    if doc:
        name = doc.get("project", {}).get("name")  # type: ignore
        if name:
            return str(name)
        name = doc.get("tool", {}).get("poetry", {}).get("name")  # type: ignore
        if name:
            return str(name)

    # 2. Try setup.cfg
    config = _load_setup_cfg(repo_path)
    if config and config.has_option("metadata", "name"):
        return config.get("metadata", "name")

    # Final fallback
    dist = _find_distribution_by_candidates(_candidate_dist_names(repo_path, doc))
    if dist:
        nm = dist.metadata.get("Name")
        return str(nm) if nm else None

    return None


def get_project_dependencies(
    repo_path: Path, *, venv_mode: bool = False
) -> list[str] | None:
    """
    Get runtime dependencies from pyproject.toml/setup.cfg, or from installed dist
    (Requires-Dist) when venv_mode=True or as a final fallback.
    """
    doc = load_pyproject_toml(repo_path)

    if venv_mode:
        dist = _find_distribution_by_candidates(_candidate_dist_names(repo_path, doc))
        if dist:
            reqs = _get_metadata_list(dist, "Requires-Dist")
            return reqs if reqs else []

    # 1. Try pyproject.toml
    doc = load_pyproject_toml(repo_path)
    if doc:
        # PEP 621
        if "project" in doc and "dependencies" in doc["project"]:  # type: ignore
            deps = list(doc["project"]["dependencies"])  # type: ignore
            return deps

        # Poetry
        poetry_deps = doc.get("tool", {}).get("poetry", {}).get("dependencies")  # type: ignore
        if poetry_deps:
            # Poetry deps are a table. Exclude python version constraint.
            return [dep for dep in poetry_deps if str(dep).lower() != "python"]

    # 2. Try setup.cfg
    config = _load_setup_cfg(repo_path)
    if config and config.has_option("options", "install_requires"):
        raw_deps = config.get("options", "install_requires", fallback="")
        return [dep.strip() for dep in raw_deps.split("\n") if dep.strip()]

    # Final fallback
    dist = _find_distribution_by_candidates(_candidate_dist_names(repo_path, doc))
    if dist:
        reqs = _get_metadata_list(dist, "Requires-Dist")
        return reqs if reqs else []

    return None


def get_analysis_mode(repo_path: Path, *, venv_mode: bool = False) -> str:
    """
    Parse pyproject.toml to find the analysis mode from [tool.troml-dev-status].
    There is no equivalent for this in installed metadata; if files are missing,
    fall back to DEFAULT_ANALYSIS_MODE.
    """
    if os.environ.get("TROML_DEV_STATUS_VENV_MODE"):
        pass
    doc = load_pyproject_toml(repo_path)
    if not doc:
        return DEFAULT_ANALYSIS_MODE

    tool_config = doc.get("tool", {}).get("troml-dev-status", {})  # type: ignore
    mode = tool_config.get("mode", DEFAULT_ANALYSIS_MODE)

    return mode if mode in VALID_ANALYSIS_MODES else DEFAULT_ANALYSIS_MODE


# --- Filesystem Analysis -------------------------------------------------------


def find_src_dir(repo_path: Path, *, venv_mode: bool = False) -> Path | None:
    """Finds the primary source directory (e.g., 'src/' or the package dir)."""
    if os.environ.get("TROML_DEV_STATUS_VENV_MODE"):
        venv_mode = True
    src_path = repo_path / "src"
    if src_path.is_dir():
        return src_path

    name = get_project_name(repo_path, venv_mode=venv_mode)
    if name:
        # Handle both hyphenated and underscored package names
        package_path_hyphen = repo_path / name
        package_path_underscore = repo_path / name.replace("-", "_")
        if package_path_hyphen.is_dir():
            return package_path_hyphen
        if package_path_underscore.is_dir():
            return package_path_underscore
    return None


def count_test_files(repo_path: Path) -> int:
    """Counts files matching common test patterns."""
    total = 0
    for dir_name in ["test", "tests"]:
        tests_dir = repo_path / dir_name
        if tests_dir.is_dir():
            total += len(list(tests_dir.glob("**/test_*.py")))
            total += len(list(tests_dir.glob("**/*_test.py")))
    return total


def count_source_modules(src_path: Path) -> int:
    """Counts non-__init__.py Python modules in the source directory."""
    if not src_path or not src_path.is_dir():
        return 0
    return sum(
        1 for f in src_path.rglob("*.py") if f.is_file() and f.name != "__init__.py"
    )


def get_ci_config_files(repo_path: Path) -> list[Path]:
    """Finds common CI configuration files."""
    patterns = [
        ".github/workflows/*.yml",
        ".github/workflows/*.yaml",
        ".gitlab-ci.yml",
    ]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(repo_path.glob(pattern))
    return files


def has_multi_python_in_ci(ci_files: list[Path]) -> bool:
    """Checks if CI files mention at least two distinct Python versions."""
    py_versions = set()
    versions_to_check = ["3.8", "3.9", "3.10", "3.11", "3.12", "3.13"]

    for file_path in ci_files:
        try:
            content = file_path.read_text(encoding="utf-8")
            for version in versions_to_check:
                if version in content:
                    py_versions.add(version)
        except IOError:
            continue
    return len(py_versions) >= 2


def analyze_type_hint_coverage(src_path: Path) -> tuple[float, int]:
    """
    Calculate the percentage of public functions/methods with type hints.

    Returns:
        A tuple containing (coverage_percentage, total_public_symbols).
    """
    if not src_path or not src_path.is_dir():
        return 0.0, 0

    total_symbols = 0
    annotated_symbols = 0

    for py_file in src_path.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    total_symbols += 1
                    # A return annotation is a strong signal of intent to type.
                    if node.returns is not None:
                        annotated_symbols += 1

    if total_symbols == 0:
        # More points on the rubric means better.
        # 0 symbols, 0 annotations are both bad.
        return 0, 0  # No public symbols means 0% coverage.

    coverage = (annotated_symbols / total_symbols) * 100
    return coverage, total_symbols


def get_bureaucracy_files(repo_path: Path) -> list[Path]:
    """Finds common bureaucracy files like SECURITY.md, ignoring case."""
    found_files: list[Path] = []
    # Use glob with character sets for case-insensitivity
    patterns = [
        "[sS][eE][cC][uU][rR][iI][tT][yY].*",
        "[cC][oO][nN][tT][rR][iI][bB][uU][tT][iI][nN][gG].*",
        "[cC][oO][dD][eE]_[oO][fF]_[cC][oO][nN][dD][uU][cC][tT].*",
    ]
    for pattern in patterns:
        found_files.extend(repo_path.glob(pattern))
    return found_files
