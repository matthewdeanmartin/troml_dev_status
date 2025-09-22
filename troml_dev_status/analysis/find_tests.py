# troml_dev_status/analysis/find_tests.py
from __future__ import annotations

import logging
import subprocess  # nosec
import unittest
from pathlib import Path
from typing import Iterable, List, Tuple

from troml_dev_status.analysis.filesystem import find_src_dir

logger = logging.getLogger(__name__)


def _existing_dirs(repo_path: Path, candidate_dirs: Iterable[str]) -> List[Path]:
    """Filter candidate dir names to ones that actually exist under repo_path."""
    return [repo_path / d for d in candidate_dirs if (repo_path / d).is_dir()]


def _count_unittest(repo_path: Path, start_dirs: Iterable[str]) -> int:
    """
    Use unittest's discovery engine to count test cases.
    Counts individual test functions/methods (suite.countTestCases()).
    """
    # handle case of people who put their tests in their module code.
    more_dirs = []
    module_dir = find_src_dir(repo_path)
    if module_dir:
        more_dirs.append(module_dir)
    dirs = _existing_dirs(repo_path, start_dirs) + more_dirs

    if not dirs:
        return 0

    loader = unittest.TestLoader()
    master_suite = unittest.TestSuite()

    # Discover separately per start dir (mirrors how people usually run them)
    for d in dirs:
        # Default pattern matches test*.py; this picks up both test_*.py and *_test.py
        suite = loader.discover(
            start_dir=str(d), pattern="test*.py", top_level_dir=str(repo_path)
        )
        master_suite.addTests(suite)

    return master_suite.countTestCases()


def _count_pytest(repo_path: Path, start_dirs: Iterable[str]) -> int:
    """
    Use pytest's collector to count test items without running them.
    We shell out to avoid relying on private pytest APIs.
    """
    dirs = _existing_dirs(repo_path, start_dirs)
    if not dirs:
        logger.debug("No directories found specifically for tests")
        return 0

    try:
        # Use Python to invoke pytest to reduce PATH weirdness on Windows.

        cmd = [
            # sys.executable,
            # "-m",
            "pytest",
            "--collect-only",
            "-q",  # quiet: prints nodeids one per line
            *[str(d) for d in dirs],
        ]
        proc = subprocess.run(  # nosec
            cmd,
            cwd=str(repo_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # merge for simpler parsing
            text=True,
            check=False,
        )
    except FileNotFoundError:
        # pytest not installed or Python can't spawn
        # raise
        return 0

    # Pytest with -q --collect-only prints nodeids line-by-line.
    # Filter out empties and common noise lines.
    count = 0
    for line in proc.stdout.splitlines():
        s = line.strip()
        if not s:
            continue
        # Skip separators / warnings / summary noise that sometimes sneak in
        if s.startswith(
            ("[", "=", "-", "collected ", "no tests", "warning", "ERROR", "E   ")
        ):
            continue
        # Heuristic: collected nodeids usually contain '::' when they’re tests;
        # parameterized tests also appear as nodeids with '::'.
        # Module-level nodes (no test items) might end with '.py' without '::'—skip those.
        if "::" in s:
            count += 1

    return count


def count_tests(
    repo_path: Path,
    start_dirs: Iterable[str] | None = None,
) -> Tuple[str, int]:
    """
    Count tests discoverable by unittest; if none, try pytest.

    Parameters
    ----------
    repo_path : Path
        Path to the repository root.
    start_dirs : Iterable[str] | None
        One or more directory names to search relative to repo_path.
        Defaults to ["test", "tests"].

    Returns
    -------
    (framework, count) : Tuple[str, int]
        framework is "unittest", "pytest", or "none".
        count is the number of discovered test cases/items.
    """
    if start_dirs is None:
        start_dirs = ("test", "tests")

    # 2) Fall back to pytest collection
    py_count = _count_pytest(repo_path, start_dirs)
    if py_count > 0:
        return ("pytest", py_count)

    # 1) Try unittest discovery
    unit_count = _count_unittest(repo_path, start_dirs)
    if unit_count > 0:
        return ("unittest", unit_count)

    return ("none", 0)


if __name__ == "__main__":
    # relative paths don't work?
    print(count_tests(Path("../.."), ["test", "tests"]))
