"""Bounded LangGraph workflow for evidence-checked attendance analysis."""

from __future__ import annotations

from hashlib import sha256
import json
from datetime import date
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from attendance_analyst.database import (
    DEFAULT_CSV,
    INITIAL_ROW_LIMIT,
    READ_QUERY,
    RETRY_ROW_LIMIT,
    load_synthetic_rows,
    read_attendance_rows,
)
from attendance_analyst.metrics import calculate_comparison, calculate_metrics
from attendance_analyst.parser import parse_question


class AnalystState(TypedDict, total=False):
    question: str
    source_records: list[dict[str, Any]]
    source_name: str
    request: dict[str, Any]
    status: str
    message: str
    records: list[dict[str, Any]]
    period_records: list[list[dict[str, Any]]]
    query: str
    query_parameters: list[object]
    query_id: str
    query_limit: int
    query_truncated: bool
    query_error: str | None
    execution_count: int
    sql_statement_count: int
    evidence_retry_count: int
    analysis: dict[str, Any]
    reflection_issues: list[str]
    final_status: str
    answer: str


def _query_id(
    parameters: tuple[object, ...] | list[tuple[object, ...]], records: list[dict[str, Any]]
) -> str:
    payload = {
        "query": " ".join(READ_QUERY.split()),
        "parameters": [list(item) for item in parameters] if parameters and isinstance(parameters[0], tuple) else list(parameters),
        "source_row_ids": [row.get("source_row_id") for row in records],
    }
    digest = sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]
    return f"EVI-{digest}"


def _parse_node(state: AnalystState) -> dict[str, Any]:
    parsed = parse_question(state.get("question", ""))
    update: dict[str, Any] = {"status": parsed["status"]}
    if "request" in parsed:
        update["request"] = parsed["request"]
        update["evidence_retry_count"] = 0
        update["execution_count"] = 0
    else:
        update["message"] = str(parsed["message"])
    return update


def _route_after_parse(state: AnalystState) -> str:
    return "query" if state.get("status") == "ready" else "answer"


def _query_node(state: AnalystState, initial_limit: int, retry_limit: int) -> dict[str, Any]:
    request = state["request"]
    retry_count = int(state.get("evidence_retry_count", 0))
    limit = retry_limit if retry_count else initial_limit
    # Read one look-ahead row so an exactly full result can be distinguished
    # from a truncated result without treating an exact-cap dataset as overflow.
    comparison_periods = request.get("comparison_periods")
    parameter_sets: list[tuple[object, ...]] = (
        [(period["start_date"], period["end_date"], limit + 1) for period in comparison_periods]
        if comparison_periods else
        [(request["start_date"], request["end_date"], limit + 1)]
    )
    period_records: list[list[dict[str, Any]]] = []
    try:
        for params in parameter_sets:
            period_records.append(read_attendance_rows(
                state.get("source_records", []), str(params[0]), str(params[1]), int(params[2])
            ))
        records = [row for period_rows in period_records for row in period_rows]
        return {
            "records": records,
            "period_records": period_records if comparison_periods else [],
            "query": READ_QUERY,
            "query_parameters": [list(params) for params in parameter_sets] if comparison_periods else list(parameter_sets[0]),
            "query_id": _query_id(parameter_sets if comparison_periods else parameter_sets[0], records),
            "query_limit": limit,
            "query_truncated": (
                any(len(period_rows) > limit for period_rows in period_records)
                if comparison_periods else len(records) > limit
            ),
            "query_error": None,
            "execution_count": int(state.get("execution_count", 0)) + 1,
            "sql_statement_count": int(state.get("sql_statement_count", 0)) + len(parameter_sets),
        }
    except Exception as error:  # surfaced as a final evidence failure, never guessed around
        records = [row for period_rows in period_records for row in period_rows]
        return {
            "records": records,
            "period_records": period_records if comparison_periods else [],
            "query": READ_QUERY,
            "query_parameters": [list(params) for params in parameter_sets] if comparison_periods else list(parameter_sets[0]),
            "query_id": _query_id(parameter_sets if comparison_periods else parameter_sets[0], records),
            "query_limit": limit,
            "query_truncated": False,
            "query_error": f"{type(error).__name__}: {error}",
            "execution_count": int(state.get("execution_count", 0)) + 1,
            "sql_statement_count": int(state.get("sql_statement_count", 0)) + len(period_records) + 1,
        }


def _analyze_node(state: AnalystState) -> dict[str, Any]:
    if state.get("query_error"):
        return {"analysis": {"issues": [str(state["query_error"])]}}
    request = state["request"]
    if request.get("comparison_periods"):
        return {"analysis": calculate_comparison(state.get("period_records", []), request)}
    return {"analysis": calculate_metrics(state.get("records", []), request)}


def _validate_period_evidence(
    analysis: dict[str, Any],
    records: list[dict[str, Any]],
    start_date: str,
    end_date: str,
    metric: str,
    *,
    require_rate_denominator: bool = True,
) -> list[str]:
    issues = list(analysis.get("issues", []))
    if len(records) != int(analysis.get("raw_row_count", len(records))):
        issues.append("The analyzed row count does not match the query result row count.")
    observed_dates = analysis.get("observed_dates", [])
    if any(not start_date <= value <= end_date for value in observed_dates):
        issues.append("Returned work dates fall outside the requested date range.")
    if analysis.get("conflicting_duplicates"):
        issues.append("Conflicting duplicate source IDs prevent a reliable result.")
    if any("invalid dates" in issue or "Mixed timezone" in issue for issue in issues):
        issues.append("The date/time fields are inconsistent; a reliable result cannot be verified.")

    results = analysis.get("results", [])
    unique_count = int(analysis.get("unique_row_count", len(records)))
    if metric == "attendance_summary" and sum(int(item.get("count", 0)) for item in results) != unique_count:
        issues.append("Attendance summary group counts do not reconcile to the unique query row count.")
    if metric in {"missing_check_in", "missing_check_in_rate"} and sum(
        int(item.get("denominator", 0)) for item in results
    ) != unique_count:
        issues.append("Missing check-in denominators do not reconcile to the unique query row count.")
    if metric in {"late_count", "late_rate", "missing_check_out", "missing_check_out_rate"}:
        for item in results:
            numerator = int(item.get("numerator", 0))
            denominator = int(item.get("denominator", 0))
            if numerator > denominator:
                issues.append(f"Metric numerator exceeds denominator for group {item.get('group')}.")
            if denominator and item.get("rate_pct") != round(numerator * 100 / denominator, 1):
                issues.append(f"Metric rate does not reconcile for group {item.get('group')}.")
    if require_rate_denominator and metric.endswith("_rate") and records and not any(
        item.get("denominator", 0) for item in results
    ):
        issues.append("No eligible records are available for the requested rate denominator.")
    return list(dict.fromkeys(issues))


def _reflect_node(state: AnalystState) -> dict[str, Any]:
    """Check concrete data invariants and permit one larger bounded query."""
    if state.get("query_error"):
        return {
            "reflection_issues": [str(state["query_error"])],
            "final_status": "abstain",
        }

    analysis = state.get("analysis", {})
    request = state.get("request", {})
    records = state.get("records", [])
    start_date = str(request.get("start_date", ""))
    end_date = str(request.get("end_date", ""))

    if state.get("query_truncated"):
        retries = int(state.get("evidence_retry_count", 0))
        if retries < 1:
            return {
                "evidence_retry_count": retries + 1,
                "reflection_issues": [
                    f"The result reached the {state.get('query_limit')} row limit; retry once with a larger limit."
                ],
                "final_status": "retry",
            }
        return {
            "reflection_issues": [
                f"The result still reached the {state.get('query_limit')} row limit after the one allowed retry."
            ],
            "final_status": "abstain",
        }

    comparison_periods = request.get("comparison_periods")
    if comparison_periods:
        period_records = state.get("period_records", [])
        period_analyses = analysis.get("period_analyses", [])
        issues: list[str] = []
        if len(period_records) != 2 or len(period_analyses) != 2:
            issues.append("The query or analysis did not return evidence for both comparison periods.")
        for index, (period, period_rows, period_analysis) in enumerate(
            zip(comparison_periods, period_records, period_analyses), start=1
        ):
            issues.extend(
                f"Period {index}: {issue}"
                for issue in _validate_period_evidence(
                    period_analysis,
                    period_rows,
                    str(period["start_date"]),
                    str(period["end_date"]),
                    str(request.get("metric", "")),
                    require_rate_denominator=False,
                )
            )
        if len(period_records) == 2:
            first_ids = {str(row.get("source_row_id") or "") for row in period_records[0]}
            second_ids = {str(row.get("source_row_id") or "") for row in period_records[1]}
            shared_ids = sorted((first_ids & second_ids) - {""})
            if shared_ids:
                issues.append(
                    "Source row IDs occur in both non-overlapping periods: "
                    + ", ".join(shared_ids[:5]) + "."
                )
        if issues:
            return {"reflection_issues": list(dict.fromkeys(issues)), "final_status": "abstain"}
        empty_periods = [index for index, period_rows in enumerate(period_records, start=1) if not period_rows]
        if empty_periods:
            labels = ", ".join(f"Period {index}" for index in empty_periods)
            return {
                "reflection_issues": [f"{labels} has no matching attendance rows; comparison withheld."],
                "final_status": "no_data",
            }
        return {"reflection_issues": [], "final_status": "supported"}

    metric = str(request.get("metric", ""))
    issues = _validate_period_evidence(analysis, records, start_date, end_date, metric)

    if issues:
        return {"reflection_issues": list(dict.fromkeys(issues)), "final_status": "abstain"}
    if not records:
        return {"reflection_issues": [], "final_status": "no_data"}
    return {"reflection_issues": [], "final_status": "supported"}


def _route_after_reflection(state: AnalystState) -> str:
    return "retry" if state.get("final_status") == "retry" else "answer"


def metric_definition(metric: str) -> str:
    """Return the canonical, deterministic display definition for a supported metric."""
    definitions = {
        "late_count": f"Late arrivals are check-ins more than {5} minutes after scheduled start; only valid check-ins with a valid scheduled start are eligible.",
        "late_rate": f"Late arrivals divided by eligible check-ins; late means more than {5} minutes after scheduled start.",
        "missing_check_in": "Rows without a check-in, excluding rows explicitly marked absent.",
        "missing_check_in_rate": "Rows without a check-in, excluding rows explicitly marked absent, divided by all returned shift rows.",
        "missing_check_out": "Rows with a check-in but no check-out.",
        "missing_check_out_rate": "Rows with a check-in but no check-out divided by rows with a check-in.",
        "exceptions_by_type": "Count of rows with a non-empty exception_type, grouped by that source label.",
        "attendance_summary": "Count of returned shift rows grouped by the selected field (attendance_status by default).",
    }
    return definitions.get(metric, "Metric definition unavailable.")


def _period_label(period: dict[str, Any]) -> str:
    start = date.fromisoformat(str(period["start_date"]))
    end = date.fromisoformat(str(period["end_date"]))
    days = (end - start).days + 1
    suffix = "day" if days == 1 else "days"
    return f"{start.isoformat()} through {end.isoformat()} (inclusive, {days} {suffix})"


def _render_comparison_answer(state: AnalystState, final_status: str) -> dict[str, Any]:
    request = state.get("request", {})
    periods = request.get("comparison_periods", [])
    analysis = state.get("analysis", {})
    metric = str(request.get("metric", ""))
    source_name = state.get("source_name", "attendance data")
    evidence = state.get("query_id", "unavailable")
    rows = state.get("records", [])
    title = {
        "abstain": "Status: abstained",
        "no_data": "Status: no data",
    }.get(final_status, "Status: answered")
    lines = [
        title,
        f"Period 1: {_period_label(periods[0])}",
        f"Period 2: {_period_label(periods[1])}",
        f"Metric definition: {metric_definition(metric)}",
    ]
    if final_status == "abstain":
        reasons = "; ".join(state.get("reflection_issues", [])) or "Evidence checks did not pass."
        lines.extend([
            "Results: withheld because the evidence checks did not pass.",
            f"Reason: {reasons}",
        ])
    elif final_status == "no_data":
        reasons = "; ".join(state.get("reflection_issues", [])) or "At least one period has no matching rows."
        lines.extend([
            "Results: comparison withheld because at least one period has no matching attendance rows; an empty period is not treated as zero.",
            f"Reason: {reasons}",
        ])
    else:
        lines.append("Results (delta = Period 2 minus Period 1):")
        if metric.endswith("_rate"):
            lines.append("Percentage-point changes are calculated from the unrounded numerator/denominator values, then rounded to one decimal place.")
        for item in analysis.get("results", []):
            group = item.get("group", "All records")
            first = item.get("period_1", {})
            second = item.get("period_2", {})
            if metric.endswith("_rate"):
                def rate_value(value: dict[str, Any]) -> str:
                    if not value.get("denominator") or value.get("rate_pct") is None:
                        return "unavailable (denominator 0)"
                    return f"{value.get('numerator')}/{value.get('denominator')} = {value.get('rate_pct')}%"

                delta = item.get("rate_delta_pp")
                change = (
                    f"{float(delta):+.1f} percentage points"
                    if delta is not None else "unavailable (a period has denominator 0)"
                )
                lines.append(
                    f"- {group}: Period 1={rate_value(first)}; Period 2={rate_value(second)}; change={change}."
                )
            else:
                first_count = int(first.get("count", 0))
                second_count = int(second.get("count", 0))
                delta = int(item.get("count_delta", second_count - first_count))
                details = ""
                if metric == "late_count":
                    details = (
                        f" (eligible check-ins P1={first.get('denominator', 0)}, "
                        f"P2={second.get('denominator', 0)})"
                    )
                lines.append(
                    f"- {group}: Period 1={first_count}; Period 2={second_count}; delta={delta:+d}{details}."
                )
        if not analysis.get("results") and metric == "exceptions_by_type":
            lines.append("- No exception_type values were recorded in either period.")
        durations = [
            (date.fromisoformat(str(period["end_date"])) - date.fromisoformat(str(period["start_date"]))).days + 1
            for period in periods
        ]
        if durations[0] != durations[1] and not metric.endswith("_rate"):
            lines.append("Count deltas are raw totals; the periods have different lengths and counts are not normalized per day.")

    observed_by_period = analysis.get("observed_dates_by_period", [])
    observed_parts: list[str] = []
    for index in range(2):
        observed = observed_by_period[index] if len(observed_by_period) > index else []
        observed_text = f"{observed[0]} to {observed[-1]}" if observed else "none"
        observed_parts.append(f"P{index + 1}={observed_text}")
    lines.append(
        f"Evidence: {evidence}; source={source_name}; read-only SELECTs={state.get('sql_statement_count', 0)}; "
        f"rows read={analysis.get('raw_row_count', len(rows))}; observed work dates: "
        + "; ".join(observed_parts) + "."
    )
    lines.append(f"Evidence re-queries: {state.get('evidence_retry_count', 0)} (maximum one retry for the pair).")
    if final_status == "supported":
        quality_notes: list[str] = []
        if analysis.get("duplicate_count"):
            quality_notes.append(f"removed {analysis['duplicate_count']} duplicate row(s) by source_row_id before calculations")
        if analysis.get("invalid_schedule_count"):
            quality_notes.append(
                f"{analysis['invalid_schedule_count']} row(s) had no valid scheduled_start and were excluded from late-arrival eligibility"
            )
        if analysis.get("missing_check_in_count"):
            quality_notes.append(f"{analysis['missing_check_in_count']} non-absence row(s) had no check-in")
        if analysis.get("missing_check_out_count"):
            quality_notes.append(f"{analysis['missing_check_out_count']} checked-in row(s) had no check-out")
        if quality_notes:
            lines.append("Data caveats: " + "; ".join(quality_notes) + ".")
        lines.append("Data is synthetic and demonstrates the workflow; it is not a finding about actual employees.")
    return {
        "answer": "\n".join(lines),
        "status": {
            "abstain": "abstained",
            "no_data": "no_data",
            "supported": "answered",
        }.get(final_status, "abstained"),
    }


def _render_answer(state: AnalystState) -> dict[str, Any]:
    status = state.get("status", "unknown")
    if status in {"clarification", "unsupported"}:
        return {"answer": f"{status.title()}: {state.get('message', 'No answer was produced.')}"}

    final_status = state.get("final_status", "abstain")
    request = state.get("request", {})
    if request.get("comparison_periods"):
        return _render_comparison_answer(state, final_status)
    start_date = request.get("start_date", "unknown")
    end_date = request.get("end_date", "unknown")
    metric = str(request.get("metric", ""))
    analysis = state.get("analysis", {})
    rows = state.get("records", [])
    source_name = state.get("source_name", "attendance data")
    evidence = state.get("query_id", "unavailable")

    if final_status == "abstain":
        reasons = "; ".join(state.get("reflection_issues", [])) or "Evidence checks did not pass."
        read_rows = analysis.get("raw_row_count", len(rows))
        observed = analysis.get("observed_dates", [])
        observed_text = f"{observed[0]} to {observed[-1]}" if observed else "none"
        answer = "\n".join([
            "Status: abstained",
            f"Reporting period: {start_date} through {end_date} (inclusive)",
            f"Metric definition: {metric_definition(metric)}",
            "Results: withheld because the evidence checks did not pass.",
            f"Evidence: {evidence}; source={source_name}; read-only SELECT; rows read={read_rows}; observed work dates={observed_text}.",
            f"Evidence re-queries: {state.get('evidence_retry_count', 0)}.",
            f"Reason: {reasons}",
        ])
        return {"answer": answer, "status": "abstained"}

    if final_status == "no_data":
        answer = "\n".join([
            "Status: no data",
            f"Reporting period: {start_date} through {end_date} (inclusive)",
            f"Metric definition: {metric_definition(metric)}",
            "Results: no matching attendance rows.",
            f"Evidence: {evidence}; source={source_name}; read-only SELECT; rows read=0; observed work dates=none.",
            f"Evidence re-queries: {state.get('evidence_retry_count', 0)}.",
            "This does not establish that no attendance events occurred; the selected dataset has no matching rows.",
        ])
        return {"answer": answer, "status": "no_data"}

    result_lines: list[str] = []
    for item in analysis.get("results", []):
        group = item.get("group", "All records")
        if metric.endswith("_rate") or metric == "late_count":
            denominator = item.get("denominator")
            numerator = item.get("numerator")
            rate = item.get("rate_pct")
            if metric.endswith("_rate"):
                value = f"{numerator}/{denominator} = {rate}%" if denominator else "rate unavailable (denominator 0)"
            else:
                value = f"{item.get('count')} late; eligible check-ins={denominator}"
        elif metric in {"missing_check_in", "missing_check_out"}:
            value = f"{item.get('count')} / denominator {item.get('denominator')}"
        elif metric in {"missing_check_in_rate", "missing_check_out_rate"}:
            denominator = item.get("denominator")
            value = f"{item.get('numerator')}/{denominator} = {item.get('rate_pct')}%" if denominator else "rate unavailable (denominator 0)"
        else:
            value = f"{item.get('count')} rows"
        result_lines.append(f"- {group}: {value}")

    if not result_lines and metric == "exceptions_by_type":
        result_lines.append("- No exception_type values were recorded in the selected rows.")

    quality_notes: list[str] = []
    if analysis.get("duplicate_count"):
        quality_notes.append(
            f"Removed {analysis['duplicate_count']} exact duplicate row(s) by source_row_id before calculating metrics."
        )
    if analysis.get("invalid_schedule_count"):
        quality_notes.append(
            f"{analysis['invalid_schedule_count']} row(s) had no valid scheduled_start and were excluded from late-arrival eligibility."
        )
    if analysis.get("missing_check_in_count"):
        quality_notes.append(f"{analysis['missing_check_in_count']} non-absence row(s) had no check-in.")
    if analysis.get("missing_check_out_count"):
        quality_notes.append(f"{analysis['missing_check_out_count']} checked-in row(s) had no check-out.")

    observed = analysis.get("observed_dates", [])
    observed_text = f"{observed[0]} to {observed[-1]}" if observed else "none"
    answer_lines = [
        f"Status: answered",
        f"Reporting period: {start_date} through {end_date} (inclusive)",
        f"Metric definition: {metric_definition(metric)}",
        "Results:",
        *result_lines,
        f"Evidence: {evidence}; source={source_name}; read-only SELECT; rows read={analysis.get('raw_row_count', len(rows))}; observed work dates={observed_text}.",
        f"Evidence re-queries: {state.get('evidence_retry_count', 0)}.",
    ]
    if quality_notes:
        answer_lines.append("Data caveats: " + " ".join(quality_notes))
    answer_lines.append("Data is synthetic and demonstrates the workflow; it is not a finding about actual employees.")
    return {"answer": "\n".join(answer_lines), "status": "answered"}


def build_graph(
    *,
    initial_row_limit: int = INITIAL_ROW_LIMIT,
    retry_row_limit: int = RETRY_ROW_LIMIT,
):
    if not 1 <= initial_row_limit < retry_row_limit <= RETRY_ROW_LIMIT:
        raise ValueError("Limits must satisfy 1 <= initial_row_limit < retry_row_limit <= RETRY_ROW_LIMIT.")

    graph = StateGraph(AnalystState)
    graph.add_node("parse_question", _parse_node)
    graph.add_node("query_attendance", lambda state: _query_node(state, initial_row_limit, retry_row_limit))
    graph.add_node("calculate_metrics", _analyze_node)
    graph.add_node("reflect_on_evidence", _reflect_node)
    graph.add_node("render_answer", _render_answer)

    graph.add_edge(START, "parse_question")
    graph.add_conditional_edges(
        "parse_question",
        _route_after_parse,
        {"query": "query_attendance", "answer": "render_answer"},
    )
    graph.add_edge("query_attendance", "calculate_metrics")
    graph.add_edge("calculate_metrics", "reflect_on_evidence")
    graph.add_conditional_edges(
        "reflect_on_evidence",
        _route_after_reflection,
        {"retry": "query_attendance", "answer": "render_answer"},
    )
    graph.add_edge("render_answer", END)
    return graph.compile()


def run_question(
    question: str,
    *,
    rows: list[dict[str, Any]] | None = None,
    csv_path: Path = DEFAULT_CSV,
    initial_row_limit: int = INITIAL_ROW_LIMIT,
    retry_row_limit: int = RETRY_ROW_LIMIT,
) -> dict[str, Any]:
    source_records = rows if rows is not None else load_synthetic_rows(csv_path)
    graph = build_graph(initial_row_limit=initial_row_limit, retry_row_limit=retry_row_limit)
    return graph.invoke(
        {
            "question": question,
            "source_records": source_records,
            "source_name": "synthetic_attendance.csv" if rows is None else "provided synthetic test rows",
        },
        config={"recursion_limit": 12},
    )
