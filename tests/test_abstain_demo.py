from demo.abstain_demo import run_demo


def test_reproducible_abstain_demo_uses_a_conflicting_fixture_row():
    result = run_demo()
    assert result["status"] == "abstained"
    assert "Conflicting duplicate source IDs" in result["answer"]
    assert result["execution_count"] == 1
