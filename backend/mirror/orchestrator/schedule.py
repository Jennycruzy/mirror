from datetime import UTC, datetime, time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select

from mirror.agents.blue import run_blue_scan
from mirror.agents.patcher import propose_patch_for_finding
from mirror.agents.red import run_red_once
from mirror.agents.strategy_schema import parse_strategy_yaml
from mirror.config import Settings
from mirror.db import SessionLocal
from mirror.errors import KrakenCliCommandFailed
from mirror.models import Agent, Event, Trade
from mirror.orchestrator.resolution import build_resolution_graph
from mirror.tournament.adaptive import compute_direction_stats, rank_symbols_by_recent_pnl
from mirror.tournament.exits import manage_tournament_exits


async def run_lineage_once(settings: Settings, lineage: str, ticker_override: str | None = None) -> None:
    async with SessionLocal() as session:
        try:
            await run_red_once(session, settings, lineage, ticker_override=ticker_override)
        except Exception as exc:
            payload = {"lineage": lineage, "error": str(exc)}
            if ticker_override:
                payload["ticker"] = ticker_override
            session.add(Event(agent_id=None, kind="red_run_failed", severity="error", payload_json=payload))
            await session.commit()


async def run_all_reds(settings: Settings) -> None:
    lineages = ("red-a", "red-b", "red-c", "red-d")
    if settings.kraken_execution_mode == "spot_paper":
        for pair in settings.trading_pairs_list():
            for lineage in lineages:
                await run_lineage_once(settings, lineage, ticker_override=pair)
        return
    if settings.kraken_execution_mode == "account":
        for symbol in await adaptive_symbol_order(settings):
            for lineage in lineages:
                await run_lineage_once(settings, lineage, ticker_override=symbol)
        return
    for lineage in lineages:
        await run_lineage_once(settings, lineage)


async def adaptive_symbol_order(settings: Settings) -> list[str]:
    symbols = settings.trading_futures_symbols_list()
    if not settings.tournament_adaptive_enabled or not symbols:
        return symbols
    async with SessionLocal() as session:
        recent_closed_trades = (
            await session.execute(
                select(Trade)
                .where(
                    Trade.status == "closed",
                    Trade.mode == settings.kraken_execution_mode,
                    Trade.realized_pnl_usd.is_not(None),
                    Trade.ticker.in_(symbols),
                )
                .order_by(Trade.closed_at.desc())
                .limit(settings.tournament_adaptive_lookback_trades * len(symbols) * 2)
            )
        ).scalars().all()
    stats = compute_direction_stats(list(recent_closed_trades), settings.tournament_adaptive_lookback_trades)
    return rank_symbols_by_recent_pnl(symbols, stats, min_samples=settings.tournament_adaptive_min_samples)


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
                findings = await run_blue_scan(session, settings, lineage)
                for finding in findings:
                    if finding.status == "pending":
                        await propose_patch_for_finding(session, settings, str(finding.id))
            except Exception as exc:
                session.add(Event(agent_id=None, kind="blue_scan_failed", severity="error", payload_json={"lineage": lineage, "error": str(exc)}))
                await session.commit()


async def run_scout_floor_check(settings: Settings) -> None:
    del settings
    today_start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    async with SessionLocal() as session:
        agents = (
            await session.execute(
                select(Agent)
                .where(Agent.status == "active")
                .order_by(Agent.lineage, Agent.version.desc())
            )
        ).scalars().all()

        seen_lineages: set[str] = set()
        for agent in agents:
            if agent.lineage in seen_lineages:
                continue
            seen_lineages.add(agent.lineage)
            strategy = parse_strategy_yaml(agent.strategy_yaml)
            trades_today = await session.scalar(
                select(func.count())
                .select_from(Trade)
                .where(Trade.agent_id == agent.id, Trade.opened_at >= today_start)
            )
            floor = strategy.locked.min_trades_per_day
            payload = {
                "lineage": agent.lineage,
                "agent_id": str(agent.id),
                "trades_today": int(trades_today or 0),
                "min_trades_per_day": floor,
            }
            if (trades_today or 0) < floor:
                payload["deficit"] = floor - int(trades_today or 0)
                session.add(Event(agent_id=agent.id, kind="scout_floor_below_target", severity="warning", payload_json=payload))
            else:
                session.add(Event(agent_id=agent.id, kind="scout_floor_met", severity="info", payload_json=payload))
        await session.commit()


async def run_tournament_exits(settings: Settings) -> None:
    try:
        async with SessionLocal() as session:
            result = await manage_tournament_exits(session, settings)
            if not result.degraded:
                await mark_exit_sweep_recovered(session)
            if result.closed_count:
                session.add(Event(agent_id=None, kind="tournament_exit_sweep", severity="info", payload_json={"closed_count": result.closed_count}))
                await session.commit()
            elif session.new:
                await session.commit()
    except KrakenCliCommandFailed as exc:
        async with SessionLocal() as session:
            session.add(
                Event(
                    agent_id=None,
                    kind="tournament_exit_sweep_degraded",
                    severity="warning",
                    payload_json={"error": str(exc), "transient": True, "source": "scheduler"},
                )
            )
            await session.commit()
    except Exception as exc:
        async with SessionLocal() as session:
            session.add(Event(agent_id=None, kind="tournament_exit_sweep_failed", severity="error", payload_json={"error": str(exc), "source": "scheduler"}))
            await session.commit()


async def mark_exit_sweep_recovered(session) -> None:
    latest = (
        await session.execute(
            select(Event)
            .where(
                Event.kind.in_(
                    [
                        "tournament_exit_sweep_failed",
                        "tournament_exit_sweep_degraded",
                        "tournament_exit_sweep_recovered",
                    ]
                )
            )
            .order_by(Event.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest is None or latest.kind == "tournament_exit_sweep_recovered":
        return
    session.add(
        Event(
            agent_id=None,
            kind="tournament_exit_sweep_recovered",
            severity="info",
            payload_json={"recovered_from": latest.kind, "previous_at": latest.created_at.isoformat() if latest.created_at else None},
        )
    )


def build_scheduler(settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(run_all_reds, "interval", minutes=30, args=[settings], id="red_forecasts", replace_existing=True)
    scheduler.add_job(run_resolution_sweep, "interval", minutes=1, args=[settings], id="resolution_sweep", replace_existing=True)
    scheduler.add_job(run_all_blue_scans, "interval", hours=4, args=[settings], id="blue_scan", replace_existing=True)
    scheduler.add_job(run_scout_floor_check, "interval", hours=1, args=[settings], id="scout_floor_check", replace_existing=True)
    scheduler.add_job(run_tournament_exits, "interval", seconds=settings.tournament_exit_check_seconds, args=[settings], id="tournament_exits", replace_existing=True)
    return scheduler
