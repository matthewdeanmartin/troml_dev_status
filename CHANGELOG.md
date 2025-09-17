# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

- Added for new features.
- Changed for changes in existing functionality.
- Deprecated for soon-to-be removed features.
- Removed for now removed features.
- Fixed for any bug fixes.
- Security in case of vulnerabilities.

## [0.2.0] - 2025-09-16

### Changed

- Default command is gone, now must use `troml-dev-status analyze .` to analyze current project.
- API stability rubric mostly gone.
- Rubric changed from credits for git signature to pypi attestations
- Tool will no longer ever rate project as "Development Status :: 7 - Inactive"

### Added

- Current python support logic is better
- New rubric for completeness based on TODO and NotImplemented signals

### Fixed

- Fixed grid which couldn't handle emoji width.

## [0.1.0] - 2025-09-15

### Added

- Many things work. `troml-dev-status .` will rate your code.