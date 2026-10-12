# troml_dev_status/models.py

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CheckResult(BaseModel):
    """Represents the outcome of a single objective check."""

    passed: bool
    evidence: str


class Metrics(BaseModel):
    """A collection of quantifiable data points gathered during analysis."""

    eps_score: int | None = None
    eps_total: int | None = None
    public_symbols_latest: int | None = None
    # public_symbols_previous: Optional[int] = None
    # removed_symbols_percent: Optional[float] = None
    tests_count: int | None = None
    src_modules_count: int | None = None
    type_annotation_coverage: float | None = None
    readme_word_count: int | None = None


class EvidenceReport(BaseModel):
    """The final, comprehensive report produced by the tool."""

    inferred_classifier: str
    reason: str
    project_name: str
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    checks: dict[str, CheckResult]
    metrics: Metrics
