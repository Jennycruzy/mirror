from mirror.backtest.gate import evaluate_holdout_gate


def test_holdout_gate_pass():
    result = evaluate_holdout_gate(0.2, 0.18, 10, 8)
    assert result.passed


def test_holdout_gate_fail_brier():
    result = evaluate_holdout_gate(0.2, 0.195, 10, 9)
    assert not result.passed
    assert "brier" in result.rejection_reason

