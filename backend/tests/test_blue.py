import uuid
from datetime import UTC, datetime

from mirror.agents.blue import stratify_forecasts
from mirror.models import Forecast


def make_forecast(*, ticker: str, confidence: float, predicted_direction: str, realized_direction: str, tags: list[str]) -> Forecast:
    now = datetime.now(UTC)
    return Forecast(
        id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        ticker=ticker,
        horizon_minutes=60,
        predicted_direction=predicted_direction,
        predicted_magnitude_bps=40,
        confidence=confidence,
        probability_up=confidence,
        regime_tags=tags,
        will_trade=True,
        position_size_usd=100,
        leverage=1,
        stop_loss_pct=1.0,
        take_profit_pct=2.0,
        reasoning="test",
        raw_model_response={"ok": True},
        emitted_at=now,
        resolves_at=now,
        resolved_at=now,
        realized_direction=realized_direction,
        realized_magnitude_bps=25,
        realized_probability_outcome=1.0 if realized_direction == "up" else 0.0,
        brier_score=0.2,
        status="resolved",
    )


def test_blue_stratification_includes_global_and_coarse_groups():
    forecasts = [
        make_forecast(ticker="BTC/USD", confidence=0.7, predicted_direction="long", realized_direction="up", tags=["trend_up", "weekday"]),
        make_forecast(ticker="ETH/USD", confidence=0.68, predicted_direction="long", realized_direction="down", tags=["trend_up", "weekday"]),
        make_forecast(ticker="SOL/USD", confidence=0.58, predicted_direction="long", realized_direction="up", tags=["mean_reversion", "weekend"]),
    ]

    summaries = stratify_forecasts(forecasts)
    contexts = [summary["regime_context"] for summary in summaries]

    assert {"scope": "all"} in contexts
    assert {"direction": "long"} in contexts
    assert {"tag": "trend"} in contexts
    assert {"confidence": "medium"} in contexts
