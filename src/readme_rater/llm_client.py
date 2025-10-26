# readme_rater/llm_client.py
"""LLM client speaking TOML (single request, no batching)."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Sequence

from openai import OpenAI, OpenAIError

from readme_rater import config
from readme_rater.models import RubricItem

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

try:
    import tomllib as _tomli  # Py>=3.11
except Exception:  # pragma: no cover
    import tomli as _tomli  # type: ignore[no-redef]

RUBRIC_DESCRIPTIONS: Dict[str, str] = {
    "CLARITY_OF_PURPOSE": "Clear one-paragraph summary of purpose.",
    "QUICKSTART_INSTALL": "Copy-paste install command or obvious link.",
    "HELLO_WORLD_EXAMPLE": "Minimal runnable example of core use.",
    "VISUAL_DEMONSTRATION": "Screenshot/GIF if visual tool else N/A.",
    "CONTRIBUTION_GATEWAY": "Contributing section or CONTRIBUTING.md.",
    "DEVELOPMENT_SETUP": "Local dev/test instructions.",
    "LICENSE_CLARITY": "License stated or linked.",
    "PROJECT_HEALTH_BADGES": "Badges (CI/coverage/version/etc.).",
    "PRIOR_ART_COMPARISON": "Comparison to similar tools.",
    "DESIGN_RATIONALE": "Design choices / trade-offs.",
    "TUTORIAL_OR_WALKTHROUGH": "Step-by-step tutorial.",
    "REAL_WORLD_USAGE": "Named users or examples.",
    "PERFORMANCE_SECTION": "Perf/benchmarks/limits.",
    "CONTAINER_IMAGE_LINK": "Official container or recipe.",
    "SUPPORT_MATRIX": "Supported OS/Python matrix.",
    "I18N_SUPPORT_INFO": "Internationalization notes.",
    "ACCESSIBILITY_DISCUSSION": "Accessibility notes.",
    "ETHICAL_STATEMENT": "Ethics/responsible-use statement.",
    "CHANGELOG_LINK": "CHANGELOG/release notes link.",
    "ROADMAP_OR_VISION": "Roadmap/vision/future plans.",
    "COMMUNITY_GUIDELINES": "Code of Conduct/community norms.",
    "FUNDING_INFORMATION": "Funding/sponsorship info.",
    "ACKNOWLEDGMENTS": "Credits/acknowledgments.",
    "CONFIGURATION_EXAMPLES": "Config examples.",
    "API_REFERENCE_LINK": "API reference link.",
    "ARCHITECTURE_OVERVIEW": "High-level architecture.",
    "DEPENDENCY_POLICY": "Pins/updates/security policy.",
    "REPRODUCIBILITY_NOTES": "Lockfiles/seeds/repro notes.",
    "SECURITY_POLICY_LINK": "SECURITY.md/reporting policy link.",
}

# --- Prompt construction (TOML, compact, no JSON schema) ---


def _construct_system_prompt() -> str:
    return (
        "You are an expert Python documentation reviewer.\n"
        "Task: assess a README against requested rubric items.\n\n"
        "OUTPUT: TOML ONLY. No prose, no markdown fences, no JSON, no schema echos.\n"
        "TOML schema to follow EXACTLY:\n"
        "[meta]\n"
        "version = 1\n"
        'note = "status in {pass, fail, na}; advice = one short sentence."\n\n'
        "[[rubric]]\n"
        'id = "RUBRIC_ID"\n'
        'status = "pass"\n'
        'advice = "One-sentence recommendation or confirmation."\n'
        "\n"
        "Provide one [[rubric]] table per requested item. Use status='na' when not applicable."
    )


def _format_rubric_descriptions(ids: Sequence[str]) -> str:
    return "\n".join(
        f"- {rid}: {RUBRIC_DESCRIPTIONS.get(rid, 'No description.')}" for rid in ids
    )


def _construct_user_prompt(
    readme_content: str, ids_to_check: Sequence[str], forbid_schema_words: bool = False
) -> str:
    # To counter schema-echo, we optionally “forbid” schema terms on retry.
    forbid = ""
    if forbid_schema_words:
        forbid = (
            "\nDO NOT output any JSON, JSON-Schema, or fields like: properties, type, enum, required, title.\n"
            "Start your output with: [meta]\n"
        )
    return (
        "Evaluate ONLY the rubric items listed below against the README content.\n\n"
        "RUBRIC ITEMS:\n"
        f"{_format_rubric_descriptions(ids_to_check)}\n\n"
        "README CONTENT (verbatim):\n"
        "-----\n"
        f"{readme_content}\n"
        "-----\n\n"
        "Respond in TOML exactly as specified above. No extra commentary." + forbid
    )


_CODE_FENCE_RE = re.compile(r"^```(?:toml)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def _strip_code_fences(s: str) -> str:
    m = _CODE_FENCE_RE.search(s.strip())
    return m.group(1) if m else s


def _looks_like_schema_echo(text: str) -> bool:
    t = text.lower()
    # Heuristic: typical JSON-schema tokens that indicate echoing the schema.
    bad_markers = (
        '"properties"',
        '"type"',
        '"enum"',
        '"required"',
        '"title": "rubricitem"',
    )
    return any(k in t for k in bad_markers)


def _parse_toml_items(toml_text: str) -> List[RubricItem]:
    data = _tomli.loads(toml_text)
    blocks = data.get("rubric", [])
    if not isinstance(blocks, list):
        raise ValueError("TOML parse error: [[rubric]] must be an array of tables.")
    out: List[RubricItem] = []
    for b in blocks:
        out.append(
            RubricItem.model_validate(
                {
                    "id": b.get("id"),
                    "status": b.get("status"),
                    "advice": b.get("advice"),
                }
            )
        )
    return out


# --- Public API (unchanged signature) ---


def assess_readme(readme_content: str, ids_to_check: List[str]) -> List[RubricItem]:
    if not config.settings.llm.api_key:
        raise ValueError("LLM API key is not configured.")
    if not ids_to_check:
        logging.info("No rubric items to check. Skipping LLM call.")
        return []

    client = OpenAI(
        base_url=config.settings.llm.base_url, api_key=config.settings.llm.api_key
    )

    sys_prompt = _construct_system_prompt()
    user_prompt = _construct_user_prompt(readme_content, ids_to_check)

    # Single request. High max_tokens to avoid truncation; configurable.
    max_tokens = getattr(config.settings.llm, "max_tokens", 8000)

    def _call(prompt: str):
        return client.chat.completions.create(
            model=config.settings.llm.model,
            # IMPORTANT: do not set response_format=json_object; we want raw text.
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            top_p=1,
            max_tokens=max_tokens,
        )

    try:
        resp = _call(user_prompt)
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            raise ValueError("LLM returned empty content.")

        text = _strip_code_fences(content)
        if _looks_like_schema_echo(text):
            # One retry with stricter anti-echo instruction.
            logging.warning(
                "Model echoed a schema. Retrying once with stricter TOML instruction."
            )
            retry_prompt = _construct_user_prompt(
                readme_content, ids_to_check, forbid_schema_words=True
            )
            resp = _call(retry_prompt)
            content = (resp.choices[0].message.content or "").strip()
            if not content:
                raise ValueError("LLM returned empty content on retry.")
            text = _strip_code_fences(content)

        if "[[rubric]]" not in text and "id" not in text:
            raise ValueError("Response does not look like TOML rubric output.")

        items = _parse_toml_items(text)
        # Only return requested IDs
        wanted = set(ids_to_check)
        return [it for it in items if it.id in wanted]

    except OpenAIError as e:
        logging.error(f"LLM API error: {e}")
        return []
    except Exception as e:
        logging.error(f"TOML parsing/validation error: {e}")
        return []
