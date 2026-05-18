from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.clients.kraken import KrakenClient, extract_price_for_symbol, extract_spot_price
from mirror.config import Settings
from mirror.models import Event, Forecast, Trade


async def manage_tournament_exits(session: AsyncSession, settings: Settings) -> int:
    if settings.mirror_mode != "tournament" or not settings.trading_enabled:
        return 0

    trades = (
        await session.execute(
            select(Trade)
            .where(Trade.status == "open", Trade.mode == settings.kraken_execution_mode)
            .order_by(Trade.opened_at.asc())
            .limit(100)
        )
    ).scalars().all()
    if not trades:
        return 0

    kraken = KrakenClient(settings)
    if settings.kraken_execution_mode == "spot_paper":
        symbols = sorted({trade.ticker for trade in trades})
        ticker_payload = {symbol: await kraken.spot_ticker(symbol) for symbol in symbols}
    else:
        ticker_payload = await kraken.futures_tickers()
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
        reason = exit_reason(forecast, trade, pnl_pct)
        if reason is None:
            continue

        close_side = "sell" if trade.side == "buy" else "buy"
        idempotency_key = f"{trade.id}:exit:{reason}"
        response = await kraken.place_order(
            symbol=trade.ticker,
            side=close_side,
            size_usd=trade.size_usd,
            leverage=trade.leverage,
            idempotency_key=idempotency_key,
            reduce_only=True,
        )
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
    return closed_count


def exit_reason(forecast: Forecast, trade: Trade, pnl_pct: float) -> str | None:
    if pnl_pct >= forecast.take_profit_pct:
        return "take_profit"
    if pnl_pct <= -forecast.stop_loss_pct:
        return "stop_loss"
    if forecast.resolves_at <= datetime.now(UTC):
        return "time_stop"
    return None


def leveraged_pnl_pct(side: str, entry_price: float, exit_price: float, leverage: int) -> float:
    direction = 1.0 if side == "buy" else -1.0
    return ((exit_price - entry_price) / entry_price) * direction * leverage * 100.0


def estimated_pnl_usd(side: str, entry_price: float, exit_price: float, size_usd: float, leverage: int) -> float:
    return (leveraged_pnl_pct(side, entry_price, exit_price, leverage) / 100.0) * size_usd
