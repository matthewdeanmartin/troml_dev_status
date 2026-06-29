# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `validate`/`update` `--allow-first-release` flag (and `[tool.troml-dev-status] allow_first_release`) to infer from code quality instead of flooring to Planning when a project has no PyPI releases yet

### Fixed

- No longer crashes on a `tests/` directory without `__init__.py` (unittest discovery `ImportError`)

## [0.6.1] - 2026-03-27

### Fixed

- Fix source finder failing to locate source folders in some layouts
- Pin dependency versions to improve reproducibility

## [0.6.0] - 2025-11-30

### Fixed

- Wheel did not include readme_rater, breaking the package

## [0.5.0] - 2025-10-27

### Added

- Readme Rater, an LLM-based rater; opt-in, has no effect unless an API key is present

### Fixed

- Failed to detect py.typed correctly in multi-module /src/ layouts

### Removed

- NLP style README rating removed because it did not produce reliable results

## [0.4.2] - 2025-10-02

### Fixed

- Better fallback when a status would be unknown

## [0.4.1] - 2025-09-22

### Fixed

- Replace stray `print` call in test finder with a proper `logger.debug` message
- Fix incorrect venv-mode flag assignment in `get_analysis_mode`
- Correct Pre-Alpha determination test to enforce completeness threshold properly
- Prevent some checks from iterating across .gitignored files
- Restrict new checks to module folders rather than the project root

## [0.4.0] - 2025-09-21

### Added

- Checks for near total incompleteness to detect apps that are empty or incapable of running

### Changed

- Logic for evaluation makes it possible to get production status
- Unknown status should no longer occur, or at least not often

## [0.3.1] - 2025-09-20

### Added

- New output formats

### Fixed

- Bugs related to poetry config, setup.cfg, counting files in .venv, null safety

## [0.3.0] - 2025-09-20

### Added

- Implement changelog validation check (q9)
- Implement README completeness check (q8)
- Implement declares dunder-all check (s1)
- Ensure nothing reports NotImplemented

### Changed

- More rules implemented, scale changed accordingly

## [0.2.0] - 2025-09-17

### Added

- Improve current Python support detection logic
- New rubric for completeness based on TODO and NotImplemented signals

### Changed

- Default command removed; use `troml-dev-status analyze .` to analyze the current project
- API stability rubric mostly removed
- Rubric changed from credits for git signature to PyPI attestations
- Tool will no longer ever rate a project as "Development Status :: 7 - Inactive"

### Fixed

- Fix grid display that could not handle emoji width

## [0.1.0] - 2025-09-16

### Added

- Initial release; `troml-dev-status .` will rate your code

[Unreleased]: https://github.com/matthewdeanmartin/troml_dev_status/compare/v0.6.1...HEAD
[0.6.1]: https://github.com/matthewdeanmartin/troml_dev_status/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/matthewdeanmartin/troml_dev_status/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/matthewdeanmartin/troml_dev_status/compare/v0.4.2...v0.5.0
[0.4.2]: https://github.com/matthewdeanmartin/troml_dev_status/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/matthewdeanmartin/troml_dev_status/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/matthewdeanmartin/troml_dev_status/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/matthewdeanmartin/troml_dev_status/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/matthewdeanmartin/troml_dev_status/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/matthewdeanmartin/troml_dev_status/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/matthewdeanmartin/troml_dev_status/releases/tag/v0.1.0
