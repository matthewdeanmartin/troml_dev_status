# troml_dev_status/analysis/validate_changelog.py
"""
A standalone validator for changelog strings based on the 'Keep a Changelog' format.
"""

import datetime
import logging
import re
from typing import Iterable, List

import llvm_diagnostics
from semantic_version import Version

logger = logging.getLogger(__name__)

# --- Dependencies copied from change_types.py ---

UNRELEASED_ENTRY = "unreleased"
TypesOfChange = [
    "added",
    "changed",
    "deprecated",
    "removed",
    "fixed",
    "security",
]


class ChangelogValidator:
    """
    Validates a changelog string against the 'Keep a Changelog' standard.
    """

    def __init__(self, file_name: str = "in-memory-changelog.md"):
        """
        Initializes the validator.

        Args:
            file_name: A name to use in error messages for context.
        """
        self._file_name = file_name

    def validate(self, content: str) -> List[llvm_diagnostics.Error]:
        """
        Validates the changelog content from a string.

        Args:
            content: The full changelog file content as a string.

        Returns:
            A list of llvm_diagnostics.Error objects. The list is empty if validation succeeds.
        """
        errors = []
        lines = content.splitlines()

        for line_number, line in enumerate(lines, 1):
            errors.extend(list(self._validate_heading(line_number, line)))
            errors.extend(list(self._validate_entry(line_number, line)))

        return errors

    def _validate_change_heading(
        self, line_number: int, line: str, depth: int, content: str
    ) -> Iterable[llvm_diagnostics.Error]:
        """Check if acceptable change type keywords are present (e.g., ### Added)."""
        accepted_types = [change_type.title() for change_type in TypesOfChange]
        if content not in accepted_types:
            friendly_types = ", ".join(accepted_types)
            yield llvm_diagnostics.Error(
                file_path=self._file_name,
                line=line,
                line_number=llvm_diagnostics.Range(start=line_number),
                column_number=llvm_diagnostics.Range(
                    start=depth + 2, range=len(content)
                ),
                message=f"Incompatible change type, MUST be one of: {friendly_types}",
            )

    def _validate_version_heading(
        self, line_number: int, line: str, depth: int, content: str
    ) -> Iterable[llvm_diagnostics.Error]:
        """Check if a version heading is valid (e.g., ## [1.0.0] - 2025-09-20)."""
        match = re.compile(r"\[(.*)\](.*)").match(content)
        if not match:
            yield llvm_diagnostics.Error(
                file_path=self._file_name,
                line=line,
                line_number=llvm_diagnostics.Range(start=line_number),
                column_number=llvm_diagnostics.Range(
                    start=depth + 2, range=len(content)
                ),
                message="Missing version tag like [1.0.0] or [Unreleased]",
            )
            return

        version_str = match.group(1)
        if version_str.lower() == UNRELEASED_ENTRY:
            return

        try:
            Version(version_str)
        except ValueError:
            yield llvm_diagnostics.Error(
                file_path=self._file_name,
                line=line,
                line_number=llvm_diagnostics.Range(start=line_number),
                column_number=llvm_diagnostics.Range(
                    start=line.find("[") + 2, range=len(version_str)
                ),
                message=f"Version '{version_str}' is not SemVer compliant",
            )

        metadata_match = re.compile(r" - (.*)").match(match.group(2))
        if not metadata_match:
            yield llvm_diagnostics.Error(
                file_path=self._file_name,
                line=line,
                line_number=llvm_diagnostics.Range(start=line_number),
                column_number=llvm_diagnostics.Range(start=line.find("]") + 2),
                message=f"Missing date metadata ('- YYYY-MM-DD') for version '{version_str}'",
            )
            return

        release_date = metadata_match.group(1)
        try:
            datetime.datetime.strptime(release_date, "%Y-%m-%d")
        except ValueError:
            yield llvm_diagnostics.Error(
                file_path=self._file_name,
                line=line,
                line_number=llvm_diagnostics.Range(start=line_number),
                column_number=llvm_diagnostics.Range(
                    start=line.find(" - ") + 4, range=len(release_date)
                ),
                message=f"Release date for version '{version_str}' is not 'YYYY-MM-DD' format",
            )

    def _validate_heading(
        self, line_number: int, line: str
    ) -> Iterable[llvm_diagnostics.Error]:
        """Validate that a markdown heading is at a valid depth."""
        match = re.compile(r"^(#{1,6}) (.*)").match(line)
        if not match:
            return

        depth = len(match.group(1))
        content = match.group(2)

        if depth > 3:
            yield llvm_diagnostics.Error(
                file_path=self._file_name,
                line=line,
                line_number=llvm_diagnostics.Range(start=line_number),
                column_number=llvm_diagnostics.Range(start=1, range=depth),
                message="Heading depth is too high; MUST be 1, 2, or 3.",
            )
            return

        if depth == 2:
            yield from self._validate_version_heading(line_number, line, depth, content)
        elif depth == 3:
            yield from self._validate_change_heading(line_number, line, depth, content)

    def _validate_entry(
        self, line_number: int, line: str
    ) -> Iterable[llvm_diagnostics.Error]:
        """Validate that a changelog entry does not contain invalid nested elements."""
        match = re.compile(r"^\s*[-+*] (.*)").match(line)
        if not match:
            return

        entry_content = match.group(1)
        # Rule: Sub-lists are not permitted in changelog entries.
        if re.compile(r"^\s*[-+*] ").match(entry_content):
            yield llvm_diagnostics.Error(
                file_path=self._file_name,
                line=line,
                line_number=llvm_diagnostics.Range(start=line_number),
                column_number=llvm_diagnostics.Range(
                    start=line.find(entry_content) + 1
                ),
                message="Sub-lists are not permitted in changelog entries.",
            )


if __name__ == "__main__":
    # --- Example Usage ---

    # 1. A valid changelog string
    valid_changelog_string = """# Changelog
## [Unreleased]
### Fixed
- A bug was fixed.
## [1.0.0] - 2025-09-20
### Added
- Initial project release.
"""

    # 2. An invalid changelog string with multiple errors
    invalid_changelog_string = """# Changelog
## [1.0.0] - 2025/09/20
### New Things
- A new feature.
  - A sub-list item which is not allowed.
#### Invalid Header
"""

    validator = ChangelogValidator(file_name="../../CHANGELOG.md")

    print("--- 1. Validating a correct changelog ---")
    errors = validator.validate(valid_changelog_string)
    if not errors:
        print("✅ OK: No errors found.\n")
    else:
        for error in errors:
            error.report()

    print("\n--- 2. Validating an incorrect changelog ---")
    errors = validator.validate(invalid_changelog_string)
    if errors:
        print(f"❌ Found {len(errors)} error(s):")
        # The .report() method prints the fancy error format
        for error in errors:
            error.report()
    else:
        print("Validation passed unexpectedly.")
