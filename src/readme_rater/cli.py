"""Command-line interface for the README Rater."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import rater, state


def main() -> int:
    """
    The main entry point for the command-line tool.

    Returns:
        An integer exit code (0 for success, non-zero for failure).
    """
    parser = argparse.ArgumentParser(
        description="Rate a README.md file based on a rubric using an LLM.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "readme_path",
        nargs="?",
        default="README.md",
        help="Path to the README.md file to rate (default: ./README.md).",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Force re-evaluation of all rubric items, ignoring the cache.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging for debugging.",
    )
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(levelname)s: %(message)s", stream=sys.stderr
    )

    readme_file = Path(args.readme_path)
    if not readme_file.is_file():
        logging.error(f"Error: README file not found at '{readme_file}'")
        return 1

    try:
        content = readme_file.read_text(encoding="utf-8")
        final_rating = rater.rate_readme(content, args.full_refresh)
        toml_output = state.render_toml_output(final_rating)
        print(toml_output)
        return 0
    except FileNotFoundError:
        logging.error(f"Error: Could not read file at '{readme_file}'")
        return 1
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return 1
