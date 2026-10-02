from attendance_analyst.database import load_synthetic_rows
from attendance_analyst.graph import run_question


PERIOD = "from 2026-01-05 to 2026-01-09"


def test_graph_answers_with_period_definition_and_evidence_id():
    result = run_question(f"What was the late rate by department {PERIOD}")
    assert result["status"] == "answered"
    assert result["analysis"]["unique_row_count"] == 18
    assert result["execution_count"] == 1
    assert result["evidence_retry_count"] == 0
    assert "Reporting period: 2026-01-05 through 2026-01-09" in result["answer"]
    assert "Metric definition:" in result["answer"]
    assert result["query_id"].startswith("EVI-")
    assert "Operations: 2/7 = 28.6%" in result["answer"]
    assert "Sales: 3/8 = 37.5%" in result["answer"]


def test_graph_asks_for_missing_period_without_querying():
    result = run_question("What was the late rate by department?")
    assert result["status"] == "clarification"
    assert result.get("execution_count", 0) == 0


def test_graph_reports_empty_period_without_inventing_results():
    result = run_question("How many late arrivals from 2026-02-01 to 2026-02-02?")
    assert result["status"] == "no_data"
    assert "Results: no matching attendance rows." in result["answer"]
    assert "Reporting period:" in result["answer"]
    assert "Metric definition:" in result["answer"]
    assert "Evidence: EVI-" in result["answer"]
    assert "source=synthetic_attendance.csv" in result["answer"]


def test_graph_abstains_for_conflicting_source_rows():
    rows = load_synthetic_rows()
    conflict = rows[0].copy()
    conflict["department"] = "Conflicting Department"
    result = run_question(
        f"How many late arrivals {PERIOD}",
        rows=rows + [conflict],
    )
    assert result["status"] == "abstained"
    assert "Conflicting duplicate" in result["answer"]
    assert "Reporting period:" in result["answer"]
    assert "Metric definition:" in result["answer"]
    assert "Evidence: EVI-" in result["answer"]


def test_graph_reports_exact_duplicate_deduplication_as_a_caveat():
    rows = load_synthetic_rows()
    result = run_question(
        f"Give an attendance summary by status {PERIOD}",
        rows=rows + [rows[0].copy()],
    )
    assert result["status"] == "answered"
    assert result["analysis"]["unique_row_count"] == 18
    assert "Removed 1 exact duplicate row(s)" in result["answer"]


def test_graph_abstains_when_rate_has_no_eligible_denominator():
    row = load_synthetic_rows()[2]
    result = run_question(
        "What was the late rate from 2026-01-05 to 2026-01-05?",
        rows=[row],
    )
    assert result["status"] == "abstained"
    assert "No eligible records" in result["answer"]


def test_graph_reports_query_tool_failure_as_abstention(monkeypatch):
    def fail_query(*args, **kwargs):
        raise RuntimeError("simulated read failure")

    monkeypatch.setattr("attendance_analyst.graph.read_attendance_rows", fail_query)
    result = run_question(f"How many late arrivals {PERIOD}", rows=load_synthetic_rows())
    assert result["status"] == "abstained"
    assert "simulated read failure" in result["answer"]
    assert result["execution_count"] == 1


def test_graph_retries_once_when_initial_result_limit_is_reached():
    rows = load_synthetic_rows()[:6]
    expanded = []
    for index in range(7):
        row = rows[index % len(rows)].copy()
        row["source_row_id"] = f"BATCH-{index:03d}"
        row["employee_key"] = f"EMP-{index:03d}"
        expanded.append(row)
    result = run_question(
        f"How many late arrivals {PERIOD}",
        rows=expanded,
        initial_row_limit=3,
        retry_row_limit=10,
    )
    assert result["status"] == "answered"
    assert result["execution_count"] == 2
    assert result["evidence_retry_count"] == 1
    assert result["analysis"]["raw_row_count"] == 7


def test_graph_does_not_retry_when_result_exactly_matches_initial_limit():
    rows = load_synthetic_rows()[:3]
    result = run_question(
        f"How many late arrivals {PERIOD}",
        rows=rows,
        initial_row_limit=3,
        retry_row_limit=10,
    )
    assert result["status"] == "answered"
    assert result["execution_count"] == 1
    assert result["analysis"]["raw_row_count"] == 3


def test_graph_answers_when_retry_result_exactly_matches_retry_limit():
    rows = []
    for index, source in enumerate(load_synthetic_rows()[:5]):
        row = source.copy()
        row["source_row_id"] = f"EXACT-{index:03d}"
        row["employee_key"] = f"EMP-EXACT-{index:03d}"
        rows.append(row)
    result = run_question(
        f"How many late arrivals {PERIOD}",
        rows=rows,
        initial_row_limit=3,
        retry_row_limit=5,
    )
    assert result["status"] == "answered"
    assert result["execution_count"] == 2
    assert result["evidence_retry_count"] == 1
    assert result["analysis"]["raw_row_count"] == 5


def test_graph_abstains_after_one_retry_if_results_remain_truncated():
    rows = load_synthetic_rows()[:6]
    expanded = []
    for index in range(9):
        row = rows[index % len(rows)].copy()
        row["source_row_id"] = f"LARGE-{index:03d}"
        row["employee_key"] = f"EMP-{index:03d}"
        expanded.append(row)
    result = run_question(
        f"How many late arrivals {PERIOD}",
        rows=expanded,
        initial_row_limit=3,
        retry_row_limit=5,
    )
    assert result["status"] == "abstained"
    assert result["execution_count"] == 2
    assert result["evidence_retry_count"] == 1
    assert "one allowed retry" in result["answer"]


def test_graph_answers_comparison_with_period_lengths_deltas_and_two_selects():
    result = run_question(
        "Compare late rates by department from 2026-01-05 to 2026-01-05 "
        "versus 2026-01-06 to 2026-01-09"
    )
    assert result["status"] == "answered"
    assert result["execution_count"] == 1
    assert result["sql_statement_count"] == 2
    assert "Period 1: 2026-01-05 through 2026-01-05 (inclusive, 1 day)" in result["answer"]
    assert "Period 2: 2026-01-06 through 2026-01-09 (inclusive, 4 days)" in result["answer"]
    assert "Operations: Period 1=1/2 = 50.0%; Period 2=1/5 = 20.0%; change=-30.0 percentage points." in result["answer"]
    assert "Sales: Period 1=1/2 = 50.0%; Period 2=2/6 = 33.3%; change=-16.7 percentage points." in result["answer"]
    assert "Percentage-point changes are calculated from the unrounded numerator/denominator values" in result["answer"]
    assert "Count deltas are raw totals" not in result["answer"]
    assert "read-only SELECTs=2" in result["answer"]


def test_graph_withholds_comparison_when_either_period_has_no_rows():
    result = run_question(
        "Compare late counts from 2026-01-09 to 2026-01-09 versus 2026-02-01 to 2026-02-02"
    )
    assert result["status"] == "no_data"
    assert "comparison withheld" in result["answer"]
    assert "an empty period is not treated as zero" in result["answer"]
    assert "Period 2 has no matching" in result["answer"]
    assert "read-only SELECTs=2" in result["answer"]


def test_graph_compares_raw_count_totals_and_discloses_denominators():
    result = run_question(
        "Compare how many late arrivals from 2026-01-05 to 2026-01-05 "
        "versus 2026-01-06 to 2026-01-09"
    )
    assert result["status"] == "answered"
    assert "All records: Period 1=2; Period 2=3; delta=+1 (eligible check-ins P1=4, P2=11)." in result["answer"]
    assert "Count deltas are raw totals" in result["answer"]


def test_graph_reports_zero_denominator_group_as_unavailable_in_comparison():
    result = run_question(
        "Compare missing check-out rates by shift from 2026-01-05 to 2026-01-05 "
        "versus 2026-01-06 to 2026-01-09"
    )
    assert result["status"] == "answered"
    assert "Overnight: Period 1=unavailable (denominator 0); Period 2=1/2 = 50.0%; change=unavailable (a period has denominator 0)." in result["answer"]


def test_graph_retries_both_comparison_periods_only_once():
    result = run_question(
        "Compare late counts from 2026-01-05 to 2026-01-05 versus 2026-01-06 to 2026-01-09",
        initial_row_limit=3,
        retry_row_limit=20,
    )
    assert result["status"] == "answered"
    assert result["execution_count"] == 2
    assert result["evidence_retry_count"] == 1
    assert result["sql_statement_count"] == 4
    assert "Evidence re-queries: 1 (maximum one retry for the pair)." in result["answer"]


def test_graph_abstains_when_comparison_remains_truncated_after_one_retry():
    source_rows = load_synthetic_rows()
    expanded = []
    for index in range(12):
        row = source_rows[index % len(source_rows)].copy()
        row["work_date"] = "2026-01-05" if index < 6 else "2026-01-06"
        row["source_row_id"] = f"COMPARE-LIMIT-{index:03d}"
        row["employee_key"] = f"COMPARE-EMP-{index:03d}"
        expanded.append(row)
    result = run_question(
        "Compare late counts from 2026-01-05 to 2026-01-05 versus 2026-01-06 to 2026-01-06",
        rows=expanded,
        initial_row_limit=2,
        retry_row_limit=4,
    )
    assert result["status"] == "abstained"
    assert result["execution_count"] == 2
    assert result["evidence_retry_count"] == 1
    assert result["sql_statement_count"] == 4
    assert "one allowed retry" in result["answer"]
