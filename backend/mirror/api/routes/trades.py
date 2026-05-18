from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.config import get_settings
from mirror.clients.kraken import KrakenClient
from mirror.db import get_session
from mirror.models import Trade

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("/paper-status")
async def paper_status():
    kraken = KrakenClient(get_settings())
    return await kraken.trading_status()


@router.get("")
async def list_trades(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Trade).order_by(Trade.opened_at.desc()).limit(100))).scalars().all()
    return [
        {
            "id": str(t.id),
            "agent_id": str(t.agent_id),
            "forecast_id": str(t.forecast_id),
            "ticker": t.ticker,
            "side": t.side,
            "mode": t.mode,
            "size_usd": t.size_usd,
            "leverage": t.leverage,
            "status": t.status,
            "kraken_order_id": t.kraken_order_id,
            "opened_at": t.opened_at.isoformat() if t.opened_at else None,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "realized_pnl_usd": t.realized_pnl_usd,
        }
        for t in rows
    ]
