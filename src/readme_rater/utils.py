"""Stateless helper functions for hashing and timestamps."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def now_utc() -> str:
    """
    Returns the current time in UTC as an ISO 8601 formatted string.

    Returns:
        str: The formatted UTC timestamp.
    """
    return datetime.now(timezone.utc).isoformat()


def norm_hash(content: str) -> str:
    """
    Computes a normalized SHA256 hash of a string.

    Normalization includes replacing Windows line endings (CRLF) with Unix
    endings (LF) and stripping leading/trailing whitespace before hashing.

    Args:
        content: The string content to hash.

    Returns:
        str: The 'sha256:' prefixed hex digest of the content.
    """
    normalized_content = content.replace("\r\n", "\n").strip()
    hasher = hashlib.sha256(normalized_content.encode("utf-8"))
    return f"sha256:{hasher.hexdigest()}"
