from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.db import get_session
from mirror.models import Event

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
async def list_events(session: AsyncSession = Depends(get_session), limit: int = 100):
    capped_limit = min(max(limit, 1), 250)
    rows = (await session.execute(select(Event).order_by(Event.created_at.desc()).limit(capped_limit))).scalars().all()
    return [
        {
            "id": str(row.id),
            "agent_id": str(row.agent_id) if row.agent_id else None,
            "kind": row.kind,
            "severity": row.severity,
            "payload": row.payload_json,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
