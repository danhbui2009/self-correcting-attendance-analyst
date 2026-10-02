"""Command-line interface for the synthetic attendance analyst."""

from __future__ import annotations

import argparse

from attendance_analyst.graph import run_question
from attendance_analyst.parser import SUPPORTED_QUESTION_FAMILIES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evidence-checking attendance analyst (synthetic demo)")
    parser.add_argument("--question", "-q", help="Ask one supported attendance question.")
    parser.add_argument("--examples", action="store_true", help="List supported question types and examples.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.examples:
        print("Supported question families:")
        for family in SUPPORTED_QUESTION_FAMILIES:
            print(f"- {family}")
        print('\nExample: module2-analyst --question "What was the late rate by department from 2026-01-05 to 2026-01-09?"')
        print('Comparison: module2-analyst --question "Compare late rates by department from 2026-01-05 to 2026-01-05 versus 2026-01-06 to 2026-01-09"')
        return 0
    if not args.question:
        build_parser().print_help()
        return 2
    try:
        result = run_question(args.question)
    except (OSError, ValueError) as error:
        print(f"Could not run the analyst: {error}")
        return 1
    print(result.get("answer", "No answer was produced."))
    return 0 if result.get("status") in {"answered", "no_data", "clarification", "unsupported"} else 1
