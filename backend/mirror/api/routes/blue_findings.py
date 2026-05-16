from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.db import get_session
from mirror.models import BlueFinding

router = APIRouter(prefix="/blue-findings", tags=["blue-findings"])


@router.get("")
async def list_blue_findings(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(BlueFinding).order_by(BlueFinding.created_at.desc()).limit(100))).scalars().all()
    return [
        {
            "id": str(row.id),
            "agent_id": str(row.agent_id),
            "regime_context": row.regime_context,
            "sample_size": row.sample_size,
            "predicted_confidence_avg": row.predicted_confidence_avg,
            "realized_accuracy": row.realized_accuracy,
            "brier_gap": row.brier_gap,
            "suggested_failure_mode": row.suggested_failure_mode,
            "suggested_fix_direction": row.suggested_fix_direction,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]

