"""Safe view-model helpers that keep raw graph and attendance rows out of the UI."""

from __future__ import annotations

from typing import Any, Mapping

from attendance_analyst.graph import metric_definition

_REQUEST_KEYS = ("metric", "grouping", "start_date", "end_date")
_VALUE_KEYS = ("count", "numerator", "denominator", "rate_pct", "count_delta", "rate_delta_pp")
_QUALITY_KEYS = (
    "raw_row_count", "unique_row_count", "duplicate_count", "exact_duplicate_count",
    "conflicting_duplicates", "invalid_schedule_count", "missing_check_in_count",
    "missing_check_out_count", "observed_dates", "observed_dates_by_period",
)
_RATE_METRICS = {"late_rate", "missing_check_in_rate", "missing_check_out_rate"}
_COUNT_METRICS = {
    "late_count", "missing_check_in", "missing_check_out",
    "attendance_summary", "exceptions_by_type",
}


def _safe_metric_result(item: Mapping[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    if "group" in item:
        safe["group"] = str(item["group"])
    for key in _VALUE_KEYS:
        if key in item:
            safe[key] = item[key]
    for period_key in ("period_1", "period_2"):
        period = item.get(period_key)
        if isinstance(period, Mapping):
            safe[period_key] = {
                key: period[key]
                for key in ("count", "numerator", "denominator", "rate_pct")
                if key in period
            }
    return safe


def _safe_period_analysis(analysis: Mapping[str, Any]) -> dict[str, Any]:
    return {key: analysis[key] for key in _QUALITY_KEYS if key in analysis}


def _safe_issue(issue: object) -> str:
    normalized = str(issue).casefold()
    if "conflicting" in normalized and ("source_row_id" in normalized or "source id" in normalized):
        return "Conflicting source row identifiers were detected."
    if "query" in normalized and ("error" in normalized or "failed" in normalized):
        return "The read-only attendance query could not be completed."
    if "source_row_id" in normalized or "source row id" in normalized:
        return "An evidence issue involving source row identifiers was detected."
    if "timezone" in normalized or "date/time" in normalized or "invalid dates" in normalized:
        return "Date/time fields were inconsistent; reliability could not be verified."
    if "row limit" in normalized:
        return "The result reached the configured row limit and could not be fully checked."
    if "no matching attendance rows" in normalized:
        return "At least one selected period has no matching attendance rows."
    if "outside the requested date range" in normalized:
        return "Returned work dates fell outside the requested period."
    if "row count" in normalized and ("match" in normalized or "reconcile" in normalized):
        return "The analyzed row count did not reconcile with the query result."
    if any(word in normalized for word in ("denominator", "numerator", "rate does not reconcile", "group counts")):
        return "A metric consistency check did not pass."
    return "An evidence validation issue was detected."


def _rate_chart_cell(item: Mapping[str, Any]) -> tuple[Any, str, int]:
    denominator = int(item.get("denominator", 0) or 0)
    value = item.get("rate_pct")
    if denominator <= 0 or value is None:
        return None, "Unavailable", denominator
    return value, f"{float(value):.1f}%", denominator


def _chart_view_model(
    status: str,
    final_status: Any,
    request: Mapping[str, Any],
    analysis: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Shape calculated values for charts without deriving any metric values."""
    if status != "answered" or final_status != "supported":
        return None

    metric = str(request.get("metric", ""))
    if metric not in _RATE_METRICS and metric not in _COUNT_METRICS:
        return None
    results = analysis.get("results")
    if not isinstance(results, list) or not results:
        return None

    is_rate = metric in _RATE_METRICS
    measure_key = "rate_pct" if is_rate else "count"
    periods = request.get("comparison_periods")
    is_comparison = isinstance(periods, list)
    if is_comparison and len(periods) != 2:
        return None

    if not is_comparison:
        rows = []
        for item in results:
            group = str(item.get("group", "All records"))
            if is_rate:
                value, display_value, denominator = _rate_chart_cell(item)
                rows.append({
                    "group": group,
                    "value": value,
                    "display_value": display_value,
                    "availability": "available" if value is not None else "unavailable",
                    "denominator": denominator,
                })
            else:
                value = item.get(measure_key)
                rows.append({
                    "group": group,
                    "value": value,
                    "display_value": str(value) if value is not None else "Unavailable",
                    "availability": "available" if value is not None else "unavailable",
                })
        return {
            "type": "single_rate" if is_rate else "single_count",
            "metric": metric,
            "unit": "percent" if is_rate else "count",
            "rows": rows,
        }

    rows = []
    delta_key = "rate_delta_pp" if is_rate else "count_delta"
    for item in results:
        first = item.get("period_1")
        second = item.get("period_2")
        if not isinstance(first, Mapping) or not isinstance(second, Mapping):
            continue
        group = str(item.get("group", "All records"))
        if is_rate:
            first_value, first_display, first_denominator = _rate_chart_cell(first)
            second_value, second_display, second_denominator = _rate_chart_cell(second)
            delta = item.get(delta_key)
            delta_display = f"{float(delta):+.1f} pp" if delta is not None else "Unavailable"
            rows.append({
                "group": group,
                "period_1": first_value,
                "period_1_display": first_display,
                "period_1_denominator": first_denominator,
                "period_2": second_value,
                "period_2_display": second_display,
                "period_2_denominator": second_denominator,
                "delta": delta,
                "delta_display": delta_display,
            })
        else:
            first_value = first.get(measure_key)
            second_value = second.get(measure_key)
            delta = item.get(delta_key)
            rows.append({
                "group": group,
                "period_1": first_value,
                "period_1_display": str(first_value) if first_value is not None else "Unavailable",
                "period_2": second_value,
                "period_2_display": str(second_value) if second_value is not None else "Unavailable",
                "delta": delta,
                "delta_display": f"{int(delta):+d}" if delta is not None else "Unavailable",
            })

    if not rows:
        return None
    return {
        "type": "comparison_rate" if is_rate else "comparison_count",
        "metric": metric,
        "unit": "percent" if is_rate else "count",
        "period_1_label": "Period 1",
        "period_2_label": "Period 2",
        "period_1_dates": _period_dates_label(periods[0]),
        "period_2_dates": _period_dates_label(periods[1]),
        "delta_label": "Change (pp)" if is_rate else "Change",
        "rows": rows,
    }


def _period_dates_label(period: Mapping[str, Any]) -> str:
    start = str(period.get("start_date", ""))
    end = str(period.get("end_date", ""))
    return start if start == end else f"{start} to {end}"


def _workflow_step(label: str, state: str, detail: str | None = None) -> dict[str, str]:
    step = {"label": label, "state": state}
    if detail:
        step["detail"] = detail
    return step


def _workflow_path_view_model(
    *,
    status: str,
    final_status: Any,
    parsed_request: bool,
    query_passes: int,
    retry_count: int,
    query_failed: bool,
    calculation_ran: bool,
    comparison: bool,
) -> dict[str, Any] | None:
    """Describe the completed graph path from terminal state evidence only."""
    expected_final_status = {
        "answered": "supported",
        "no_data": "no_data",
        "abstained": "abstain",
        "clarification": None,
        "unsupported": None,
    }
    if status not in expected_final_status or final_status != expected_final_status[status]:
        return None

    parse_exit = status in {"clarification", "unsupported"}
    if parsed_request == parse_exit:
        return None
    steps = [_workflow_step("Parse request", "complete")]
    outcome_labels = {
        "answered": "Supported answer",
        "no_data": "No data",
        "abstained": "Result withheld",
        "clarification": "Clarification requested",
        "unsupported": "Unsupported question",
    }
    workflow_outcome = "supported" if status == "answered" else status

    if parse_exit:
        if status == "clarification":
            steps.append(_workflow_step("Missing information", "issue"))
        else:
            steps.append(_workflow_step("Outside supported scope", "issue"))
        steps.extend([
            _workflow_step("Query data", "not_run"),
            _workflow_step("Calculate metric", "not_run"),
            _workflow_step("Validate evidence", "not_run"),
            _workflow_step(outcome_labels[status], "outcome"),
        ])
        return {"outcome": workflow_outcome, "steps": steps, "retry_count": 0}

    if retry_count not in {0, 1} or query_passes != retry_count + 1:
        return None
    if query_failed == calculation_ran:
        return None

    if retry_count:
        steps.extend([
            _workflow_step("Query data", "complete", "Initial query pass"),
            _workflow_step("Calculate metric", "complete", "Initial calculation"),
            _workflow_step("Validate evidence", "issue", "Evidence incomplete; one retry was requested"),
            _workflow_step("Re-query evidence (1)", "retry", "Second bounded query pass"),
        ])
        query_state = "failed" if query_failed else "complete"
        query_detail = "Read-only query attempt failed" if query_failed else "Retry query completed"
        steps.append(_workflow_step("Query data (retry)", query_state, query_detail))
        calculation_state = "not_applicable" if query_failed else "complete"
        calculation_detail = "Query failure prevented metric calculation" if query_failed else "Retry calculation completed"
        steps.append(_workflow_step("Calculate metric (retry)", calculation_state, calculation_detail))
    else:
        query_state = "failed" if query_failed else "complete"
        query_detail = "Read-only query attempt failed" if query_failed else None
        steps.append(_workflow_step("Query data", query_state, query_detail))
        calculation_state = "not_applicable" if query_failed else "complete"
        calculation_detail = "Query failure prevented metric calculation" if query_failed else None
        steps.append(_workflow_step("Calculate metric", calculation_state, calculation_detail))

    if status == "answered":
        validation_state = "complete"
        validation_detail = "Evidence supports the result"
    elif status == "no_data":
        validation_state = "issue"
        validation_detail = (
            "At least one comparison period was empty; the comparison was withheld"
            if comparison
            else "No matching rows; the empty result was not treated as a zero metric"
        )
    else:
        validation_state = "failed"
        validation_detail = (
            "The query failed before evidence could be validated"
            if query_failed
            else "Evidence checks did not support a reliable result"
        )
    steps.append(_workflow_step("Validate evidence", validation_state, validation_detail))
    steps.append(_workflow_step(outcome_labels[status], "outcome"))
    return {"outcome": workflow_outcome, "steps": steps, "retry_count": retry_count}


def to_safe_view(result: Mapping[str, Any]) -> dict[str, Any]:
    """Copy only presentation-safe fields from the graph's structured state.

    Source rows, query text/parameters, and the full LangGraph state are excluded.
    """
    raw_request = result.get("request")
    request: dict[str, Any] = {}
    if isinstance(raw_request, Mapping):
        request = {key: raw_request[key] for key in _REQUEST_KEYS if key in raw_request}
        if request.get("metric"):
            request["metric_definition"] = metric_definition(str(request["metric"]))
        periods = raw_request.get("comparison_periods")
        if isinstance(periods, list):
            request["comparison_periods"] = [
                {key: period[key] for key in ("start_date", "end_date") if key in period}
                for period in periods
                if isinstance(period, Mapping)
            ]

    raw_analysis = result.get("analysis")
    analysis: dict[str, Any] = {}
    if isinstance(raw_analysis, Mapping):
        analysis = {
            key: raw_analysis[key]
            for key in _QUALITY_KEYS
            if key in raw_analysis and key != "observed_dates"
        }
        if "observed_dates" in raw_analysis:
            analysis["observed_dates"] = raw_analysis["observed_dates"]
        raw_results = raw_analysis.get("results")
        if isinstance(raw_results, list):
            analysis["results"] = [
                _safe_metric_result(item) for item in raw_results if isinstance(item, Mapping)
            ]
        period_analyses = raw_analysis.get("period_analyses")
        if isinstance(period_analyses, list):
            analysis["period_analyses"] = [
                _safe_period_analysis(item) for item in period_analyses if isinstance(item, Mapping)
            ]

    reflection_issues = result.get("reflection_issues", [])
    safe_issues = (
        list(dict.fromkeys(_safe_issue(issue) for issue in reflection_issues if issue))
        if isinstance(reflection_issues, list)
        else []
    )
    evidence = {
        "query_id": result.get("query_id"),
        "source_name": result.get("source_name"),
        "final_status": result.get("final_status"),
        "rows_read": analysis.get("raw_row_count", 0),
        "unique_rows": analysis.get("unique_row_count", 0),
        "duplicate_count": analysis.get("duplicate_count", 0),
        "conflicting_duplicates": analysis.get("conflicting_duplicates", False),
        "invalid_schedule_count": analysis.get("invalid_schedule_count", 0),
        "missing_check_in_count": analysis.get("missing_check_in_count", 0),
        "missing_check_out_count": analysis.get("missing_check_out_count", 0),
        "query_limit": result.get("query_limit"),
        "query_truncated": bool(result.get("query_truncated", False)),
        "graph_passes": result.get("execution_count", 0),
        "sql_statement_count": result.get("sql_statement_count", 0),
        "retry_count": result.get("evidence_retry_count", 0),
        "issues": safe_issues,
    }
    status = str(result.get("status", "unknown"))
    final_status = result.get("final_status")
    chart = _chart_view_model(status, final_status, request, analysis)
    query_failed = bool(result.get("query_error"))
    workflow_path = _workflow_path_view_model(
        status=status,
        final_status=final_status,
        parsed_request=bool(raw_request),
        query_passes=int(result.get("execution_count", 0) or 0),
        retry_count=int(result.get("evidence_retry_count", 0) or 0),
        query_failed=query_failed,
        calculation_ran=(
            isinstance(raw_analysis, Mapping)
            and bool(raw_analysis.get("metric"))
            and not query_failed
        ),
        comparison=bool(request.get("comparison_periods")),
    )
    return {
        "status": status,
        "message": str(result.get("message", "")),
        "request": request,
        "analysis": analysis,
        "evidence": evidence,
        "chart": chart,
        "workflow_path": workflow_path,
    }
