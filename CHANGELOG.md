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

## [0.4.1] - 9999-12-31

### Fixed

- Some checks iterate across .gitignored files
- Some new checks iterated root and not module folders

## [0.4.0] - 2025-09-20

### Added

- Checks for near total incompleteness - app is empty or incapable of running.

### Changed

- Logic for evaluation makes it possible to get production status.
- Unknown status shouldn't occur at all or at least not often.

## [0.3.1] - 2025-09-20

### Added

- New output formats.

### Fixed

- Bugs related to poetry config, setup.cfg, counting files in .venv, null safety

## [0.3.0] - 2025-09-20

### Added

- Implemented changelog validates - q9
- Implemented README complete - q8
- Implemented Declares dunder-all - s1
- Nothing reports NotImplemented now

### Changed

- More rules implemented so scale changed.

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