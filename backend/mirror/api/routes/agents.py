from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from mirror.db import get_session
from mirror.models import Agent, Forecast, Trade

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_agents(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Agent).order_by(Agent.lineage, Agent.version))).scalars().all()
    now = datetime.now(UTC)
    day_start = datetime.combine(now.date(), time.min, tzinfo=UTC)
    output = []
    for a in rows:
        latest_forecast = (
            await session.execute(
                select(Forecast)
                .where(Forecast.agent_id == a.id)
                .order_by(Forecast.emitted_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        brier_24h = await session.scalar(
            select(func.avg(Forecast.brier_score)).where(
                Forecast.agent_id == a.id,
                Forecast.status == "resolved",
                Forecast.resolved_at >= now - timedelta(hours=24),
                Forecast.brier_score.is_not(None),
            )
        )
        trades_today = await session.scalar(
            select(func.count()).select_from(Trade).where(Trade.agent_id == a.id, Trade.opened_at >= day_start)
        )
        open_positions = await session.scalar(
            select(func.count()).select_from(Trade).where(Trade.agent_id == a.id, Trade.status == "open")
        )
        output.append(
            {
            "id": str(a.id),
            "lineage": a.lineage,
            "name": a.name,
            "version": a.version,
            "status": a.status,
            "on_chain_token_id": a.on_chain_token_id,
            "basescan_url": f"https://sepolia.basescan.org/token/{a.on_chain_token_id}" if a.on_chain_token_id else None,
            "rolling_24h_brier": float(brier_24h) if brier_24h is not None else None,
            "trades_today": int(trades_today or 0),
            "open_positions": int(open_positions or 0),
            "trade_floor": 8,
            "unrealized_pnl_usd": None,
            "latest_forecast": serialize_forecast(latest_forecast) if latest_forecast else None,
        }
        )
    return output


def serialize_forecast(forecast: Forecast) -> dict:
    return {
        "id": str(forecast.id),
        "ticker": forecast.ticker,
        "predicted_direction": forecast.predicted_direction,
        "confidence": forecast.confidence,
        "will_trade": forecast.will_trade,
        "status": forecast.status,
        "emitted_at": forecast.emitted_at.isoformat(),
        "brier_score": forecast.brier_score,
    }
