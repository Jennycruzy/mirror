from mirror.agents.crossover import donor_holdout_summary
from mirror.models import Patch


def test_donor_holdout_summary_contains_gate_metrics():
    patch = Patch(
        source_agent_id=None,
        target_agent_id=None,
        patch_type="blue_finding",
        base_strategy_yaml="base",
        proposed_yaml="proposed",
        proposed_patch_json={},
        patch_hash="hash",
        holdout_pre_brier=0.2,
        holdout_post_brier=0.18,
        holdout_pre_trade_rate=0.5,
        holdout_post_trade_rate=0.45,
        brier_improvement_pct=10,
        trade_rate_preservation_pct=90,
        status="accepted",
    )
    summary = donor_holdout_summary(patch)
    assert summary["holdout_pre_brier"] == 0.2
    assert summary["trade_rate_preservation_pct"] == 90

