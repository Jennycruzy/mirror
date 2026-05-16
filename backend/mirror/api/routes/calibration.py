import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.calibration.brier import calibration_buckets
from mirror.db import get_session
from mirror.models import Forecast

router = APIRouter(prefix="/calibration", tags=["calibration"])


@router.get("")
async def calibration(agent_id: uuid.UUID | None = Query(default=None), session: AsyncSession = Depends(get_session)):
    query = select(Forecast).where(Forecast.status == "resolved", Forecast.realized_probability_outcome.is_not(None))
    if agent_id:
        query = query.where(Forecast.agent_id == agent_id)
    rows = (await session.execute(query.order_by(Forecast.resolved_at.desc()).limit(1000))).scalars().all()
    samples = [(f.probability_up, f.realized_probability_outcome) for f in rows if f.realized_probability_outcome is not None]
    return [
        {
            "lower": bucket.lower,
            "upper": bucket.upper,
            "count": bucket.count,
            "predicted_avg": bucket.predicted_avg,
            "realized_frequency": bucket.realized_frequency,
        }
        for bucket in calibration_buckets(samples)
    ]
