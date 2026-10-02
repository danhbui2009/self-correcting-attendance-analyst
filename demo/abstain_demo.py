"""Show a controlled evidence conflict and verify the analyst abstains."""

from __future__ import annotations

import sys
from typing import Any

from attendance_analyst.database import load_synthetic_rows
from attendance_analyst.graph import run_question


QUESTION = "How many late arrivals from 2026-01-05 to 2026-01-09?"


def conflicting_rows() -> list[dict[str, Any]]:
    """Return the shared synthetic fixture with one conflicting duplicate row."""
    rows = load_synthetic_rows()
    conflict = rows[0].copy()
    conflict["department"] = "Conflicting Department"
    return rows + [conflict]


def run_demo() -> dict[str, Any]:
    """Use the same synthetic duplicate-ID conflict pattern as the graph test."""
    return run_question(QUESTION, rows=conflicting_rows())


def main() -> int:
    result = run_demo()
    print(result.get("answer", "No answer was produced."))
    if result.get("status") != "abstained":
        print(
            "Expected the controlled conflicting source_row_id scenario to abstain.",
            file=sys.stderr,
        )
        return 1
    print("Verified demo outcome: the analyst withheld the result after detecting conflicting evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
