"""
Main orchestrator for the README rating process.
"""

from __future__ import annotations

import logging
from typing import Dict, List

from . import llm_client, rubric, scoring, state, utils
from .models import Rating, RubricItem, State


def _select_ids_for_check(
    previous_state: State | None, full_refresh: bool
) -> list[str]:
    """
    Determines which rubric items need to be sent to the LLM.

    If it's a full refresh, all items are sent. Otherwise, only items that
    previously failed or were not present in the cache are sent.

    Args:
        previous_state: The cached state from the last run, if any.
        full_refresh: Flag to force re-evaluation of all items.

    Returns:
        A list of rubric item IDs to be checked.
    """
    all_ids = rubric.CORE + rubric.EXTRA
    if full_refresh or not previous_state:
        logging.info("Performing a full refresh of all rubric items.")
        return all_ids

    prev_results: Dict[str, RubricItem] = {
        item.id: item for item in previous_state.rubric_results
    }
    ids_to_check: List[str] = []

    for item_id in all_ids:
        prev_item = prev_results.get(item_id)
        if not prev_item or prev_item.status == "fail":
            ids_to_check.append(item_id)

    logging.info(f"Found {len(ids_to_check)} items needing re-evaluation.")
    return ids_to_check


def rate_readme(readme_content: str, full_refresh: bool = False) -> Rating:
    """
    Rates a README file's content against the PEP 8001 rubric.

    This function orchestrates the entire process:
    1. Hashes the README content.
    2. Loads the previous state from cache.
    3. Determines which rubric items need LLM analysis (convergence).
    4. Calls the LLM client to get new assessments.
    5. Merges new and old results.
    6. Computes the final score.
    7. Saves the new state to the cache.
    8. Returns the final rating.

    Args:
        readme_content: The full string content of the README.md file.
        full_refresh: If True, re-evaluates all rubric items, ignoring cache.

    Returns:
        A Rating object containing the full analysis and score.
    """
    readme_hash = utils.norm_hash(readme_content)
    previous_state = state.load_state()

    # If the file hasn't changed and it's not a full refresh, use the cache.
    if (
        previous_state
        and previous_state.readme_file_hash == readme_hash
        and not full_refresh
    ):
        logging.info(
            "README content is unchanged. Using cached results for 'pass' items."
        )
    else:
        # Content has changed, so ignore the old state for assessment purposes.
        previous_state = None

    ids_to_check = _select_ids_for_check(previous_state, full_refresh)
    new_results = llm_client.assess_readme(readme_content, ids_to_check)

    # Merge new results with previous passing results
    merged_results_map: Dict[str, RubricItem] = {}
    if previous_state:
        for item in previous_state.rubric_results:
            if item.status != "fail":
                merged_results_map[item.id] = item

    for item in new_results:
        merged_results_map[item.id] = item

    # Ensure the final list is in the canonical order
    final_results_list = [
        merged_results_map[i]
        for i in (rubric.CORE + rubric.EXTRA)
        if i in merged_results_map
    ]

    score = scoring.compute_score(final_results_list)
    label = scoring.qual_label(score)
    timestamp = utils.now_utc()

    # Save the new complete state
    new_state = State(
        readme_file_hash=readme_hash,
        rubric_results=final_results_list,
        score=score,
        updated=timestamp,
    )
    state.save_state(new_state)

    # Create the final rating object for output
    final_rating = Rating(
        overall_score=label,
        overall_score_numeric=score,
        last_checked_utc=timestamp,
        readme_file_hash=readme_hash,
        rubric_results=final_results_list,
    )
    return final_rating
