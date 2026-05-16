import pytest

from mirror.agents.strategy_schema import apply_patch_to_strategy, initial_strategy_yaml, parse_strategy_yaml
from mirror.errors import PatchValidationFailed


def test_initial_strategy_valid():
    strategy = parse_strategy_yaml(initial_strategy_yaml("red-a", ["PF_TESTX_PERP"]))
    assert strategy.meta.lineage == "red-a"
    assert strategy.locked.locked_tickers == ["PF_TESTX_PERP"]


def test_locked_field_rejected():
    strategy_yaml = initial_strategy_yaml("red-a")
    with pytest.raises(PatchValidationFailed):
        apply_patch_to_strategy(strategy_yaml, {"locked": {"max_position_hold_hours": 99}, "mutable_changes": {}, "rationale": "", "expected_brier_improvement": 0})


def test_out_of_range_rejected():
    strategy_yaml = initial_strategy_yaml("red-a")
    with pytest.raises(PatchValidationFailed):
        apply_patch_to_strategy(strategy_yaml, {"mutable_changes": {"max_leverage": 99}, "rationale": "bad", "expected_brier_improvement": 0})

