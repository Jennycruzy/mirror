from mirror.agents.strategy_schema import apply_patch_to_strategy, initial_strategy_yaml


def test_patch_parser_applies_mutable_only():
    patched = apply_patch_to_strategy(
        initial_strategy_yaml("red-a"),
        {
            "mutable_changes": {"entry_confidence_threshold": 0.67},
            "rationale": "raise threshold",
            "expected_brier_improvement": 0.05,
        },
    )
    assert patched.mutable.entry_confidence_threshold == 0.67

