import asyncio
import json
import sys
from datetime import UTC, datetime
from typing import Annotated

import typer
from sqlalchemy import func, select

from mirror.agents.red import run_red_once
from mirror.agents.blue import run_blue_scan
from mirror.agents.patcher import propose_patch_for_finding
from mirror.agents.strategy_schema import initial_strategy_yaml, parse_strategy_yaml
from mirror.chain.identity import queue_or_register_agent, verify_identity_abi
from mirror.chain.reputation import verify_reputation_abi
from mirror.clients.chain import ChainClient
from mirror.clients.featherless import FeatherlessClient
from mirror.clients.gemini import GeminiClient
from mirror.clients.kraken import KrakenClient
from mirror.config import get_settings
from mirror.db import SessionLocal, create_all
from mirror.logging import configure_logging
from mirror.models import Agent, BlueFinding, Event, Forecast, OnchainJob, Patch, Trade
from mirror.orchestrator.resolution import build_resolution_graph
from mirror.orchestrator.schedule import build_scheduler

app = typer.Typer(no_args_is_help=True)
init_app = typer.Typer(no_args_is_help=True)
run_app = typer.Typer(no_args_is_help=True)
app.add_typer(init_app, name="init")
app.add_typer(run_app, name="run")


def run_async(coro):
    return asyncio.run(coro)


@app.callback()
def main() -> None:
    configure_logging()


@app.command()
def verify() -> None:
    result = run_async(_verify())
    typer.echo(json.dumps(result, indent=2, default=str))
    if not result["ok"]:
        raise typer.Exit(1)


async def _verify() -> dict:
    settings = get_settings()
    checks: dict[str, dict] = {}

    checks["python"] = {"ok": sys.version_info >= (3, 11), "detail": sys.version.split()[0]}

    try:
        async with SessionLocal() as session:
            await session.execute(select(1))
        checks["postgres"] = {"ok": True}
    except Exception as exc:
        checks["postgres"] = {"ok": False, "detail": str(exc)}

    kraken = KrakenClient(settings)
    try:
        checks["kraken_installed"] = {"ok": True, "detail": await kraken.help_text(["--help"])}
    except Exception as exc:
        checks["kraken_installed"] = {"ok": False, "detail": str(exc)}

    try:
        checks["kraken_paper_mode"] = {"ok": True, "detail": await kraken.verify_paper_mode()}
    except Exception as exc:
        checks["kraken_paper_mode"] = {"ok": False, "detail": str(exc)}

    try:
        checks["kraken_xstock_symbols"] = {"ok": True, "detail": await kraken.discover_xstock_perp_symbols()}
    except Exception as exc:
        checks["kraken_xstock_symbols"] = {"ok": False, "detail": str(exc)}

    try:
        checks["featherless"] = {"ok": True, "detail": await FeatherlessClient(settings).verify()}
    except Exception as exc:
        checks["featherless"] = {"ok": False, "detail": str(exc)}

    try:
        checks["gemini"] = {"ok": True, "detail": await GeminiClient(settings).verify()}
    except Exception as exc:
        checks["gemini"] = {"ok": False, "detail": str(exc)}

    try:
        chain = await ChainClient(settings).verify()
        checks["base_sepolia"] = {"ok": chain["connected"] and chain["chain_id"] == settings.base_sepolia_chain_id, "detail": chain}
    except Exception as exc:
        checks["base_sepolia"] = {"ok": False, "detail": str(exc)}

    checks["erc8004_addresses"] = {
        "ok": (
            settings.erc8004_identity_registry == "0x8004A818BFB912233c491871b3d84c89A494BD9e"
            and settings.erc8004_reputation_registry == "0x8004B663056A597Dffe9eCcC1965A193B7388713"
        ),
        "detail": {
            "identity": settings.erc8004_identity_registry,
            "reputation": settings.erc8004_reputation_registry,
            "verified_source": "docs/ERC8004_ADDRESSES.md",
        },
    }
    identity_abi = verify_identity_abi()
    reputation_abi = verify_reputation_abi()
    checks["erc8004_abis"] = {"ok": identity_abi["ok"] and reputation_abi["ok"], "detail": {"identity": identity_abi, "reputation": reputation_abi}}
    checks["frontend_env"] = {"ok": bool(settings.public_app_url and settings.backend_public_url)}

    return {"ok": all(check["ok"] for check in checks.values()), "checks": checks}


@init_app.callback(invoke_without_command=True)
def init_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        run_async(_init_all())


async def _init_all() -> None:
    await create_all()
    await _init_agents()
    typer.echo("Initialized database and starting agents.")


@init_app.command("agents")
def init_agents() -> None:
    run_async(_init_agents())


async def _init_agents(tickers: list[str] | None = None) -> None:
    async with SessionLocal() as session:
        for lineage in ("red-a", "red-b", "red-c", "red-d"):
            existing = (await session.execute(select(Agent).where(Agent.lineage == lineage, Agent.version == 1))).scalar_one_or_none()
            if existing:
                continue
            strategy_yaml = initial_strategy_yaml(lineage, tickers or [])
            strategy = parse_strategy_yaml(strategy_yaml)
            session.add(
                Agent(
                    lineage=lineage,
                    name=f"MIRROR {lineage.upper()}",
                    version=1,
                    prior=strategy.meta.prior,
                    strategy_yaml=strategy_yaml,
                    strategy_hash=strategy.strategy_hash(),
                    status="active",
                )
            )
        await session.commit()


@init_app.command("kraken")
def init_kraken() -> None:
    run_async(_discover_symbols(assign=True))


@init_app.command("wallet")
def init_wallet() -> None:
    typer.echo("Wallet initialization requires OWNER_PRIVATE_KEY and EVALUATOR_PRIVATE_KEY in .env; no keys are generated or logged.")


@app.command("discover-symbols")
def discover_symbols() -> None:
    symbols = run_async(_discover_symbols(assign=True))
    typer.echo(json.dumps({"symbols": symbols}, indent=2))


async def _discover_symbols(assign: bool) -> list[str]:
    settings = get_settings()
    symbols = await KrakenClient(settings).discover_xstock_perp_symbols()
    if assign:
        async with SessionLocal() as session:
            agents = (await session.execute(select(Agent))).scalars().all()
            for agent in agents:
                strategy = parse_strategy_yaml(agent.strategy_yaml)
                updated = strategy.model_copy(update={"locked": strategy.locked.model_copy(update={"locked_tickers": symbols})})
                agent.strategy_yaml = updated.to_yaml()
                agent.strategy_hash = updated.strategy_hash()
                session.add(Event(agent_id=agent.id, kind="symbols_discovered", severity="info", payload_json={"symbols": symbols}))
            await session.commit()
    return symbols


@run_app.callback(invoke_without_command=True)
def run_root(
    once: Annotated[bool, typer.Option("--once")] = False,
    agent: Annotated[str, typer.Option("--agent")] = "red-a",
    scheduler: Annotated[bool, typer.Option("--scheduler")] = False,
) -> None:
    if once:
        forecast = run_async(_run_once(agent))
        typer.echo(json.dumps({"forecast_id": str(forecast.id), "agent_id": str(forecast.agent_id)}, indent=2))
    elif scheduler:
        run_async(_run_scheduler())
    else:
        raise typer.Exit("Use `mirror run --once --agent red-a` or `mirror run --scheduler`.")


async def _run_once(agent: str):
    async with SessionLocal() as session:
        return await run_red_once(session, get_settings(), agent)


async def _run_scheduler() -> None:
    scheduler = build_scheduler(get_settings())
    scheduler.start()
    typer.echo("MIRROR scheduler started. Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        scheduler.shutdown(wait=False)


@run_app.command("resolve")
def run_resolve_once() -> None:
    result = run_async(build_resolution_graph().ainvoke({"settings": get_settings(), "session_factory": SessionLocal}))
    typer.echo(json.dumps({"resolved_count": result.get("resolved_count", 0)}, indent=2))


@run_app.command("blue-scan")
def blue_scan(agent: Annotated[str, typer.Option("--agent")] = "red-a") -> None:
    findings = run_async(_blue_scan(agent))
    typer.echo(json.dumps({"findings": [str(f.id) for f in findings]}, indent=2))


async def _blue_scan(agent: str):
    async with SessionLocal() as session:
        return await run_blue_scan(session, get_settings(), agent)


@app.command()
def status() -> None:
    typer.echo(json.dumps(run_async(_status()), indent=2, default=str))


async def _status() -> dict:
    try:
        async with SessionLocal() as session:
            forecasts = await session.scalar(select(func.count()).select_from(Forecast))
            trades = await session.scalar(select(func.count()).select_from(Trade))
            pending_findings = await session.scalar(select(func.count()).select_from(BlueFinding).where(BlueFinding.status == "pending"))
            pending_patches = await session.scalar(select(func.count()).select_from(Patch).where(Patch.status.in_(["pending", "proposed"])))
            onchain_queued = await session.scalar(select(func.count()).select_from(OnchainJob).where(OnchainJob.status.in_(["queued", "pending", "failed"])))
            unresolved = await session.scalar(select(func.count()).select_from(Forecast).where(Forecast.status == "open"))
            agents = (await session.execute(select(Agent).order_by(Agent.lineage, Agent.version))).scalars().all()
            latest_events = (await session.execute(select(Event).order_by(Event.created_at.desc()).limit(5))).scalars().all()
    except Exception as exc:
        return {
            "scheduler": "unknown",
            "generated_at": datetime.now(UTC).isoformat(),
            "database": {"ok": False, "detail": str(exc)},
            "api_health": "unavailable until Postgres is reachable",
            "sse_health": "unavailable until Postgres is reachable",
        }
    return {
        "scheduler": "stopped",
        "generated_at": datetime.now(UTC).isoformat(),
        "database": {"ok": True},
        "agents": [{"id": str(a.id), "lineage": a.lineage, "version": a.version, "status": a.status} for a in agents],
        "total_forecasts": forecasts,
        "unresolved_forecasts": unresolved,
        "total_trades": trades,
        "pending_blue_findings": pending_findings,
        "pending_patches": pending_patches,
        "onchain_queue": onchain_queued,
        "api_health": "available if FastAPI process is running",
        "sse_health": "events table backed",
        "latest_events": [
            {"id": str(e.id), "kind": e.kind, "severity": e.severity, "created_at": e.created_at.isoformat() if e.created_at else None}
            for e in latest_events
        ],
    }


@app.command()
def reset(confirm: Annotated[bool, typer.Option("--confirm")] = False) -> None:
    if not confirm:
        raise typer.Exit("Refusing reset without --confirm")
    raise typer.Exit("Reset is intentionally not implemented yet to avoid destructive mistakes.")


@app.command("register-agents")
def register_agents() -> None:
    jobs = run_async(_register_agents())
    typer.echo(json.dumps({"jobs": jobs}, indent=2))


async def _register_agents() -> list[dict]:
    settings = get_settings()
    async with SessionLocal() as session:
        agents = (await session.execute(select(Agent).where(Agent.status == "active").order_by(Agent.lineage, Agent.version))).scalars().all()
        output = []
        for agent in agents:
            job = await queue_or_register_agent(session, settings, agent)
            output.append({"agent_id": str(agent.id), "lineage": agent.lineage, "job_id": str(job.id) if job else None, "status": job.status if job else "already_registered"})
        await session.commit()
        return output


@app.command()
def backtest(agent: Annotated[str, typer.Option("--agent")] = "red-a") -> None:
    raise typer.Exit(f"Backtest for {agent} is implemented in Day 4 gate work.")


@app.command()
def patch(agent: Annotated[str, typer.Option("--agent")] = "red-a", finding: Annotated[str | None, typer.Option("--finding")] = None) -> None:
    if not finding:
        raise typer.Exit("--finding is required")
    patch_row = run_async(_patch(finding))
    typer.echo(
        json.dumps(
            {
                "patch_id": str(patch_row.id),
                "target_agent_id": str(patch_row.target_agent_id),
                "status": patch_row.status,
                "gate_passed": patch_row.gate_passed,
                "rejection_reason": patch_row.rejection_reason,
                "applied_agent_id": str(patch_row.applied_agent_id) if patch_row.applied_agent_id else None,
            },
            indent=2,
        )
    )


async def _patch(finding_id: str):
    async with SessionLocal() as session:
        return await propose_patch_for_finding(session, get_settings(), finding_id)


if __name__ == "__main__":
    app()
