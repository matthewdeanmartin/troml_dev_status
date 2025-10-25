#!/usr/bin/env python3
"""
readme_rater_min.py — minimal sketch
Stdlib-only, single file. Design aid, not final.
- Emits TOML to stdout
- Keeps tiny JSON state for convergence
- Toy heuristics stand in for the LLM
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Dict, List

# --- Rubric definitions (IDs only; semantics implied) ---
CORE = [
    "CLARITY_OF_PURPOSE",
    "QUICKSTART_INSTALL",
    "HELLO_WORLD_EXAMPLE",
    "VISUAL_DEMONSTRATION",
    "CONTRIBUTION_GATEWAY",
    "DEVELOPMENT_SETUP",
    "LICENSE_CLARITY",
    "PROJECT_HEALTH_BADGES",
]
EXTRA = [
    "PRIOR_ART_COMPARISON",
    "DESIGN_RATIONALE",
]

STATE_JSON = ".readme_rater.state.json"  # convergence cache (tiny, pragmatic)

# --- Small helpers ---
def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def read_text(p: str) -> str:
    with open(p, "r", encoding="utf-8") as f:
        return f.read()

def norm_hash(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n").strip()
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()

def load_state() -> dict:
    if os.path.exists(STATE_JSON):
        try:
            return json.loads(read_text(STATE_JSON))
        except Exception:
            return {}
    return {}

def save_state(obj: dict) -> None:
    with open(STATE_JSON, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

# --- Toy heuristics standing in for the LLM ---
def toy_llm_assess(readme: str, ids: List[str]) -> List[Dict[str,str]]:
    r = readme.lower()
    def present(*ks):
        return any(k in r for k in ks)

    results = []
    for id_ in ids:
        status, advice = "fail", ""
        if id_ == "CLARITY_OF_PURPOSE":
            # Heuristic: first non-empty paragraph length threshold
            paras = [p.strip() for p in re.split(r"\n\s*\n", readme) if p.strip()]
            ok = bool(paras and len(paras[0]) >= 40)
            status = "pass" if ok else "fail"
            advice = "Good opening summary." if ok else "Add a one-paragraph purpose statement near the top."
        elif id_ == "QUICKSTART_INSTALL":
            ok = present("pip install", "installation", "install\n", "install:")
            status = "pass" if ok else "fail"
            advice = "Install command or link present." if ok else "Provide a pip install or clear install link."
        elif id_ == "HELLO_WORLD_EXAMPLE":
            ok = present("```", "import ", "from ")
            status = "pass" if ok else "fail"
            advice = "Minimal code example detected." if ok else "Add a short, copy-pasteable usage example."
        elif id_ == "VISUAL_DEMONSTRATION":
            has_visual = present("![", ".png", ".gif", "screenshot")
            # allow N/A for non-visual libs (guess: no ui/plot/image words)
            is_visual_domain = present("plot", "figure", "chart", "ui", "screenshot")
            if has_visual:
                status, advice = "pass", "Visual/demo found."
            elif not is_visual_domain:
                status, advice = "na", "Not a visual/plotting tool; demo optional."
            else:
                status, advice = "fail", "Provide a screenshot/GIF or sample output image."
        elif id_ == "CONTRIBUTION_GATEWAY":
            ok = present("contributing", "how to contribute", "pull request")
            status = "pass" if ok else "fail"
            advice = "Contribution guidance present." if ok else "Link CONTRIBUTING.md or add a contribution section."
        elif id_ == "DEVELOPMENT_SETUP":
            ok = present("pytest", "make test", "uv run", "poetry run", "tox")
            status = "pass" if ok else "fail"
            advice = "Dev/test setup is documented." if ok else "Document local dev setup and how to run tests."
        elif id_ == "LICENSE_CLARITY":
            ok = present("license", "apache-2.0", "mit license", "bsd", "lgpl", "mpl")
            status = "pass" if ok else "fail"
            advice = "License visible." if ok else "State the license or link to LICENSE."
        elif id_ == "PROJECT_HEALTH_BADGES":
            ok = present("badge", "github actions", "ci status", "coverage", "pypi")
            status = "pass" if ok else "fail"
            advice = "Badges detected." if ok else "Add CI/coverage/version badges."
        elif id_ == "PRIOR_ART_COMPARISON":
            ok = present("similar", "alternatives", "prior art", "compare")
            status = "pass" if ok else "fail"
            advice = "Ecosystem context present." if ok else "Briefly compare to similar tools or prior art."
        elif id_ == "DESIGN_RATIONALE":
            ok = present("design", "rationale", "why we", "trade-off", "tradeoff")
            status = "pass" if ok else "fail"
            advice = "Design rationale present." if ok else "Explain key design choices and trade-offs."
        else:
            status, advice = "na", "Unknown rubric item."
        results.append({"id": id_, "status": status, "advice": advice})
    return results

# --- Scoring ---
def compute_score(rubric_results: List[Dict[str,str]]) -> int:
    core = [x for x in rubric_results if x["id"] in CORE and x["status"] != "na"]
    extra = [x for x in rubric_results if x["id"] in EXTRA and x["status"] == "pass"]
    if core:
        core_pass = sum(1 for x in core if x["status"] == "pass")
        core_score = int(round((core_pass / len(core)) * 80))
    else:
        core_score = 0
    extra_score = int(round((len(extra) / len(EXTRA)) * 20)) if EXTRA else 0
    return min(100, core_score + extra_score)

def qual_label(n: int) -> str:
    return (
        "Problematic" if n < 40 else
        "Needs Improvement" if n < 70 else
        "Good" if n < 90 else
        "Excellent"
    )

# --- Convergence selection ---
def select_ids_for_check(prev: dict, full_refresh: bool) -> List[str]:
    if full_refresh or not prev:
        return CORE + EXTRA
    prev_results = {x["id"]: x for x in prev.get("rubric_results", [])}
    ids = []
    for id_ in (CORE + EXTRA):
        st = prev_results.get(id_, {}).get("status")
        if st in (None, "fail"):
            ids.append(id_)
    return ids

# --- TOML emission (tiny manual) ---
def to_toml(readme_hash: str, score: int, results: List[Dict[str,str]]) -> str:
    lines = []
    lines.append("[rating]")
    lines.append(f"overall_score = \"{qual_label(score)}\"")
    lines.append(f"overall_score_numeric = {score}")
    lines.append(f"last_checked_utc = \"{now_utc()}\"")
    lines.append(f"readme_file_hash = \"{readme_hash}\"")
    for r in results:
        lines.append("")
        lines.append("[[rubric_results]]")
        lines.append(f"id = \"{r['id']}\"")
        lines.append(f"status = \"{r['status']}\"")
        advice = r["advice"].replace("\"", "\\\"")
        lines.append(f"advice = \"{advice}\"")
    return "\n".join(lines) + "\n"

# --- Main ---
def main(argv: List[str]) -> int:
    full = "--full-refresh" in argv
    path = "README.md"
    if not os.path.exists(path):
        sys.stderr.write("ERROR: README.md not found\n")
        return 2

    readme = read_text(path)
    rhash = norm_hash(readme)
    prev = load_state()

    ids = select_ids_for_check(prev, full)
    new_partial = toy_llm_assess(readme, ids)

    # merge with previous passes
    merged: Dict[str,Dict[str,str]] = {x["id"]: x for x in prev.get("rubric_results", [])}
    for x in new_partial:
        merged[x["id"]] = x
    merged_list = [merged[i] for i in (CORE + EXTRA) if i in merged]

    score = compute_score(merged_list)
    toml_out = to_toml(rhash, score, merged_list)

    # persist tiny state for convergence (JSON)
    save_state({
        "readme_file_hash": rhash,
        "rubric_results": merged_list,
        "score": score,
        "updated": now_utc(),
    })

    sys.stdout.write(toml_out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
