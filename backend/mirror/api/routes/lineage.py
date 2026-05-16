from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.db import get_session
from mirror.models import Agent

router = APIRouter(prefix="/lineage", tags=["lineage"])


@router.get("")
async def lineage(session: AsyncSession = Depends(get_session)):
    agents = (await session.execute(select(Agent))).scalars().all()
    nodes = [{"id": str(a.id), "lineage": a.lineage, "version": a.version, "token_id": a.on_chain_token_id} for a in agents]
    edges = []
    for a in agents:
        if a.parent_agent_id:
            edges.append({"source": str(a.parent_agent_id), "target": str(a.id), "type": "vertical"})
        if a.crossover_parent_agent_id:
            edges.append({"source": str(a.crossover_parent_agent_id), "target": str(a.id), "type": "crossover"})
    return {"nodes": nodes, "edges": edges}
