from datetime import UTC, datetime, timedelta
from uuid import uuid4

from mirror.agents.strategy_schema import initial_strategy_yaml
from mirror.backtest.replay import replay_strategy
from mirror.models import Forecast


def forecast(confidence: float, direction: str, realized: str) -> Forecast:
    now = datetime.now(UTC)
    return Forecast(
        id=uuid4(),
        agent_id=uuid4(),
        ticker="PF_TESTX_PERP",
        horizon_minutes=60,
        predicted_direction=direction,
        predicted_magnitude_bps=10,
        confidence=confidence,
        probability_up=confidence if direction == "long" else 1 - confidence,
        regime_tags=[],
        will_trade=True,
        position_size_usd=50,
        leverage=1,
        stop_loss_pct=1,
        take_profit_pct=2,
        reasoning="test",
        raw_model_response={},
        emitted_at=now,
        resolves_at=now + timedelta(minutes=60),
        resolved_at=now + timedelta(minutes=60),
        realized_direction=realized,
        realized_magnitude_bps=10 if realized == "up" else -10,
        realized_probability_outcome=1 if realized == "up" else 0,
        brier_score=0.1,
        status="resolved",
    )


def test_replay_strategy_uses_threshold_for_trade_rate():
    strategy_yaml = initial_strategy_yaml("red-a")
    result = replay_strategy(strategy_yaml, [forecast(0.7, "long", "up"), forecast(0.55, "long", "down")])
    assert result.sample_size == 2
    assert result.trade_count == 1
    assert result.trade_rate == 0.5

