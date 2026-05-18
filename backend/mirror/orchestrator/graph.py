from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import func, select

from mirror.agents.red import RED_FORECAST_SYSTEM_PROMPT, abstention_forecast, extract_order_id, extract_record_for_symbol
from mirror.agents.strategy_schema import RedForecast, parse_strategy_yaml
from mirror.calibration.brier import direction_to_probability_up
from mirror.clients.featherless import FeatherlessClient
from mirror.clients.gemini import GeminiClient
from mirror.clients.kraken import KrakenClient, extract_price_for_symbol, select_best_xstock_record, spot_ticker_record
from mirror.config import Settings
from mirror.errors import InferenceMalformedJSON
from mirror.models import Agent, Event, Forecast, MarketTick, Trade
from mirror.tournament.risk import RiskDecision, validate_tournament_trade


class RedState(TypedDict, total=False):
    agent_lineage: str
    settings: Settings
    session_factory: Any
    ticker_override: str
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
        if settings.kraken_execution_mode == "spot_paper":
            ticker = state.get("ticker_override") or default_spot_pair_for_lineage(settings, state["agent_lineage"])
            ticker_payload = await kraken.spot_ticker(ticker)
            selected_ticker = spot_ticker_record(ticker_payload, ticker)
        elif settings.kraken_execution_mode == "account":
            ticker = state.get("ticker_override") or default_futures_symbol_for_lineage(settings, state["agent_lineage"])
            if not ticker:
                raise RuntimeError("No configured futures symbols are available for account execution mode")
            ticker_payload = (await kraken.run_json(["futures", "tickers", "-o", "json"])).json_data
            selected_ticker = extract_record_for_symbol(ticker_payload, ticker) or {}
        else:
            ticker = strategy.locked.locked_tickers[0] if strategy.locked.locked_tickers else None
            if not ticker:
                raise RuntimeError("No discovered Kraken xStock perpetual symbols are assigned to this strategy")
            ticker_payload = (await kraken.run_json(["futures", "tickers", "-o", "json"])).json_data
            if state["settings"].mirror_mode == "tournament":
                selected_record = select_best_xstock_record(ticker_payload, strategy.locked.locked_tickers)
                if selected_record is not None:
                    ticker = selected_record.symbol
                    selected_ticker = selected_record.raw
                else:
                    selected_ticker = extract_record_for_symbol(ticker_payload, ticker) or {}
            else:
                selected_ticker = extract_record_for_symbol(ticker_payload, ticker) or {}
        price = extract_price_for_symbol(selected_ticker or ticker_payload, ticker)
        if price is None:
            raise RuntimeError(f"Could not extract a real price for discovered symbol {ticker} from Kraken ticker output")
        session.add(MarketTick(ticker=ticker, price=price, raw_ticker=ticker_payload, observed_at=datetime.now(UTC)))
        await session.commit()
        return {
            **state,
            "agent_id": agent.id,
            "strategy_yaml": agent.strategy_yaml,
            "ticker": ticker,
            "market_state": selected_ticker or {"symbol": ticker, "price": price},
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
    if settings.mirror_mode == "tournament" and not forecast_obj.will_trade:
        forecast_obj = tournament_scout_forecast(strategy, state, forecast_obj)

    return {**state, "forecast_payload": forecast_obj.model_dump()}


def tournament_scout_forecast(strategy, state: RedState, forecast_obj: RedForecast) -> RedForecast:
    if not strategy.locked.scout_mode_enabled:
        return forecast_obj
    market = state.get("market_state") or {}
    change24h = parse_market_float(market.get("change24h"))
    volume_quote = parse_market_float(market.get("volumeQuote"))
    if change24h is None or abs(change24h) < 0.15:
        return forecast_obj
    if volume_quote is not None and volume_quote < 100_000:
        return forecast_obj
    if state["settings"].kraken_execution_mode == "spot_paper":
        direction = "long"
        scout_tag = "spot_paper_dip_buy" if change24h < 0 else "spot_paper_momentum_long"
    else:
        direction = "long" if change24h > 0 else "short"
        scout_tag = "momentum_up" if direction == "long" else "momentum_down"
    expected_move_bps = min(max(abs(change24h) * 100.0, strategy.mutable.tournament_min_expected_move_bps), 150.0)
    confidence = min(max(strategy.mutable.entry_confidence_threshold, 0.55 + min(abs(change24h), 2.0) / 20.0), 0.74)
    scout_size = strategy.locked.scout_size_usd * min(max(strategy.mutable.position_size_multiplier, 1.0), 2.0)
    return RedForecast(
        predicted_direction=direction,
        predicted_magnitude_bps=expected_move_bps,
        confidence=confidence,
        time_horizon_minutes=strategy.locked.default_horizon_minutes,
        regime_tags=[*forecast_obj.regime_tags, "tournament_scout", scout_tag],
        will_trade=True,
        position_size_usd=scout_size,
        leverage=min(strategy.mutable.max_leverage, 2),
        stop_loss_pct=max(strategy.mutable.stop_distance_atr * 0.5, 0.5),
        take_profit_pct=max(strategy.mutable.take_profit_atr * 0.5, 0.75),
        reasoning=(
            f"Tournament scout override: model abstained, but {state['ticker']} has 24h change {change24h} "
            f"with quote volume {volume_quote}. Taking a controlled paper {direction} scout for PnL discovery."
        ),
    )


def parse_market_float(value):
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


async def decide_action(state: RedState) -> RedState:
    settings = state["settings"]
    payload = state["forecast_payload"]
    should_trade = bool(payload["will_trade"] and payload["predicted_direction"] in {"long", "short"})
    if settings.kraken_execution_mode == "spot_paper" and payload["predicted_direction"] == "short":
        should_trade = False
        payload = {
            **payload,
            "tournament_risk_decision": {"allowed": False, "reason": "spot_paper does not open short positions"},
        }
    if should_trade and settings.mirror_mode == "tournament":
        strategy = parse_strategy_yaml(state["strategy_yaml"])
        forecast_obj = RedForecast.model_validate(payload)
        payload = apply_tournament_position_sizing(settings, strategy, forecast_obj, state)
        forecast_obj = RedForecast.model_validate(payload)
        risk = await evaluate_tournament_risk(state, strategy, forecast_obj)
        should_trade = risk.allowed
        payload = {**payload, "tournament_risk_decision": {"allowed": risk.allowed, "reason": risk.reason}}
    return {**state, "forecast_payload": payload, "should_trade": should_trade}


def apply_tournament_position_sizing(settings: Settings, strategy, forecast_obj: RedForecast, state: RedState) -> dict[str, Any]:
    equity = settings.tournament_account_equity_usd
    market = state.get("market_state") or {}
    confidence_edge = max(forecast_obj.confidence - 0.5, 0.0)
    equity_pct = settings.tournament_scout_equity_pct
    if confidence_edge >= 0.18:
        equity_pct = settings.tournament_aggressive_equity_pct
    elif confidence_edge >= 0.10:
        equity_pct = (settings.tournament_scout_equity_pct + settings.tournament_aggressive_equity_pct) / 2
    volume_quote = parse_market_float(market.get("volumeQuote")) or 0.0
    if volume_quote < 500_000:
        equity_pct *= 0.5
    notional = equity * (equity_pct / 100.0) * min(max(strategy.mutable.position_size_multiplier, 0.25), 2.0)
    max_symbol_notional = equity * (settings.tournament_max_symbol_exposure_pct / 100.0)
    notional = min(max(notional, strategy.locked.scout_size_usd), max_symbol_notional)
    leverage = 1 if settings.kraken_execution_mode == "spot_paper" else min(max(forecast_obj.leverage, 2), strategy.mutable.max_leverage)
    risk_notional_cap = equity * (settings.tournament_max_position_risk_pct / 100.0) / max(leverage, 1)
    notional = min(notional, int(risk_notional_cap * 100) / 100)
    return {
        **forecast_obj.model_dump(),
        "position_size_usd": round(notional, 2),
        "leverage": leverage,
        "reasoning": f"{forecast_obj.reasoning} Tournament sizing set notional to ${notional:.2f} at {leverage}x.",
    }


async def evaluate_tournament_risk(state: RedState, strategy, forecast_obj: RedForecast):
    settings = state["settings"]
    market = state.get("market_state") or {}
    spread_bps = compute_spread_bps(market)
    volume_quote = parse_market_float(market.get("volumeQuote")) or 0.0
    confidence_floor = max(settings.tournament_min_confidence, strategy.mutable.entry_confidence_threshold)
    direction = "buy" if forecast_obj.predicted_direction == "long" else "sell"

    if forecast_obj.confidence < confidence_floor and forecast_obj.position_size_usd > strategy.locked.scout_size_usd:
        return RiskDecision(False, "confidence below tournament minimum")
    trend_bps = await trend_bps_for_symbol(state)
    if trend_bps is not None and settings.tournament_min_trend_bps > 0:
        if forecast_obj.predicted_direction == "long" and trend_bps < settings.tournament_min_trend_bps:
            return RiskDecision(False, f"long rejected by trend filter ({trend_bps:.2f} bps)")
        if forecast_obj.predicted_direction == "short" and trend_bps > -settings.tournament_min_trend_bps:
            return RiskDecision(False, f"short rejected by trend filter ({trend_bps:.2f} bps)")
    spread_cap_bps = spread_cap_for_symbol(settings, state["ticker"], strategy.mutable.tournament_max_spread_bps)
    if spread_bps is not None and spread_bps > spread_cap_bps:
        return RiskDecision(False, f"spread exceeds tournament maximum ({spread_bps:.2f} > {spread_cap_bps:.2f} bps)")
    if (
        settings.tournament_min_quote_volume > 0
        and volume_quote
        and volume_quote < settings.tournament_min_quote_volume
        and forecast_obj.position_size_usd > strategy.locked.scout_size_usd
    ):
        return RiskDecision(False, "liquidity below tournament minimum")

    async with state["session_factory"]() as session:
        open_positions_count = int(
            await session.scalar(
                select(func.count()).select_from(Trade).where(
                    Trade.status == "open",
                    Trade.mode == settings.kraken_execution_mode,
                )
            )
            or 0
        )
        symbol_notional = float(
            await session.scalar(
                select(func.coalesce(func.sum(Trade.size_usd), 0.0)).where(
                    Trade.status == "open",
                    Trade.mode == settings.kraken_execution_mode,
                    Trade.ticker == state["ticker"],
                )
            )
            or 0.0
        )
        same_side_count = int(
            await session.scalar(
                select(func.count()).select_from(Trade).where(
                    Trade.status == "open",
                    Trade.mode == settings.kraken_execution_mode,
                    Trade.ticker == state["ticker"],
                    Trade.side == direction,
                )
            )
            or 0
        )
    account_equity_usd = settings.tournament_account_equity_usd
    if same_side_count >= settings.tournament_max_same_side_symbol_positions:
        return RiskDecision(False, "same-direction symbol exposure already open")
    max_symbol_notional = account_equity_usd * (settings.tournament_max_symbol_exposure_pct / 100.0)
    if symbol_notional + forecast_obj.position_size_usd > max_symbol_notional:
        return RiskDecision(False, "symbol exposure exceeds tournament limit")
    strategy_for_risk = strategy.model_copy(
        update={
            "mutable": strategy.mutable.model_copy(
                update={
                    "tournament_min_expected_move_bps": min(
                        strategy.mutable.tournament_min_expected_move_bps,
                        settings.tournament_min_expected_move_bps,
                    )
                }
            )
        }
    )
    return validate_tournament_trade(
        strategy_for_risk,
        forecast_obj,
        min_confidence=confidence_floor,
        max_position_risk_pct=settings.tournament_max_position_risk_pct,
        account_equity_usd=account_equity_usd,
        open_positions_count=open_positions_count,
        max_concurrent_positions=settings.tournament_max_concurrent_positions,
    )


def compute_spread_bps(market: dict[str, Any]) -> float | None:
    bid = parse_market_float(market.get("bid"))
    ask = parse_market_float(market.get("ask"))
    price = parse_market_float(market.get("markPrice")) or parse_market_float(market.get("price")) or parse_market_float(market.get("last"))
    if bid is None or ask is None or price is None or price <= 0 or ask < bid:
        return None
    spread = ((ask - bid) / price) * 10000.0
    bid_deviation = abs((price - bid) / price) * 10000.0
    ask_deviation = abs((ask - price) / price) * 10000.0
    if spread > 300 or bid_deviation > 300 or ask_deviation > 300:
        return None
    return spread


async def trend_bps_for_symbol(state: RedState) -> float | None:
    settings = state["settings"]
    market = state.get("market_state") or {}
    change24h = parse_market_float(market.get("change24h"))
    if change24h is not None:
        return change24h * 100.0
    current_price = state.get("market_price")
    if current_price is None or current_price <= 0:
        return None
    since = datetime.now(UTC) - timedelta(minutes=settings.tournament_trend_lookback_minutes)
    async with state["session_factory"]() as session:
        previous = (
            await session.execute(
                select(MarketTick)
                .where(MarketTick.ticker == state["ticker"], MarketTick.observed_at <= since)
                .order_by(MarketTick.observed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if previous is None or previous.price <= 0:
        return None
    return ((current_price - previous.price) / previous.price) * 10000.0


def spread_cap_for_symbol(settings: Settings, symbol: str, strategy_cap_bps: float) -> float:
    return settings.tournament_symbol_spread_caps_map().get(symbol.upper(), strategy_cap_bps)


def default_spot_pair_for_lineage(settings: Settings, lineage: str) -> str:
    pairs = settings.trading_pairs_list()
    lineages = ["red-a", "red-b", "red-c", "red-d"]
    try:
        idx = lineages.index(lineage)
    except ValueError:
        idx = 0
    return pairs[idx % len(pairs)]


def default_futures_symbol_for_lineage(settings: Settings, lineage: str) -> str | None:
    symbols = settings.trading_futures_symbols_list()
    if not symbols:
        return None
    lineages = ["red-a", "red-b", "red-c", "red-d"]
    try:
        idx = lineages.index(lineage)
    except ValueError:
        idx = 0
    return symbols[idx % len(symbols)]


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
            idempotency_key = f"{state['agent_id']}:{forecast_row.id}:{settings.kraken_execution_mode}"
            side = "buy" if forecast_row.predicted_direction == "long" else "sell"
            response = await KrakenClient(settings).place_order(
                symbol=state["ticker"],
                side=side,
                size_usd=forecast_row.position_size_usd,
                leverage=forecast_row.leverage,
                idempotency_key=idempotency_key,
            )
            trade = Trade(
                agent_id=state["agent_id"],
                forecast_id=forecast_row.id,
                mode=settings.kraken_execution_mode,
                ticker=state["ticker"],
                side=side,
                size_usd=forecast_row.position_size_usd,
                leverage=forecast_row.leverage,
                order_type="market",
                kraken_order_id=extract_order_id(response),
                idempotency_key=idempotency_key,
                opened_at=now,
                entry_price=state["market_price"],
                status="open",
                raw_kraken_response=response,
            )
            session.add(trade)
            await session.flush()
            trade_id = str(trade.id)
        elif state["should_trade"]:
            session.add(Event(agent_id=state["agent_id"], kind="trade_skipped", severity="warning", payload_json={"reason": "TRADING_ENABLED=false"}))
        elif settings.mirror_mode == "tournament" and payload.get("tournament_risk_decision", {}).get("reason"):
            session.add(
                Event(
                    agent_id=state["agent_id"],
                    kind="tournament_trade_vetoed",
                    severity="info",
                    payload_json={"forecast_id": str(forecast_row.id), **payload["tournament_risk_decision"]},
                )
            )

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
