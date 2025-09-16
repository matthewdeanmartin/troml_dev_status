# PEP XXXX — A Fully-Objective Rubric for Inferring “Development Status :: X – …” from Code & Release Artifacts

| PEP          | XXXX                                                        |
|--------------|-------------------------------------------------------------|
| Title        | A fully-objective rubric for Development Status classifiers |
| Author       | you + tool authors (TBD)                                    |
| Status       | Draft                                                       |
| Type         | Standards Track                                             |
| Created      | 2025-09-14                                                  |
| Requires     | None                                                        |
| Post-History | N/A                                                         |

## Abstract

This PEP defines a **objective** method to **infer** one of the canonical PyPI “Development Status :: X – …”
classifiers for a Python project **exclusively from code, version control history, and published release artifacts**
—with **no reliance on maintainer statements, intentions, or “vibes.”** at the time of package publication.

The rubric is deterministic, based on verifiable checks. It treats “Planning / Pre-Alpha / Alpha / Beta” as **counted
checkboxes**, “Production/Stable” as **all-checks-passed product maturity**, “Mature” as **time-tested production**, and
“Inactive” as **publication and maintenance SLA failures**—never on whether a repository is read-only or whether
maintainers feel done. Inactive implies the last publication and is not a metric of release tempo.

This PEP does **not** change Trove Classifier semantics managed by PyPI; it specifies a **repeatable algorithm** that
tools may use to recommend a classifier.

## Motivation

Trove development-status classifiers are self-declared and often ambiguous. Teams, users, and automated systems benefit
from an **evidence-based, reproducible** inference that:

* Works **only** from code and published artifacts.

* Is **independent** of maintainers’ subjective claims or current life situation.

* Yields a classifier that **matches measurable software maturity**.

## Scope & Non-Goals

* **In scope:** Rules that derive a status from Git history, tags, diffs, static analysis of code/docs/config, and *
  *PyPI releases** (sdist/wheels and metadata).

* **Out of scope:** Popularity metrics (stars/forks), issue triage, discussion forums, “is it good?”, or running tests
  in CI. (We may **discover** tests exist; we do **not** need to *execute* them.)

## Definitions (Objective Signals)

All dates/times are UTC; “now” is the evaluation timestamp.

We assume access to:

* The Git repository (default branch).

* The project’s **PyPI project name** (via `pyproject.toml [project].name` or `setup.cfg`).

* Published artifacts and metadata for the latest release on PyPI.

We compute the following **checks**. Each check is a yes/no derived from code or release artifacts. If a check is “not
applicable,” count it as **failed** (objective pressure to provide evidence).

### Release & Packaging

**R1. Published at least once:** At least **one** release (any version) exists on PyPI.

**R2. Wheel + sdist present:** Latest PyPI release contains **both** a wheel and an sdist.

**R3. PEP 440 versioning:** All release versions on PyPI are valid PEP 440; strictly increasing.

**R4. Recent activity:** A **release in the last 12 months** (365 days).

**R5. Python‐version declaration:** Latest release declares `Requires-Python` and has **at least one** trove classifier
for a specific Python version.

**R6. Current Python coverage:** Declared support includes **current-1** CPython minor (e.g., if current is 3.13,
supports ≥3.12).

**R7. Distribution health:** Source tree contains `pyproject.toml` with a build backend; and sdist includes
README/license files.

### CI, Tests, Types, Docs (Discoverability Only)

**Q1. CI config present:** A CI workflow file exists that runs on push/PR (e.g., `.github/workflows/*.yml`,
`.gitlab-ci.yml`, or similar).

**Q2. Multi-Python matrix:** CI config includes **≥2** distinct CPython minors.

**Q3. Tests present:** Repo contains ≥ **5** test files matching `test_*.py` or `*_test.py` under `tests/` or alongside
`src/`.

**Q4. Test/file ratio:** `(# test files) / (# public src modules)` ≥ **0.20** (count modules under `src/` or top-level
package excluding `__init__.py`).

**Q5. Type hints shipped:** Either `py.typed` present in package **or** ≥ **70%** of public functions/classes in `src/`
have type annotations (static count via AST).

**Q6. Docs present:** A `docs/` dir with Sphinx or MkDocs config (`conf.py` or `mkdocs.yml`) **or** README length ≥ *
*500 words** and includes an “Installation” section.

**Q7. CHANGELOG present:** `CHANGELOG*` (or `NEWS*`) exists with ≥ **3** dated entries.

### API Declaration

Define **public symbol** = any name in `__all__`, or not prefixed `_`, from modules under the top-level package.

**S1. Declares dunder-all:** Dunder-init has dunder-all. Ideally, all modules have dunder-all. Dunder-all can be empty.

## Completeness Metric

A measure of how much of the codebase is **implemented vs. stubbed**. Completeness provides insight into whether the project is actively filled out or mostly placeholders.

**Signals:**

* **Cmpl1. TODO/FIXME/BUG markers.** Count occurrences in code and docs. Fail if >5 markers per 1kLOC.

* **Cmpl2. NotImplemented usage.** Pass if <1% of functions/methods raise `NotImplementedError`. (Intentional abstract base classes may whitelist exceptions.)

* **Cmpl3. Placeholder `pass`.** Pass if <5% of functions/methods are only `pass`. (Allow pass in class definitions for style.)

* **Cmpl4. Stub files.** Fail if >10% of discovered `.py` files contain only stubs (e.g., <10 lines of code, mostly comments/`pass`).

* **Cmpl5. Functionality coverage.** Pass if `tests/` exercises ≥50% of public modules (measured by import and symbol reference, not runtime coverage).

**Completeness Score (0–5):** Sum of signals passed.

Projects with low Completeness scores are objectively less likely to be usable, regardless of stated ambitions.


### Deprecation Hygiene (Static)

**D1. Deprecation policy evidence:** Presence of **either**:

* `CHANGELOG` entries containing headings “Deprecated”/“Removed” with itemized entries, **or**

* `warnings.warn(..., DeprecationWarning)` in code committed **before** the removal release.

### Security & Supply Chain

**C1. SECURITY.md present:** `SECURITY.md` exists in repo root.

**C2. Trusted Publisher:** Latest package is published using pypi's trusted publisher feature.

**C3. Minimal pin sanity:** Runtime dependencies in `pyproject.toml` avoid bare unconstrained `*`; each has at least a
lower bound (e.g., `>=`).

**C4. Repro inputs:** A lockfile is present for dev tooling (any of: `uv.lock`, `poetry.lock`, `requirements*.txt`) **or
** a `constraints.txt`.

### Maintenance Age & Cadence

**M1. Project age:** Time since **first PyPI release** ≥ **90 days**.

**M2. Code motion:** At least **one** commit touching `src/` (or package dir) in last **365** days.

**M3. Mature grace:** For “Mature” evaluation, see thresholds below.


> **Note:** All checks are **objective**: they do not require executing code or tests; they rely on static files, Git
> metadata, release metadata, and tag signatures.

## Status Mapping

A project **must** satisfy **R1** (at least one PyPI release) to be classifiable at all. (Rationale: classifiers are
most visible/meaningful in published distributions.)

When “Inactive” conditions are met, “Inactive” **overrides** all other computations.

### Inactive (override)

If you publish a package on pypi, it is active again. By definition, a just published packages is active again. You
can't update a trove classifier without republishing a package. Inactive at best, is a signal that this is the last
planned package ever. No static code analysis can determine the future or intentions of the maintainer. If a package 
has no new versions for 100 years and a new package is published, maybe it will be published daily from then on, no
one can tell from past history. If anything, a revived package wouldn't want to signal inactivity if it were to revive.

### Production/Stable

Classify as **Development Status :: 5 – Production/Stable** iff **all** of the following pass:

* **Release/packaging:** R1–R7

* **Quality discoverability:** Q1–Q7

* **API stability:** S1–S2 (or S3 if <1.0, see note below)

* **Deprecation hygiene:** D1

* **Security/supply chain:** C1–C4

* **Maintenance:** M1–M2, and **R4 within 12 months**

* **Completeness** ≥4/5 must pass.

> **Note on <1.0 “stable”:** If latest release is `<1.0`, you **cannot** be Production/Stable; require `>=1.0.0`. (
> Objective, simple to verify.)



### Mature

Classify as **Development Status :: 6 – Mature** iff **Production/Stable** passes **and**:

* **First 1.0.0** (or higher) was **≥ 24 months** ago, **and**

* Over the last **18 months** of releases, **S2** holds (no breaking API between minor versions), **and**

* Release cadence may slow: **R4 within 24 months** (instead of 12) **but** M2 still within **12 months** (someone
  touched code/docs/metadata).

### Planning / Pre-Alpha / Alpha / Beta (checkbox counts)

For “early” statuses, we use counts of the same objective checks. Define the **Early-Phase Score (EPS)** as the number
of checks passed in this set:

`EPS_SET = {R2,R3,R5,R6,R7,Q1,Q2,Q3,Q4,Q5,Q6,Q7,S1,S3,D1,C1,C3,C4,M1}`

* **Planning (1):** R1 passes, and **EPS ∈ \[0, 3]**, and latest version `<0.1.0`.

* **Pre-Alpha (2):** R1 passes, and \*\*EPS ∈ \[4, 6]`, version `<0.1.0\`.

* **Alpha (3):** R1 passes, and \*\*EPS ∈ \[7, 11]`, version `<1.0.0\`.

* **Beta (4):** R1 passes, and \*\*EPS ∈ \[12, |EPS\_SET|]`, version `<1.0.0\`, and **S3** holds (pre-1.0 churn ≤ 20%)
  and **R4 within 12 months**.  Must pass ≥3/5 of completeness tests.

> Rationale: Early phases are expressed as **how many boxes you’ve objectively checked**. Beta adds an extra guard for
> manageable API churn and current activity.

### Tie-Breaking & Unknown

* If a project fails **R1** (no PyPI release), it is **Planning**.

## Algorithm (Deterministic)

1. **Discover project name** from `pyproject.toml` / `setup.cfg`.

2. **Fetch PyPI releases** and artifacts; compute R1–R7, R4 windowed for 12 and 24 months.

3. **Read Git history** (default branch) to compute M2, tag signatures for C2.

4. **Parse repo** to compute Q1–Q7, D1, C1, C3–C4, S1–S3 (using AST across two releases).

5. **Apply Inactive override.**

6. If not Inactive, check **Production**; if passes, then evaluate **Mature**.

7. If not Production/Mature, compute **EPS** and map to Planning/Pre-Alpha/Alpha/Beta.

8. Return: **classifier** + **evidence report** (which checks passed/failed, with file/commit/release references).

## Reference “Evidence” Report (Normative Format)

Tools **must** produce a machine-readable JSON and a human summary:

```json

{
  "inferred_classifier": "Development Status :: 4 - Beta",
  "evaluated_at": "2025-09-14T15:00:00Z",
  "checks": {
    "R1": {
      "pass": true,
      "evidence": "pypi: mypkg 0.9.3"
    },
    "R2": {
      "pass": true,
      "evidence": "wheel+sdist present for 0.9.3"
    },
    "...": {}
  },
  "overrides": {
    "inactive": false
  },
  "metrics": {
    "public_symbols_latest": 182,
    "removed_symbols_pct": 8.2,
    "tests_count": 41,
    "src_modules_count": 150
  }
}

```

The human summary must list **why** the final state was chosen (e.g., “Beta: EPS=14; <1.0; pre-1.0 churn 8% (≤20%); last
release 4 months ago”).

## Backwards Compatibility

This PEP does **not** change Trove classifiers themselves. It specifies an **inference** method that tooling can
implement; maintainers remain free to declare any classifier.

## Reference Implementation (Sketch)

* **Release data:** `pip index versions`, or JSON API `https://pypi.org/pypi/<name>/json`.

* **Wheel/sdist structure:** Download and inspect metadata; validate `Requires-Python`, classifiers.

* **Repo parse:** Use `git` to enumerate tags, commits; parse source via `ast` to extract public API.

* **API diff:** Build symbol maps (module → {names → signatures}) per release; compute removal/compat deltas.

* **Type coverage:** Count annotated functions/classes (presence of type annotations in AST).

* **Docs/CI detection:** Static presence checks for configs and docs.

* **Security bits:** Check `SECURITY.md`; use trusted publisher.

* **Constraints:** Never run code; only static inspection.

## Security Considerations

* Do not execute downloaded artifacts or repo code.

* Verify downloaded files’ hashes; prefer PyPI’s hashes.

## Rationale & Alternatives

* “Inactive” is defined by **time since last release**, **lack of code motion**, and **outdated Python support**—not
  repo “archival” or sentiment.

* “Production” is intentionally strict: it demands robust packaging, docs, CI, API stability hygiene, and supply-chain
  signals—**all demonstrably present in the code/release**.

* Early statuses are **pure checkbox counts**, per the request, with explicit, testable thresholds.

## Appendix A — Exact Thresholds (for clarity)

* **Recent release window:** 12 months (Production/Beta) / 24 months (Mature acceptable).

* **API churn thresholds:** ≤5% removals for S1; 0% removals for S2 (≥1.0); ≤20% removals for S3 (<1.0).

* **Test ratio:** ≥0.20.

* **Type hints:** ≥70% public objects annotated (function/method params & returns).

* **README length:** ≥500 words and contains case-insensitive heading “Installation”.

* **Project age:** ≥90 days since first PyPI release for M1.

* **Trusted Publisher:** Latest release tag must use trusted-publisher; inability to verify counts as fail.

---


App will

* runs these checks,

* emits the JSON evidence + a neat table,
