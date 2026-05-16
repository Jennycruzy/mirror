from fastapi import APIRouter
from sqlalchemy import select

from mirror.db import SessionLocal

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health():
    checks = {}
    try:
        async with SessionLocal() as session:
            await session.execute(select(1))
        checks["postgres"] = {"ok": True}
    except Exception as exc:
        checks["postgres"] = {"ok": False, "detail": str(exc)}
    return {"ok": all(check["ok"] for check in checks.values()), "checks": checks}
