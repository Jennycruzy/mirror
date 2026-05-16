from dataclasses import dataclass

from mirror.agents.strategy_schema import Strategy, parse_strategy_yaml
from mirror.calibration.brier import direction_to_probability_up
from mirror.models import Forecast


@dataclass(frozen=True)
class ReplayResult:
    brier: float
    trade_rate: float
    sample_size: int
    trade_count: int


def replay_strategy(strategy_yaml: str, forecasts: list[Forecast]) -> ReplayResult:
    strategy = parse_strategy_yaml(strategy_yaml)
    resolved = [f for f in forecasts if f.realized_direction in {"up", "down"}]
    if not resolved:
        raise ValueError("holdout replay requires at least one resolved forecast")

    brier_values: list[float] = []
    trade_count = 0
    for forecast in resolved:
        will_trade = would_trade_under_strategy(strategy, forecast)
        if will_trade:
            trade_count += 1
        probability_up = probability_under_strategy(strategy, forecast, will_trade)
        outcome = 1.0 if forecast.realized_direction == "up" else 0.0
        brier_values.append((probability_up - outcome) ** 2)

    return ReplayResult(
        brier=sum(brier_values) / len(brier_values),
        trade_rate=trade_count / len(resolved),
        sample_size=len(resolved),
        trade_count=trade_count,
    )


def would_trade_under_strategy(strategy: Strategy, forecast: Forecast) -> bool:
    if forecast.predicted_direction not in {"long", "short"}:
        return False
    if forecast.confidence < strategy.mutable.entry_confidence_threshold:
        return False
    if forecast.leverage > strategy.mutable.max_leverage:
        return False
    if strategy.mutable.news_signal_required and "news" not in {tag.lower() for tag in (forecast.regime_tags or [])}:
        return False
    return True


def probability_under_strategy(strategy: Strategy, forecast: Forecast, will_trade: bool) -> float:
    if not will_trade:
        return 0.5
    capped_confidence = min(max(forecast.confidence, strategy.mutable.regime_confidence_min), 0.99)
    return direction_to_probability_up(forecast.predicted_direction, capped_confidence)
