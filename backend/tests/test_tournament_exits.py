from datetime import UTC, datetime, timedelta
from uuid import uuid4

from mirror.models import Forecast, Trade
from mirror.tournament.exits import estimated_pnl_usd, exit_reason, leveraged_pnl_pct


def make_forecast(take_profit_pct: float = 1.0, stop_loss_pct: float = 0.5) -> Forecast:
    now = datetime.now(UTC)
    return Forecast(
        id=uuid4(),
        agent_id=uuid4(),
        ticker="PF_NVDAXUSD",
        horizon_minutes=60,
        predicted_direction="long",
        predicted_magnitude_bps=40,
        confidence=0.62,
        probability_up=0.62,
        regime_tags=[],
        will_trade=True,
        position_size_usd=400,
        leverage=2,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        reasoning="test",
        raw_model_response={},
        emitted_at=now,
        resolves_at=now + timedelta(minutes=60),
        status="open",
    )


def make_trade(side: str = "buy") -> Trade:
    return Trade(
        id=uuid4(),
        agent_id=uuid4(),
        forecast_id=uuid4(),
        mode="paper",
        ticker="PF_NVDAXUSD",
        side=side,
        size_usd=400,
        leverage=2,
        order_type="market",
        idempotency_key="idem",
        opened_at=datetime.now(UTC),
        entry_price=100,
        status="open",
        raw_kraken_response={},
    )


def test_leveraged_pnl_pct_long_and_short():
    assert leveraged_pnl_pct("buy", 100, 101, 2) == 2
    assert leveraged_pnl_pct("sell", 100, 99, 2) == 2


def test_exit_reason_take_profit_and_stop_loss():
    forecast = make_forecast()
    trade = make_trade()
    assert exit_reason(forecast, trade, 1.2) == "take_profit"
    assert exit_reason(forecast, trade, -0.6) == "stop_loss"
    assert exit_reason(forecast, trade, 0.2) is None


def test_estimated_pnl_usd_uses_leverage_and_notional():
    assert estimated_pnl_usd("buy", 100, 101, 400, 2) == 8

