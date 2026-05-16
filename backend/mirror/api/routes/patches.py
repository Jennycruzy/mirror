from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.db import get_session
from mirror.models import Patch

router = APIRouter(prefix="/patches", tags=["patches"])


@router.get("")
async def list_patches(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Patch).order_by(Patch.created_at.desc()).limit(100))).scalars().all()
    return [
        {
            "id": str(p.id),
            "source_agent_id": str(p.source_agent_id) if p.source_agent_id else None,
            "target_agent_id": str(p.target_agent_id),
            "blue_finding_id": str(p.blue_finding_id) if p.blue_finding_id else None,
            "patch_type": p.patch_type,
            "proposed_patch_json": p.proposed_patch_json,
            "holdout_pre_brier": p.holdout_pre_brier,
            "holdout_post_brier": p.holdout_post_brier,
            "holdout_pre_trade_rate": p.holdout_pre_trade_rate,
            "holdout_post_trade_rate": p.holdout_post_trade_rate,
            "brier_improvement_pct": p.brier_improvement_pct,
            "trade_rate_preservation_pct": p.trade_rate_preservation_pct,
            "status": p.status,
            "gate_passed": p.gate_passed,
            "rejection_reason": p.rejection_reason,
            "applied_agent_id": str(p.applied_agent_id) if p.applied_agent_id else None,
            "created_at": p.created_at.isoformat(),
        }
        for p in rows
    ]
