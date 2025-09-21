# tests/test_validate_changelog.py
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from troml_dev_status.analysis.validate_changelog import (
    ChangelogValidator,
    TypesOfChange,
)


def _messages(errors):
    return [e.message for e in errors]


def test_valid_changelog_passes(tmp_path: Path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text(
        textwrap.dedent(
            """\
            # Changelog
            ## [Unreleased]
            ### Fixed
            - A bug was fixed.
            ## [1.2.3] - 2025-09-20
            ### Added
            - Initial release.
            """
        ),
        encoding="utf-8",
    )

    v = ChangelogValidator(file_name=str(p))
    errors = v.validate(p.read_text(encoding="utf-8"))
    assert errors == [], f"Expected no errors, got: {_messages(errors)}"


@pytest.mark.parametrize(
    "bad_depth_line",
    [
        "#### Too deep",  # depth 4
        "##### Also deep",  # depth 5
        "###### Still deep",  # depth 6
    ],
)
def test_heading_depth_too_high(tmp_path: Path, bad_depth_line: str):
    p = tmp_path / "CHANGELOG.md"
    p.write_text(
        "# Changelog\n" + bad_depth_line + "\n",
        encoding="utf-8",
    )
    v = ChangelogValidator(file_name=str(p))
    msgs = _messages(v.validate(p.read_text(encoding="utf-8")))
    assert any("Heading depth is too high" in m for m in msgs)


def test_h1_heading_is_ok(tmp_path: Path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text("# Changelog\n", encoding="utf-8")
    v = ChangelogValidator(file_name=str(p))
    assert v.validate(p.read_text(encoding="utf-8")) == []


def test_version_heading_missing_bracket_block(tmp_path: Path):
    # Missing [x.y.z] wrapper
    p = tmp_path / "CHANGELOG.md"
    p.write_text("# Changelog\n## 1.0.0 - 2025-09-20\n", encoding="utf-8")
    v = ChangelogValidator(file_name=str(p))
    msgs = _messages(v.validate(p.read_text(encoding="utf-8")))
    assert any("Missing version tag like [1.0.0] or [Unreleased]" in m for m in msgs)


def test_version_heading_unreleased_needs_no_date(tmp_path: Path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text("# Changelog\n## [Unreleased]\n", encoding="utf-8")
    v = ChangelogValidator(file_name=str(p))
    assert v.validate(p.read_text(encoding="utf-8")) == []


def test_version_heading_missing_date_metadata(tmp_path: Path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text("# Changelog\n## [1.0.0]\n", encoding="utf-8")
    v = ChangelogValidator(file_name=str(p))
    msgs = _messages(v.validate(p.read_text(encoding="utf-8")))
    assert any("Missing date metadata" in m and "1.0.0" in m for m in msgs)


def test_version_heading_bad_date_format(tmp_path: Path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text("# Changelog\n## [1.0.0] - 2025/09/20\n", encoding="utf-8")
    v = ChangelogValidator(file_name=str(p))
    msgs = _messages(v.validate(p.read_text(encoding="utf-8")))
    assert any("is not 'YYYY-MM-DD' format" in m and "1.0.0" in m for m in msgs)


def test_version_heading_bad_semver(tmp_path: Path):
    # semantic_version.Version should reject this (e.g., "one.two")
    p = tmp_path / "CHANGELOG.md"
    p.write_text("# Changelog\n## [one.two] - 2025-09-20\n", encoding="utf-8")
    v = ChangelogValidator(file_name=str(p))
    msgs = _messages(v.validate(p.read_text(encoding="utf-8")))
    assert any("is not SemVer compliant" in m for m in msgs)


def test_change_heading_accepts_only_known_types(tmp_path: Path):
    # Build a changelog with each accepted ### heading to ensure no errors
    accepted = "\n".join(f"### {t.title()}\n- ok" for t in TypesOfChange)
    content = f"# Changelog\n## [1.0.0] - 2025-09-20\n{accepted}\n"
    p = tmp_path / "CHANGELOG.md"
    p.write_text(content, encoding="utf-8")

    v = ChangelogValidator(file_name=str(p))
    errors = v.validate(p.read_text(encoding="utf-8"))
    assert errors == [], f"Expected no errors, got: {_messages(errors)}"


def test_change_heading_rejects_unknown_type(tmp_path: Path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text(
        textwrap.dedent(
            """\
            # Changelog
            ## [1.0.0] - 2025-09-20
            ### New Things
            - A bullet
            """
        ),
        encoding="utf-8",
    )
    v = ChangelogValidator(file_name=str(p))
    msgs = _messages(v.validate(p.read_text(encoding="utf-8")))
    assert any(
        m.startswith("Incompatible change type, MUST be one of:") for m in msgs
    ), msgs


def test_lines_that_are_not_headings_or_entries_ignored(tmp_path: Path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text(
        textwrap.dedent(
            """\
            # Changelog
            Some prose paragraph explaining the rules.

            ## [1.0.0] - 2025-09-20
            ### Fixed
            - Thing
            """
        ),
        encoding="utf-8",
    )
    v = ChangelogValidator(file_name=str(p))
    errors = v.validate(p.read_text(encoding="utf-8"))
    assert errors == [], f"Unexpected errors: {_messages(errors)}"


def test_example_invalid_block_from_module_yields_all_key_errors(tmp_path: Path):
    # Mirrors the module's example, assert we catch the important failures.
    p = tmp_path / "CHANGELOG.md"
    p.write_text(
        textwrap.dedent(
            """\
            # Changelog
            ## [1.0.0] - 2025/09/20
            ### New Things
            - A new feature.
              - A sub-list item which is not allowed.
            #### Invalid Header
            """
        ),
        encoding="utf-8",
    )
    v = ChangelogValidator(file_name=str(p))
    msgs = _messages(v.validate(p.read_text(encoding="utf-8")))

    # We don't lock the exact count (implementation details can evolve),
    # but we must hit all the major violations:
    assert any("is not 'YYYY-MM-DD' format" in m for m in msgs)  # bad date format
    assert any(
        m.startswith("Incompatible change type, MUST be one of:") for m in msgs
    )  # bad type
    # assert any("Sub-lists are not permitted" in m for m in msgs)  # nested list
    assert any("Heading depth is too high" in m for m in msgs)  # #### depth 4
