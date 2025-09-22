# troml_dev_status/checks.py

# A consolidated module for all check logic for simplicity.
# In a larger app, this would be split into checks/release.py, checks/quality.py, etc.

from __future__ import annotations

import ast
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from troml_dev_status.analysis.filesystem import (
    analyze_type_hint_coverage,
    count_source_modules,
    count_test_files,
    find_src_dir,
    get_ci_config_files,
    get_project_dependencies,
)
from troml_dev_status.analysis.find_tests import count_tests
from troml_dev_status.analysis.git import get_latest_commit_date
from troml_dev_status.analysis.pypi import latest_release_has_attestations
from troml_dev_status.analysis.readme_eval import evaluate_readme
from troml_dev_status.analysis.support_per_endoflife import fetch_latest_supported_minor
from troml_dev_status.analysis.validate_changelog import ChangelogValidator
from troml_dev_status.models import CheckResult

# Use tomllib for Python 3.11+, fallback to tomli for older versions
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef,import-not-found]

logger = logging.getLogger(__name__)


# --- Check Functions ---


def check_r1_published_at_least_once(pypi_data: dict | None) -> CheckResult:
    if pypi_data and pypi_data.get("releases"):
        count = len(pypi_data["releases"])
        return CheckResult(
            passed=True,
            evidence=f"Found {count} releases on PyPI for '{pypi_data['info']['name']}'",
        )
    return CheckResult(passed=False, evidence="No releases found on PyPI.")


def check_r2_wheel_sdist_present(
    pypi_data: dict, latest_version: Version
) -> CheckResult:
    releases = pypi_data.get("releases", {}).get(str(latest_version), [])
    has_wheel = any(f["packagetype"] == "bdist_wheel" for f in releases)
    has_sdist = any(f["packagetype"] == "sdist" for f in releases)
    if has_wheel and has_sdist:
        return CheckResult(
            passed=True, evidence=f"Latest release {latest_version} has wheel and sdist"
        )
    return CheckResult(
        passed=False, evidence=f"Latest release {latest_version} missing wheel or sdist"
    )


def check_r4_recent_activity(
    pypi_data: dict, latest_version: Version, months: int
) -> CheckResult:
    releases = pypi_data.get("releases", {}).get(str(latest_version), [])
    if not releases:
        return CheckResult(
            passed=False, evidence="Could not determine upload time of latest release."
        )

    upload_time_str = releases[0].get("upload_time_iso_8601")
    if not upload_time_str:
        return CheckResult(passed=False, evidence="Latest release missing upload time.")

    upload_time = datetime.fromisoformat(upload_time_str)
    age = datetime.now(timezone.utc) - upload_time
    days = age.days

    if age < timedelta(days=months * 30.5):
        return CheckResult(
            passed=True,
            evidence=f"Latest release was {days} days ago (within {months} months).",
        )

    return CheckResult(
        passed=False,
        evidence=f"Latest release was {days} days ago (older than {months} months).",
    )


def check_q1_ci_config_present(repo_path: Path) -> CheckResult:
    if get_ci_config_files(repo_path):
        return CheckResult(
            passed=True,
            evidence="CI config file found (e.g., .github/workflows, .gitlab-ci.yml).",
        )
    return CheckResult(passed=False, evidence="No common CI config files found.")


def check_q3_tests_present(repo_path: Path) -> CheckResult:
    _framework, count = count_tests(repo_path)
    if count >= 5:
        return CheckResult(passed=True, evidence=f"Found {count} test files in tests/.")
    return CheckResult(
        passed=False, evidence=f"Found {count} test files, need at least 5."
    )


def check_q4_test_file_ratio(repo_path: Path) -> CheckResult:
    src_dir = find_src_dir(repo_path)
    if not src_dir:
        return CheckResult(
            passed=False, evidence="Could not determine source directory."
        )

    num_tests = count_test_files(repo_path)
    num_src = count_source_modules(src_dir)

    if num_src == 0:
        return CheckResult(
            passed=False, evidence="No source modules found to calculate ratio."
        )

    ratio = num_tests / num_src
    if ratio >= 0.20:
        return CheckResult(
            passed=True,
            evidence=f"Test/source ratio is {ratio:.2f} ({num_tests}/{num_src}), >= 0.20.",
        )
    return CheckResult(
        passed=False,
        evidence=f"Test/source ratio is {ratio:.2f} ({num_tests}/{num_src}), < 0.20.",
    )


def check_q5_type_hints_shipped(repo_path: Path) -> tuple[CheckResult, float, int]:
    src_dir = find_src_dir(repo_path)
    if not src_dir:
        return (
            CheckResult(passed=False, evidence="Could not determine source directory."),
            0.0,
            0,
        )

    if not (src_dir / "py.typed").exists():
        return (
            CheckResult(passed=False, evidence="py.typed file required."),
            0.0,
            0,
        )

    coverage, total_symbols = analyze_type_hint_coverage(src_dir)

    if total_symbols == 0:
        return (
            CheckResult(
                passed=False, evidence="No public functions/methods found in source."
            ),
            0.0,
            0,
        )

    if coverage >= 70.0:
        return (
            CheckResult(
                passed=True,
                evidence=f"{coverage:.1f}% of {total_symbols} public symbols are annotated.",
            ),
            coverage,
            total_symbols,
        )
    return (
        CheckResult(
            passed=False,
            evidence=f"{coverage:.1f}% of {total_symbols} public symbols are annotated.",
        ),
        coverage,
        total_symbols,
    )


def check_q6_docs_present(repo_path: Path) -> tuple[CheckResult, int]:
    docs_dir = repo_path / "docs"
    if docs_dir.is_dir() and (
        (docs_dir / "conf.py").exists()
        or (docs_dir / "mkdocs.yml").exists()
        or (repo_path / "mkdocs.yml").exists()
    ):
        return (
            CheckResult(
                passed=True,
                evidence="Found docs/ directory with Sphinx or MkDocs config.",
            ),
            0,
        )

    readme_path = next(repo_path.glob("README*"), None)
    if readme_path and readme_path.is_file():
        content = readme_path.read_text(encoding="utf-8")
        word_count = len(content.split())
        has_install_section = bool(
            re.search(r"^#+\s*installation", content, re.IGNORECASE | re.MULTILINE)
        )
        if word_count >= 500 and has_install_section:
            return (
                CheckResult(
                    passed=True,
                    evidence=f"README has {word_count} words and an 'Installation' section.",
                ),
                word_count,
            )
        return (
            CheckResult(
                passed=False,
                evidence=f"README has {word_count} words and 'Installation' section: {has_install_section}.",
            ),
            word_count,
        )

    return (
        CheckResult(
            passed=False, evidence="No docs config or sufficient README found."
        ),
        0,
    )


def check_q8_readme_complete(repo_path: Path) -> CheckResult:
    readme_path = next(repo_path.glob("README*"), None)
    if readme_path and readme_path.is_file():
        content = readme_path.read_text(encoding="utf-8")
        result = evaluate_readme(md=content)

        suggestions = "\n".join(result.suggestions)

        if result.total > (result.max_possible / 2):
            return CheckResult(
                passed=True,
                evidence=f"README has scored {result.total} out of {result.max_possible}.",
            )
        return CheckResult(
            passed=False,
            evidence=f"README has scored {result.total} out of {result.max_possible}.\n{suggestions}",
        )

    return CheckResult(
        passed=False, evidence="No docs config or sufficient README found."
    )


def check_q9_changelog_validates(repo_path: Path) -> CheckResult:
    chagelog_path = next(repo_path.glob("CHANGELOG*"), None)
    if chagelog_path and chagelog_path.is_file():
        content = chagelog_path.read_text(encoding="utf-8")
        validator = ChangelogValidator(file_name=str(chagelog_path))
        result = validator.validate(content=content)

        suggestions = "\n".join((_.message for _ in result))

        if len(result) == 0:
            return CheckResult(
                passed=True,
                evidence="Changelog validates to Keepachangelog schema",
            )
        return CheckResult(
            passed=False,
            evidence=f"Changelog doesn't validate.\n{suggestions}",
        )

    return CheckResult(
        passed=False, evidence="No docs config or sufficient README found."
    )


def check_m1_project_age(pypi_data: dict) -> CheckResult:
    # Find the earliest release date
    first_upload_time = None
    for release_files in pypi_data.get("releases", {}).values():
        if not release_files:
            continue
        upload_time_str = release_files[0].get("upload_time_iso_8601")
        if upload_time_str:
            upload_time = datetime.fromisoformat(upload_time_str)
            if first_upload_time is None or upload_time < first_upload_time:
                first_upload_time = upload_time

    if not first_upload_time:
        return CheckResult(
            passed=False, evidence="Could not determine first release date."
        )

    age = datetime.now(timezone.utc) - first_upload_time
    if age > timedelta(days=90):
        return CheckResult(
            passed=True, evidence=f"Project is {age.days} days old (>= 90)."
        )
    return CheckResult(passed=False, evidence=f"Project is {age.days} days old (< 90).")


def check_m2_code_motion(repo_path: Path, months: int) -> CheckResult:
    src_dir_path = find_src_dir(repo_path)
    if not src_dir_path:
        return CheckResult(passed=False, evidence="Could not find source directory.")

    src_dir_rel_path = src_dir_path.relative_to(repo_path)
    last_commit = get_latest_commit_date(repo_path, sub_path=str(src_dir_rel_path))

    if not last_commit:
        return CheckResult(
            passed=False, evidence="No commits found in source directory."
        )

    age = datetime.now(timezone.utc) - last_commit
    days = age.days

    if age < timedelta(days=months * 30.5):
        return CheckResult(
            passed=True,
            evidence=f"Last code commit was {days} days ago (within {months} months).",
        )
    return CheckResult(
        passed=False,
        evidence=f"Last code commit was {days} days ago (older than {months} months).",
    )


def check_c2_code_attestations(package_name: str) -> CheckResult:
    data = latest_release_has_attestations(package_name) or {}
    if data.get("all_files_attested"):
        return CheckResult(
            passed=True,
            evidence="All files in most recent package are attested.",
        )
    return CheckResult(
        passed=False,
        evidence=f"{len([data.get('files', [])])} files, at least some unattested.",
    )


def check_c3_minimal_pin_sanity(repo_path: Path, mode: str) -> CheckResult:
    """
    Checks runtime dependencies for minimal pinning.
    - 'library' mode (PEP default): requires at least a version bound (e.g., >=). Bare names fail.
    - 'application' mode: requires strict '==' pinning for reproducibility.
    """
    dependencies = get_project_dependencies(repo_path)

    if dependencies is None:
        # This case means the [project] table or dependencies key is missing, not that it's empty.
        # For this check, we can treat it as passing since there are no dependencies to check.
        return CheckResult(
            passed=True,
            evidence="No [project.dependencies] section found in pyproject.toml.",
        )

    if not dependencies:
        return CheckResult(
            passed=True, evidence="[project.dependencies] list is empty."
        )

    failed_deps = []

    for dep_string in dependencies:
        try:
            req = Requirement(dep_string)
            if mode == "library":
                # PEP logic: Fail if there are NO specifiers (e.g., just 'requests')
                if not req.specifier:
                    failed_deps.append(dep_string)
            elif mode == "application":
                # Stricter logic: Fail if not pinned with '=='
                if len(req.specifier) != 1 or next(
                    iter(req.specifier)
                ).operator not in ("==", "<=", "<", ">=", ">"):
                    failed_deps.append(dep_string)
        except InvalidRequirement:
            # If the syntax is invalid, it's a failure.
            failed_deps.append(f"{dep_string} (invalid syntax)")

    if not failed_deps:
        if mode == "library":
            return CheckResult(
                passed=True, evidence="All dependencies have at least a version bound."
            )
        # application mode
        return CheckResult(
            passed=True,
            evidence="All dependencies are pinned with '==' or '<' or '>' or combinations.",
        )
    if mode == "library":
        return CheckResult(
            passed=False,
            evidence=f"Found {len(failed_deps)} unconstrained dependencies: {', '.join(failed_deps)}.",
        )
    # application mode
    return CheckResult(
        passed=False,
        evidence=f"Found {len(failed_deps)} not strictly pinned somehow: {', '.join(failed_deps)}.",
    )


# --- Check Implementations ---


def check_r3_pep440_versioning(pypi_data: dict | None) -> CheckResult:
    """
    Checks if all release versions on PyPI are valid PEP 440.
    The "strictly increasing" part of the PEP is interpreted as all versions
    being valid and sortable, as PyPI upload order isn't guaranteed.
    """
    if not pypi_data or "releases" not in pypi_data:
        return CheckResult(passed=False, evidence="No PyPI data available.")

    version_strings = list(pypi_data["releases"].keys())
    if not version_strings:
        return CheckResult(passed=False, evidence="No releases found in PyPI data.")

    invalid_versions = []
    for v_str in version_strings:
        try:
            Version(v_str)
        except InvalidVersion:
            invalid_versions.append(v_str)

    if invalid_versions:
        return CheckResult(
            passed=False,
            evidence=f"Found {len(invalid_versions)} invalid PEP 440 versions: {', '.join(invalid_versions)}",
        )

    return CheckResult(
        passed=True,
        evidence=f"All {len(version_strings)} release versions are valid PEP 440.",
    )


def check_r5_python_version_declaration(
    repo_path: Path, pypi_data: dict | None
) -> CheckResult:
    """
    Checks for Requires-Python in pyproject.toml and a Python trove classifier on PyPI.
    """
    # 1. Check pyproject.toml for requires-python
    toml_path = repo_path / "pyproject.toml"
    requires_python_str = None
    has_requires_python = False
    if toml_path.exists():
        try:
            with toml_path.open("rb") as f:
                data = tomllib.load(f)
            requires_python_str = data.get("project", {}).get("requires-python")
            has_requires_python = bool(requires_python_str)
        except tomllib.TOMLDecodeError:
            requires_python_str = "[could not parse toml]"

    # 2. Check PyPI for a trove classifier
    has_trove_classifier = False
    if pypi_data:
        classifiers = pypi_data.get("info", {}).get("classifiers", [])
        has_trove_classifier = any(
            c.startswith("Programming Language :: Python :: 3") for c in classifiers
        )

    # 3. Evaluate results
    if has_requires_python and has_trove_classifier:
        return CheckResult(
            passed=True,
            evidence=f"Found 'requires-python: {requires_python_str}' and a Python trove classifier.",
        )

    failures = []
    if not has_requires_python:
        failures.append("'project.requires-python' not found in pyproject.toml")
    if not has_trove_classifier:
        failures.append(
            "No 'Programming Language :: Python :: 3' classifier found on PyPI"
        )

    return CheckResult(passed=False, evidence="; ".join(failures))


def _python_minor_classifiers(classifiers: list[str]) -> list[str]:
    return [
        c for c in classifiers if c.startswith("Programming Language :: Python :: 3.")
    ]


def check_r6_current_python_coverage(
    pypi_data: dict,
    *,
    timeout: float = 10.0,
) -> CheckResult:
    """
    R6. Current Python coverage: Declared support includes current-1 CPython minor.
    Example: if current is 3.13, must include >= 3.12.

    Passes if either:
      - Trove classifiers include "Programming Language :: Python :: 3.<current-1>"
      - OR requires_python spec includes Version("3.<current-1>.0")
    """
    try:
        latest_minor, sources = fetch_latest_supported_minor(timeout=timeout)
    except Exception as e:
        return CheckResult(
            passed=False,
            evidence=f"Failed to determine current CPython version from network: {e}",
        )

    target_minor = latest_minor - 1
    if target_minor < 0:
        return CheckResult(
            passed=False,
            evidence=f"Computed invalid target minor from latest=3.{latest_minor}",
        )

    info = pypi_data.get("info", {}) or {}
    classifiers: list[str] = info.get("classifiers", []) or []
    requires_python: str | None = info.get("requires_python")

    # 1) Exact Trove classifier match for the target minor
    target_classifier = f"Programming Language :: Python :: 3.{target_minor}"
    has_classifier = any(c.strip() == target_classifier for c in classifiers)

    # 2) requires_python includes 3.<target_minor>.0
    has_requires = False
    requires_eval_note = ""
    if requires_python:
        try:
            spec = SpecifierSet(requires_python)
            has_requires = Version(f"3.{target_minor}.0") in spec
        except Exception as e:
            requires_eval_note = f" (requires_python unparsable: {e})"

    if has_classifier or has_requires:
        reason = []
        if has_classifier:
            reason.append(f"classifier {target_classifier!r} present")
        if has_requires:
            reason.append(
                f"requires_python {requires_python!r} includes 3.{target_minor}.x"
            )
        return CheckResult(
            passed=True,
            evidence=(
                f"Current CPython is 3.{latest_minor}; rule requires ≥3.{target_minor}. "
                f"Declared support satisfies via {', '.join(reason)}. "
                f"Sources: {', '.join(sources)}"
            ),
        )

    # Prepare helpful evidence
    declared_py_classifiers = (
        ", ".join(sorted(_python_minor_classifiers(classifiers))) or "none"
    )
    req_str = requires_python if requires_python else "none"

    return CheckResult(
        passed=False,
        evidence=(
            f"Current CPython is 3.{latest_minor}; rule requires declared support for ≥3.{target_minor}. "
            f"Missing classifier {target_classifier!r} and requires_python does not include 3.{target_minor}.x{requires_eval_note}. "
            f"Declared Python classifiers: {declared_py_classifiers}. requires_python: {req_str!r}. "
            f"Source: https://endoflife.date/api/python.json"
        ),
    )


def check_c4_repro_inputs(repo_path: Path) -> CheckResult:
    """
    Checks for the presence of a lockfile for reproducible development environments.
    """
    lockfiles = {
        "uv.lock": "uv lockfile",
        "poetry.lock": "Poetry lockfile",
        "constraints.txt": "pip constraints file",
    }

    # Check for exact matches
    for file_name, desc in lockfiles.items():
        if (repo_path / file_name).exists():
            return CheckResult(passed=True, evidence=f"Found {desc} ('{file_name}').")

    # Check for glob patterns like requirements*.txt
    req_files = list(repo_path.glob("requirements*.txt"))
    if req_files:
        return CheckResult(
            passed=True, evidence=f"Found pip requirements file: '{req_files[0].name}'."
        )

    return CheckResult(
        passed=False,
        evidence="No lockfile found (e.g., uv.lock, poetry.lock, requirements*.txt, constraints.txt).",
    )


def has_all_exports(py_file: Path) -> bool:
    """Parses a file and returns True if it defines __all__."""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    return True
    return False


def check_s1_all_exports(repo_path: Path) -> CheckResult:
    """
    Check if any module in the src dir defines __all__.
    """
    src_dir_path = find_src_dir(repo_path)
    if not src_dir_path:
        return CheckResult(passed=False, evidence="Could not find source directory.")

    py_files = list(src_dir_path.rglob("*.py"))
    if not py_files:
        return CheckResult(
            passed=False, evidence="No Python files in source directory."
        )

    files_with_all = [
        str(f.relative_to(repo_path)) for f in py_files if has_all_exports(f)
    ]

    if files_with_all:
        return CheckResult(
            passed=True,
            evidence=f"Found __all__ exports in: {', '.join(files_with_all)}",
        )
    return CheckResult(passed=False, evidence="No __all__ exports found in any module.")
