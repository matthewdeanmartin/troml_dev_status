"""
Implements the scoring logic and qualitative labeling from PEP 8001.
"""

from __future__ import annotations

from . import rubric
from .models import RubricItem


def compute_score(rubric_results: list[RubricItem]) -> int:
    """
    Computes the overall score based on the rubric results.

    The scoring system is weighted:
    - Core items contribute up to 80 points.
    - Extra credit items contribute up to 20 points.
    - The final score is capped at 100.
    - 'na' (not applicable) items are excluded from the denominator.

    Args:
        rubric_results: A list of evaluated rubric items.

    Returns:
        int: The final numeric score from 0 to 100.
    """
    core_items = [r for r in rubric_results if r.id in rubric.CORE and r.status != "na"]
    extra_items = [r for r in rubric_results if r.id in rubric.EXTRA]

    passed_core = sum(1 for item in core_items if item.status == "pass")
    passed_extra = sum(1 for item in extra_items if item.status == "pass")

    core_score = 0.0
    if core_items:
        core_score = (passed_core / len(core_items)) * 80

    extra_score = 0.0
    if rubric.EXTRA:
        # Note: All extra items are considered, even 'na' or 'fail',
        # in the denominator per the PEP's intent.
        extra_score = (passed_extra / len(rubric.EXTRA)) * 20

    total_score = round(core_score + extra_score)
    return min(100, total_score)


def qual_label(score: int) -> str:
    """
    Assigns a qualitative label to a numeric score.

    Args:
        score: The numeric score (0-100).

    Returns:
        str: The corresponding qualitative label.
    """
    if score < 40:
        return "Problematic"
    if score < 70:
        return "Needs Improvement"
    if score < 90:
        return "Good"
    return "Excellent"
