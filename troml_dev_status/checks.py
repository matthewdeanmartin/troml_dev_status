# troml_dev_status/checks.py

# A consolidated module for all check logic for simplicity.
# In a larger app, this would be split into checks/release.py, checks/quality.py, etc.

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import Version

from troml_dev_status.analysis.filesystem import (
    analyze_type_hint_coverage,
    count_source_modules,
    count_test_files,
    find_src_dir,
    get_ci_config_files,
    get_project_dependencies,
)
from troml_dev_status.analysis.git import get_latest_commit_date
from troml_dev_status.models import CheckResult

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
    count = count_test_files(repo_path)
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
        (docs_dir / "conf.py").exists() or (docs_dir / "mkdocs.yml").exists()
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
