from dataclasses import dataclass

from mirror.agents.strategy_schema import RedForecast, Strategy


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str | None = None


def validate_tournament_trade(
    strategy: Strategy,
    forecast: RedForecast,
    *,
    min_confidence: float,
    max_position_risk_pct: float,
    account_equity_usd: float | None = None,
    open_positions_count: int = 0,
    max_concurrent_positions: int = 3,
) -> RiskDecision:
    if forecast.predicted_direction not in {"long", "short"}:
        return RiskDecision(False, "flat forecast")
    if not forecast.will_trade:
        return RiskDecision(False, "forecast abstained")
    if forecast.confidence < min_confidence and forecast.position_size_usd > strategy.locked.scout_size_usd:
        return RiskDecision(False, "confidence below tournament minimum")
    if abs(forecast.predicted_magnitude_bps) < strategy.mutable.tournament_min_expected_move_bps:
        return RiskDecision(False, "expected move below tournament minimum")
    if forecast.leverage > strategy.mutable.max_leverage:
        return RiskDecision(False, "leverage exceeds strategy max")
    if open_positions_count >= max_concurrent_positions:
        return RiskDecision(False, "max concurrent positions reached")
    if account_equity_usd and account_equity_usd > 0:
        risk_pct = (forecast.position_size_usd * forecast.leverage / account_equity_usd) * 100.0
        if risk_pct > max_position_risk_pct:
            return RiskDecision(False, "position risk exceeds tournament limit")
    return RiskDecision(True)
