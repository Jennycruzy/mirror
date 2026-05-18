from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class ClosedTradeLike(Protocol):
    ticker: str
    side: str
    realized_pnl_usd: float | None
    closed_at: datetime | None


@dataclass(frozen=True)
class DirectionStats:
    ticker: str
    side: str
    sample_size: int
    realized_pnl_usd: float
    win_rate: float

    @property
    def key(self) -> tuple[str, str]:
        return (self.ticker.upper(), self.side.lower())


def side_for_direction(direction: str) -> str:
    if direction == "long":
        return "buy"
    if direction == "short":
        return "sell"
    return direction


def compute_direction_stats(trades: list[ClosedTradeLike], lookback_per_direction: int) -> list[DirectionStats]:
    buckets: dict[tuple[str, str], list[ClosedTradeLike]] = {}
    for trade in trades:
        if trade.realized_pnl_usd is None:
            continue
        key = (trade.ticker.upper(), trade.side.lower())
        buckets.setdefault(key, []).append(trade)

    stats: list[DirectionStats] = []
    for (ticker, side), bucket in buckets.items():
        recent = sorted(bucket, key=lambda item: item.closed_at or datetime.min, reverse=True)[:lookback_per_direction]
        pnl_values = [float(item.realized_pnl_usd or 0.0) for item in recent]
        if not pnl_values:
            continue
        wins = sum(1 for value in pnl_values if value > 0)
        stats.append(
            DirectionStats(
                ticker=ticker,
                side=side,
                sample_size=len(pnl_values),
                realized_pnl_usd=round(sum(pnl_values), 8),
                win_rate=wins / len(pnl_values),
            )
        )
    return stats


def losing_direction_reason(
    stats: list[DirectionStats],
    *,
    ticker: str,
    side: str,
    min_samples: int,
    disable_loss_usd: float,
) -> str | None:
    key = (ticker.upper(), side.lower())
    direction_stats = next((item for item in stats if item.key == key), None)
    if direction_stats is None or direction_stats.sample_size < min_samples:
        return None
    if direction_stats.realized_pnl_usd <= disable_loss_usd:
        return (
            f"adaptive disabled {direction_stats.ticker} {direction_stats.side}: "
            f"recent pnl {direction_stats.realized_pnl_usd:.2f} over {direction_stats.sample_size} trades"
        )
    return None


def rank_symbols_by_recent_pnl(symbols: list[str], stats: list[DirectionStats], *, min_samples: int) -> list[str]:
    scores = {symbol.upper(): 0.0 for symbol in symbols}
    samples = {symbol.upper(): 0 for symbol in symbols}
    for item in stats:
        symbol = item.ticker.upper()
        if symbol not in scores or item.sample_size < min_samples:
            continue
        scores[symbol] += item.realized_pnl_usd
        samples[symbol] += item.sample_size

    return sorted(
        symbols,
        key=lambda symbol: (
            scores.get(symbol.upper(), 0.0),
            samples.get(symbol.upper(), 0),
            -symbols.index(symbol),
        ),
        reverse=True,
    )
