Here’s a refinement that replaces the historical API-diff approach with **point-in-time static indicators** and introduces a new **Completeness metric**. This avoids the unrealistic demand to evaluate API churn across history while still rewarding projects that show stability and intentional API design.

---

## Alternative API Stability Rubric (Point-in-Time)

Instead of diffing across releases, evaluate the **API stability signals** visible in the latest snapshot of the codebase:

**A1. Explicit API surface (`__all__`).**

* Pass if the top-level package and ≥50% of public modules define a non-empty `__all__`. This indicates an intentional, bounded public API.

**A2. Semantic versioning alignment.**

* Pass if the latest release version ≥1.0.0, or if a `VERSION` constant (or equivalent) exists and follows \[PEP 440].

**A3. Deprecation practices.**

* Pass if at least one of:

  * `DeprecationWarning` usage in code,
  * A `DEPRECATED` section in CHANGELOG,
  * Inline docstring markers (`.. deprecated::`).

**A4. API surface documentation.**

* Pass if ≥70% of modules/classes/functions have docstrings, **or** autodoc-ready structure exists in Sphinx/MkDocs config.

**A5. Namespacing hygiene.**

* Fail if package exports ≥10% names starting with `_` that are re-exported in `__all__` (leaky internals).

This rubric focuses on whether the project **signals intentional stability** and **documents its boundaries**, without requiring comparison to the past or prediction of the future.

---

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

---

## Integration into Status Mapping

* For **Beta and higher**, require **Completeness ≥3/5**.
* For **Production**, require **Completeness ≥4/5**.
* For **Mature**, require **Completeness = 5/5**.

This ensures that beyond packaging/docs/CI, the project is actually *implemented* and not riddled with TODOs.
