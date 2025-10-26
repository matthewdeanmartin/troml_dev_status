# readme_rater/state.py
"""Handles reading/writing the state cache and rendering TOML output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import tomlkit

from readme_rater import config
from readme_rater.models import Rating, State


def get_state_path() -> Path:
    """Constructs the path to the state cache file."""
    return config.get_cache_dir() / "readme_rater.state.json"


def load_state() -> Optional[State]:
    """
    Loads the cached state from the JSON file.

    Returns:
        An optional State object if the cache file exists and is valid,
        otherwise None.
    """
    state_path = get_state_path()
    if not state_path.exists():
        return None
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return State.model_validate(data)
    except (json.JSONDecodeError, IOError):
        return None


def save_state(state: State) -> None:
    """
    Saves the application state to the JSON cache file.

    Args:
        state: The State object to persist.
    """
    state_path = get_state_path()
    with open(state_path, "w", encoding="utf-8") as f:
        f.write(state.model_dump_json(indent=2))


def render_toml_output(rating: Rating) -> str:
    """
    Renders the final rating object into a TOML formatted string.

    Args:
        rating: The final Rating object.

    Returns:
        A string containing the TOML representation of the rating.
    """
    doc = tomlkit.document()
    rating_table = tomlkit.table()
    rating_dict = rating.model_dump()

    # Handle the main rating table
    for key, value in rating_dict.items():
        if key != "rubric_results":
            rating_table.add(key, value)
    doc.add("rating", rating_table)

    # Handle the array of rubric results tables
    results_array = tomlkit.aot()
    for item in rating_dict["rubric_results"]:
        item_table = tomlkit.table()
        item_table.add("id", item["id"])
        item_table.add("status", item["status"])
        item_table.add("advice", item["advice"])
        results_array.append(item_table)
    doc.add("rubric_results", results_array)

    return tomlkit.dumps(doc)
