from apscheduler.schedulers.asyncio import AsyncIOScheduler

from mirror.agents.blue import run_blue_scan
from mirror.agents.red import run_red_once
from mirror.config import Settings
from mirror.db import SessionLocal
from mirror.models import Event
from mirror.orchestrator.resolution import build_resolution_graph


async def run_lineage_once(settings: Settings, lineage: str) -> None:
    async with SessionLocal() as session:
        try:
            await run_red_once(session, settings, lineage)
        except Exception as exc:
            session.add(Event(agent_id=None, kind="red_run_failed", severity="error", payload_json={"lineage": lineage, "error": str(exc)}))
            await session.commit()


async def run_all_reds(settings: Settings) -> None:
    for lineage in ("red-a", "red-b", "red-c", "red-d"):
        await run_lineage_once(settings, lineage)


async def run_resolution_sweep(settings: Settings) -> None:
    try:
        await build_resolution_graph().ainvoke({"settings": settings, "session_factory": SessionLocal})
    except Exception as exc:
        async with SessionLocal() as session:
            session.add(Event(agent_id=None, kind="resolution_sweep_failed", severity="error", payload_json={"error": str(exc)}))
            await session.commit()


async def run_all_blue_scans(settings: Settings) -> None:
    for lineage in ("red-a", "red-b", "red-c", "red-d"):
        async with SessionLocal() as session:
            try:
                await run_blue_scan(session, settings, lineage)
            except Exception as exc:
                session.add(Event(agent_id=None, kind="blue_scan_failed", severity="error", payload_json={"lineage": lineage, "error": str(exc)}))
                await session.commit()


async def run_scout_floor_check_placeholder() -> None:
    async with SessionLocal() as session:
        session.add(
            Event(
                agent_id=None,
                kind="scout_floor_check_skipped",
                severity="warning",
                payload_json={"reason": "Scout floor enforcement requires live trade history"},
            )
        )
        await session.commit()


def build_scheduler(settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(run_all_reds, "interval", minutes=30, args=[settings], id="red_forecasts", replace_existing=True)
    scheduler.add_job(run_resolution_sweep, "interval", minutes=1, args=[settings], id="resolution_sweep", replace_existing=True)
    scheduler.add_job(run_all_blue_scans, "interval", hours=4, args=[settings], id="blue_scan", replace_existing=True)
    scheduler.add_job(run_scout_floor_check_placeholder, "interval", hours=1, id="scout_floor_check", replace_existing=True)
    return scheduler
