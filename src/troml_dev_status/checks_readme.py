from __future__ import annotations

import os
from pathlib import Path

# import from your vendored/package install of readme_rater
from readme_rater.rater import rate_readme
from readme_rater import rubric
from troml_dev_status.models import CheckResult

_MIN_SCORE = int(os.getenv("READMERATER_MIN_SCORE", "70"))
_FULL_REFRESH = os.getenv("READMERATER_FULL_REFRESH", "0") == "1"
_STRICT = os.getenv("READMERATER_STRICT", "1") == "1"


def check_q8_readme_complete(repo_path: Path, *, use_ai: bool) -> CheckResult:
    """
    Evaluate README quality via readme_rater.
    Pass if overall_score_numeric >= _MIN_SCORE.
    If use_ai is False, this check will pass with a note if a README exists.
    """
    readme_path = next(repo_path.glob("README*"), None)
    if not (readme_path and readme_path.is_file()):
        return CheckResult(passed=False, evidence="No README found.")

    content = readme_path.read_text(encoding="utf-8").strip()
    if not content:
        return CheckResult(passed=False, evidence="README is empty.")

    if not use_ai:
        return CheckResult(
            passed=True,
            evidence="README exists. AI-based rating is disabled via configuration.",
        )

    try:
        rating = rate_readme(content, full_refresh=_FULL_REFRESH)
        score = rating.overall_score_numeric
        label = rating.overall_score

        core_pass = sum(
            1
            for r in rating.rubric_results
            if r.id in rubric.CORE and r.status == "pass"
        )
        core_total = sum(
            1 for r in rating.rubric_results if r.id in rubric.CORE and r.status != "na"
        )
        extra_pass = sum(
            1
            for r in rating.rubric_results
            if r.id in rubric.EXTRA and r.status == "pass"
        )

        failed = ", ".join(
            r.id
            for r in rating.rubric_results
            if r.id in rubric.CORE and r.status == "fail"
        )

        evidence = (
            f"readme_rater score={score} ({label}); "
            f"core {core_pass}/{core_total} passed; extra {extra_pass}/{len(rubric.EXTRA)} passed. "
            f"threshold={_MIN_SCORE}"
        )
        if failed:
            evidence += f"Need to improve: {failed}"
        return CheckResult(passed=(score >= _MIN_SCORE), evidence=evidence)

    except Exception as e:
        # Deterministic fallback behavior
        if _STRICT:
            return CheckResult(
                passed=False,
                evidence=f"LLM rating failed: {e.__class__.__name__}. Set READMERATER_STRICT=0 to degrade.",
            )
        return CheckResult(
            passed=True,
            evidence=f"README exists; LLM unavailable ({e.__class__.__name__}); degraded pass.",
        )
