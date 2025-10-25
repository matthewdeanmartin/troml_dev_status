"""Data models for rubric items, ratings, and application state."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# The status of a single rubric check.
RubricStatus = Literal["pass", "fail", "na"]


class RubricItem(BaseModel):
    """Represents the result of a single rubric item evaluation."""

    id: str = Field(..., description="The unique identifier of the rubric item.")
    status: RubricStatus = Field(
        "fail", description="The status of the check (pass, fail, or n/a)."
    )
    advice: str = Field(
        "", description="Actionable advice for the user to improve this item."
    )


class Rating(BaseModel):
    """Represents the overall rating of a README file."""

    overall_score: str = Field(
        ..., description="Qualitative label for the score (e.g., 'Good')."
    )
    overall_score_numeric: int = Field(
        ..., ge=0, le=100, description="The numeric score from 0 to 100."
    )
    last_checked_utc: str = Field(
        ..., description="ISO 8601 timestamp of when the check was performed."
    )
    readme_file_hash: str = Field(
        ..., description="The SHA256 hash of the README content that was rated."
    )
    rubric_results: list[RubricItem] = Field(
        ..., description="A list of all the individual rubric item results."
    )


class State(BaseModel):
    """
    Models the data stored in the .cache/state.json file for convergence.
    """

    readme_file_hash: str
    rubric_results: list[RubricItem]
    score: int
    updated: str