# troml_dev_status/analysis/bureaucracy.py
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Pattern, Set, Tuple

from troml_dev_status.analysis.iter_the_files import iter_repo_files

logger = logging.getLogger(__name__)
# ---- categories we recognize -------------------------------------------------

# Keep these stable so users can filter reliably.
CATEGORIES: Tuple[str, ...] = (
    "contributing",  # how to contribute
    "code_of_conduct",
    "security",
    "governance",
    "support",
    "funding",
    "legal",  # license/notice/trademark
    "citation",  # research citation formats
    "templates",  # issue/PR templates
    "release_notes",  # changelog/news/history
    "roadmap",
    "style",  # style guides / testing guides
    "meta",  # repo meta like CODEOWNERS, MAINTAINERS, AUTHORS
    "automation",  # config for bots/tools that shape contribution process
)

# Extensions to consider, including "no extension" via empty string.
DEFAULT_EXTS: Tuple[str, ...] = ("", ".md", ".markdown", ".rst", ".txt", ".adoc")


# Utility to build filename variants like "code-of-conduct", "code_of_conduct", "code of conduct"
def _variants(base: str) -> List[str]:
    parts = re.split(r"[\s_\-\.\+]+", base.strip())
    if not parts:
        return []
    joins = ["-".join(parts), "_".join(parts), " ".join(parts), "".join(parts)]
    return list(dict.fromkeys([base] + joins))  # dedupe, preserve order


# Spec for one pattern family
@dataclass(frozen=True)
class PatternSpec:
    # Match against full POSIX path (e.g., ".github/FUNDING.yml") OR filename
    # Provide either filename variants or explicit path regexes.
    filename_bases: Tuple[str, ...] = ()
    path_regexes: Tuple[str, ...] = ()
    exts: Tuple[str, ...] = DEFAULT_EXTS

    def compile(self) -> Tuple[List[Pattern[str]], List[Pattern[str]]]:
        # Build case-insensitive regexes for filenames and full paths.
        fname_regexes: List[Pattern[str]] = []
        path_regexes: List[Pattern[str]] = []

        # Filename patterns: cover hyphen/underscore/space/concat variants + extensions.
        for base in self.filename_bases:
            for name_variant in _variants(base):
                # Allow optional extension from allowed set.
                # Example: r"^code[-_ ]?of[-_ ]?conduct(?:\.(md|rst|txt|adoc|markdown))?$" but faster to inject list
                if self.exts and any(self.exts):
                    exts_pattern = "|".join(
                        re.escape(e.lstrip(".")) for e in self.exts if e
                    )
                    # Either no extension or one of the listed (if "" present)
                    allow_no_ext = "" in self.exts
                    if exts_pattern:
                        if allow_no_ext:
                            ext_regex = rf"(?:\.(?:{exts_pattern}))?"
                        else:
                            ext_regex = rf"\.(?:{exts_pattern})"
                    else:
                        ext_regex = ""  # only no-ext
                else:
                    ext_regex = ""  # only no-ext
                rx = re.compile(
                    rf"^{re.escape(name_variant)}{ext_regex}$", re.IGNORECASE
                )
                fname_regexes.append(rx)

        # Explicit path regexes (already regex, we just compile case-insensitively).
        for pr in self.path_regexes:
            path_regexes.append(re.compile(pr, re.IGNORECASE))

        return fname_regexes, path_regexes


# Master registry mapping categories to one or more PatternSpecs.
PATTERNS: Mapping[str, Tuple[PatternSpec, ...]] = {
    "contributing": (PatternSpec(filename_bases=("contributing", "contribute")),),
    "code_of_conduct": (
        PatternSpec(
            filename_bases=("code_of_conduct", "code-of-conduct", "code of conduct")
        ),
    ),
    "security": (PatternSpec(filename_bases=("security", "security policy")),),
    "governance": (PatternSpec(filename_bases=("governance", "governance policy")),),
    "support": (PatternSpec(filename_bases=("support", "getting help")),),
    "funding": (
        # Common: .github/FUNDING.yml; also accept FUNDING.* elsewhere
        PatternSpec(
            filename_bases=("funding",),
            path_regexes=(r"/\.github/(?:.*/)?funding\.ya?ml$",),
            exts=("", ".yml", ".yaml", ".md", ".rst", ".txt"),
        ),
    ),
    "legal": (
        PatternSpec(filename_bases=("license", "licence")),
        PatternSpec(filename_bases=("notice", "notices")),
        PatternSpec(filename_bases=("patent", "patents", "trademark", "copyright")),
    ),
    "citation": (
        PatternSpec(filename_bases=("citation",), exts=("", ".cff", ".md", ".txt")),
        PatternSpec(path_regexes=(r"/citation\.cff$",)),
    ),
    "templates": (
        # Issue/PR templates in .github or root
        PatternSpec(filename_bases=("pull_request_template", "pr_template")),
        PatternSpec(filename_bases=("issue_template",)),
        PatternSpec(
            path_regexes=(r"/\.github/(?:.*/)?pull_request_template\.(?:md|rst|txt)$",)
        ),
        PatternSpec(
            path_regexes=(
                r"/\.github/(?:.*/)?issue_template(?:s)?/.*\.(?:md|rst|txt)$",
            )
        ),
    ),
    "release_notes": (
        PatternSpec(
            filename_bases=("changelog", "changes", "history", "news", "release_notes")
        ),
    ),
    "roadmap": (PatternSpec(filename_bases=("roadmap",)),),
    "style": (
        PatternSpec(
            filename_bases=(
                "styleguide",
                "style guide",
                "style",
                "testing",
                "test guide",
            )
        ),
    ),
    "meta": (
        PatternSpec(filename_bases=("authors", "maintainers", "contributors")),
        PatternSpec(
            filename_bases=("codeowners",), exts=("",)
        ),  # CODEOWNERS usually no ext
        PatternSpec(path_regexes=(r"/\.github/CODEOWNERS$",)),
    ),
    "automation": (
        # Things that strongly influence contribution/maintenance process
        PatternSpec(filename_bases=(".editorconfig",), exts=("",)),
        PatternSpec(filename_bases=(".gitattributes",), exts=("",)),
        PatternSpec(filename_bases=(".pre-commit-config",), exts=("", ".yaml", ".yml")),
        PatternSpec(filename_bases=("dependabot",), exts=(".yml", ".yaml")),
        PatternSpec(
            filename_bases=("renovate",), exts=(".json", ".json5", ".yaml", ".yml")
        ),
        PatternSpec(
            path_regexes=(r"/\.github/dependabot\.ya?ml$", r"/renovate\.json5?$")
        ),
        # Python tooling that often encodes “policy” for contributions
        PatternSpec(filename_bases=("pyproject",), exts=(".toml",)),
        PatternSpec(filename_bases=("setup",), exts=(".cfg",)),
        PatternSpec(filename_bases=("mypy",), exts=(".ini", ".cfg")),
        PatternSpec(filename_bases=("ruff",), exts=(".toml", ".cfg")),
    ),
}

# ---- core scanning helpers ---------------------------------------------------


def _compile_registry(
    include_categories: Iterable[str] | None,
    exclude_categories: Iterable[str] | None,
) -> Dict[str, Tuple[List[Pattern[str]], List[Pattern[str]]]]:
    include: Set[str] = set(include_categories or CATEGORIES)
    exclude: Set[str] = set(exclude_categories or ())
    active = sorted((include - exclude) & set(CATEGORIES))

    compiled: Dict[str, Tuple[List[Pattern[str]], List[Pattern[str]]]] = {}
    for cat in active:
        fname_list: List[Pattern[str]] = []
        path_list: List[Pattern[str]] = []
        for spec in PATTERNS.get(cat, ()):
            f, p = spec.compile()
            fname_list.extend(f)
            path_list.extend(p)
        compiled[cat] = (fname_list, path_list)
    return compiled


def _match_category(
    cat: str,
    compiled: Mapping[str, Tuple[List[Pattern[str]], List[Pattern[str]]]],
    path: Path,
) -> bool:
    fname = path.name
    posix = path.as_posix()
    fname_regexes, path_regexes = compiled[cat]
    return any(rx.search(fname) for rx in fname_regexes) or any(
        rx.search(posix) for rx in path_regexes
    )


def scan_bureaucracy(
    repo_path: Path,
    include_categories: Iterable[str] | None = None,
    exclude_categories: Iterable[str] | None = None,
    follow_symlinks: bool = False,
) -> Dict[str, List[Path]]:
    """
    Return a mapping of category -> list of Paths found.

    - Case-insensitive filename matching with multiple stylistic variants.
    - Matches also on full POSIX path for special locations (e.g., .github/FUNDING.yml).
    - Deduplicates paths per category and overall (no duplicates across categories for the same file).
      (If a file matches multiple categories, it is assigned to the first category in CATEGORIES order.)
    """

    compiled = _compile_registry(include_categories, exclude_categories)
    found_by_cat: dict[str, list[Path]] = {cat: [] for cat in compiled}
    seen: set[Path] = set()

    for p in iter_repo_files(repo_path, follow_symlinks=follow_symlinks):
        for cat in (c for c in CATEGORIES if c in compiled):
            if _match_category(cat, compiled, p):
                if p not in seen:
                    found_by_cat[cat].append(p)
                    seen.add(p)
                break

    # sort results
    for cat in found_by_cat:
        found_by_cat[cat].sort(key=lambda x: x.as_posix().lower())
    return found_by_cat


# ---- public APIs -------------------------------------------------------------


def get_bureaucracy_files(
    repo_path: Path,
    categories: Iterable[str] | None = None,
    exclude_categories: Iterable[str] | None = None,
) -> List[Path]:
    """
    Drop-in replacement for your original function but expansive:
    returns a flat, deduped list of matching files.

    Args:
        repo_path: root of the repo.
        categories: include only these categories (default: all known).
        exclude_categories: skip these categories.
    """
    mapping = scan_bureaucracy(
        repo_path, include_categories=categories, exclude_categories=exclude_categories
    )
    # Preserve deterministic order: category order then path order.
    ordered: List[Path] = []
    for cat in CATEGORIES:
        if cat in mapping:
            ordered.extend(mapping[cat])
    return ordered


def summarize_bureaucracy(
    repo_path: Path,
    categories: Iterable[str] | None = None,
    exclude_categories: Iterable[str] | None = None,
) -> Dict[str, int]:
    """
    Convenience: category -> count.
    """
    mapping = scan_bureaucracy(
        repo_path, include_categories=categories, exclude_categories=exclude_categories
    )
    return {k: len(v) for k, v in mapping.items()}


# ---- quick extension guide ---------------------------------------------------
# To add a new doc kind:
# 1) Pick a category (or add a new one to CATEGORIES).
# 2) Add a PatternSpec to PATTERNS[category] with `filename_bases` and/or `path_regexes`.
#    - filename_bases are human names; variants (-/_/space/concat) are generated automatically.
#    - exts controls which extensions are accepted (include "" to allow no extension).
#    - path_regexes are matched against full POSIX path (e.g., r"/\.github/somefile\.yml$").
# 3) Done. The scanner will include it automatically.
