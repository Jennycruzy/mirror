from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from mirror.agents.red import RED_FORECAST_SYSTEM_PROMPT, abstention_forecast, extract_order_id, extract_price_for_symbol
from mirror.agents.strategy_schema import RedForecast, parse_strategy_yaml
from mirror.calibration.brier import direction_to_probability_up
from mirror.clients.featherless import FeatherlessClient
from mirror.clients.gemini import GeminiClient
from mirror.clients.kraken import KrakenClient
from mirror.config import Settings
from mirror.errors import InferenceMalformedJSON
from mirror.models import Agent, Event, Forecast, MarketTick, Trade


class RedState(TypedDict, total=False):
    agent_lineage: str
    settings: Settings
    session_factory: Any
    agent_id: str
    strategy_yaml: str
    ticker: str
    market_state: dict[str, Any]
    market_price: float
    features: dict[str, Any]
    forecast_payload: dict[str, Any]
    forecast_id: str
    should_trade: bool
    trade_id: str
    event_id: str


async def fetch_market_state(state: RedState) -> RedState:
    settings = state["settings"]
    kraken = KrakenClient(settings)
    async with state["session_factory"]() as session:
        agent = (
            await session.execute(
                select(Agent)
                .where(Agent.lineage == state["agent_lineage"], Agent.status == "active")
                .order_by(Agent.version.desc())
                .limit(1)
            )
        ).scalar_one()
        strategy = parse_strategy_yaml(agent.strategy_yaml)
        ticker = strategy.locked.locked_tickers[0] if strategy.locked.locked_tickers else None
        if not ticker:
            raise RuntimeError("No discovered Kraken xStock perpetual symbols are assigned to this strategy")
        ticker_payload = (await kraken.run_json(["futures", "tickers", "-o", "json"])).json_data
        price = extract_price_for_symbol(ticker_payload, ticker)
        if price is None:
            raise RuntimeError(f"Could not extract a real price for discovered symbol {ticker} from Kraken ticker output")
        session.add(MarketTick(ticker=ticker, price=price, raw_ticker=ticker_payload, observed_at=datetime.now(UTC)))
        await session.commit()
        return {
            **state,
            "agent_id": agent.id,
            "strategy_yaml": agent.strategy_yaml,
            "ticker": ticker,
            "market_state": ticker_payload,
            "market_price": price,
        }


async def build_features(state: RedState) -> RedState:
    now = datetime.now(UTC)
    features = {
        "observed_at": now.isoformat(),
        "hour_utc": now.hour,
        "weekday": now.weekday(),
        "session": "weekend" if now.weekday() >= 5 else "weekday",
        "price": state["market_price"],
    }
    return {**state, "features": features}


async def forecast(state: RedState) -> RedState:
    settings = state["settings"]
    strategy = parse_strategy_yaml(state["strategy_yaml"])
    messages = [
        {"role": "system", "content": RED_FORECAST_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Strategy YAML:\n"
                f"{state['strategy_yaml']}\n\n"
                "Features JSON:\n"
                f"{state['features']}\n\n"
                "Kraken ticker JSON:\n"
                f"{state['market_state']}\n\n"
                "Return the Red Forecast JSON schema exactly."
            ),
        },
    ]
    try:
        if settings.featherless_api_key:
            forecast_obj = await FeatherlessClient(settings).chat_json(messages, RedForecast)
        elif settings.gemini_api_key:
            forecast_obj = await GeminiClient(settings).generate_json(messages[-1]["content"], RedForecast)
        else:
            raise RuntimeError("Set FEATHERLESS_API_KEY or GEMINI_API_KEY for real forecast inference")
    except InferenceMalformedJSON:
        forecast_obj = abstention_forecast(strategy.locked.default_horizon_minutes)

    if forecast_obj.leverage > strategy.mutable.max_leverage:
        forecast_obj = forecast_obj.model_copy(update={"leverage": strategy.mutable.max_leverage, "will_trade": False})
    if forecast_obj.confidence < strategy.mutable.entry_confidence_threshold:
        forecast_obj = forecast_obj.model_copy(update={"will_trade": False})

    return {**state, "forecast_payload": forecast_obj.model_dump()}


async def decide_action(state: RedState) -> RedState:
    payload = state["forecast_payload"]
    should_trade = bool(payload["will_trade"] and payload["predicted_direction"] in {"long", "short"})
    return {**state, "should_trade": should_trade}


async def execute_trade(state: RedState) -> RedState:
    settings = state["settings"]
    payload = state["forecast_payload"]
    now = datetime.now(UTC)
    async with state["session_factory"]() as session:
        forecast_row = Forecast(
            agent_id=state["agent_id"],
            ticker=state["ticker"],
            horizon_minutes=payload["time_horizon_minutes"],
            predicted_direction=payload["predicted_direction"],
            predicted_magnitude_bps=payload["predicted_magnitude_bps"],
            confidence=payload["confidence"],
            probability_up=direction_to_probability_up(payload["predicted_direction"], payload["confidence"]),
            regime_tags=payload["regime_tags"],
            will_trade=payload["will_trade"],
            position_size_usd=payload["position_size_usd"],
            leverage=payload["leverage"],
            stop_loss_pct=payload["stop_loss_pct"],
            take_profit_pct=payload["take_profit_pct"],
            reasoning=payload["reasoning"],
            raw_model_response=payload,
            emitted_at=now,
            resolves_at=now + timedelta(minutes=payload["time_horizon_minutes"]),
            status="open",
        )
        session.add(forecast_row)
        await session.flush()

        trade_id: str | None = None
        if settings.trading_enabled and state["should_trade"]:
            idempotency_key = f"{state['agent_id']}:{forecast_row.id}:paper"
            side = "buy" if forecast_row.predicted_direction == "long" else "sell"
            response = await KrakenClient(settings).place_paper_order(
                symbol=state["ticker"],
                side=side,
                size_usd=forecast_row.position_size_usd,
                leverage=forecast_row.leverage,
                idempotency_key=idempotency_key,
            )
            trade = Trade(
                agent_id=state["agent_id"],
                forecast_id=forecast_row.id,
                mode="paper",
                ticker=state["ticker"],
                side=side,
                size_usd=forecast_row.position_size_usd,
                leverage=forecast_row.leverage,
                order_type="market",
                kraken_order_id=extract_order_id(response),
                idempotency_key=idempotency_key,
                opened_at=now,
                status="open",
                raw_kraken_response=response,
            )
            session.add(trade)
            await session.flush()
            trade_id = str(trade.id)
        elif state["should_trade"]:
            session.add(Event(agent_id=state["agent_id"], kind="trade_skipped", severity="warning", payload_json={"reason": "TRADING_ENABLED=false"}))

        session.add(Event(agent_id=state["agent_id"], kind="forecast_emitted", severity="info", payload_json={"forecast_id": str(forecast_row.id)}))
        await session.commit()
        return {**state, "forecast_id": str(forecast_row.id), "trade_id": trade_id or ""}


async def log_event(state: RedState) -> RedState:
    async with state["session_factory"]() as session:
        event = Event(
            agent_id=state.get("agent_id"),
            kind="red_graph_completed",
            severity="info",
            payload_json={
                "agent_lineage": state["agent_lineage"],
                "agent_id": str(state.get("agent_id")),
                "forecast_id": state.get("forecast_id"),
                "trade_id": state.get("trade_id"),
            },
        )
        session.add(event)
        await session.commit()
        return {**state, "event_id": str(event.id)}


def build_red_graph():
    graph = StateGraph(RedState)
    graph.add_node("fetch_market_state", fetch_market_state)
    graph.add_node("build_features", build_features)
    graph.add_node("forecast", forecast)
    graph.add_node("decide_action", decide_action)
    graph.add_node("execute_trade", execute_trade)
    graph.add_node("log_event", log_event)
    graph.add_edge(START, "fetch_market_state")
    graph.add_edge("fetch_market_state", "build_features")
    graph.add_edge("build_features", "forecast")
    graph.add_edge("forecast", "decide_action")
    graph.add_edge("decide_action", "execute_trade")
    graph.add_edge("execute_trade", "log_event")
    graph.add_edge("log_event", END)
    return graph.compile()
