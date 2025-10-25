"""Handles all communication with the OpenAI-compatible LLM API."""

from __future__ import annotations

import json
import logging
from typing import Dict, List

from openai import OpenAI, OpenAIError

from . import config
from .models import RubricItem

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# A mapping from rubric ID to a more descriptive goal for the LLM.
# This helps the model understand the *intent* behind each check.
RUBRIC_DESCRIPTIONS: Dict[str, str] = {
    "CLARITY_OF_PURPOSE": "Does the README begin with a clear, concise summary of what the package does and its main purpose? A new user should understand the project's goal in the first paragraph.",
    "QUICKSTART_INSTALL": "Is there a clear, copy-pasteable installation command (e.g., `pip install`) or a prominent link to an installation guide?",
    "HELLO_WORLD_EXAMPLE": "Can a user find a minimal, complete, and copy-pasteable code example to quickly understand the package's primary function and see it in action?",
    "VISUAL_DEMONSTRATION": "If the project is visual (e.g., plotting, UI, image processing), does the README include a screenshot, GIF, or example output image? If not a visual tool, this is not applicable.",
    "CONTRIBUTION_GATEWAY": "Is there a clear section or link to a `CONTRIBUTING.md` file that explains how others can contribute to the project (e.g., bug reports, pull requests)?",
    "DEVELOPMENT_SETUP": "Are there instructions for a contributor to set up a local development environment and run tests? (e.g., `git clone`, `pip install -e .`, `pytest`)",
    "LICENSE_CLARITY": "Is the software license clearly stated in the README, or is there a prominent link to a `LICENSE` file?",
    "PROJECT_HEALTH_BADGES": "Does the README include status badges for things like CI/CD (e.g., GitHub Actions), test coverage, or the latest version on PyPI?",
    "PRIOR_ART_COMPARISON": "Does the documentation discuss how this project compares to other similar tools or alternatives in the ecosystem?",
    "DESIGN_RATIONALE": "Does the README explain key design choices, trade-offs, or the philosophy behind the project?",
    # Add descriptions for all other EXTRA items as needed...
}


def _construct_system_prompt() -> str:
    """Creates the system prompt to instruct the LLM on its role and task."""
    rubric_item_model_schema = RubricItem.model_json_schema()

    return f"""
You are an expert technical documentation reviewer for Python projects.
Your task is to evaluate a project's README.md file based on a specific set of criteria.

You will be given the full content of the README.md and a list of rubric items to assess.
For each rubric item, you must determine if the README successfully meets the goal.

Your response MUST be a JSON array of objects, where each object conforms to the following JSON schema:
{json.dumps(rubric_item_model_schema, indent=2)}

- The 'id' must be one of the rubric IDs you were asked to assess.
- The 'status' must be 'pass', 'fail', or 'na' (not applicable).
- The 'advice' must be a concise, one-sentence recommendation for how the author can improve that specific rubric item. If the status is 'pass', provide a brief confirmation like "Excellent quickstart example provided."

Evaluate each item independently and critically. Be strict but fair.
"""


def _construct_user_prompt(readme_content: str, ids_to_check: List[str]) -> str:
    """Creates the user prompt containing the README and rubric items."""
    descriptions = "\n".join(
        f"- {id_}: {RUBRIC_DESCRIPTIONS.get(id_, 'No description available.')}"
        for id_ in ids_to_check
    )

    return f"""
Please evaluate the following README.md file.

README CONTENT:
---
{readme_content}
---

RUBRIC ITEMS TO ASSESS:
{descriptions}

Provide your evaluation as a JSON array of objects.
"""


def assess_readme(readme_content: str, ids_to_check: List[str]) -> List[RubricItem]:
    """
    Assesses a README file against a list of rubric items using an LLM.

    Args:
        readme_content: The full text content of the README file.
        ids_to_check: A list of rubric item IDs to be evaluated.

    Returns:
        A list of RubricItem objects with the LLM's assessment.
    """
    if not config.settings.llm.api_key:
        raise ValueError("LLM API key is not configured.")
    if not ids_to_check:
        logging.info("No new rubric items to check. Skipping LLM call.")
        return []

    client = OpenAI(
        base_url=config.settings.llm.base_url,
        api_key=config.settings.llm.api_key,
    )

    system_prompt = _construct_system_prompt()
    user_prompt = _construct_user_prompt(readme_content, ids_to_check)

    logging.info(f"Sending {len(ids_to_check)} items to LLM for assessment...")
    try:
        response = client.chat.completions.create(
            model=config.settings.llm.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,  # Low temperature for deterministic results
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty response.")

        # The schema asks for an array, but some models wrap it in a root key.
        # We handle this by trying to parse the content as-is, and if that fails,
        # we look for a root key that contains an array.
        try:
            parsed_json = json.loads(content)
        except json.JSONDecodeError:
            logging.error(f"Failed to decode LLM JSON response: {content}")
            return []

        if isinstance(parsed_json, list):
            results_list = parsed_json
        elif isinstance(parsed_json, dict) and len(parsed_json) == 1:
            key, value = next(iter(parsed_json.items()))
            if isinstance(value, list):
                logging.warning(f"Response was wrapped in a '{key}' key. Unwrapping.")
                results_list = value
            else:
                raise ValueError("LLM response is a dict but not a simple wrapper.")
        else:
            raise ValueError("LLM response is not a JSON array or a simple wrapper.")

        return [RubricItem.model_validate(item) for item in results_list]

    except OpenAIError as e:
        logging.error(f"An API error occurred: {e}")
        return []
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        logging.error(f"Failed to parse or validate LLM response: {e}")
        return []
