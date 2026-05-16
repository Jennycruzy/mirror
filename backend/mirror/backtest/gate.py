from dataclasses import dataclass


@dataclass(frozen=True)
class HoldoutGateResult:
    passed: bool
    brier_improvement_pct: float
    trade_rate_preservation_pct: float
    rejection_reason: str | None


def evaluate_holdout_gate(
    pre_brier: float,
    post_brier: float,
    pre_trade_rate: float,
    post_trade_rate: float,
) -> HoldoutGateResult:
    if pre_brier <= 0:
        raise ValueError("pre_brier must be positive")
    if pre_trade_rate < 0 or post_trade_rate < 0:
        raise ValueError("trade rates must be non-negative")

    brier_improvement_pct = ((pre_brier - post_brier) / pre_brier) * 100
    trade_rate_preservation_pct = 100.0 if pre_trade_rate == 0 else (post_trade_rate / pre_trade_rate) * 100

    reasons: list[str] = []
    if post_brier > pre_brier * 0.95:
        reasons.append("brier improvement below 5%")
    if post_trade_rate < pre_trade_rate * 0.80:
        reasons.append("trade rate below 80% of previous strategy")

    return HoldoutGateResult(
        passed=not reasons,
        brier_improvement_pct=brier_improvement_pct,
        trade_rate_preservation_pct=trade_rate_preservation_pct,
        rejection_reason="; ".join(reasons) if reasons else None,
    )

