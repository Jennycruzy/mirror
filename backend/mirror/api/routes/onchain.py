from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.db import get_session
from mirror.models import OnchainJob

router = APIRouter(prefix="/onchain-jobs", tags=["onchain"])


@router.get("")
async def list_onchain_jobs(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(OnchainJob).order_by(OnchainJob.created_at.desc()).limit(100))).scalars().all()
    return [
        {
            "id": str(row.id),
            "job_type": row.job_type,
            "agent_id": str(row.agent_id) if row.agent_id else None,
            "patch_id": str(row.patch_id) if row.patch_id else None,
            "status": row.status,
            "attempt_count": row.attempt_count,
            "last_error": row.last_error,
            "tx_hash": row.tx_hash,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }
        for row in rows
    ]

