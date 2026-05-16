from datetime import UTC, datetime, timedelta
from uuid import uuid4

from mirror.api.routes.agents import serialize_forecast
from mirror.models import Forecast


def test_serialize_forecast_shape():
    now = datetime.now(UTC)
    forecast = Forecast(
        id=uuid4(),
        agent_id=uuid4(),
        ticker="PF_TESTX_PERP",
        horizon_minutes=60,
        predicted_direction="long",
        predicted_magnitude_bps=12,
        confidence=0.7,
        probability_up=0.7,
        regime_tags=["trend_up"],
        will_trade=True,
        position_size_usd=50,
        leverage=1,
        stop_loss_pct=1,
        take_profit_pct=2,
        reasoning="test",
        raw_model_response={},
        emitted_at=now,
        resolves_at=now + timedelta(minutes=60),
        status="open",
    )
    payload = serialize_forecast(forecast)
    assert payload["ticker"] == "PF_TESTX_PERP"
    assert payload["predicted_direction"] == "long"
    assert payload["confidence"] == 0.7

