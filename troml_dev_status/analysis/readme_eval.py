#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ---- optional dependency for readability -------------------------------------
try:
    import textstat  # type: ignore
except Exception:  # pragma: no cover
    textstat = None  # we'll handle gracefully


# ---- config ------------------------------------------------------------------

# Synonyms for sections we consider “expected”.
# Keys are canonical section slugs; values are lists of synonyms (case-insensitive).
SECTION_SYNONYMS: Dict[str, List[str]] = {
    # NOTE: No points for Installation (per user requirement),
    # but we still detect it so we can *avoid* rewarding it.
    "overview": [
        "overview",
        "description",
        "what is",
        "about",
        "introduction",
        "intro",
    ],
    "quickstart": ["quickstart", "quick start", "getting started", "start here"],
    "usage": [
        "usage",
        "how to use",
        "examples",
        "example",
        "tutorial",
        "demo",
        "cookbook",
    ],
    "api": ["api", "reference", "cli", "commands", "endpoints", "module reference"],
    "configuration": [
        "configuration",
        "config",
        "settings",
        "environment variables",
        "env vars",
    ],
    "testing": ["tests", "testing", "how to test", "running tests"],
    "contributing": ["contributing", "how to contribute", "development", "dev setup"],
    "license": ["license", "licence"],
    "status": ["status", "project status", "maturity", "roadmap"],
    "changelog": ["changelog", "release notes", "history", "news"],
    "security": ["security", "reporting security issues", "vulnerability disclosure"],
    "support": ["support", "help", "contact", "feedback", "questions", "q&a", "faq"],
    "installation": [
        "installation",
        "install",
        "pip install",
        "how to install",
    ],  # scored 0
}

# Weights (tweak to taste)
WEIGHTS = {
    "code_blocks_base_per_block": 0.5,  # any fenced block
    "code_blocks_python_bonus": 0.5,  # if lang is python
    "code_blocks_python_parses_bonus": 1.0,  # parses via ast
    "code_blocks_cap": 6.0,  # cap total code-block points
    "badges_per_badge": 0.5,
    "badges_cap": 4.0,
    # specific badge bonuses (in addition to per-badge)
    "badge_pypi": 0.5,
    "badge_ci": 0.5,
    "badge_coverage": 0.5,
    "badge_license": 0.5,
    # sections (per unique canonical section found)
    "section_present": 1.0,
    "sections_cap": 10.0,
    # readability (prefer HS or lower; more points for lower grades)
    # Points by FK grade bucket
    "readability_excellent": 3.0,  # grade <= 9
    "readability_good": 2.0,  # 9 < grade <= 12
    "readability_fair": 1.0,  # 12 < grade <= 14
    "readability_poor": 0.0,  # > 14 or unknown
    # extras
    "toc_present": 1.0,  # Table of contents
    "links_to_policy_files": 1.0,  # LICENSE / CONTRIBUTING / CODE_OF_CONDUCT linked
    "examples_with_code": 1.0,  # “usage/examples” section that actually contains a code block
    "python_version_info": 0.5,  # mentions Python version or shows a Python-version badge
    "extras_cap": 3.0,
}

# Badge URL patterns (simple heuristics)
BADGE_PATTERNS = [
    r"shields\.io",  # common badges
    r"badge\.",  # generic "badge."
    r"github\.com/.+?/actions",  # GitHub Actions status badge
    r"circleci\.com",  # CircleCI
    r"travis-ci\.com|travis-ci\.org",
    r"codecov\.io",
    r"coveralls\.io",
    r"readthedocs\.io",
    r"appveyor\.com",
    r"azure\.com/.+?/pipelines",
]

# Specific badge classifiers
SPECIFIC_BADGE_CHECKS: Dict[str, List[str]] = {
    "pypi": [r"pypi\.org", r"/pypi/v/"],
    "ci": [r"actions", r"travis", r"circleci", r"appveyor", r"azure.*pipelines"],
    "coverage": [r"codecov", r"coveralls"],
    "license": [r"/license", r"license-"],
}


# Simple slugifier for headings
def _slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s


@dataclass
class ScoreItem:
    key: str
    points: float
    max_points: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RubricResult:
    total: float
    max_possible: float
    items: List[ScoreItem]
    suggestions: List[str]


# ---- parsing helpers ---------------------------------------------------------

CODE_BLOCK_RE = re.compile(
    r"```(?P<lang>[a-zA-Z0-9_+-]*)\s*\n(?P<code>.*?)(?:\n)?```",
    re.DOTALL,
)

HEADING_RE = re.compile(r"^(#{1,6})\s+(?P<title>.+?)\s*$", re.MULTILINE)

IMAGE_LINK_RE = re.compile(r"!\[[^\]]*\]\((?P<url>[^)]+)\)")


def extract_code_blocks(md: str) -> List[Tuple[str, str]]:
    """Return list of (lang, code) for fenced blocks."""
    return [
        (m.group("lang").lower(), m.group("code")) for m in CODE_BLOCK_RE.finditer(md)
    ]


def extract_headings(md: str) -> List[str]:
    """Return list of heading titles as they appear (no #)."""
    return [m.group("title").strip() for m in HEADING_RE.finditer(md)]


def find_badge_urls(md: str) -> List[str]:
    """Return list of image URLs that look like badges."""
    urls: List[str] = []
    for m in IMAGE_LINK_RE.finditer(md):
        url = m.group("url")
        if any(re.search(p, url, flags=re.I) for p in BADGE_PATTERNS):
            urls.append(url)
    return urls


def heading_index(md: str) -> Dict[str, List[int]]:
    """Map of normalized heading text -> list of indices where they occur (by appearance order)."""
    titles = extract_headings(md)
    idx: Dict[str, List[int]] = {}
    for i, t in enumerate(titles):
        idx.setdefault(_slug(t), []).append(i)
    return idx


def contains_section(md: str, synonyms: Iterable[str]) -> bool:
    """Return True if any synonym appears as a heading title (case-insensitive)."""
    titles = extract_headings(md)
    norm_titles = [_slug(t) for t in titles]
    syn_slugs = {_slug(s) for s in synonyms}
    return any(t in syn_slugs for t in norm_titles)


def section_slice(md: str, section_syns: Iterable[str]) -> str | None:
    """Return content under a section heading (first match), up to next heading. For checks like code-in-examples."""
    titles = extract_headings(md)
    if not titles:
        return None
    [_slug(t) for t in titles]
    syn_slugs = {_slug(s) for s in section_syns}

    # Build positions (start index in string) of headings
    spans = [
        (m.start(), m.end(), m.group("title").strip()) for m in HEADING_RE.finditer(md)
    ]
    # Map index -> (start_pos, end_pos, title)
    by_order = list(spans)

    # find first heading that matches synonyms
    for i, (_, endpos, title) in enumerate(by_order):
        if _slug(title) in syn_slugs:
            # content is from end of this heading line to start of next heading (or end of doc)
            content_start = endpos
            content_end = by_order[i + 1][0] if i + 1 < len(by_order) else len(md)
            return md[content_start:content_end].strip()

    return None


# ---- individual scoring functions -------------------------------------------


def score_code_blocks(md: str) -> ScoreItem:
    blocks = extract_code_blocks(md)
    total = 0.0
    parsed_ok = 0
    py_blocks = 0
    for lang, code in blocks:
        total += WEIGHTS["code_blocks_base_per_block"]
        if lang == "python":
            py_blocks += 1
            total += WEIGHTS["code_blocks_python_bonus"]
            try:
                ast.parse(code)
            except Exception:  # nosec
                pass
            else:
                parsed_ok += 1
                total += WEIGHTS["code_blocks_python_parses_bonus"]

    total = min(total, WEIGHTS["code_blocks_cap"])
    return ScoreItem(
        key="code_blocks",
        points=total,
        max_points=WEIGHTS["code_blocks_cap"],
        details={
            "total_blocks": len(blocks),
            "python_blocks": py_blocks,
            "python_parsed_ok": parsed_ok,
        },
    )


def score_badges(md: str) -> ScoreItem:
    urls = find_badge_urls(md)
    points = min(len(urls) * WEIGHTS["badges_per_badge"], WEIGHTS["badges_cap"])

    # specific badge bonuses (only once per class)
    specific = {k: False for k in SPECIFIC_BADGE_CHECKS.keys()}
    for url in urls:
        for cls, pats in SPECIFIC_BADGE_CHECKS.items():
            if specific[cls]:
                continue
            if any(re.search(p, url, flags=re.I) for p in pats):
                specific[cls] = True

    bonus = 0.0
    if specific["pypi"]:
        bonus += WEIGHTS["badge_pypi"]
    if specific["ci"]:
        bonus += WEIGHTS["badge_ci"]
    if specific["coverage"]:
        bonus += WEIGHTS["badge_coverage"]
    if specific["license"]:
        bonus += WEIGHTS["badge_license"]

    points = min(points + bonus, WEIGHTS["badges_cap"])
    return ScoreItem(
        key="badges",
        points=points,
        max_points=WEIGHTS["badges_cap"],
        details={"count": len(urls), "specific": specific},
    )


def score_sections(md: str) -> ScoreItem:
    present: List[str] = []
    missing: List[str] = []

    for canonical, syns in SECTION_SYNONYMS.items():
        found = contains_section(md, syns)
        # Zero points for installation (per requirements)
        if canonical == "installation":
            if found:
                # record as present but no points
                present.append(canonical + " (0 pts)")
            else:
                missing.append(canonical)
            continue

        if found:
            present.append(canonical)
        else:
            missing.append(canonical)

    pts = (
        len([p for p in present if not p.endswith("(0 pts)")])
        * WEIGHTS["section_present"]
    )
    pts = min(pts, WEIGHTS["sections_cap"])
    return ScoreItem(
        key="sections",
        points=pts,
        max_points=WEIGHTS["sections_cap"],
        details={"present": present, "missing": missing},
    )


def score_readability(md: str) -> ScoreItem:
    # Strip code fences for readability assessment
    text = CODE_BLOCK_RE.sub(" ", md)
    grade: Optional[float] = None

    if textstat is not None:
        try:
            # Flesch-Kincaid Grade is a decent proxy for “grade level needed”.
            grade = float(textstat.flesch_kincaid_grade(text))
        except Exception:  # pragma: no cover
            grade = None

    # Tiered scoring
    if grade is None:
        pts = WEIGHTS["readability_poor"]
        bucket = "unknown"
    elif grade <= 9:
        pts = WEIGHTS["readability_excellent"]
        bucket = "≤9 (excellent)"
    elif grade <= 12:
        pts = WEIGHTS["readability_good"]
        bucket = "≤12 (good)"
    elif grade <= 14:
        pts = WEIGHTS["readability_fair"]
        bucket = "≤14 (fair)"
    else:
        pts = WEIGHTS["readability_poor"]
        bucket = ">14 (poor)"

    # Gentle penalty if there’s obviously no prose (too short),
    # but don’t go negative.
    if grade is None and len(text.strip()) < 200:
        pts = max(0.0, pts - 0.5)

    return ScoreItem(
        key="readability",
        points=pts,
        max_points=WEIGHTS["readability_excellent"],
        details={
            "grade": grade,
            "bucket": bucket,
            "library": "textstat" if textstat else "missing",
        },
    )


def score_extras(md: str) -> ScoreItem:
    pts = 0.0
    details: Dict[str, object] = {}

    # Table of contents (very rough—common patterns)
    toc_present = bool(re.search(r"\btable of contents\b", md, flags=re.I)) or bool(
        re.search(r"^\s*-\s*\[.+?\]\(#.+?\)", md, flags=re.I | re.M)
    )
    if toc_present:
        pts += WEIGHTS["toc_present"]
    details["toc_present"] = toc_present

    # Links to LICENSE / CONTRIBUTING / CODE_OF_CONDUCT
    policy_link = any(
        re.search(p, md, flags=re.I)
        for p in [
            r"\blicense\b",
            r"contributing\.md",
            r"code[_-]of[_-]conduct",
            r"\bcontributing\b",
        ]
    )
    if policy_link:
        pts += WEIGHTS["links_to_policy_files"]
    details["policy_links_present"] = policy_link

    # Examples section actually contains code
    examples = section_slice(md, SECTION_SYNONYMS["usage"])
    examples_has_code = bool(examples and CODE_BLOCK_RE.search(examples))
    if examples_has_code:
        pts += WEIGHTS["examples_with_code"]
    details["examples_with_code"] = examples_has_code

    # Mention of Python version in text or badge
    py_ver_mention = bool(re.search(r"\bpython\s*([3]\.\d{1,2}|\d+)\b", md, flags=re.I))
    py_ver_badge = bool(re.search(r"pyversions|python-?version", md, flags=re.I))
    if py_ver_mention or py_ver_badge:
        pts += WEIGHTS["python_version_info"]
    details["python_version_info"] = py_ver_mention or py_ver_badge

    pts = min(pts, WEIGHTS["extras_cap"])
    return ScoreItem(
        key="extras",
        points=pts,
        max_points=WEIGHTS["extras_cap"],
        details=details,
    )


# ---- aggregator --------------------------------------------------------------


def evaluate_readme(md: str) -> RubricResult:
    items = [
        score_code_blocks(md),
        score_badges(md),
        score_sections(md),
        score_readability(md),
        score_extras(md),
    ]
    total = sum(i.points for i in items)
    max_possible = sum(i.max_points for i in items)

    # Suggestions (lightweight, actionable)
    suggestions: List[str] = []

    # Missing expected sections (except installation)
    sect_item = next(i for i in items if i.key == "sections")
    missing = [m for m in sect_item.details.get("missing", []) if m != "installation"]
    if missing:
        suggestions.append(f"Consider adding sections: {', '.join(sorted(missing))}.")

    # Code blocks weak
    cb = next(i for i in items if i.key == "code_blocks")
    if cb.details.get("python_blocks", 0) == 0:
        suggestions.append("Add Python examples (fenced ```python blocks).")
    elif cb.details.get("python_parsed_ok", 0) == 0:
        suggestions.append("Ensure Python examples parse (no syntax errors).")

    # Readability suggestion
    rd = next(i for i in items if i.key == "readability")
    if rd.details.get("bucket") in (">14 (poor)", "unknown"):
        if textstat is None:
            suggestions.append(
                "Install `textstat` for readability scoring: `pip install textstat`."
            )
        suggestions.append(
            "Aim for a high-school or lower reading level—shorter sentences & simpler words."
        )

    # Badges suggestion
    bd = next(i for i in items if i.key == "badges")
    spec = (
        bd.details.get("specific", {})
        if isinstance(bd.details.get("specific", {}), dict)
        else {}
    )
    want_specific = [k for k, v in dict(spec).items() if not v]
    if want_specific:
        human = ", ".join(want_specific)
        suggestions.append(f"Add helpful badges ({human}) via shields.io.")

    # Extras
    ex = next(i for i in items if i.key == "extras")
    if not ex.details.get("toc_present"):
        suggestions.append("Add a Table of Contents for longer READMEs.")
    if not ex.details.get("examples_with_code"):
        suggestions.append("Include a concrete example under Usage (with code).")
    if not ex.details.get("policy_links_present"):
        suggestions.append("Link to LICENSE / CONTRIBUTING / CODE_OF_CONDUCT.")

    # Don’t award points for Installation, so if README is only “install via pip”, nudge for more
    if contains_section(md, SECTION_SYNONYMS["installation"]) and not contains_section(
        md, SECTION_SYNONYMS["usage"]
    ):
        suggestions.append("Installation alone isn’t enough—add Usage with examples.")

    return RubricResult(
        total=total, items=items, suggestions=suggestions, max_possible=max_possible
    )


# ---- CLI ---------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score a README.md for completeness (Python-focused)."
    )
    parser.add_argument(
        "readme",
        type=Path,
        help="Path to README.md (or any Markdown file).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of a human-readable summary.",
    )
    args = parser.parse_args(args=argv)

    md_path: Path = args.readme
    if not md_path.exists():
        print(f"ERROR: File not found: {md_path}")
        return 2

    md = md_path.read_text(encoding="utf-8", errors="replace")
    result = evaluate_readme(md)

    if args.json:
        payload = {
            "total": result.total,
            "items": [
                {
                    "key": i.key,
                    "points": i.points,
                    "max_points": i.max_points,
                    "details": i.details,
                }
                for i in result.items
            ],
            "suggestions": result.suggestions,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"\nREADME completeness score: {result.total:.2f}\n")
        for i in result.items:
            print(f"- {i.key:12s}: {i.points:.2f} / {i.max_points:.2f}")
            if i.details:
                # brief inline details
                det = ", ".join(f"{k}={v}" for k, v in i.details.items())
                print(f"    {det}")
        if result.suggestions:
            print("\nSuggestions:")
            for s in result.suggestions:
                print(f"  • {s}")
        print()
        if textstat is None:
            print(
                "(Install `textstat` to enable readability scoring: `pip install textstat`)"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=["../../README.md"]))
