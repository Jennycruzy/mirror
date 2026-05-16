from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.db import get_session
from mirror.models import Forecast

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.get("")
async def list_forecasts(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Forecast).order_by(Forecast.emitted_at.desc()).limit(100))).scalars().all()
    return [
        {
            "id": str(f.id),
            "agent_id": str(f.agent_id),
            "ticker": f.ticker,
            "predicted_direction": f.predicted_direction,
            "confidence": f.confidence,
            "probability_up": f.probability_up,
            "will_trade": f.will_trade,
            "status": f.status,
            "emitted_at": f.emitted_at.isoformat(),
            "resolves_at": f.resolves_at.isoformat(),
            "brier_score": f.brier_score,
        }
        for f in rows
    ]
