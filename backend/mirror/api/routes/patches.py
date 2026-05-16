from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.db import get_session
from mirror.models import Patch

router = APIRouter(prefix="/patches", tags=["patches"])


@router.get("")
async def list_patches(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Patch).order_by(Patch.created_at.desc()).limit(100))).scalars().all()
    return [{"id": str(p.id), "target_agent_id": str(p.target_agent_id), "status": p.status, "gate_passed": p.gate_passed} for p in rows]
