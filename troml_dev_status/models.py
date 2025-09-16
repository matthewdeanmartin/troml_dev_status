# troml_dev_status/models.py

from __future__ import annotations

from datetime import datetime
from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field


class CheckResult(BaseModel):
    """Represents the outcome of a single objective check."""

    passed: bool
    evidence: str


class Metrics(BaseModel):
    """A collection of quantifiable data points gathered during analysis."""

    eps_score: Optional[int] = None
    eps_total: Optional[int] = None
    public_symbols_latest: Optional[int] = None
    public_symbols_previous: Optional[int] = None
    removed_symbols_percent: Optional[float] = None
    tests_count: Optional[int] = None
    src_modules_count: Optional[int] = None
    type_annotation_coverage: Optional[float] = None
    readme_word_count: Optional[int] = None


class EvidenceReport(BaseModel):
    """The final, comprehensive report produced by the tool."""

    inferred_classifier: str
    reason: str
    project_name: str
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    checks: Dict[str, CheckResult]
    metrics: Metrics
    # For future use, not fully implemented in this sketch
    overrides: Dict[Literal["inactive"], bool] = {"inactive": False}
