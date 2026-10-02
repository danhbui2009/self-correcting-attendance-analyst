import pytest

from ui.presentation import to_safe_view


def test_safe_view_uses_real_nested_state_and_excludes_raw_data_and_query_internals():
    raw = {
        "status": "answered",
        "final_status": "supported",
        "message": "",
        "request": {
            "metric": "late_rate",
            "grouping": "department",
            "start_date": "2026-01-05",
            "end_date": "2026-01-09",
        },
        "analysis": {
            "metric": "late_rate",
            "raw_row_count": 1,
            "unique_row_count": 1,
            "results": [{"group": "Sales", "numerator": 1, "denominator": 2, "rate_pct": 50.0}],
        },
        "source_records": [{"employee_key": "RAW-EMPLOYEE-ID"}],
        "records": [{"employee_key": "RAW-EMPLOYEE-ID"}],
        "query": "SELECT private query details",
        "query_parameters": ["private parameter"],
        "query_id": "EVI-demo",
        "source_name": "synthetic_attendance.csv",
        "execution_count": 1,
        "sql_statement_count": 1,
    }

    view = to_safe_view(raw)
    rendered = repr(view)
    assert view["request"]["metric"] == "late_rate"
    assert view["request"]["metric_definition"] == (
        "Late arrivals divided by eligible check-ins; late means more than 5 minutes after scheduled start."
    )
    assert view["analysis"]["results"][0]["rate_pct"] == 50.0
    assert view["evidence"]["query_id"] == "EVI-demo"
    assert view["chart"]["rows"][0]["value"] == 50.0
    assert "RAW-EMPLOYEE-ID" not in repr(view["chart"])
    assert "source_records" not in view
    assert "records" not in view
    assert "query" not in view
    assert "SELECT private query details" not in rendered
    assert "private parameter" not in rendered
    assert "RAW-EMPLOYEE-ID" not in rendered


def test_safe_view_preserves_comparison_periods_and_sanitizes_source_ids():
    view = to_safe_view({
        "status": "abstained",
        "request": {
            "metric": "late_rate",
            "grouping": "department",
            "comparison_periods": [
                {"start_date": "2026-01-05", "end_date": "2026-01-05"},
                {"start_date": "2026-01-06", "end_date": "2026-01-09"},
            ],
        },
        "analysis": {
            "raw_row_count": 2,
            "results": [{
                "group": "Sales",
                "period_1": {"numerator": 1, "denominator": 2, "rate_pct": 50.0},
                "period_2": {"numerator": 1, "denominator": 3, "rate_pct": 33.3},
                "rate_delta_pp": -16.7,
            }],
        },
        "reflection_issues": ["Conflicting rows share source_row_id EMP-SECRET-001."],
    })
    assert len(view["request"]["comparison_periods"]) == 2
    assert view["analysis"]["results"][0]["rate_delta_pp"] == -16.7
    assert view["evidence"]["issues"] == ["Conflicting source row identifiers were detected."]
    assert "EMP-SECRET-001" not in repr(view)


def test_safe_view_uses_fixed_issue_template_for_arbitrary_source_identifiers():
    view = to_safe_view({
        "status": "abstained",
        "request": {"metric": "late_rate"},
        "reflection_issues": ["Mixed timezone awareness in row PRIVATE/Employee:4432."],
    })

    assert view["evidence"]["issues"] == [
        "Date/time fields were inconsistent; reliability could not be verified."
    ]
    assert "PRIVATE/Employee:4432" not in repr(view)
    assert "Mixed timezone awareness" not in repr(view)


def test_chart_view_model_uses_single_period_engine_rate_values():
    view = to_safe_view({
        "status": "answered",
        "final_status": "supported",
        "request": {"metric": "late_rate", "grouping": "department"},
        "analysis": {"results": [
            {"group": "Operations", "numerator": 2, "denominator": 7, "rate_pct": 28.6},
            {"group": "Sales", "numerator": 3, "denominator": 8, "rate_pct": 37.5},
        ]},
    })

    assert view["chart"] == {
        "type": "single_rate",
        "metric": "late_rate",
        "unit": "percent",
        "rows": [
            {
                "group": "Operations", "value": 28.6, "display_value": "28.6%",
                "availability": "available", "denominator": 7,
            },
            {
                "group": "Sales", "value": 37.5, "display_value": "37.5%",
                "availability": "available", "denominator": 8,
            },
        ],
    }


def test_chart_view_model_uses_precomputed_comparison_rates_and_deltas():
    view = to_safe_view({
        "status": "answered",
        "final_status": "supported",
        "request": {
            "metric": "late_rate",
            "comparison_periods": [
                {"start_date": "2026-01-05", "end_date": "2026-01-05"},
                {"start_date": "2026-01-06", "end_date": "2026-01-09"},
            ],
        },
        "analysis": {"results": [
            {
                "group": "Operations",
                "period_1": {"numerator": 1, "denominator": 2, "rate_pct": 50.0},
                "period_2": {"numerator": 1, "denominator": 5, "rate_pct": 20.0},
                "rate_delta_pp": -30.0,
            },
            {
                "group": "Sales",
                "period_1": {"numerator": 1, "denominator": 2, "rate_pct": 50.0},
                "period_2": {"numerator": 1, "denominator": 3, "rate_pct": 33.3},
                "rate_delta_pp": -16.7,
            },
        ]},
    })

    chart = view["chart"]
    assert chart["type"] == "comparison_rate"
    assert chart["rows"] == [
        {
            "group": "Operations", "period_1": 50.0, "period_1_display": "50.0%",
            "period_1_denominator": 2, "period_2": 20.0, "period_2_display": "20.0%",
            "period_2_denominator": 5, "delta": -30.0, "delta_display": "-30.0 pp",
        },
        {
            "group": "Sales", "period_1": 50.0, "period_1_display": "50.0%",
            "period_1_denominator": 2, "period_2": 33.3, "period_2_display": "33.3%",
            "period_2_denominator": 3, "delta": -16.7, "delta_display": "-16.7 pp",
        },
    ]


def test_zero_denominator_is_unavailable_and_never_a_zero_rate_bar():
    view = to_safe_view({
        "status": "answered",
        "final_status": "supported",
        "request": {
            "metric": "late_rate",
            "comparison_periods": [
                {"start_date": "2026-01-05", "end_date": "2026-01-05"},
                {"start_date": "2026-01-06", "end_date": "2026-01-06"},
            ],
        },
        "analysis": {"results": [{
            "group": "Overnight",
            "period_1": {"numerator": 0, "denominator": 0, "rate_pct": None},
            "period_2": {"numerator": 1, "denominator": 2, "rate_pct": 50.0},
            "rate_delta_pp": None,
        }]},
    })

    row = view["chart"]["rows"][0]
    assert row["period_1"] is None
    assert row["period_1_display"] == "Unavailable"
    assert row["period_1_denominator"] == 0
    assert row["period_2"] == 50.0
    assert row["delta"] is None
    assert row["delta_display"] == "Unavailable"


def test_single_rate_with_zero_denominator_is_unavailable_not_zero_percent():
    view = to_safe_view({
        "status": "answered",
        "final_status": "supported",
        "request": {"metric": "late_rate"},
        "analysis": {"results": [{
            "group": "Overnight", "numerator": 0, "denominator": 0, "rate_pct": None,
        }]},
    })

    row = view["chart"]["rows"][0]
    assert row["value"] is None
    assert row["display_value"] == "Unavailable"
    assert row["availability"] == "unavailable"


def test_count_chart_values_are_counts_not_percentages():
    view = to_safe_view({
        "status": "answered",
        "final_status": "supported",
        "request": {"metric": "attendance_summary", "grouping": "department"},
        "analysis": {"results": [
            {"group": "Operations", "count": 3, "denominator": 8},
        ]},
    })

    chart = view["chart"]
    assert chart["type"] == "single_count"
    assert chart["unit"] == "count"
    assert chart["rows"][0]["value"] == 3
    assert chart["rows"][0]["display_value"] == "3"
    assert "%" not in chart["rows"][0]["display_value"]


def test_comparison_count_chart_uses_engine_counts_and_raw_delta():
    view = to_safe_view({
        "status": "answered",
        "final_status": "supported",
        "request": {
            "metric": "late_count",
            "comparison_periods": [
                {"start_date": "2026-01-05", "end_date": "2026-01-05"},
                {"start_date": "2026-01-06", "end_date": "2026-01-09"},
            ],
        },
        "analysis": {"results": [{
            "group": "Operations",
            "period_1": {"count": 2, "denominator": 7},
            "period_2": {"count": 5, "denominator": 20},
            "count_delta": 3,
        }]},
    })

    chart = view["chart"]
    assert chart["type"] == "comparison_count"
    assert chart["unit"] == "count"
    assert chart["rows"][0]["period_1"] == 2
    assert chart["rows"][0]["period_2"] == 5
    assert chart["rows"][0]["delta"] == 3
    assert chart["rows"][0]["delta_display"] == "+3"
    assert "pp" not in chart["rows"][0]["delta_display"]


@pytest.mark.parametrize("status", ["clarification", "no_data", "abstained", "unsupported"])
def test_non_answered_results_never_receive_a_chart(status: str):
    view = to_safe_view({
        "status": status,
        "final_status": "abstain" if status == "abstained" else None,
        "request": {"metric": "late_rate"},
        "analysis": {"results": [
            {"group": "Operations", "numerator": 1, "denominator": 2, "rate_pct": 50.0},
        ]},
    })

    assert view["chart"] is None


@pytest.mark.parametrize("final_status", ["abstain", None])
def test_final_status_must_explicitly_be_supported_before_charting(final_status):
    view = to_safe_view({
        "status": "answered",
        "final_status": final_status,
        "request": {"metric": "late_rate"},
        "analysis": {"results": [
            {"group": "Operations", "numerator": 1, "denominator": 2, "rate_pct": 50.0},
        ]},
    })

    assert view["chart"] is None


def test_supported_workflow_path_shows_completed_real_stages_without_retry():
    view = to_safe_view({
        "status": "answered",
        "final_status": "supported",
        "request": {"metric": "late_rate", "start_date": "2026-01-05", "end_date": "2026-01-09"},
        "execution_count": 1,
        "sql_statement_count": 1,
        "evidence_retry_count": 0,
        "analysis": {
            "metric": "late_rate",
            "results": [{"group": "Operations", "numerator": 2, "denominator": 7, "rate_pct": 28.6}],
        },
    })

    path = view["workflow_path"]
    assert path["outcome"] == "supported"
    assert path["retry_count"] == 0
    assert [step["label"] for step in path["steps"]] == [
        "Parse request", "Query data", "Calculate metric", "Validate evidence", "Supported answer",
    ]
    assert [step["state"] for step in path["steps"]] == [
        "complete", "complete", "complete", "complete", "outcome",
    ]


@pytest.mark.parametrize(
    ("status", "expected_middle", "expected_outcome"),
    [
        ("clarification", "Missing information", "Clarification requested"),
        ("unsupported", "Outside supported scope", "Unsupported question"),
    ],
)
def test_parse_exit_workflow_paths_mark_query_and_calculation_not_run(
    status: str, expected_middle: str, expected_outcome: str
):
    path = to_safe_view({"status": status, "message": "safe message"})["workflow_path"]

    assert [step["label"] for step in path["steps"]] == [
        "Parse request", expected_middle, "Query data", "Calculate metric",
        "Validate evidence", expected_outcome,
    ]
    assert [step["state"] for step in path["steps"]][2:5] == ["not_run"] * 3
    assert path["retry_count"] == 0


def test_no_data_workflow_path_records_that_empty_result_was_calculated():
    path = to_safe_view({
        "status": "no_data",
        "final_status": "no_data",
        "request": {"metric": "late_rate", "start_date": "2026-02-01", "end_date": "2026-02-05"},
        "execution_count": 1,
        "sql_statement_count": 1,
        "evidence_retry_count": 0,
        "analysis": {"metric": "late_rate", "raw_row_count": 0, "results": []},
    })["workflow_path"]

    assert [step["state"] for step in path["steps"]] == [
        "complete", "complete", "complete", "issue", "outcome",
    ]
    assert path["steps"][2]["label"] == "Calculate metric"
    assert "empty result" in path["steps"][3]["detail"]


def test_abstained_workflow_path_marks_evidence_validation_failed():
    path = to_safe_view({
        "status": "abstained",
        "final_status": "abstain",
        "request": {"metric": "late_rate"},
        "execution_count": 1,
        "sql_statement_count": 1,
        "evidence_retry_count": 0,
        "analysis": {"metric": "late_rate", "results": []},
        "reflection_issues": ["Conflicting rows share source_row_id PRIVATE-ROW-001."],
    })["workflow_path"]

    assert path["steps"][-2]["state"] == "failed"
    assert path["steps"][-1] == {"label": "Result withheld", "state": "outcome"}
    assert "PRIVATE-ROW-001" not in repr(path)


def test_retry_path_appears_only_after_one_recorded_evidence_retry():
    view = to_safe_view({
        "status": "answered",
        "final_status": "supported",
        "request": {"metric": "late_rate"},
        "execution_count": 2,
        "sql_statement_count": 2,
        "evidence_retry_count": 1,
        "analysis": {"metric": "late_rate", "results": []},
    })
    path = view["workflow_path"]

    retry_steps = [step for step in path["steps"] if step["state"] == "retry"]
    assert len(retry_steps) == 1
    assert retry_steps[0]["label"] == "Re-query evidence (1)"
    assert path["retry_count"] == 1


def test_query_failure_path_hides_exception_details_and_skips_metric_calculation():
    path = to_safe_view({
        "status": "abstained",
        "final_status": "abstain",
        "request": {"metric": "late_rate"},
        "execution_count": 1,
        "sql_statement_count": 1,
        "evidence_retry_count": 0,
        "query_error": "PrivateDriverError: SECRET_QUERY_DETAIL",
        "analysis": {"issues": ["PrivateDriverError: SECRET_QUERY_DETAIL"]},
    })["workflow_path"]

    assert path["steps"][1]["state"] == "failed"
    assert path["steps"][2]["state"] == "not_applicable"
    assert "SECRET_QUERY_DETAIL" not in repr(path)
