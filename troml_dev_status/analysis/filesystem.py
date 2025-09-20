# troml_dev_status/analysis/filesystem.py
"""
Filesystem analysis utility to read and modify Python project metadata.

This module provides functions to inspect and update project configuration files
such as pyproject.toml (for both PEP 621 and Poetry) and setup.cfg. It also
includes utilities for analyzing source code, test files, and CI configurations.
"""
from __future__ import annotations

import ast
import configparser
import logging
from pathlib import Path
from typing import Any, Union

import tomlkit
from tomlkit.items import Table

# Use tomllib for Python 3.11+, fallback to tomli for older versions
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef,import-not-found]


logger = logging.getLogger(__name__)

# --- Constants ---
DEV_STATUS_PREFIX = "Development Status :: "
VALID_ANALYSIS_MODES = ["library", "application"]
DEFAULT_ANALYSIS_MODE = "library"


# --- Private Helper Functions: File I/O ---


def _load_pyproject_toml(
    repo_path: Path,
) -> Union[dict[str, Any], "tomlkit.TOMLDocument"] | None:
    """Load pyproject.toml using tomlkit if available, else tomllib."""
    pyproject_path = repo_path / "pyproject.toml"
    if not pyproject_path.is_file():
        return None

    content = pyproject_path.read_text(encoding="utf-8")
    if tomlkit:
        try:
            return tomlkit.parse(content)
        except Exception:  # nosec # noqa
            return None

    return tomllib.loads(content)


def _dump_pyproject_toml(
    repo_path: Path, doc: Union[dict[str, Any], "tomlkit.TOMLDocument"]
) -> None:
    """Dump document to pyproject.toml, requiring tomlkit to preserve styles."""
    if not tomlkit or not isinstance(doc, tomlkit.TOMLDocument):
        raise RuntimeError(
            "tomlkit is required for safe in-place updates of pyproject.toml. "
            "Please install it."
        )
    pyproject_path = repo_path / "pyproject.toml"
    pyproject_path.write_text(tomlkit.dumps(doc), encoding="utf-8")


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


# --- Private Helper Functions: Classifier Manipulation ---


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


# --- Public API ---


def get_dev_status_classifier(repo_path: Path) -> str | None:
    """Return the first Development Status classifier from pyproject.toml or setup.cfg."""
    # 1. Try pyproject.toml
    doc = _load_pyproject_toml(repo_path)
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

    return None


def set_dev_status_classifier(repo_path: Path, new_classifier: str) -> bool:
    """Set/replace the Development Status classifier, prioritizing pyproject.toml."""
    pyproject_path = repo_path / "pyproject.toml"
    setup_cfg_path = repo_path / "setup.cfg"

    if pyproject_path.is_file():
        doc = _load_pyproject_toml(repo_path)
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
        _dump_pyproject_toml(repo_path, doc)
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

    raise FileNotFoundError("No pyproject.toml or setup.cfg found in the repository.")


def get_project_name(repo_path: Path) -> str | None:
    """Parses pyproject.toml or setup.cfg to find the project name."""
    # 1. Try pyproject.toml (PEP 621 and Poetry)
    doc = _load_pyproject_toml(repo_path)
    if doc:
        name = doc.get("project", {}).get("name")  # type: ignore
        if name:
            return name
        name = doc.get("tool", {}).get("poetry", {}).get("name")  # type: ignore
        if name:
            return name

    # 2. Try setup.cfg
    config = _load_setup_cfg(repo_path)
    if config and config.has_option("metadata", "name"):
        return config.get("metadata", "name")

    return None


def get_project_dependencies(repo_path: Path) -> list[str] | None:
    """Parses config files to get the list of runtime dependencies."""
    # 1. Try pyproject.toml
    doc = _load_pyproject_toml(repo_path)
    if doc:
        # PEP 621
        if "project" in doc and "dependencies" in doc["project"]:  # type: ignore
            return list(doc["project"]["dependencies"])  # type: ignore

        # Poetry
        poetry_deps = doc.get("tool", {}).get("poetry", {}).get("dependencies")  # type: ignore
        if poetry_deps:
            # Poetry deps are a table. Exclude python version constraint.
            return [dep for dep in poetry_deps if dep.lower() != "python"]

    # 2. Try setup.cfg
    config = _load_setup_cfg(repo_path)
    if config and config.has_option("options", "install_requires"):
        raw_deps = config.get("options", "install_requires", fallback="")
        return [dep.strip() for dep in raw_deps.split("\n") if dep.strip()]

    return None


def get_analysis_mode(repo_path: Path) -> str:
    """
    Parse pyproject.toml to find the analysis mode from [tool.troml-dev-status].
    """
    doc = _load_pyproject_toml(repo_path)
    if not doc:
        return DEFAULT_ANALYSIS_MODE

    tool_config = doc.get("tool", {}).get("troml-dev-status", {})  # type: ignore
    mode = tool_config.get("mode", DEFAULT_ANALYSIS_MODE)

    return mode if mode in VALID_ANALYSIS_MODES else DEFAULT_ANALYSIS_MODE


# --- Filesystem Analysis ---


def find_src_dir(repo_path: Path) -> Path | None:
    """Finds the primary source directory (e.g., 'src/' or the package dir)."""
    src_path = repo_path / "src"
    if src_path.is_dir():
        return src_path

    name = get_project_name(repo_path)
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
