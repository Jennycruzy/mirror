from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.db import get_session
from mirror.models import Trade

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("")
async def list_trades(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Trade).order_by(Trade.opened_at.desc()).limit(100))).scalars().all()
    return [{"id": str(t.id), "agent_id": str(t.agent_id), "ticker": t.ticker, "side": t.side, "status": t.status} for t in rows]
