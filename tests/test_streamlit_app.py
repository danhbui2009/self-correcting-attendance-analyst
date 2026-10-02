from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from ui.presentation import to_safe_view


APP_PATH = Path(__file__).resolve().parents[1] / "ui" / "app.py"
EXAMPLE_QUESTIONS = {
    "Late rate": "What was the late rate by department from 2026-01-05 to 2026-01-09?",
    "Missing check-out": (
        "What is the missing check-out rate by department from 2026-01-05 to 2026-01-09?"
    ),
    "Attendance summary": (
        "Give an attendance summary by status from 2026-01-05 to 2026-01-09."
    ),
    "Compare periods": (
        "Compare late rates by department from 2026-01-05 to 2026-01-05 "
        "versus 2026-01-06 to 2026-01-09"
    ),
    "No data": "What was the late rate by department from 2026-02-01 to 2026-02-05?",
    "Clarification": "What was the late rate by department?",
}
EXPECTED_STATUSES = {
    "Late rate": "answered",
    "Missing check-out": "answered",
    "Attendance summary": "answered",
    "Compare periods": "answered",
    "No data": "no_data",
    "Clarification": "clarification",
}


def _start_app() -> AppTest:
    return AppTest.from_file(APP_PATH, default_timeout=30).run()


def _click_button(app: AppTest, label: str) -> AppTest:
    button = next(button for button in app.button if button.label == label)
    return button.click().run(timeout=30)


@pytest.mark.parametrize("label", EXAMPLE_QUESTIONS)
def test_each_example_prefills_and_runs_to_its_expected_status(label: str):
    app = _start_app()
    app = _click_button(app, label)

    assert not app.exception
    assert app.text_area(key="question").value == EXAMPLE_QUESTIONS[label]
    assert app.session_state["result"] is None

    app = _click_button(app, "Analyze")

    assert not app.exception
    result = app.session_state["result"]
    assert result["status"] == EXPECTED_STATUSES[label]
    assert result["workflow_path"] is not None
    if label in {"No data", "Clarification"}:
        assert result["chart"] is None
    if label == "No data":
        assert result["workflow_path"]["steps"][2]["state"] == "complete"
    if label == "Clarification":
        assert result["evidence"]["sql_statement_count"] == 0
        assert [step["state"] for step in result["workflow_path"]["steps"][2:5]] == [
            "not_run", "not_run", "not_run",
        ]


def test_normal_late_rate_chart_uses_safe_engine_values():
    app = _start_app()
    app = _click_button(app, "Analyze")

    chart = app.session_state["result"]["chart"]
    assert chart["type"] == "single_rate"
    assert [(row["group"], row["value"]) for row in chart["rows"]] == [
        ("Operations", 28.6),
        ("Sales", 37.5),
    ]
    assert "source_records" not in repr(chart)
    assert "employee_key" not in repr(chart)


def test_analyzed_result_survives_input_rerun_but_example_clears_it():
    app = _start_app()
    app = _click_button(app, "Analyze")
    original_result = app.session_state["result"]
    assert original_result["status"] == "answered"

    app.text_area(key="question").set_value("A different question not yet analyzed")
    app = app.run(timeout=30)
    assert not app.exception
    assert app.session_state["result"] == original_result
    assert any("last completed analysis" in item.value.casefold() for item in app.info)

    app = _click_button(app, "Compare periods")
    assert app.session_state["result"] is None
    assert app.text_area(key="question").value == EXAMPLE_QUESTIONS["Compare periods"]


def test_scenario_change_clears_old_result_and_conflict_mode_abstains_safely():
    app = _start_app()
    app = _click_button(app, "Analyze")
    assert app.session_state["result"]["status"] == "answered"

    app.radio(key="demo_scenario").set_value("Conflicting evidence")
    app = app.run(timeout=30)
    assert app.session_state["result"] is None

    app = _click_button(app, "Analyze")
    result = app.session_state["result"]
    assert result["status"] == "abstained"
    assert result["chart"] is None
    assert result["workflow_path"]["steps"][-2]["state"] == "failed"
    assert result["evidence"]["issues"] == [
        "Conflicting source row identifiers were detected."
    ]
    assert "SYN-001" not in repr(result)


def test_rate_comparison_shows_period_lengths_and_percentage_points():
    app = _start_app()
    app = _click_button(app, "Compare periods")
    app = _click_button(app, "Analyze")

    assert not app.exception
    rendered_scope = " ".join(str(item.value) for item in app.markdown)
    assert "2026-01-05 (1 day)" in rendered_scope
    assert "2026-01-06 → 2026-01-09 (4 days)" in rendered_scope
    assert any(
        "Period 1: 2026-01-05" in item.value
        and "Period 2: 2026-01-06 to 2026-01-09" in item.value
        for item in app.caption
    )
    rendered_tables = " ".join(str(item.value) for item in app.dataframe)
    assert "-30.0 pp" in rendered_tables
    assert "-16.7 pp" in rendered_tables
    chart = app.session_state["result"]["chart"]
    assert chart["type"] == "comparison_rate"
    assert [(row["period_1"], row["period_2"], row["delta"]) for row in chart["rows"]] == [
        (50.0, 20.0, -30.0),
        (50.0, 33.3, -16.7),
    ]


def test_count_comparison_explains_unequal_period_totals():
    app = _start_app()
    app.text_area(key="question").set_value(
        "Compare late arrivals by department from 2026-01-05 to 2026-01-05 "
        "versus 2026-01-06 to 2026-01-09"
    )
    app = app.run(timeout=30)
    app = _click_button(app, "Analyze")

    assert not app.exception
    assert any(
        "raw totals" in item.value and "not normalized per day" in item.value
        for item in app.caption
    )


def test_safe_result_state_and_no_data_copy_do_not_expose_source_rows():
    app = _start_app()
    app = _click_button(app, "No data")
    app = _click_button(app, "Analyze")

    assert app.session_state["result"]["status"] == "no_data"
    rendered = repr(app.session_state["result"])
    assert "source_records" not in rendered
    assert "query_parameters" not in rendered
    assert "records" not in rendered
    assert any("does not establish" in item.value for item in app.caption)


def test_unsupported_question_has_a_parse_exit_path_and_no_query():
    app = _start_app()
    app.text_area(key="question").set_value(
        "Rank employees for disciplinary action from 2026-01-05 to 2026-01-09"
    )
    app = app.run(timeout=30)
    app = _click_button(app, "Analyze")

    result = app.session_state["result"]
    path = result["workflow_path"]
    assert result["status"] == "unsupported"
    assert path["steps"][1]["label"] == "Outside supported scope"
    assert [step["state"] for step in path["steps"][2:5]] == [
        "not_run", "not_run", "not_run",
    ]


def test_workflow_path_is_collapsed_and_described_as_completed_not_live():
    app = _start_app()
    app = _click_button(app, "Analyze")

    path_expander = next(item for item in app.expander if item.label == "How this analysis worked")
    assert path_expander.proto.expanded is False
    assert any("not a live trace" in item.value for item in app.caption)
    assert any(
        "1. **Parse request** — Complete" in item.value
        and "2. **Query data** — Complete" in item.value
        for item in app.markdown
    )


def test_polished_layout_keeps_exact_results_before_chart_and_evidence_visible():
    app = _start_app()
    app = _click_button(app, "Analyze")

    assert not app.exception
    assert app.text_area(key="question").label == "Attendance question"
    headings = [item.value for item in app.subheader]
    assert headings.index("Results") < headings.index("Visual summary")
    assert headings.index("Visual summary") < headings.index("Evidence snapshot")
    assert any(item.value == "SUPPORTED" for item in app.metric)
    assert any("Evidence ID: EVI-" in item.value for item in app.caption)


def test_comparison_no_data_copy_says_a_period_is_missing():
    app = _start_app()
    app.text_area(key="question").set_value(
        "Compare late rates by department from 2026-01-05 to 2026-01-05 "
        "versus 2026-02-01 to 2026-02-05"
    )
    app = app.run(timeout=30)
    app = _click_button(app, "Analyze")

    assert not app.exception
    assert app.session_state["result"]["status"] == "no_data"
    assert any(
        "At least one selected period has no matching rows" in item.value
        for item in app.info
    )


def _start_app_with_existing_result(raw_result: dict) -> AppTest:
    app = _start_app()
    app.session_state["result"] = to_safe_view(raw_result)
    app.session_state["result_question"] = app.session_state["question"]
    app.session_state["result_scenario"] = "Normal dataset"
    return app.run(timeout=30)


def test_app_test_renders_recorded_retry_step_from_safe_view():
    app = _start_app_with_existing_result({
        "status": "answered",
        "final_status": "supported",
        "request": {
            "metric": "late_rate",
            "start_date": "2026-01-05",
            "end_date": "2026-01-09",
        },
        "execution_count": 2,
        "sql_statement_count": 2,
        "evidence_retry_count": 1,
        "analysis": {
            "metric": "late_rate",
            "results": [{
                "group": "Operations", "numerator": 2, "denominator": 7, "rate_pct": 28.6,
            }],
        },
    })

    assert not app.exception
    assert any("Re-query evidence (1)" in item.value for item in app.markdown)
    assert app.session_state["result"]["workflow_path"]["retry_count"] == 1


def test_app_test_renders_query_error_generically_without_private_details():
    app = _start_app_with_existing_result({
        "status": "abstained",
        "final_status": "abstain",
        "request": {"metric": "late_rate"},
        "execution_count": 1,
        "sql_statement_count": 1,
        "evidence_retry_count": 0,
        "query_error": "PrivateDriverError: SECRET_QUERY_DETAIL",
        "analysis": {"issues": ["PrivateDriverError: SECRET_QUERY_DETAIL"]},
    })

    rendered = repr({
        "markdown": [item.value for item in app.markdown],
        "captions": [item.value for item in app.caption],
        "result": app.session_state["result"],
    })
    assert not app.exception
    assert any("Query data" in item.value and "Failed" in item.value for item in app.markdown)
    assert any("Calculate metric" in item.value and "Not applicable" in item.value for item in app.markdown)
    assert "SECRET_QUERY_DETAIL" not in rendered
    assert "PrivateDriverError" not in rendered
