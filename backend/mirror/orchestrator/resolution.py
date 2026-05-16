from datetime import UTC, datetime

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from typing_extensions import TypedDict

from mirror.agents.red import extract_price_for_symbol
from mirror.calibration.brier import brier_score
from mirror.clients.kraken import KrakenClient
from mirror.config import Settings
from mirror.models import Event, Forecast, MarketTick


class ResolutionState(TypedDict, total=False):
    settings: Settings
    session_factory: async_sessionmaker
    resolved_count: int


async def load_due_forecasts(state: ResolutionState) -> ResolutionState:
    return state


async def resolve_due_forecasts(state: ResolutionState) -> ResolutionState:
    settings = state["settings"]
    resolved_count = 0
    async with state["session_factory"]() as session:
        due_forecasts = (
            await session.execute(
                select(Forecast)
                .where(Forecast.status == "open", Forecast.resolves_at <= datetime.now(UTC))
                .order_by(Forecast.resolves_at.asc())
                .limit(100)
            )
        ).scalars().all()

        if not due_forecasts:
            return {**state, "resolved_count": 0}

        ticker_payload = (await KrakenClient(settings).run_json(["futures", "tickers", "-o", "json"])).json_data
        for forecast in due_forecasts:
            observed_at = datetime.now(UTC)
            current_price = extract_price_for_symbol(ticker_payload, forecast.ticker)
            if current_price is None:
                session.add(
                    Event(
                        agent_id=forecast.agent_id,
                        kind="forecast_resolution_failed",
                        severity="error",
                        payload_json={"forecast_id": str(forecast.id), "reason": "current Kraken price unavailable"},
                    )
                )
                continue

            start_tick = (
                await session.execute(
                    select(MarketTick)
                    .where(MarketTick.ticker == forecast.ticker, MarketTick.observed_at <= forecast.emitted_at)
                    .order_by(MarketTick.observed_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if start_tick is None:
                start_tick = (
                    await session.execute(
                        select(MarketTick)
                        .where(MarketTick.ticker == forecast.ticker)
                        .order_by(MarketTick.observed_at.asc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
            if start_tick is None:
                session.add(
                    Event(
                        agent_id=forecast.agent_id,
                        kind="forecast_resolution_failed",
                        severity="error",
                        payload_json={"forecast_id": str(forecast.id), "reason": "entry market tick unavailable"},
                    )
                )
                continue

            realized_magnitude_bps = ((current_price - start_tick.price) / start_tick.price) * 10000
            realized_direction = "up" if realized_magnitude_bps > 0 else "down"
            outcome = 1.0 if realized_direction == "up" else 0.0
            forecast.resolved_at = observed_at
            forecast.realized_direction = realized_direction
            forecast.realized_magnitude_bps = realized_magnitude_bps
            forecast.realized_probability_outcome = outcome
            forecast.brier_score = brier_score(forecast.probability_up, realized_direction)
            forecast.status = "resolved"
            session.add(
                MarketTick(ticker=forecast.ticker, price=current_price, raw_ticker=ticker_payload, observed_at=observed_at)
            )
            session.add(
                Event(
                    agent_id=forecast.agent_id,
                    kind="forecast_resolved",
                    severity="info",
                    payload_json={
                        "forecast_id": str(forecast.id),
                        "brier_score": forecast.brier_score,
                        "realized_direction": realized_direction,
                        "realized_magnitude_bps": realized_magnitude_bps,
                    },
                )
            )
            resolved_count += 1

        await session.commit()
        return {**state, "resolved_count": resolved_count}


def build_resolution_graph():
    graph = StateGraph(ResolutionState)
    graph.add_node("load_due_forecasts", load_due_forecasts)
    graph.add_node("resolve_due_forecasts", resolve_due_forecasts)
    graph.add_edge(START, "load_due_forecasts")
    graph.add_edge("load_due_forecasts", "resolve_due_forecasts")
    graph.add_edge("resolve_due_forecasts", END)
    return graph.compile()
