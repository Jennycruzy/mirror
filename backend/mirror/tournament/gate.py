from dataclasses import dataclass

from mirror.backtest.replay import ReplayResult


@dataclass(frozen=True)
class TournamentGateResult:
    passed: bool
    pnl_improvement_pct: float
    drawdown_change_pct: float
    brier_change_pct: float
    rejection_reason: str | None


def evaluate_tournament_gate(
    pre: ReplayResult,
    post: ReplayResult,
    *,
    min_pnl_improvement_pct: float = 10.0,
    max_drawdown_worsening_pct: float = 20.0,
    max_brier_degradation_pct: float = 10.0,
) -> TournamentGateResult:
    pnl_improvement_pct = percentage_change(pre.realized_pnl_usd, post.realized_pnl_usd)
    drawdown_change_pct = percentage_change(pre.max_drawdown_usd, post.max_drawdown_usd)
    brier_change_pct = percentage_change(pre.brier, post.brier)

    reasons: list[str] = []
    if pnl_improvement_pct < min_pnl_improvement_pct:
        reasons.append(f"pnl improvement below {min_pnl_improvement_pct:.1f}%")
    if drawdown_change_pct > max_drawdown_worsening_pct:
        reasons.append(f"drawdown worsened by more than {max_drawdown_worsening_pct:.1f}%")
    if brier_change_pct > max_brier_degradation_pct:
        reasons.append(f"brier degraded by more than {max_brier_degradation_pct:.1f}%")

    return TournamentGateResult(
        passed=not reasons,
        pnl_improvement_pct=pnl_improvement_pct,
        drawdown_change_pct=drawdown_change_pct,
        brier_change_pct=brier_change_pct,
        rejection_reason="; ".join(reasons) if reasons else None,
    )


def percentage_change(previous: float, current: float) -> float:
    if previous == 0:
        if current == 0:
            return 0.0
        return 100.0 if current > 0 else -100.0
    return ((current - previous) / abs(previous)) * 100.0

