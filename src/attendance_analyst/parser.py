"""Small, credential-free intent parser for the supported MVP questions."""

from __future__ import annotations

from datetime import date
import re

DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
DATE_RANGE_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2})\s+(?:to|through|until|đến|tới)\s+(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

SUPPORTED_QUESTION_FAMILIES = (
    "late arrival counts or rates",
    "missing check-in counts or rates",
    "missing check-out counts or rates",
    "attendance exceptions by type",
    "attendance summary counts",
)


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


_FAMILY_TERMS = {
    "missing_check_in": (
        "missing check-in", "missing check in", "missing clock-in",
        "thiếu check-in", "thiếu giờ vào", "thiếu chấm công vào",
    ),
    "missing_check_out": (
        "missing check-out", "missing check out", "missing clock-out",
        "thiếu check-out", "thiếu giờ ra", "thiếu chấm công ra",
    ),
    "exceptions": ("exception", "ngoại lệ", "loại lỗi"),
    "attendance_summary": (
        "attendance summary", "attendance status", "tổng quan chấm công",
        "phân bổ trạng thái", "trạng thái chấm công",
    ),
    "late": ("late", "tardy", "đi muộn", "đi trễ"),
}

_GROUP_TERMS = {
    "department": ("by department", "per department", "by dept", "and department", "and dept", "theo phòng ban", "theo bộ phận"),
    "shift": ("by shift", "per shift", "and shift", "theo ca"),
    "week": ("by week", "weekly", "and week", "theo tuần"),
    "day": ("by day", "daily", "and day", "theo ngày"),
    "attendance_status": ("by status", "per status", "and status", "theo trạng thái"),
}


def _clarification(message: str) -> dict[str, str]:
    return {"status": "clarification", "message": message}


def _is_comparison(text: str) -> bool:
    return (
        _has_any(text, ("compare", "comparison", "so sánh", "so với", "versus"))
        or re.search(r"\bvs\.?\b", text) is not None
    )


def _parse_comparison_periods(
    dates: list[str], text: str
) -> tuple[list[dict[str, str]] | None, str | None]:
    ranges = DATE_RANGE_PATTERN.findall(text)
    if len(dates) != 4 or len(ranges) != 2:
        return None, (
            "For a comparison, provide exactly two inclusive date ranges in order: "
            "Period 1 start/end, then Period 2 start/end (four YYYY-MM-DD dates)."
        )
    try:
        parsed = [date.fromisoformat(value) for value in dates]
    except ValueError:
        return None, "One comparison date is invalid. Use real calendar dates in YYYY-MM-DD format."

    first_start, first_end, second_start, second_end = parsed
    if first_start > first_end or second_start > second_end:
        return None, "Each comparison period must have its start date on or before its end date."
    if first_end >= second_start:
        return None, "Period 1 must come before Period 2, and the two inclusive date ranges must not overlap."
    periods = [
        {"start_date": first_start.isoformat(), "end_date": first_end.isoformat()},
        {"start_date": second_start.isoformat(), "end_date": second_end.isoformat()},
    ]
    return periods, None


def parse_question(question: str) -> dict[str, object]:
    """Return a narrow, typed-by-convention request or a clarification result.

    The MVP deliberately parses a fixed set of user intents without a remote
    model. Dates must be explicit ISO calendar dates so that the query can be
    parameterized and the requested reporting window is unambiguous.
    """
    text = " ".join(question.casefold().split())
    if not text:
        return {"status": "clarification", "message": "Please enter an attendance question."}

    if _has_any(text, ("disciplin", "terminate", "fire employee", "sa thải", "kỷ luật", "xếp hạng nhân viên")):
        return {
            "status": "unsupported",
            "message": "This demo does not make employee-level rankings or employment decisions.",
        }

    is_comparison = _is_comparison(text)

    families = [name for name, terms in _FAMILY_TERMS.items() if _has_any(text, terms)]
    if len(families) > 1:
        return _clarification("Ask for one attendance metric family at a time so the result is not silently narrowed.")
    if not families:
        supported = "; ".join(SUPPORTED_QUESTION_FAMILIES)
        return {
            "status": "unsupported",
            "message": f"I could not map that question to the supported MVP metrics: {supported}.",
        }

    grouping_matches = [name for name, terms in _GROUP_TERMS.items() if _has_any(text, terms)]
    if len(grouping_matches) > 1:
        return _clarification("Ask for one grouping dimension at a time (for example, by department or by shift).")

    family = families[0]
    if family == "missing_check_in":
        metric = "missing_check_in_rate" if _has_any(text, ("rate", "percentage", "tỷ lệ", "%")) else "missing_check_in"
    elif family == "missing_check_out":
        metric = "missing_check_out_rate" if _has_any(text, ("rate", "percentage", "tỷ lệ", "%")) else "missing_check_out"
    elif family == "exceptions":
        metric = "exceptions_by_type"
    elif family == "attendance_summary":
        metric = "attendance_summary"
    else:
        metric = "late_rate" if _has_any(text, ("rate", "percentage", "tỷ lệ", "%")) else "late_count"

    if family in {"late", "missing_check_in", "missing_check_out"}:
        asks_rate = _has_any(text, ("rate", "percentage", "tỷ lệ", "%"))
        asks_count = _has_any(text, ("count", "counts", "how many", "number of", "đếm", "số lượng"))
        if asks_rate and asks_count:
            return _clarification("Do you want a count or a rate? Ask for one result type at a time.")

    dates = DATE_PATTERN.findall(text)
    comparison_periods: list[dict[str, str]] | None = None
    if is_comparison:
        comparison_periods, error = _parse_comparison_periods(dates, text)
        if error:
            return _clarification(error)
    else:
        if len(dates) != 2:
            return {
                "status": "clarification",
                "message": "Provide one inclusive date range using two ISO dates, for example 2026-01-05 to 2026-01-09.",
            }
        try:
            start = date.fromisoformat(dates[0])
            end = date.fromisoformat(dates[1])
        except ValueError:
            return {
                "status": "clarification",
                "message": "One date is invalid. Use real calendar dates in YYYY-MM-DD format.",
            }
        if start > end:
            return {
                "status": "clarification",
                "message": "The start date is after the end date. Provide the range in chronological order.",
            }

    grouping: str | None = grouping_matches[0] if grouping_matches else None

    if metric == "exceptions_by_type":
        if grouping is not None:
            return _clarification("Attendance exceptions are grouped by exception type in this MVP; remove the other grouping.")
        grouping = "exception_type"
    elif metric == "attendance_summary" and grouping is None:
        grouping = "attendance_status"

    request: dict[str, object] = {"metric": metric, "grouping": grouping}
    if comparison_periods is not None:
        request["comparison_periods"] = comparison_periods
    else:
        request["start_date"] = start.isoformat()
        request["end_date"] = end.isoformat()
    return {"status": "ready", "request": request}
