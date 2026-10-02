import json
from pathlib import Path

from attendance_analyst.graph import run_question


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_curated_evaluation_questions_match_expected_routes_and_metrics():
    cases = json.loads((PROJECT_ROOT / "evaluation" / "cases.json").read_text(encoding="utf-8"))
    for case in cases:
        result = run_question(case["question"])
        assert result["status"] == case["status"], case["name"]
        if "expected_executions" in case:
            assert result.get("execution_count", 0) == case["expected_executions"], case["name"]
        if "metric" in case:
            assert result["request"]["metric"] == case["metric"], case["name"]
        if "expected_results" in case:
            actual = result["analysis"]["results"]
            for expected in case["expected_results"]:
                match = next((item for item in actual if item["group"] == expected["group"]), None)
                assert match is not None, case["name"]
                for key, value in expected.items():
                    if isinstance(value, dict):
                        for nested_key, nested_value in value.items():
                            assert match[key][nested_key] == nested_value, f"{case['name']}: {key}.{nested_key}"
                    else:
                        assert match[key] == value, f"{case['name']}: {key}"
        if "expected_comparison_results" in case:
            actual = result["analysis"]["results"]
            for expected in case["expected_comparison_results"]:
                match = next((item for item in actual if item["group"] == expected["group"]), None)
                assert match is not None, case["name"]
                for key, value in expected.items():
                    if isinstance(value, dict):
                        for nested_key, nested_value in value.items():
                            assert match[key][nested_key] == nested_value, f"{case['name']}: {key}.{nested_key}"
                    else:
                        assert match[key] == value, f"{case['name']}: {key}"


def test_evaluation_set_contains_an_edge_case_with_numeric_expectations():
    cases = json.loads((PROJECT_ROOT / "evaluation" / "cases.json").read_text(encoding="utf-8"))
    assert any(case.get("edge_case") and case.get("expected_results") for case in cases)
