from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.agents.strategy_schema import RedForecast, parse_strategy_yaml
from mirror.calibration.brier import direction_to_probability_up
from mirror.clients.featherless import FeatherlessClient
from mirror.clients.gemini import GeminiClient
from mirror.clients.kraken import KrakenClient
from mirror.config import Settings
from mirror.errors import InferenceMalformedJSON
from mirror.models import Agent, Event, Forecast, MarketTick, Trade


RED_FORECAST_SYSTEM_PROMPT = """You are a MIRROR Red trading agent.
Return strict JSON only. Do not include markdown.
Allowed predicted_direction values: long, short, flat.
Use the provided strategy and real Kraken market ticker data.
If confidence is below strategy threshold, set will_trade=false unless scout_mode_enabled is true and the setup has a directional edge.
For scout trades, keep position_size_usd near scout_size_usd and use conservative leverage.
Required JSON keys:
predicted_direction, predicted_magnitude_bps, confidence, time_horizon_minutes,
regime_tags, will_trade, position_size_usd, leverage, stop_loss_pct,
take_profit_pct, reasoning.
For flat/abstain, use confidence=0.5, position_size_usd=0, leverage=1,
stop_loss_pct=0, take_profit_pct=0, and explain in reasoning.
"""


def abstention_forecast(horizon_minutes: int) -> RedForecast:
    return RedForecast(
        predicted_direction="flat",
        predicted_magnitude_bps=0,
        confidence=0.5,
        time_horizon_minutes=horizon_minutes,
        regime_tags=["abstention"],
        will_trade=False,
        position_size_usd=0,
        leverage=1,
        stop_loss_pct=0,
        take_profit_pct=0,
        reasoning="Model response was unavailable or malformed; abstaining.",
    )


async def run_red_once(session: AsyncSession, settings: Settings, lineage: str) -> Forecast:
    from mirror.db import SessionLocal
    from mirror.orchestrator.graph import build_red_graph

    result = await build_red_graph().ainvoke({"agent_lineage": lineage, "settings": settings, "session_factory": SessionLocal})
    forecast = await session.get(Forecast, result["forecast_id"])
    if forecast is None:
        raise RuntimeError(f"LangGraph completed without persisted forecast {result['forecast_id']}")
    return forecast


async def run_red_once_legacy(session: AsyncSession, settings: Settings, lineage: str) -> Forecast:
    agent = (
        await session.execute(
            select(Agent).where(Agent.lineage == lineage, Agent.status == "active").order_by(Agent.version.desc()).limit(1)
        )
    ).scalar_one()
    strategy = parse_strategy_yaml(agent.strategy_yaml)
    ticker = strategy.locked.locked_tickers[0] if strategy.locked.locked_tickers else None
    if not ticker:
        raise RuntimeError("No discovered Kraken xStock perpetual symbols are assigned to this strategy")

    kraken = KrakenClient(settings)
    ticker_payload = (await kraken.run_json(["futures", "tickers", "-o", "json"])).json_data
    selected_ticker = extract_record_for_symbol(ticker_payload, ticker) or {}
    price = extract_price_for_symbol(selected_ticker or ticker_payload, ticker)
    if price is None:
        raise RuntimeError(f"Could not extract a real price for discovered symbol {ticker} from Kraken ticker output")
    tick = MarketTick(ticker=ticker, price=price, raw_ticker=ticker_payload, observed_at=datetime.now(UTC))
    session.add(tick)

    prompt = [
        {"role": "system", "content": RED_FORECAST_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Strategy YAML:\n"
                f"{agent.strategy_yaml}\n\n"
                "Kraken ticker JSON:\n"
                f"{selected_ticker}\n\n"
                "Return the Red Forecast JSON schema exactly."
            ),
        },
    ]
    try:
        if settings.featherless_api_key:
            forecast_obj = await FeatherlessClient(settings).chat_json(prompt, RedForecast)
        elif settings.gemini_api_key:
            forecast_obj = await GeminiClient(settings).generate_json(prompt[-1]["content"], RedForecast)
        else:
            raise RuntimeError("Set FEATHERLESS_API_KEY or GEMINI_API_KEY for real forecast inference")
    except InferenceMalformedJSON:
        forecast_obj = abstention_forecast(strategy.locked.default_horizon_minutes)

    if forecast_obj.leverage > strategy.mutable.max_leverage:
        forecast_obj = forecast_obj.model_copy(update={"leverage": strategy.mutable.max_leverage, "will_trade": False})
    if forecast_obj.confidence < strategy.mutable.entry_confidence_threshold:
        forecast_obj = forecast_obj.model_copy(update={"will_trade": False})

    now = datetime.now(UTC)
    forecast = Forecast(
        agent_id=agent.id,
        ticker=ticker,
        horizon_minutes=forecast_obj.time_horizon_minutes,
        predicted_direction=forecast_obj.predicted_direction,
        predicted_magnitude_bps=forecast_obj.predicted_magnitude_bps,
        confidence=forecast_obj.confidence,
        probability_up=direction_to_probability_up(forecast_obj.predicted_direction, forecast_obj.confidence),
        regime_tags=forecast_obj.regime_tags,
        will_trade=forecast_obj.will_trade,
        position_size_usd=forecast_obj.position_size_usd,
        leverage=forecast_obj.leverage,
        stop_loss_pct=forecast_obj.stop_loss_pct,
        take_profit_pct=forecast_obj.take_profit_pct,
        reasoning=forecast_obj.reasoning,
        raw_model_response=forecast_obj.model_dump(),
        emitted_at=now,
        resolves_at=now + timedelta(minutes=forecast_obj.time_horizon_minutes),
        status="open",
    )
    session.add(forecast)
    await session.flush()
    session.add(Event(agent_id=agent.id, kind="forecast_emitted", severity="info", payload_json={"forecast_id": str(forecast.id)}))

    if settings.trading_enabled and forecast.will_trade and forecast.predicted_direction in {"long", "short"}:
        idempotency_key = f"{agent.id}:{forecast.id}:paper"
        side = "buy" if forecast.predicted_direction == "long" else "sell"
        response = await KrakenClient(settings).place_paper_order(
            symbol=ticker,
            side=side,
            size_usd=forecast.position_size_usd,
            leverage=forecast.leverage,
            idempotency_key=idempotency_key,
        )
        session.add(
            Trade(
                agent_id=agent.id,
                forecast_id=forecast.id,
                mode="paper",
                ticker=ticker,
                side=side,
                size_usd=forecast.position_size_usd,
                leverage=forecast.leverage,
                order_type="market",
                kraken_order_id=extract_order_id(response),
                idempotency_key=idempotency_key,
                opened_at=now,
                status="open",
                raw_kraken_response=response,
            )
        )
        session.add(Event(agent_id=agent.id, kind="paper_trade_placed", severity="info", payload_json={"forecast_id": str(forecast.id)}))
    elif forecast.will_trade and not settings.trading_enabled:
        session.add(Event(agent_id=agent.id, kind="trade_skipped", severity="warning", payload_json={"reason": "TRADING_ENABLED=false"}))

    await session.commit()
    return forecast


def extract_order_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() in {"order_id", "orderid", "txid", "id"} and isinstance(value, str):
                return value
            found = extract_order_id(value)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = extract_order_id(item)
            if found:
                return found
    return None


def extract_price_for_symbol(payload: Any, symbol: str) -> float | None:
    candidates = []
    if isinstance(payload, dict):
        symbol_matches = any(isinstance(v, str) and v == symbol for v in payload.values())
        if symbol_matches:
            for key in ("price", "last", "markPrice", "mark_price", "lastPrice", "last_price"):
                value = payload.get(key)
                if isinstance(value, int | float):
                    candidates.append(float(value))
                if isinstance(value, str):
                    try:
                        candidates.append(float(value))
                    except ValueError:
                        pass
        for value in payload.values():
            found = extract_price_for_symbol(value, symbol)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = extract_price_for_symbol(item, symbol)
            if found is not None:
                return found
    return candidates[0] if candidates else None


def extract_record_for_symbol(payload: Any, symbol: str) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        if any(isinstance(v, str) and v == symbol for v in payload.values()):
            return payload
        for value in payload.values():
            found = extract_record_for_symbol(value, symbol)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = extract_record_for_symbol(item, symbol)
            if found is not None:
                return found
    return None
