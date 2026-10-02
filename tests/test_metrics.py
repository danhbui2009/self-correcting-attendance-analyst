from attendance_analyst.database import load_synthetic_rows
from attendance_analyst.metrics import calculate_comparison, calculate_metrics


def _request(metric: str, grouping: str | None = None) -> dict[str, object]:
    return {
        "metric": metric,
        "grouping": grouping,
        "start_date": "2026-01-05",
        "end_date": "2026-01-09",
    }


def test_late_rate_uses_five_minute_grace_and_only_valid_checkins():
    summary = calculate_metrics(load_synthetic_rows(), _request("late_rate"))
    assert summary["unique_row_count"] == 18
    assert summary["results"] == [
        {"group": "All records", "count": 5, "numerator": 5, "denominator": 15, "rate_pct": 33.3}
    ]


def test_missing_checkin_excludes_rows_marked_absent():
    summary = calculate_metrics(load_synthetic_rows(), _request("missing_check_in"))
    assert summary["results"][0]["count"] == 1
    assert summary["results"][0]["denominator"] == 18


def test_missing_checkout_denominator_is_checked_in_rows():
    summary = calculate_metrics(load_synthetic_rows(), _request("missing_check_out_rate"))
    assert summary["results"][0]["count"] == 3
    assert summary["results"][0]["denominator"] == 15
    assert summary["results"][0]["rate_pct"] == 20.0


def test_duplicate_identical_source_row_is_deduplicated_with_caveat():
    rows = load_synthetic_rows()
    summary = calculate_metrics(rows + [rows[0].copy()], _request("attendance_summary", "attendance_status"))
    assert summary["raw_row_count"] == 19
    assert summary["unique_row_count"] == 18
    assert summary["duplicate_count"] == 1
    assert any("exact duplicate" in warning for warning in summary["warnings"])


def test_conflicting_duplicate_source_row_is_flagged():
    rows = load_synthetic_rows()
    conflict = rows[0].copy()
    conflict["department"] = "Changed"
    summary = calculate_metrics(rows + [conflict], _request("late_count"))
    assert summary["conflicting_duplicates"] is True


def test_comparison_calculates_percentage_point_delta_by_group():
    rows = load_synthetic_rows()
    period_records = [
        [row for row in rows if row["work_date"] == "2026-01-05"],
        [row for row in rows if row["work_date"] in {"2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"}],
    ]
    request = {
        "metric": "late_rate",
        "grouping": "department",
        "comparison_periods": [
            {"start_date": "2026-01-05", "end_date": "2026-01-05"},
            {"start_date": "2026-01-06", "end_date": "2026-01-09"},
        ],
    }
    comparison = calculate_comparison(period_records, request)
    by_group = {item["group"]: item for item in comparison["results"]}
    assert by_group["Operations"]["period_1"]["rate_pct"] == 50.0
    assert by_group["Operations"]["period_2"]["rate_pct"] == 20.0
    assert by_group["Operations"]["rate_delta_pp"] == -30.0
    assert by_group["Sales"]["period_1"]["rate_pct"] == 50.0
    assert by_group["Sales"]["period_2"]["rate_pct"] == 33.3
    assert by_group["Sales"]["rate_delta_pp"] == -16.7


def test_comparison_keeps_missing_group_rate_unavailable():
    rows = load_synthetic_rows()
    period_records = [
        [row for row in rows if row["work_date"] == "2026-01-05"],
        [row for row in rows if row["work_date"] in {"2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"}],
    ]
    request = {
        "metric": "missing_check_out_rate",
        "grouping": "shift",
        "comparison_periods": [
            {"start_date": "2026-01-05", "end_date": "2026-01-05"},
            {"start_date": "2026-01-06", "end_date": "2026-01-09"},
        ],
    }
    comparison = calculate_comparison(period_records, request)
    overnight = next(item for item in comparison["results"] if item["group"] == "Overnight")
    assert overnight["period_1"]["denominator"] == 0
    assert overnight["period_1"]["rate_pct"] is None
    assert overnight["rate_delta_pp"] is None


def test_comparison_rounds_rate_delta_from_unrounded_period_fractions():
    def row(source_id: str, work_date: str, late: bool) -> dict[str, object]:
        return {
            "employee_key": source_id,
            "work_date": work_date,
            "department": "Sales",
            "shift": "Day",
            "scheduled_start": f"{work_date} 09:00:00",
            "scheduled_end": f"{work_date} 17:00:00",
            "actual_check_in": f"{work_date} {'09:10:00' if late else '09:00:00'}",
            "actual_check_out": f"{work_date} 17:00:00",
            "attendance_status": "present",
            "exception_type": None,
            "source_row_id": source_id,
        }

    period_1 = [row(f"P1-{index}", "2026-01-05", index == 0) for index in range(6)]
    period_2 = [row(f"P2-{index}", "2026-01-06", index < 2) for index in range(6)]
    comparison = calculate_comparison([period_1, period_2], {
        "metric": "late_rate",
        "grouping": None,
        "comparison_periods": [
            {"start_date": "2026-01-05", "end_date": "2026-01-05"},
            {"start_date": "2026-01-06", "end_date": "2026-01-06"},
        ],
    })
    result = comparison["results"][0]
    assert result["period_1"]["rate_pct"] == 16.7
    assert result["period_2"]["rate_pct"] == 33.3
    assert result["rate_delta_pp"] == 16.7
