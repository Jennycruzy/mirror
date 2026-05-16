from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from mirror.db import get_session
from mirror.models import Agent

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_agents(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Agent).order_by(Agent.lineage, Agent.version))).scalars().all()
    return [
        {
            "id": str(a.id),
            "lineage": a.lineage,
            "name": a.name,
            "version": a.version,
            "status": a.status,
            "on_chain_token_id": a.on_chain_token_id,
        }
        for a in rows
    ]

