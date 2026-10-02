"""Streamlit presentation for the synthetic attendance analyst."""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from attendance_analyst.graph import run_question
from demo.abstain_demo import conflicting_rows
from ui.presentation import to_safe_view


DEFAULT_QUESTION = "What was the late rate by department from 2026-01-05 to 2026-01-09?"

EXAMPLES = {
    "Late rate": DEFAULT_QUESTION,
    "Missing check-out": (
        "What is the missing check-out rate by department "
        "from 2026-01-05 to 2026-01-09?"
    ),
    "Attendance summary": (
        "Give an attendance summary by status from 2026-01-05 to 2026-01-09."
    ),
    "Compare periods": (
        "Compare late rates by department from 2026-01-05 to 2026-01-05 "
        "versus 2026-01-06 to 2026-01-09"
    ),
    "No data": (
        "What was the late rate by department from 2026-02-01 to 2026-02-05?"
    ),
    "Clarification": "What was the late rate by department?",
}

METRIC_LABELS = {
    "late_rate": "Late-arrival rate",
    "late_count": "Late-arrival count",
    "missing_check_in": "Missing check-in count",
    "missing_check_in_rate": "Missing check-in rate",
    "missing_check_out": "Missing check-out count",
    "missing_check_out_rate": "Missing check-out rate",
    "exceptions_by_type": "Attendance exceptions",
    "attendance_summary": "Attendance summary",
}


def _clear_result() -> None:
    st.session_state["result"] = None
    st.session_state["result_question"] = None
    st.session_state["result_scenario"] = None
    st.session_state["runtime_error"] = None


def _set_example(question: str) -> None:
    st.session_state["question"] = question
    _clear_result()


def _metric_label(metric: str) -> str:
    return METRIC_LABELS.get(metric, metric.replace("_", " ").title() or "—")


def _group_label(grouping: Any) -> str:
    return str(grouping).replace("_", " ").title() if grouping else "Overall"


def _format_rate(value: Any) -> str:
    return f"{float(value):.1f}%" if value is not None else "Unavailable"


def _period_label(period: dict[str, Any]) -> str:
    start = str(period.get("start_date", "—"))
    end = str(period.get("end_date", "—"))
    label = start if start == end else f"{start} → {end}"
    try:
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    except ValueError:
        return label
    unit = "day" if days == 1 else "days"
    return f"{label} ({days} {unit})"


def render_request(view: dict[str, Any]) -> None:
    request = view.get("request", {})
    if not request:
        return

    periods = request.get("comparison_periods")
    with st.container(border=True):
        st.subheader("Analysis scope")
        summary_columns = st.columns(2)
        summary_columns[0].caption("Metric")
        summary_columns[0].markdown(f"**{_metric_label(str(request.get('metric', '')))}**")
        summary_columns[1].caption("Group by")
        summary_columns[1].markdown(f"**{_group_label(request.get('grouping'))}**")
        if isinstance(periods, list) and len(periods) == 2:
            st.caption("Period 1")
            st.markdown(f"**{_period_label(periods[0])}**")
            st.caption("Period 2")
            st.markdown(f"**{_period_label(periods[1])}**")
        else:
            date_columns = st.columns(2)
            date_columns[0].caption("Start")
            date_columns[0].markdown(f"**{request.get('start_date', '—')}**")
            date_columns[1].caption("End")
            date_columns[1].markdown(f"**{request.get('end_date', '—')}**")

        definition = request.get("metric_definition")
        if definition:
            st.caption(f"Metric definition: {definition}")


def _single_result_row(item: dict[str, Any], metric: str) -> dict[str, str]:
    row = {"Group": str(item.get("group", "All records"))}
    if metric.endswith("_rate"):
        row["Rate"] = _format_rate(item.get("rate_pct"))
        row["Numerator / denominator"] = (
            f"{item.get('numerator', 0)} / {item.get('denominator', 0)}"
        )
    elif metric == "late_count":
        row["Late arrivals"] = str(item.get("count", 0))
        row["Eligible check-ins"] = str(item.get("denominator", 0))
    elif metric in {"missing_check_in", "missing_check_out"}:
        row["Count"] = str(item.get("count", 0))
        row["Denominator"] = str(item.get("denominator", 0))
    else:
        row["Rows"] = str(item.get("count", 0))
    return row


def render_single_results(view: dict[str, Any]) -> None:
    analysis = view.get("analysis", {})
    request = view.get("request", {})
    metric = str(request.get("metric", ""))
    results = analysis.get("results", [])
    st.subheader("Results")
    if not results:
        st.info("No exception types were recorded in the selected rows.")
        return

    if len(results) > 4:
        st.dataframe(
            [_single_result_row(item, metric) for item in results],
            width="stretch",
            hide_index=True,
        )
        return

    for offset in range(0, len(results), 2):
        batch = results[offset : offset + 2]
        columns = st.columns(len(batch))
        for column, item in zip(columns, batch):
            group = str(item.get("group", "All records"))
            with column.container(border=True):
                st.markdown(f"**{group}**")
                if metric.endswith("_rate"):
                    st.metric(_metric_label(metric), _format_rate(item.get("rate_pct")))
                    st.caption(
                        f"{item.get('numerator', 0)} / {item.get('denominator', 0)}"
                    )
                elif metric == "late_count":
                    st.metric("Late arrivals", int(item.get("count", 0)))
                    st.caption(f"Eligible check-ins: {item.get('denominator', 0)}")
                elif metric in {"missing_check_in", "missing_check_out"}:
                    st.metric("Count", int(item.get("count", 0)))
                    st.caption(f"Denominator: {item.get('denominator', 0)}")
                else:
                    st.metric("Rows", int(item.get("count", 0)))


def _comparison_rows(view: dict[str, Any]) -> list[dict[str, str]]:
    metric = str(view.get("request", {}).get("metric", ""))
    rows: list[dict[str, str]] = []
    for item in view.get("analysis", {}).get("results", []):
        row = {"Group": str(item.get("group", "All records"))}
        first = item.get("period_1", {})
        second = item.get("period_2", {})
        if metric.endswith("_rate"):
            row.update({
                "Period 1": _format_rate(first.get("rate_pct")),
                "P1 numerator / denominator": (
                    f"{first.get('numerator', 0)} / {first.get('denominator', 0)}"
                ),
                "Period 2": _format_rate(second.get("rate_pct")),
                "P2 numerator / denominator": (
                    f"{second.get('numerator', 0)} / {second.get('denominator', 0)}"
                ),
                "Change": (
                    f"{float(item['rate_delta_pp']):+.1f} pp"
                    if item.get("rate_delta_pp") is not None
                    else "Unavailable"
                ),
            })
        else:
            row.update({
                "Period 1 count": str(first.get("count", 0)),
                "Period 2 count": str(second.get("count", 0)),
                "Delta (P2 − P1)": f"{int(item.get('count_delta', 0)):+d}",
            })
            if metric == "late_count":
                row["Eligible check-ins (P1 / P2)"] = (
                    f"{first.get('denominator', 0)} / {second.get('denominator', 0)}"
                )
        rows.append(row)
    return rows


def render_chart(chart: Any) -> None:
    """Render only the safe chart-ready values supplied by the presentation adapter."""
    if not isinstance(chart, dict):
        return
    chart_type = chart.get("type")
    rows = chart.get("rows")
    if not isinstance(rows, list) or not rows:
        return

    st.subheader("Visual summary")
    if chart_type in {"single_rate", "single_count"}:
        chartable_rows = [row for row in rows if row.get("value") is not None]
        if chartable_rows:
            st.bar_chart(
                [{"Group": row.get("group", "All records"), "Value": row["value"]}
                 for row in chartable_rows],
                x="Group",
                y="Value",
                y_label="Rate (%)" if chart_type == "single_rate" else "Count",
                horizontal=True,
            )
        unavailable = [
            {"Group": row.get("group", "All records"), "Value": row.get("display_value", "Unavailable")}
            for row in rows
            if row.get("availability") == "unavailable"
        ]
        if unavailable:
            st.caption("Unavailable values are omitted from the bars and shown here.")
            st.dataframe(unavailable, width="stretch", hide_index=True)
        return

    if chart_type not in {"comparison_rate", "comparison_count"}:
        return

    periods = chart.get("period_1_label", "Period 1"), chart.get("period_2_label", "Period 2")
    st.caption(
        f"Period 1: {chart.get('period_1_dates', 'Not available')} · "
        f"Period 2: {chart.get('period_2_dates', 'Not available')}"
    )
    chartable_rows = [
        row for row in rows
        if row.get("period_1") is not None or row.get("period_2") is not None
    ]
    if chartable_rows:
        st.bar_chart(
            [
                {
                    "Group": row.get("group", "All records"),
                    periods[0]: row.get("period_1"),
                    periods[1]: row.get("period_2"),
                }
                for row in chartable_rows
            ],
            x="Group",
            y=list(periods),
            y_label="Rate (%)" if chart_type == "comparison_rate" else "Count",
            horizontal=True,
            stack=False,
        )
    else:
        st.info("No chartable values are available for these periods.")
    st.markdown(f"**{chart.get('delta_label', 'Change')} by group**")
    st.dataframe(
        [
            {
                "Group": row.get("group", "All records"),
                "Period 1": row.get("period_1_display", "Unavailable"),
                "Period 2": row.get("period_2_display", "Unavailable"),
                chart.get("delta_label", "Change"): row.get("delta_display", "Unavailable"),
            }
            for row in rows
        ],
        width="stretch",
        hide_index=True,
    )


def render_comparison_results(view: dict[str, Any]) -> None:
    st.subheader("Period comparison")
    rows = _comparison_rows(view)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    elif view.get("request", {}).get("metric") == "exceptions_by_type":
        st.info("No exception types were recorded in either period.")

    request = view.get("request", {})
    periods = request.get("comparison_periods", [])
    metric = str(request.get("metric", ""))
    if len(periods) == 2 and not metric.endswith("_rate"):
        try:
            lengths = [
                (date.fromisoformat(str(period["end_date"]))
                 - date.fromisoformat(str(period["start_date"]))).days + 1
                for period in periods
            ]
        except (KeyError, TypeError, ValueError):
            lengths = []
        if len(lengths) == 2 and lengths[0] != lengths[1]:
            st.caption(
                "Count deltas are raw totals; these periods have different lengths "
                "and are not normalized per day."
            )


def _evidence_status(view: dict[str, Any]) -> str:
    return {
        "answered": "SUPPORTED",
        "no_data": "NO DATA",
        "abstained": "ABSTAINED",
    }.get(str(view.get("status")), "NOT RUN")


def render_evidence_summary(view: dict[str, Any]) -> None:
    evidence = view.get("evidence", {})
    with st.container(border=True):
        st.subheader("Evidence snapshot")
        columns = st.columns(2)
        columns[0].metric("Evidence status", _evidence_status(view))
        columns[1].metric("Rows read", int(evidence.get("rows_read", 0)))
        st.caption(
            f"Evidence ID: {evidence.get('query_id') or 'Not available'} · "
            f"Re-queries: {int(evidence.get('retry_count', 0))} · "
            f"Source: {evidence.get('source_name') or 'Synthetic attendance'}"
        )


def render_evidence(view: dict[str, Any]) -> None:
    evidence = view.get("evidence", {})
    analysis = view.get("analysis", {})
    with st.expander("Evidence & validation", expanded=False):
        first_row = st.columns(2)
        first_row[0].metric("Evidence status", _evidence_status(view))
        first_row[1].metric("Rows read", int(evidence.get("rows_read", 0)))
        second_row = st.columns(2)
        second_row[0].metric("Evidence retries", int(evidence.get("retry_count", 0)))
        second_row[1].metric("Read-only SELECTs", int(evidence.get("sql_statement_count", 0)))

        st.write(f"**Evidence ID:** {evidence.get('query_id') or 'Not available'}")
        st.write(f"**Data source:** {evidence.get('source_name') or 'Synthetic attendance'}")
        st.write(f"**Unique rows:** {evidence.get('unique_rows', 0)}")

        period_analyses = analysis.get("period_analyses", [])
        if period_analyses:
            st.write("**Rows by period**")
            st.dataframe([
                {
                    "Period": index,
                    "Rows read": item.get("raw_row_count", 0),
                    "Unique rows": item.get("unique_row_count", 0),
                }
                for index, item in enumerate(period_analyses, start=1)
            ], width="stretch", hide_index=True)

        caveats = []
        for key, label in (
            ("duplicate_count", "Duplicate rows removed"),
            ("invalid_schedule_count", "Rows without valid scheduled start"),
            ("missing_check_in_count", "Non-absence rows missing check-in"),
            ("missing_check_out_count", "Checked-in rows missing check-out"),
        ):
            count = int(evidence.get(key, 0) or 0)
            if count:
                caveats.append({"Data-quality item": label, "Count": count})
        if caveats:
            with st.expander("Data caveats"):
                st.dataframe(caveats, width="stretch", hide_index=True)

        issues = evidence.get("issues", [])
        if issues:
            st.write("**Validation details**")
            for issue in issues:
                st.write(f"- {issue}")


def render_workflow_path(workflow_path: Any) -> None:
    """Show the completed path from the graph's final state, never as live progress."""
    if not isinstance(workflow_path, dict):
        return
    steps = workflow_path.get("steps")
    if not isinstance(steps, list) or not steps:
        return

    state_labels = {
        "complete": "Complete",
        "issue": "Attention",
        "failed": "Failed",
        "not_run": "Not run",
        "not_applicable": "Not applicable",
        "retry": "Retry",
        "outcome": "Outcome",
    }
    with st.expander("How this analysis worked", expanded=False):
        st.caption("Completed path from the workflow result; this is not a live trace.")
        lines = []
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            state = str(step.get("state", ""))
            label = str(step.get("label", "Workflow step"))
            line = f"{index + 1}. **{label}** — {state_labels.get(state, 'Not shown')}"
            detail = step.get("detail")
            if detail:
                line += f". {detail}"
            lines.append(line)
        st.markdown("\n".join(lines))


def render_result(view: dict[str, Any]) -> None:
    status = str(view.get("status", "unknown"))
    request = view.get("request", {})
    st.subheader("Analysis")

    if status == "clarification":
        st.warning("More information required")
        st.write(view.get("message") or "Please add the missing metric or date range.")
        st.caption("Example: What was the late rate by department from 2026-01-05 to 2026-01-09?")
        render_workflow_path(view.get("workflow_path"))
        return
    if status == "unsupported":
        st.info(view.get("message") or "This question is outside the supported attendance metrics.")
        render_workflow_path(view.get("workflow_path"))
        return
    if status == "no_data":
        if request.get("comparison_periods"):
            st.info("At least one selected period has no matching rows; the comparison was withheld.")
        else:
            st.info("No matching fixture rows were found.")
        st.caption("This does not establish that no attendance events occurred.")
    elif status == "abstained":
        st.error("The result was withheld because the evidence did not pass validation.")
    elif status == "answered":
        st.success("Evidence checks support this result.")
    else:
        st.error("The workflow returned an unrecognized status.")
        return

    render_request(view)
    if status == "answered":
        if request.get("comparison_periods"):
            render_comparison_results(view)
        else:
            render_single_results(view)
        render_chart(view.get("chart"))
    elif status == "abstained":
        for issue in view.get("evidence", {}).get("issues", []):
            st.write(f"- {issue}")
    render_evidence_summary(view)
    render_evidence(view)
    render_workflow_path(view.get("workflow_path"))


def main() -> None:
    st.set_page_config(
        page_title="Self-Correcting Attendance Analyst",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="auto",
    )

    st.session_state.setdefault("question", DEFAULT_QUESTION)
    st.session_state.setdefault("demo_scenario", "Normal dataset")
    st.session_state.setdefault("result", None)
    st.session_state.setdefault("result_question", None)
    st.session_state.setdefault("result_scenario", None)
    st.session_state.setdefault("runtime_error", None)

    st.caption("Module 2 · Self-Correcting AI Data Analyst")
    st.title("Attendance Analyst")
    st.write(
        "Ask about attendance operations. The analyst calculates the result, "
        "checks its evidence, and explains when it cannot answer reliably."
    )
    st.caption("Synthetic portfolio dataset · no real employee data")

    with st.sidebar:
        st.markdown("### Demo scenario")
        st.radio(
            "Dataset mode",
            options=("Normal dataset", "Conflicting evidence"),
            key="demo_scenario",
            on_change=_clear_result,
            help="Conflicting evidence adds one synthetic duplicate row to demonstrate abstention.",
        )

        st.divider()
        st.markdown("### Example questions")
        for label, example in EXAMPLES.items():
            st.button(
                label,
                key=f"example_{label.casefold().replace(' ', '_')}",
                on_click=_set_example,
                args=(example,),
                width="stretch",
            )

        st.divider()
        st.markdown("### What this demo checks")
        st.write("Deterministic metrics · Read-only query · Evidence checks · Bounded retry")

    with st.container(border=True):
        st.subheader("Ask the analyst")
        st.text_area(
            "Attendance question",
            key="question",
            height=100,
            placeholder=DEFAULT_QUESTION,
            help="Use inclusive YYYY-MM-DD dates. Comparisons need two non-overlapping periods.",
        )
        analyze = st.button("Analyze", type="primary", width="stretch")

    if analyze:
        question = str(st.session_state.get("question", "")).strip()
        if not question:
            _clear_result()
            st.warning("Please enter an attendance question.")
        else:
            try:
                with st.spinner("Running the evidence-checked workflow…"):
                    if st.session_state["demo_scenario"] == "Conflicting evidence":
                        raw_result = run_question(question, rows=conflicting_rows())
                    else:
                        raw_result = run_question(question)
                st.session_state["result"] = to_safe_view(raw_result)
                st.session_state["result_question"] = question
                st.session_state["result_scenario"] = st.session_state["demo_scenario"]
                st.session_state["runtime_error"] = None
            except Exception:
                _clear_result()
                st.session_state["runtime_error"] = (
                    "The analyst could not complete this request. Check the local demo setup and try again."
                )

    runtime_error = st.session_state.get("runtime_error")
    if runtime_error:
        st.error(runtime_error)

    result = st.session_state.get("result")
    if isinstance(result, dict):
        current_question = str(st.session_state.get("question", "")).strip()
        if current_question != st.session_state.get("result_question"):
            st.info("Showing the last completed analysis. Click Analyze to run the edited question.")
        st.divider()
        render_result(result)


if __name__ == "__main__":
    main()
