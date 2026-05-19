from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.clients.kraken import KrakenClient, extract_price_for_symbol, extract_spot_price
from mirror.config import Settings
from mirror.errors import KrakenCliCommandFailed
from mirror.models import Event, Forecast, Trade


@dataclass(frozen=True)
class ExitSweepResult:
    closed_count: int = 0
    degraded: bool = False


async def manage_tournament_exits(session: AsyncSession, settings: Settings) -> ExitSweepResult:
    if settings.mirror_mode != "tournament" or not settings.trading_enabled:
        return ExitSweepResult()

    kraken = KrakenClient(settings)
    degraded = False
    try:
        await record_equity_snapshot(session, settings, kraken)
    except KrakenCliCommandFailed as exc:
        degraded = True
        session.add(
            Event(
                agent_id=None,
                kind="tournament_exit_snapshot_degraded",
                severity="warning",
                payload_json={"error": str(exc), "transient": True},
            )
        )
        await session.flush()

    trades = (
        await session.execute(
            select(Trade)
            .where(Trade.status == "open", Trade.mode == settings.kraken_execution_mode)
            .order_by(Trade.opened_at.asc())
            .limit(100)
        )
    ).scalars().all()
    if not trades:
        await session.commit()
        return ExitSweepResult(closed_count=0, degraded=degraded)

    recovery_mode = await account_pnl_below_recovery_threshold(session, settings)
    if settings.kraken_execution_mode == "spot_paper":
        symbols = sorted({trade.ticker for trade in trades})
        try:
            ticker_payload = {symbol: await kraken.spot_ticker(symbol) for symbol in symbols}
        except KrakenCliCommandFailed as exc:
            degraded = True
            session.add(
                Event(
                    agent_id=None,
                    kind="tournament_exit_sweep_degraded",
                    severity="warning",
                    payload_json={"stage": "spot_tickers", "error": str(exc), "transient": True},
                )
            )
            await session.commit()
            return ExitSweepResult(closed_count=0, degraded=degraded)
    else:
        try:
            ticker_payload = await kraken.futures_tickers()
        except KrakenCliCommandFailed as exc:
            degraded = True
            session.add(
                Event(
                    agent_id=None,
                    kind="tournament_exit_sweep_degraded",
                    severity="warning",
                    payload_json={"stage": "futures_tickers", "error": str(exc), "transient": True},
                )
            )
            await session.commit()
            return ExitSweepResult(closed_count=0, degraded=degraded)
    closed_count = 0
    for trade in trades:
        forecast = await session.get(Forecast, trade.forecast_id)
        if forecast is None:
            continue
        if settings.kraken_execution_mode == "spot_paper":
            price = extract_spot_price(ticker_payload.get(trade.ticker, {}), trade.ticker)
        else:
            price = extract_price_for_symbol(ticker_payload, trade.ticker)
        if price is None or price <= 0:
            continue
        entry = trade.entry_price or price
        pnl_pct = leveraged_pnl_pct(trade.side, entry, price, trade.leverage)
        reason = exit_reason(forecast, trade, pnl_pct, settings=settings, recovery_mode=recovery_mode)
        if reason is None:
            update_exit_state(trade, pnl_pct)
            continue

        close_side = "sell" if trade.side == "buy" else "buy"
        idempotency_key = f"{trade.id}:exit:{reason}"
        try:
            response = await kraken.place_order(
                symbol=trade.ticker,
                side=close_side,
                size_usd=trade.size_usd,
                leverage=trade.leverage,
                idempotency_key=idempotency_key,
                reduce_only=True,
            )
        except KrakenCliCommandFailed as exc:
            degraded = True
            session.add(
                Event(
                    agent_id=trade.agent_id,
                    kind="tournament_trade_close_degraded",
                    severity="warning",
                    payload_json={
                        "trade_id": str(trade.id),
                        "forecast_id": str(trade.forecast_id),
                        "ticker": trade.ticker,
                        "reason": reason,
                        "error": str(exc),
                        "transient": True,
                    },
                )
            )
            continue
        trade.status = "closed"
        trade.closed_at = datetime.now(UTC)
        trade.exit_price = price
        trade.realized_pnl_usd = estimated_pnl_usd(trade.side, entry, price, trade.size_usd, trade.leverage)
        trade.raw_kraken_response = {"entry": trade.raw_kraken_response, "exit": response}
        session.add(
            Event(
                agent_id=trade.agent_id,
                kind="tournament_trade_closed",
                severity="info",
                payload_json={
                    "trade_id": str(trade.id),
                    "forecast_id": str(trade.forecast_id),
                    "ticker": trade.ticker,
                    "reason": reason,
                    "entry_price": entry,
                    "exit_price": price,
                    "pnl_pct": pnl_pct,
                    "estimated_pnl_usd": trade.realized_pnl_usd,
                },
            )
        )
        closed_count += 1
    await session.commit()
    return ExitSweepResult(closed_count=closed_count, degraded=degraded)


def exit_reason(
    forecast: Forecast,
    trade: Trade,
    pnl_pct: float,
    settings: Settings | None = None,
    *,
    recovery_mode: bool = False,
) -> str | None:
    min_hold_seconds = settings.tournament_min_hold_seconds if settings else 0
    if min_hold_seconds and (datetime.now(UTC) - trade.opened_at).total_seconds() < min_hold_seconds:
        return None
    if pnl_pct >= forecast.take_profit_pct:
        update_exit_state(trade, pnl_pct)
        if recovery_mode and settings and settings.tournament_recovery_take_profit_enabled:
            return "recovery_take_profit"
        return None
    if pnl_pct <= -forecast.stop_loss_pct:
        return "stop_loss"
    exit_state = update_exit_state(trade, pnl_pct)
    profit_lock = settings.tournament_profit_lock_pct if settings else 0.0
    trailing_giveback = settings.tournament_trailing_giveback_pct if settings else 0.0
    max_seen = float(exit_state.get("max_pnl_pct_seen", pnl_pct))
    if profit_lock > 0 and trailing_giveback > 0 and max_seen >= profit_lock and pnl_pct > 0 and pnl_pct <= max_seen - trailing_giveback:
        return "trailing_profit_lock"
    now = datetime.now(UTC)
    if forecast.resolves_at <= now:
        if pnl_pct > 0 and settings and settings.tournament_winner_extension_minutes:
            if now <= forecast.resolves_at + timedelta(minutes=settings.tournament_winner_extension_minutes):
                return None
        return "time_stop"
    return None


def update_exit_state(trade: Trade, pnl_pct: float) -> dict:
    raw = dict(trade.raw_kraken_response or {})
    state = dict(raw.get("exit_state") or {})
    previous = state.get("max_pnl_pct_seen")
    if previous is None or pnl_pct > float(previous):
        state["max_pnl_pct_seen"] = pnl_pct
        state["max_pnl_seen_at"] = datetime.now(UTC).isoformat()
    state["last_pnl_pct"] = pnl_pct
    raw["exit_state"] = state
    trade.raw_kraken_response = raw
    return state


def leveraged_pnl_pct(side: str, entry_price: float, exit_price: float, leverage: int) -> float:
    direction = 1.0 if side == "buy" else -1.0
    return ((exit_price - entry_price) / entry_price) * direction * leverage * 100.0


def estimated_pnl_usd(side: str, entry_price: float, exit_price: float, size_usd: float, leverage: int) -> float:
    return (leveraged_pnl_pct(side, entry_price, exit_price, leverage) / 100.0) * size_usd


async def record_equity_snapshot(session: AsyncSession, settings: Settings, kraken: KrakenClient) -> None:
    latest = (
        await session.execute(
            select(Event)
            .where(Event.kind == "account_equity_snapshot")
            .order_by(Event.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest and latest.created_at and (datetime.now(UTC) - latest.created_at).total_seconds() < settings.tournament_equity_snapshot_min_seconds:
        return
    status = await kraken.trading_status()
    account = status.get("status", {}) if isinstance(status, dict) else {}
    session.add(
        Event(
            agent_id=None,
            kind="account_equity_snapshot",
            severity="info",
            payload_json={
                "equity": account.get("equity"),
                "net_pnl": account.get("pnl"),
                "available_margin": account.get("available_margin"),
                "open_positions": account.get("open_positions"),
                "baseline_equity": settings.tournament_account_equity_usd,
            },
        )
    )


async def account_pnl_below_recovery_threshold(session: AsyncSession, settings: Settings) -> bool:
    if not settings.tournament_recovery_take_profit_enabled:
        return False
    latest = (
        await session.execute(
            select(Event)
            .where(Event.kind == "account_equity_snapshot")
            .order_by(Event.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest is None:
        return False
    payload = latest.payload_json or {}
    net_pnl = payload.get("net_pnl")
    if not isinstance(net_pnl, int | float):
        return False
    return float(net_pnl) < settings.tournament_recovery_pnl_threshold_usd
