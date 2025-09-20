# The Rubric: Objective Checks

This page details every check performed by the tool. Each check is a yes/no question derived from objective evidence. If a check is not applicable, it is counted as **failed**.

---

## Release & Packaging

**R1. Published at least once:** At least **one** release (any version) exists on PyPI.

**R2. Wheel + sdist present:** The latest PyPI release contains **both** a wheel (`bdist_wheel`) and a source distribution (`sdist`).

**R3. PEP 440 versioning:** All release versions on PyPI are valid PEP 440 versions and are strictly increasing.

**R4. Recent activity:** A release has been published in the last **12 months**.

**R5. Python‐version declaration:** The latest release declares `Requires-Python` in its metadata and has at least one trove classifier for a specific Python version (e.g., `Programming Language :: Python :: 3.11`).

**R6. Current Python coverage:** Declared support includes the **current-1** CPython minor release. (e.g., if 3.13 is current, the package must declare support for at least 3.12).

---

## Quality (CI, Tests, Docs)

**Q1. CI config present:** A CI workflow file exists that runs on push/PR (e.g., `.github/workflows/*.yml`, `.gitlab-ci.yml`).

**Q2. Multi-Python matrix:** The CI configuration includes a test matrix with **at least 2** distinct CPython minor versions.

**Q3. Tests present:** The repository contains **at least 5** test files matching `test_*.py` or `*_test.py`.

**Q4. Test/file ratio:** The ratio of `(number of test files) / (number of public source modules)` is **at least 0.20**.

**Q5. Type hints shipped:** A `py.typed` marker file is present in the package, and **at least 70%** of public functions/classes are type-annotated.

**Q6. Docs present:** A `docs/` directory with Sphinx (`conf.py`) or MkDocs (`mkdocs.yml`) configuration exists, **OR** the `README` file is at least **500 words** long and includes an "Installation" section.

**Q7. CHANGELOG present:** A file named `CHANGELOG` or `NEWS` exists and contains at least **3** dated entries.

**Q8. Docs quality scored:** The `README` has common sections, a high school readability score, badges, and code examples.

---

## Completeness Metrics

**Cmpl1. TODO/FIXME/BUG markers:** Fewer than 5 `TODO`, `FIXME`, or `BUG` markers exist per 1000 lines of code.

**Cmpl2. NotImplemented usage:** Less than 1% of functions/methods raise `NotImplementedError`.

**Cmpl3. Placeholder `pass`:** Less than 5% of functions/methods consist only of a `pass` statement.

**Cmpl4. Stub files:** Less than 10% of `.py` files are classified as stubs (e.g., <10 lines of meaningful code).

---

## API & Deprecation

**S1. Declares dunder-all:** The project's root `__init__.py` (or other modules) explicitly defines an `__all__` variable to declare its public API.

**D1. Deprecation policy evidence:** The `CHANGELOG` contains "Deprecated" or "Removed" sections, **OR** the code uses `warnings.warn(..., DeprecationWarning)`.

---

## Security & Supply Chain

**C1. SECURITY.md present:** A `SECURITY.md` file exists in the repository root.

**C2. Trusted Publisher:** The latest package on PyPI was published using the Trusted Publisher feature.

**C3. Minimal pin sanity:** Runtime dependencies in `pyproject.toml` have at least a lower version bound (e.g., `requests>=2.0`) and are not bare names (`requests`).

**C4. Repro inputs:** A lockfile for reproducible development is present (e.g., `uv.lock`, `poetry.lock`, `requirements*.txt`).

---

## Maintenance

**M1. Project age:** The time since the **first PyPI release** is at least **90 days**.

**M2. Code motion:** At least **one** commit has touched the primary source directory (e.g., `src/`) in the last **365 days**.