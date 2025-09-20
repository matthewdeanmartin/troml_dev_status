from pathlib import Path

import pytest

from troml_dev_status.analysis.filesystem import count_test_files


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# dummy\n")


def test_no_test_directories_returns_zero(tmp_path: Path):
    repo = tmp_path
    assert count_test_files(repo) == 0


@pytest.mark.parametrize("root", ["tests", "test"])
def test_counts_simple_matches_in_single_dir(tmp_path: Path, root: str):
    repo = tmp_path
    _touch(repo / root / "test_alpha.py")
    _touch(repo / root / "beta_test.py")
    _touch(repo / root / "blerg.py")  # should NOT count

    assert count_test_files(repo) == 2


@pytest.mark.parametrize("root", ["tests", "test"])
def test_counts_recursively_in_subdirectories(tmp_path: Path, root: str):
    repo = tmp_path
    _touch(repo / root / "unit" / "test_gamma.py")
    _touch(repo / root / "integration" / "delta_test.py")
    _touch(repo / root / "integration" / "helpers.py")  # should NOT count

    assert count_test_files(repo) == 2


def test_counts_both_test_and_tests_dirs_without_double_counting(tmp_path: Path):
    repo = tmp_path
    # top-level in each root
    _touch(repo / "tests" / "test_root_a.py")
    _touch(repo / "test" / "test_root_b.py")

    # nested in each root
    _touch(repo / "tests" / "pkg" / "epsilon_test.py")
    _touch(repo / "test" / "pkg" / "zeta_test.py")

    # noise that should NOT count
    _touch(repo / "tests" / "pkg" / "notes.py")
    _touch(repo / "test" / "pkg" / "tools.py")

    # Expected: 4 total matches
    assert count_test_files(repo) == 4


def test_ignores_non_matching_patterns(tmp_path: Path):
    repo = tmp_path
    # Patterns like "spec_" or "_spec.py" don't match the given globs
    _touch(repo / "tests" / "spec_widget.py")
    _touch(repo / "tests" / "widget_spec.py")
    _touch(repo / "tests" / "widget.py")

    assert count_test_files(repo) == 0


def test_handles_deeply_nested_tree(tmp_path: Path):
    repo = tmp_path
    deep = repo / "tests" / "a" / "b" / "c" / "d" / "e"
    _touch(deep / "test_deep.py")
    _touch(deep / "ultra_deep_test.py")
    _touch(deep / "helper.py")
    assert count_test_files(repo) == 2
