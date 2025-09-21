# troml_dev_status/analysis/readme_eval.py
from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

import textstat

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------------------
# Optional helper to crank logging up for JUST this module when you need it.
# Call enable_readme_eval_debug(logging.DEBUG) (or INFO) from your CLI/tests.
# --------------------------------------------------------------------------------------


def enable_readme_eval_debug(level: int = logging.DEBUG) -> None:
    """Enable verbose logging for this module only.

    Safe to call multiple times. Adds a basic StreamHandler if none are attached.
    """
    logger.setLevel(level)
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        h = logging.StreamHandler()
        fmt = "%(asctime)s %(levelname)s [readme_eval] %(message)s"
        h.setFormatter(logging.Formatter(fmt))
        logger.addHandler(h)
    logger.propagate = (
        False  # keep chatty logs from bubbling up unless caller wants that
    )
    logger.debug(
        "readme_eval debug logging enabled at level %s", logging.getLevelName(level)
    )


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
    # "api": ["api", "reference", "cli", "commands", "endpoints", "module reference"],
    # "configuration": [
    #     "configuration",
    #     "config",
    #     "settings",
    #     "environment variables",
    #     "env vars",
    # ],
    # "testing": ["tests", "testing", "how to test", "running tests"],
    # "contributing": ["contributing", "how to contribute", "development", "dev setup"],
    "license": ["license", "licence"],
    # "status": ["status", "project status", "maturity", "roadmap"],
    # "security": ["security", "reporting security issues", "vulnerability disclosure"],
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
    s2 = s.lower().strip()
    s2 = re.sub(r"[^\w\s-]", "", s2)
    s2 = re.sub(r"\s+", "-", s2)
    logger.debug("_slug: '%s' -> '%s'", s, s2)
    return s2


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
    blocks = [
        (m.group("lang").lower(), m.group("code")) for m in CODE_BLOCK_RE.finditer(md)
    ]
    logger.debug("extract_code_blocks: found %d code fences", len(blocks))
    # log a small preview for first few blocks
    for i, (lang, code) in enumerate(blocks[:5]):
        preview = code.strip().splitlines()[:3]
        logger.debug("  block[%d]: lang=%s, preview=%s", i, lang or "(none)", preview)
    if len(blocks) > 5:
        logger.debug("  … %d more blocks not shown", len(blocks) - 5)
    return blocks


def extract_headings(md: str) -> List[str]:
    """Return list of heading titles as they appear (no #)."""
    titles = [m.group("title").strip() for m in HEADING_RE.finditer(md)]
    logger.debug(
        "extract_headings: found %d headings: %s",
        len(titles),
        [t[:60] for t in titles[:10]],
    )
    return titles


def find_badge_urls(md: str) -> List[str]:
    """Return list of image URLs that look like badges."""
    urls: List[str] = []
    for m in IMAGE_LINK_RE.finditer(md):
        url = m.group("url")
        if any(re.search(p, url, flags=re.I) for p in BADGE_PATTERNS):
            urls.append(url)
    logger.debug(
        "find_badge_urls: scanned %d images, detected %d badge-like URLs",
        len(list(IMAGE_LINK_RE.finditer(md))),
        len(urls),
    )
    for i, u in enumerate(urls[:10]):
        logger.debug("  badge[%d]: %s", i, u)
    if len(urls) > 10:
        logger.debug("  … %d more badges not shown", len(urls) - 10)
    return urls


def heading_index(md: str) -> Dict[str, List[int]]:
    """Map of normalized heading text -> list of indices where they occur (by appearance order)."""
    titles = extract_headings(md)
    idx: Dict[str, List[int]] = {}
    for i, t in enumerate(titles):
        s = _slug(t)
        idx.setdefault(s, []).append(i)
    logger.debug("heading_index: %d unique slugs", len(idx))
    return idx


def contains_section(md: str, synonyms: Iterable[str]) -> bool:
    """Return True if any synonym appears as a heading title (case-insensitive)."""
    titles = extract_headings(md)
    norm_titles = [_slug(t) for t in titles]
    syn_slugs = {_slug(s) for s in synonyms}
    hit = any(t in syn_slugs for t in norm_titles)
    logger.debug(
        "contains_section: synonyms=%s -> hit=%s (norm_titles=%s)",
        list(syn_slugs)[:10],
        hit,
        norm_titles[:10],
    )
    return hit


def section_slice(md: str, section_syns: Iterable[str]) -> str | None:
    """Return content under a section heading (first match), up to next heading. For checks like code-in-examples."""
    titles = extract_headings(md)
    if not titles:
        logger.debug("section_slice: no headings -> None")
        return None
    _ = [_slug(t) for t in titles]
    syn_slugs = {_slug(s) for s in section_syns}

    # Build positions (start index in string) of headings
    spans = [
        (m.start(), m.end(), m.group("title").strip()) for m in HEADING_RE.finditer(md)
    ]
    # Map index -> (start_pos, end_pos, title)
    list(spans)

    # find first heading that matches synonyms
    for i, (_, endpos, title) in enumerate(spans):
        if _slug(title) in syn_slugs:
            content_start = endpos
            content_end = spans[i + 1][0] if i + 1 < len(spans) else len(md)
            chunk = md[content_start:content_end].strip()
            logger.debug(
                "section_slice: matched title='%s' -> content chars=%d",
                title,
                len(chunk),
            )
            return chunk

    logger.debug("section_slice: no match for synonyms=%s", list(syn_slugs))
    return None


# ---- individual scoring functions -------------------------------------------


def score_code_blocks(md: str) -> ScoreItem:
    blocks = extract_code_blocks(md)
    total = 0.0
    parsed_ok = 0
    py_blocks = 0
    for idx, (lang, code) in enumerate(blocks):
        total += WEIGHTS["code_blocks_base_per_block"]
        if lang == "python":
            py_blocks += 1
            total += WEIGHTS["code_blocks_python_bonus"]
            try:
                ast.parse(code)
            except Exception as e:  # nosec
                logger.debug(
                    "score_code_blocks: block %d python parse ERROR: %s", idx, e
                )
            else:
                parsed_ok += 1
                total += WEIGHTS["code_blocks_python_parses_bonus"]
                logger.debug("score_code_blocks: block %d python parse OK", idx)
        else:
            logger.debug(
                "score_code_blocks: block %d non-python lang=%s", idx, lang or "(none)"
            )

    capped_total = min(total, WEIGHTS["code_blocks_cap"])
    logger.debug(
        "score_code_blocks: blocks=%d py_blocks=%d parsed_ok=%d raw=%.2f capped=%.2f",
        len(blocks),
        py_blocks,
        parsed_ok,
        total,
        capped_total,
    )
    return ScoreItem(
        key="code_blocks",
        points=capped_total,
        max_points=WEIGHTS["code_blocks_cap"],
        details={
            "total_blocks": len(blocks),
            "python_blocks": py_blocks,
            "python_parsed_ok": parsed_ok,
        },
    )


def _classify_specific_badges(urls: List[str]) -> Dict[str, bool]:
    specific = {k: False for k in SPECIFIC_BADGE_CHECKS.keys()}
    for url in urls:
        for cls, pats in SPECIFIC_BADGE_CHECKS.items():
            if specific[cls]:
                continue
            if any(re.search(p, url, flags=re.I) for p in pats):
                specific[cls] = True
                logger.debug("_classify_specific_badges: matched %s via %s", cls, url)
    return specific


def score_badges(md: str) -> ScoreItem:
    urls = find_badge_urls(md)
    points_base = len(urls) * WEIGHTS["badges_per_badge"]
    points = min(points_base, WEIGHTS["badges_cap"])

    specific = _classify_specific_badges(urls)
    bonus = 0.0
    if specific["pypi"]:
        bonus += WEIGHTS["badge_pypi"]
    if specific["ci"]:
        bonus += WEIGHTS["badge_ci"]
    if specific["coverage"]:
        bonus += WEIGHTS["badge_coverage"]
    if specific["license"]:
        bonus += WEIGHTS["badge_license"]

    final_points = min(points + bonus, WEIGHTS["badges_cap"])
    logger.debug(
        "score_badges: count=%d base=%.2f bonus=%.2f final=%.2f specific=%s",
        len(urls),
        points_base,
        bonus,
        final_points,
        specific,
    )
    return ScoreItem(
        key="badges",
        points=final_points,
        max_points=WEIGHTS["badges_cap"],
        details={"count": len(urls), "specific": specific, "urls": urls[:10]},
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
                logger.debug("score_sections: installation present (0 pts)")
            else:
                missing.append(canonical)
            continue

        if found:
            present.append(canonical)
        else:
            missing.append(canonical)
        logger.debug(
            "score_sections: %-13s -> %s", canonical, "present" if found else "missing"
        )

    pts = (
        len([p for p in present if not p.endswith("(0 pts)")])
        * WEIGHTS["section_present"]
    )
    pts_capped = min(pts, WEIGHTS["sections_cap"])
    logger.debug(
        "score_sections: present=%s missing=%s raw=%.2f capped=%.2f",
        present,
        missing,
        pts,
        pts_capped,
    )
    return ScoreItem(
        key="sections",
        points=pts_capped,
        max_points=WEIGHTS["sections_cap"],
        details={"present": present, "missing": missing},
    )


def score_readability(md: str) -> ScoreItem:
    # Strip code fences for readability assessment
    text = CODE_BLOCK_RE.sub(" ", md)
    grade: Optional[float] = None

    if textstat is not None:
        try:
            grade = float(textstat.flesch_kincaid_grade(text))
            logger.debug("score_readability: FK grade=%.3f chars=%d", grade, len(text))
        except Exception as e:  # pragma: no cover
            logger.debug("score_readability: textstat error: %s", e)
            grade = None
    else:
        logger.debug("score_readability: textstat missing")

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
        pts_before = pts
        pts = max(0.0, pts - 0.5)
        logger.debug(
            "score_readability: short text penalty %.2f -> %.2f", pts_before, pts
        )

    logger.debug("score_readability: bucket=%s points=%.2f", bucket, pts)
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
    logger.debug("score_extras: toc_present=%s", toc_present)

    # Examples section actually contains code
    examples = section_slice(md, SECTION_SYNONYMS["usage"])
    examples_has_code = bool(examples and CODE_BLOCK_RE.search(examples))
    if examples_has_code:
        pts += WEIGHTS["examples_with_code"]
    details["examples_with_code"] = examples_has_code
    logger.debug("score_extras: examples_has_code=%s", examples_has_code)

    # Mention of Python version in text or badge
    py_ver_mention = bool(re.search(r"\bpython\s*([3]\.\d{1,2}|\d+)\b", md, flags=re.I))
    py_ver_badge = bool(re.search(r"pyversions|python-?version", md, flags=re.I))
    if py_ver_mention or py_ver_badge:
        pts += WEIGHTS["python_version_info"]
    details["python_version_info"] = py_ver_mention or py_ver_badge
    logger.debug(
        "score_extras: python_version_info=%s (mention=%s badge=%s)",
        details["python_version_info"],
        py_ver_mention,
        py_ver_badge,
    )

    pts_capped = min(pts, WEIGHTS["extras_cap"])
    logger.debug("score_extras: raw=%.2f capped=%.2f", pts, pts_capped)
    return ScoreItem(
        key="extras",
        points=pts_capped,
        max_points=WEIGHTS["extras_cap"],
        details=details,
    )


# ---- aggregator --------------------------------------------------------------


def evaluate_readme(md: str) -> RubricResult:
    logger.debug("evaluate_readme: input length=%d chars", len(md))
    items = [
        score_code_blocks(md),
        score_badges(md),
        score_sections(md),
        score_readability(md),
        score_extras(md),
    ]
    total = sum(i.points for i in items)
    max_possible = sum(i.max_points for i in items)
    logger.debug(
        "evaluate_readme: subtotal points=%s max_possible=%s items=%s",
        [i.points for i in items],
        max_possible,
        [i.key for i in items],
    )

    # Suggestions (lightweight, actionable)
    suggestions: List[str] = []

    # Missing expected sections (except installation)
    sect_item = next(i for i in items if i.key == "sections")
    missing = [m for m in sect_item.details.get("missing", []) if m != "installation"]
    if missing:
        suggestions.append(f"Consider adding sections: {', '.join(sorted(missing))}.")
        logger.debug("suggestion: add sections -> %s", missing)

    # Code blocks weak
    cb = next(i for i in items if i.key == "code_blocks")
    if cb.details.get("python_blocks", 0) == 0:
        suggestions.append("Add Python examples (fenced ```python blocks).")
        logger.debug("suggestion: no Python code blocks detected")
    elif cb.details.get("python_parsed_ok", 0) == 0:
        suggestions.append("Ensure Python examples parse (no syntax errors).")
        logger.debug("suggestion: Python examples present but not parsing OK")

    # Readability suggestion
    rd = next(i for i in items if i.key == "readability")
    if rd.details.get("bucket") in (">14 (poor)", "unknown"):
        suggestions.append(
            "Aim for a high-school or lower reading level—shorter sentences & simpler words."
        )
        logger.debug("suggestion: readability improvement")

    # Badges suggestion
    bd = next(i for i in items if i.key == "badges")
    spec = (
        bd.details.get("specific", {})
        if isinstance(bd.details.get("specific", {}), dict)
        else {}
    )
    want_specific = [k for k, v in dict(spec).items() if not v]
    if want_specific:
        suggestions.append(
            f"Add helpful badges ({', '.join(want_specific)}) via shields.io."
        )
        logger.debug("suggestion: add specific badges -> %s", want_specific)

    # Extras
    ex = next(i for i in items if i.key == "extras")
    if not ex.details.get("toc_present"):
        suggestions.append("Add a Table of Contents for longer READMEs.")
        logger.debug("suggestion: add TOC")
    if not ex.details.get("examples_with_code"):
        suggestions.append("Include a concrete example under Usage (with code).")
        logger.debug("suggestion: add examples with code")

    # Don’t award points for Installation, so if README is only “install via pip”, nudge for more
    if contains_section(md, SECTION_SYNONYMS["installation"]) and not contains_section(
        md, SECTION_SYNONYMS["usage"]
    ):
        suggestions.append("Installation alone isn’t enough—add Usage with examples.")
        logger.debug("suggestion: install-without-usage nudge")

    result = RubricResult(
        total=total, items=items, suggestions=suggestions, max_possible=max_possible
    )
    logger.debug(
        "evaluate_readme: TOTAL=%.2f / %.2f | suggestions=%d",
        result.total,
        result.max_possible,
        len(result.suggestions),
    )
    # Dump concise per-item details to help users see why a score happened
    for it in items:
        logger.debug(
            "item[%s]: points=%.2f/%0.2f details=%s",
            it.key,
            it.points,
            it.max_points,
            it.details,
        )
    return result
