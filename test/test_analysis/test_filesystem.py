# tests/test_filesystem.py
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from troml_dev_status.analysis.filesystem import (
    analyze_type_hint_coverage,
    count_source_modules,
    count_test_files,
    find_src_dir,
    get_analysis_mode,
    get_ci_config_files,
    get_project_dependencies,
    get_project_name,
    has_multi_python_in_ci,
)


def write(repo: Path, rel: str, content: str = "") -> Path:
    """Helper to write a file, creating parents as needed. Returns the file path."""
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ----------------------------
# get_project_name
# ----------------------------


def test_get_project_name_missing_returns_none(tmp_path: Path) -> None:
    assert get_project_name(tmp_path) is None


def test_get_project_name_reads_name(tmp_path: Path) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        textwrap.dedent(
            """
            [project]
            name = "cool-lib"
            """
        ),
    )
    assert get_project_name(tmp_path) == "cool-lib"


def test_get_project_name_bad_toml_returns_none(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", "[project\nname = 'oops'")
    assert get_project_name(tmp_path) is None


# ----------------------------
# get_analysis_mode
# ----------------------------


def test_get_analysis_mode_defaults_when_missing_file(tmp_path: Path) -> None:
    assert get_analysis_mode(tmp_path) == "library"


@pytest.mark.parametrize("mode", ["library", "application"])
def test_get_analysis_mode_valid_values(tmp_path: Path, mode: str) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        textwrap.dedent(
            f"""
            [tool."troml-dev-status"]
            mode = "{mode}"
            """
        ),
    )
    assert get_analysis_mode(tmp_path) == mode


def test_get_analysis_mode_invalid_value_falls_back_to_library(tmp_path: Path) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        textwrap.dedent(
            """
            [tool."troml-dev-status"]
            mode = "weird"
            """
        ),
    )
    assert get_analysis_mode(tmp_path) == "library"


def test_get_analysis_mode_bad_toml_returns_library(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", "[tool.'troml-dev-status']\nmode = ")
    assert get_analysis_mode(tmp_path) == "library"


# ----------------------------
# get_project_dependencies
# ----------------------------


def test_get_project_dependencies_missing_file_returns_none(tmp_path: Path) -> None:
    assert get_project_dependencies(tmp_path) is None


def test_get_project_dependencies_reads_list(tmp_path: Path) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        textwrap.dedent(
            """
            [project]
            name = "thing"
            dependencies = ["requests>=2", "pydantic==2.*"]
            """
        ),
    )
    assert get_project_dependencies(tmp_path) == ["requests>=2", "pydantic==2.*"]


def test_get_project_dependencies_bad_toml_returns_none(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", "[project]\ndependencies = [")
    assert get_project_dependencies(tmp_path) is None


# ----------------------------
# find_src_dir
# ----------------------------


def test_find_src_dir_prefers_src_folder(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    assert find_src_dir(tmp_path) == tmp_path / "src"


def test_find_src_dir_uses_project_name_dir(tmp_path: Path) -> None:
    # no src/, but package dir equals project name
    write(tmp_path, "pyproject.toml", '[project]\nname = "my-lib"\n')
    (tmp_path / "my-lib").mkdir()
    assert find_src_dir(tmp_path) == tmp_path / "my-lib"


def test_find_src_dir_converts_dash_to_underscore(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", '[project]\nname = "my-lib"\n')
    (tmp_path / "my_lib").mkdir()
    assert find_src_dir(tmp_path) == tmp_path / "my_lib"


def test_find_src_dir_returns_none_when_not_found(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", '[project]\nname = "abc"\n')
    assert find_src_dir(tmp_path) is None


# ----------------------------
# count_test_files
# ----------------------------


def test_count_test_files_handles_both_patterns(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    write(tmp_path, "tests/test_alpha.py", "def test_a(): pass")
    write(tmp_path, "tests/beta_test.py", "def test_b(): pass")
    write(tmp_path, "tests/not_a_test.txt", "")
    assert count_test_files(tmp_path) == 2


def test_count_test_files_missing_dir_returns_zero(tmp_path: Path) -> None:
    assert count_test_files(tmp_path) == 0


# ----------------------------
# count_source_modules
# ----------------------------


def test_count_source_modules_counts_recursive_and_skips_init(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "pkg" / "sub").mkdir(parents=True)
    write(tmp_path, "src/pkg/__init__.py", "")
    write(tmp_path, "src/pkg/mod1.py", "")
    write(tmp_path, "src/pkg/sub/mod2.py", "")
    write(tmp_path, "src/pkg/sub/notpy.txt", "")
    assert count_source_modules(src) == 2


def test_count_source_modules_returns_zero_for_missing(tmp_path: Path) -> None:
    assert count_source_modules(tmp_path / "nope") == 0


# ----------------------------
# CI config discovery
# ----------------------------


def test_get_ci_config_files_finds_github_and_gitlab(tmp_path: Path) -> None:
    gh_yml = write(tmp_path, ".github/workflows/ci.yml", "name: CI")
    gh_yaml = write(tmp_path, ".github/workflows/lint.yaml", "name: Lint")
    gl = write(tmp_path, ".gitlab-ci.yml", "stages: [test]")
    files = get_ci_config_files(tmp_path)
    # Order not guaranteed; compare as sets of relative paths
    assert {f.relative_to(tmp_path) for f in files} == {
        gh_yml.relative_to(tmp_path),
        gh_yaml.relative_to(tmp_path),
        gl.relative_to(tmp_path),
    }


def test_has_multi_python_in_ci_true_when_two_versions_present(tmp_path: Path) -> None:
    f1 = write(
        tmp_path,
        ".github/workflows/ci.yml",
        "strategy:\n  matrix:\n    python-version: ['3.10', '3.11']\n",
    )
    assert has_multi_python_in_ci([f1]) is True


def test_has_multi_python_in_ci_false_when_zero_or_one_version(tmp_path: Path) -> None:
    f1 = write(tmp_path, ".gitlab-ci.yml", "image: python:3.11")
    assert has_multi_python_in_ci([f1]) is False
    f2 = write(tmp_path, ".github/workflows/ci.yml", "name: CI")
    assert has_multi_python_in_ci([f2]) is False


# ----------------------------
# analyze_type_hint_coverage
# ----------------------------


def test_analyze_type_hint_coverage_counts_public_return_annotations(
    tmp_path: Path,
) -> None:
    src = tmp_path / "srcpkg"
    src.mkdir()
    write(
        tmp_path,
        "srcpkg/a.py",
        textwrap.dedent(
            """
            def f1(x):  # public, no return annotation -> not counted as annotated
                return x

            def f2(x) -> int:  # public, has return annotation -> annotated
                return 1

            def _private(x) -> int:  # private, should not be counted at all
                return 0
            """
        ),
    )
    write(
        tmp_path,
        "srcpkg/b.py",
        textwrap.dedent(
            """
            async def f3() -> str:  # public async with return annotation
                return "ok"

            def f4(y: int):  # public, param annotated only, no return -> not annotated
                return y
            """
        ),
    )
    coverage, total = analyze_type_hint_coverage(src)
    # Public symbols: f1, f2, f3, f4 => total = 4
    # Annotated by rule (return present): f2, f3 => 2/4 = 50%
    assert total == 4
    assert pytest.approx(coverage, rel=1e-6) == 50.0


def test_analyze_type_hint_coverage_handles_syntax_errors_and_empty(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    write(tmp_path, "src/bad.py", "def broken(:\n    pass")
    coverage, total = analyze_type_hint_coverage(src)
    assert total == 0
    assert coverage == 0.0


# ----------------------------
# get_bureaucracy_files
# ----------------------------


# def test_get_bureaucracy_files_matches_exact_patterns(tmp_path: Path) -> None:
#     # Only exact lowercase names with .md according to current implementation
#     _f1 = write(tmp_path, "security.md", "# sec")
#     _f2 = write(tmp_path, "contributing.md", "# contrib")
#     _f3 = write(tmp_path, "code_of_conduct.md", "# coc")
#     # Similar but should NOT match with current logic:
#     write(tmp_path, "SECURITY.md", "# nope")
#     write(tmp_path, "Contributing.MD", "# nope")
#     write(tmp_path, "CODE_OF_CONDUCT", "# nope")
#     found = {p.name for p in get_bureaucracy_files(tmp_path)}
#     # code should be case insentive or it will only be linux compatible.
#     assert found == {
#         'Contributing.MD',
#              'SECURITY.md',
#         "security.md", "contributing.md", "code_of_conduct.md"}
