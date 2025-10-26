# readme_rater/__init__.py
"""
readme-rater: Prescriptive Readme Quality Analysis via LLM.

This package provides a programmatic API and a command-line tool to rate
the quality of a README.md file based on the rubric defined in PEP 8001.
"""

from __future__ import annotations

from readme_rater.models import Rating, RubricItem, RubricStatus
from readme_rater.rater import rate_readme

__all__ = ["rate_readme", "Rating", "RubricItem", "RubricStatus"]
__version__ = "0.1.0"
