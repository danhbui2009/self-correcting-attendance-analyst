from attendance_analyst.parser import parse_question


def test_parser_builds_late_rate_request_with_grouping():
    parsed = parse_question("Late rate by department from 2026-01-05 to 2026-01-09")
    assert parsed["status"] == "ready"
    assert parsed["request"] == {
        "metric": "late_rate",
        "grouping": "department",
        "start_date": "2026-01-05",
        "end_date": "2026-01-09",
    }


def test_parser_requests_dates_instead_of_guessing():
    parsed = parse_question("How many late arrivals?")
    assert parsed["status"] == "clarification"
    assert "ISO dates" in parsed["message"]


def test_parser_rejects_invalid_or_reversed_period():
    invalid = parse_question("late arrivals from 2026-02-30 to 2026-03-01")
    reversed_range = parse_question("late arrivals from 2026-02-10 to 2026-02-01")
    assert invalid["status"] == "clarification"
    assert reversed_range["status"] == "clarification"


def test_parser_refuses_employment_decisions():
    parsed = parse_question("Rank employees for disciplinary action from 2026-01-05 to 2026-01-09")
    assert parsed["status"] == "unsupported"


def test_parser_clarifies_multiple_metric_families_or_groupings():
    multiple_metrics = parse_question(
        "Show late arrivals and missing check-ins from 2026-01-05 to 2026-01-09"
    )
    multiple_groups = parse_question(
        "Show late arrivals by department and shift from 2026-01-05 to 2026-01-09"
    )
    assert multiple_metrics["status"] == "clarification"
    assert multiple_groups["status"] == "clarification"


def test_parser_clarifies_count_and_rate_requested_together():
    parsed = parse_question(
        "Give late count and rate from 2026-01-05 to 2026-01-09"
    )
    assert parsed["status"] == "clarification"


def test_parser_clarifies_comparison_request():
    parsed = parse_question(
        "Compare late rates from 2026-01-05 to 2026-01-09"
    )
    assert parsed["status"] == "clarification"
    assert "two inclusive date ranges" in parsed["message"]


def test_parser_builds_two_ordered_comparison_periods():
    parsed = parse_question(
        "Compare late rates by department from 2026-01-05 to 2026-01-05 "
        "versus 2026-01-06 to 2026-01-09"
    )
    assert parsed["status"] == "ready"
    assert parsed["request"] == {
        "metric": "late_rate",
        "grouping": "department",
        "comparison_periods": [
            {"start_date": "2026-01-05", "end_date": "2026-01-05"},
            {"start_date": "2026-01-06", "end_date": "2026-01-09"},
        ],
    }


def test_parser_clarifies_reversed_or_overlapping_comparison_periods():
    reversed_periods = parse_question(
        "Compare late counts from 2026-01-06 to 2026-01-09 versus 2026-01-05 to 2026-01-05"
    )
    overlapping_periods = parse_question(
        "Compare late counts from 2026-01-05 to 2026-01-06 versus 2026-01-06 to 2026-01-09"
    )
    assert reversed_periods["status"] == "clarification"
    assert overlapping_periods["status"] == "clarification"
    assert "must come before" in overlapping_periods["message"]


def test_parser_clarifies_invalid_comparison_date_and_extra_date():
    invalid = parse_question(
        "Compare late counts from 2026-02-30 to 2026-03-01 versus 2026-03-02 to 2026-03-03"
    )
    extra = parse_question(
        "Compare late counts from 2026-01-01 to 2026-01-02 versus 2026-01-03 to 2026-01-04 and 2026-01-05"
    )
    assert invalid["status"] == "clarification"
    assert "invalid" in invalid["message"]
    assert extra["status"] == "clarification"


def test_parser_requires_explicit_date_range_connectors_for_comparison():
    parsed = parse_question(
        "Compare late rates for 2026-01-05, 2026-01-05, 2026-01-06, 2026-01-09"
    )
    assert parsed["status"] == "clarification"
    assert "two inclusive date ranges" in parsed["message"]


def test_parser_supports_vietnamese_comparison_wording():
    parsed = parse_question(
        "So sánh tỷ lệ đi muộn theo phòng ban từ 2026-01-05 đến 2026-01-05 "
        "so với từ 2026-01-06 đến 2026-01-09"
    )
    assert parsed["status"] == "ready"
    assert parsed["request"]["metric"] == "late_rate"
    assert len(parsed["request"]["comparison_periods"]) == 2
