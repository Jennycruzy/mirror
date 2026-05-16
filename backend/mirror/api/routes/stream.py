import asyncio
import json

from fastapi import APIRouter
from sqlalchemy import select
from starlette.responses import StreamingResponse

from mirror.db import SessionLocal
from mirror.models import Event

router = APIRouter(prefix="/stream", tags=["stream"])


async def event_stream():
    last_seen = None
    while True:
        async with SessionLocal() as session:
            query = select(Event).order_by(Event.created_at.asc()).limit(100)
            if last_seen is not None:
                query = select(Event).where(Event.created_at > last_seen).order_by(Event.created_at.asc()).limit(100)
            rows = (await session.execute(query)).scalars().all()
            for row in rows:
                last_seen = row.created_at
                payload = {
                    "id": str(row.id),
                    "agent_id": str(row.agent_id) if row.agent_id else None,
                    "kind": row.kind,
                    "severity": row.severity,
                    "payload": row.payload_json,
                    "created_at": row.created_at.isoformat(),
                }
                yield f"id: {row.id}\nevent: {row.kind}\ndata: {json.dumps(payload)}\n\n"
        yield f"event: heartbeat\ndata: {json.dumps({'kind': 'heartbeat'})}\n\n"
        await asyncio.sleep(5)


@router.get("")
async def stream():
    return StreamingResponse(event_stream(), media_type="text/event-stream")
