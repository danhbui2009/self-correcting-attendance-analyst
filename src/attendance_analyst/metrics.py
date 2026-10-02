"""Deterministic attendance metrics and evidence-quality checks."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Mapping

GRACE_MINUTES = 5


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _canonical_row(row: Mapping[str, Any]) -> tuple[str | None, ...]:
    fields = (
        "employee_key", "work_date", "department", "shift", "scheduled_start",
        "scheduled_end", "actual_check_in", "actual_check_out",
        "attendance_status", "exception_type", "source_row_id",
    )
    return tuple(str(row.get(field)) if row.get(field) is not None else None for field in fields)


def _deduplicate(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int, list[str]]:
    seen: dict[str, tuple[str | None, ...]] = {}
    unique: list[dict[str, Any]] = []
    duplicate_count = 0
    exact_duplicate_count = 0
    issues: list[str] = []
    for row in records:
        source_id = str(row.get("source_row_id") or "").strip()
        if not source_id:
            issues.append("A returned row has no source_row_id.")
            continue
        canonical = _canonical_row(row)
        if source_id in seen:
            duplicate_count += 1
            if seen[source_id] == canonical:
                exact_duplicate_count += 1
            else:
                issues.append(f"Conflicting rows share source_row_id {source_id}.")
            continue
        seen[source_id] = canonical
        unique.append(row)
    return unique, duplicate_count, exact_duplicate_count, issues


def _group_value(row: Mapping[str, Any], grouping: str | None) -> str:
    if grouping is None:
        return "All records"
    if grouping == "week":
        day = date.fromisoformat(str(row["work_date"]))
        iso = day.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if grouping == "day":
        return str(row["work_date"])
    value = row.get(grouping)
    return str(value) if value not in (None, "") else "Unspecified"


def _valid_date(row: Mapping[str, Any]) -> date | None:
    try:
        return date.fromisoformat(str(row.get("work_date")))
    except (ValueError, TypeError):
        return None


def calculate_metrics(records: list[dict[str, Any]], request: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate one supported metric, returning auditable counts and quality."""
    rows, duplicate_count, exact_duplicate_count, issues = _deduplicate(records)
    warnings: list[str] = []
    start = date.fromisoformat(str(request["start_date"]))
    end = date.fromisoformat(str(request["end_date"]))
    outside_range = [row for row in rows if (d := _valid_date(row)) is None or d < start or d > end]
    if outside_range:
        issues.append(f"{len(outside_range)} row(s) have invalid dates or fall outside the requested period.")

    invalid_schedule_count = sum(_parse_datetime(row.get("scheduled_start")) is None for row in rows)
    missing_check_in_count = sum(
        not row.get("actual_check_in") and str(row.get("attendance_status") or "").casefold() != "absent"
        for row in rows
    )
    missing_check_out_count = sum(bool(row.get("actual_check_in")) and not row.get("actual_check_out") for row in rows)
    observed_dates = sorted({str(row["work_date"]) for row in rows if _valid_date(row) is not None})

    metric = str(request["metric"])
    grouping = request.get("grouping")
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if _valid_date(row) is not None:
            buckets[_group_value(row, str(grouping) if grouping else None)].append(row)

    results: list[dict[str, Any]] = []
    if metric in {"late_count", "late_rate"}:
        for key, group_rows in sorted(buckets.items()):
            eligible = [
                row for row in group_rows
                if _parse_datetime(row.get("scheduled_start")) is not None
                and _parse_datetime(row.get("actual_check_in")) is not None
            ]
            late_count = 0
            for row in eligible:
                scheduled = _parse_datetime(row["scheduled_start"])
                actual = _parse_datetime(row["actual_check_in"])
                if scheduled is not None and actual is not None:
                    # Fixture timestamps are local naive times. Aware values must
                    # be normalized upstream rather than silently mixed.
                    if (scheduled.tzinfo is None) != (actual.tzinfo is None):
                        issues.append(f"Mixed timezone awareness in row {row.get('source_row_id')}.")
                        continue
                    if actual > scheduled + timedelta(minutes=GRACE_MINUTES):
                        late_count += 1
            denominator = len(eligible)
            results.append({
                "group": key, "count": late_count, "numerator": late_count,
                "denominator": denominator,
                "rate_pct": round(late_count * 100 / denominator, 1) if denominator else None,
            })
    elif metric in {"missing_check_in", "missing_check_in_rate"}:
        for key, group_rows in sorted(buckets.items()):
            missing = sum(
                not row.get("actual_check_in")
                and str(row.get("attendance_status") or "").casefold() != "absent"
                for row in group_rows
            )
            denominator = len(group_rows)
            results.append({
                "group": key, "count": missing, "numerator": missing,
                "denominator": denominator,
                "rate_pct": round(missing * 100 / denominator, 1) if denominator else None,
            })
    elif metric in {"missing_check_out", "missing_check_out_rate"}:
        for key, group_rows in sorted(buckets.items()):
            attended = [row for row in group_rows if row.get("actual_check_in")]
            missing = sum(not row.get("actual_check_out") for row in attended)
            denominator = len(attended)
            results.append({
                "group": key, "count": missing, "numerator": missing,
                "denominator": denominator,
                "rate_pct": round(missing * 100 / denominator, 1) if denominator else None,
            })
    elif metric == "exceptions_by_type":
        counts: dict[str, int] = defaultdict(int)
        for row in rows:
            kind = str(row.get("exception_type") or "").strip()
            if kind:
                counts[kind] += 1
        results = [
            {"group": kind, "count": count, "numerator": count, "denominator": len(rows), "rate_pct": None}
            for kind, count in sorted(counts.items())
        ]
    elif metric == "attendance_summary":
        for key, group_rows in sorted(buckets.items()):
            results.append({
                "group": key, "count": len(group_rows), "numerator": len(group_rows),
                "denominator": len(rows), "rate_pct": None,
            })
    else:
        issues.append(f"Unsupported metric in state: {metric}.")

    if exact_duplicate_count:
        warnings.append(f"Removed {exact_duplicate_count} exact duplicate source row(s) by source_row_id.")
    return {
        "metric": metric,
        "results": results,
        "raw_row_count": len(records),
        "unique_row_count": len(rows),
        "duplicate_count": duplicate_count,
        "exact_duplicate_count": exact_duplicate_count,
        "conflicting_duplicates": any(issue.startswith("Conflicting rows") for issue in issues),
        "invalid_schedule_count": invalid_schedule_count,
        "missing_check_in_count": missing_check_in_count,
        "missing_check_out_count": missing_check_out_count,
        "observed_dates": observed_dates,
        "issues": issues,
        "warnings": warnings,
    }


def calculate_comparison(
    period_records: list[list[dict[str, Any]]], request: Mapping[str, Any]
) -> dict[str, Any]:
    """Calculate the same metric independently for two periods, then join groups.

    Missing groups within a populated period have a count of zero. A rate for a
    missing group remains unavailable because its denominator is zero. Empty
    periods are preserved as empty evidence; callers must not interpret them as
    zero-valued observations.
    """
    periods = request.get("comparison_periods")
    if not isinstance(periods, list) or len(periods) != 2 or len(period_records) != 2:
        raise ValueError("A comparison requires exactly two periods and two result sets.")

    analyses: list[dict[str, Any]] = []
    period_requests: list[dict[str, Any]] = []
    for period, records in zip(periods, period_records):
        period_request = {
            "metric": request["metric"],
            "grouping": request.get("grouping"),
            "start_date": period["start_date"],
            "end_date": period["end_date"],
        }
        period_requests.append(period_request)
        analyses.append(calculate_metrics(records, period_request))

    groups = sorted({
        str(item["group"])
        for analysis in analyses
        for item in analysis.get("results", [])
    })
    by_period = [
        {str(item["group"]): item for item in analysis.get("results", [])}
        for analysis in analyses
    ]
    is_rate = str(request.get("metric", "")).endswith("_rate")
    results: list[dict[str, Any]] = []
    for group in groups:
        values: list[dict[str, Any]] = []
        for indexed in by_period:
            values.append(indexed.get(group, {
                "group": group,
                "count": 0,
                "numerator": 0,
                "denominator": 0,
                "rate_pct": None,
            }))
        first, second = values
        result: dict[str, Any] = {
            "group": group,
            "period_1": dict(first),
            "period_2": dict(second),
        }
        if is_rate:
            first_denominator = int(first.get("denominator", 0))
            second_denominator = int(second.get("denominator", 0))
            result["rate_delta_pp"] = (
                round(
                    (int(second.get("numerator", 0)) / second_denominator
                     - int(first.get("numerator", 0)) / first_denominator) * 100,
                    1,
                )
                if first_denominator and second_denominator
                else None
            )
        else:
            result["count_delta"] = int(second.get("count", 0)) - int(first.get("count", 0))
        results.append(result)

    combined_issues = [
        f"Period {index}: {issue}"
        for index, analysis in enumerate(analyses, start=1)
        for issue in analysis.get("issues", [])
    ]
    return {
        "metric": request["metric"],
        "results": results,
        "period_analyses": analyses,
        "period_requests": period_requests,
        "raw_row_count": sum(int(item.get("raw_row_count", 0)) for item in analyses),
        "unique_row_count": sum(int(item.get("unique_row_count", 0)) for item in analyses),
        "duplicate_count": sum(int(item.get("duplicate_count", 0)) for item in analyses),
        "exact_duplicate_count": sum(int(item.get("exact_duplicate_count", 0)) for item in analyses),
        "conflicting_duplicates": any(item.get("conflicting_duplicates") for item in analyses),
        "invalid_schedule_count": sum(int(item.get("invalid_schedule_count", 0)) for item in analyses),
        "missing_check_in_count": sum(int(item.get("missing_check_in_count", 0)) for item in analyses),
        "missing_check_out_count": sum(int(item.get("missing_check_out_count", 0)) for item in analyses),
        "observed_dates_by_period": [item.get("observed_dates", []) for item in analyses],
        "issues": combined_issues,
        "warnings": [warning for item in analyses for warning in item.get("warnings", [])],
    }
