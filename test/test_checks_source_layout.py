from __future__ import annotations

from pathlib import Path

from troml_dev_status.checks import (
    check_c3_minimal_pin_sanity,
    check_q4_test_file_ratio,
    check_q5_type_hints_shipped,
    check_s1_all_exports,
)


def write(repo: Path, rel: str, content: str = "") -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_source_sensitive_checks_prefer_named_root_package_over_unrelated_src(
    tmp_path: Path,
) -> None:
    write(tmp_path, "pyproject.toml", '[project]\nname = "my-lib"\n')

    write(tmp_path, "src/native_speedups/__init__.py", "")
    write(tmp_path, "src/native_speedups/bridge.py", "VALUE = 1\n")

    write(tmp_path, "my_lib/__init__.py", '__all__ = ["run"]\n')
    write(tmp_path, "my_lib/py.typed", "")
    write(tmp_path, "my_lib/api.py", "def run() -> int:\n    return 1\n")
    for idx in range(10):
        write(
            tmp_path,
            f"my_lib/mod_{idx}.py",
            f"def f_{idx}() -> int:\n    return {idx}\n",
        )

    write(tmp_path, "tests/test_api.py", "def test_run():\n    assert True\n")

    q4 = check_q4_test_file_ratio(tmp_path)
    q5, coverage, total_symbols = check_q5_type_hints_shipped(tmp_path)
    s1 = check_s1_all_exports(tmp_path)

    assert q4.passed is False
    assert "my_lib" in q4.evidence
    assert q5.passed is True
    assert "my_lib" in q5.evidence
    assert "native_speedups" not in q5.evidence
    assert coverage == 100.0
    assert total_symbols == 11
    assert s1.passed is True
    assert "my_lib" in s1.evidence
    assert "__init__.py" in s1.evidence


def test_c3_application_mode_accepts_exact_mistune_range_example(
    tmp_path: Path,
) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        (
            "[project]\n"
            'name = "demo-app"\n'
            'dependencies = ["mistune>=2.0.0,<3.0.0"]\n'
        ),
    )

    result = check_c3_minimal_pin_sanity(tmp_path, "application")

    assert result.passed is True
    assert "version constraint" in result.evidence
    assert "not strictly pinned somehow" not in result.evidence


def test_c3_application_mode_still_rejects_unconstrained_dependencies(
    tmp_path: Path,
) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        (
            "[project]\n"
            'name = "demo-app"\n'
            'dependencies = ["mistune>=2.0.0,<3.0.0", "requests"]\n'
        ),
    )

    result = check_c3_minimal_pin_sanity(tmp_path, "application")

    assert result.passed is False
    assert "unconstrained dependencies" in result.evidence
    assert "requests" in result.evidence


def test_q5_reports_missing_top_level_packages(tmp_path: Path) -> None:
    result, coverage, total_symbols = check_q5_type_hints_shipped(tmp_path)

    assert result.passed is False
    assert "No top-level packages found" in result.evidence
    assert coverage == 0.0
    assert total_symbols == 0


def test_q5_requires_py_typed_in_detected_packages(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", '[project]\nname = "demo-lib"\n')
    write(tmp_path, "src/demo_lib/__init__.py", "")
    write(tmp_path, "src/demo_lib/api.py", "def run() -> int:\n    return 1\n")

    result, coverage, total_symbols = check_q5_type_hints_shipped(tmp_path)

    assert result.passed is False
    assert "py.typed required in packages" in result.evidence
    assert "demo_lib" in result.evidence
    assert coverage == 0.0
    assert total_symbols == 0


def test_s1_all_exports_fails_when_detected_package_has_no_all(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", '[project]\nname = "demo-lib"\n')
    write(tmp_path, "src/demo_lib/__init__.py", "")
    write(tmp_path, "src/demo_lib/api.py", "def run() -> int:\n    return 1\n")

    result = check_s1_all_exports(tmp_path)

    assert result.passed is False
    assert result.evidence == "No __all__ exports found in any module."
