from dataclasses import dataclass

from mirror.backtest.replay import ReplayResult


@dataclass(frozen=True)
class TournamentScore:
    score: float
    realized_pnl_usd: float
    max_drawdown_usd: float
    win_rate: float
    trade_count: int


def score_replay(
    replay: ReplayResult,
    *,
    drawdown_penalty: float = 1.0,
    overtrading_penalty: float = 0.0,
    target_trade_count: int | None = None,
) -> TournamentScore:
    excess_trades = 0
    if target_trade_count is not None:
        excess_trades = max(0, replay.trade_count - target_trade_count)
    score = replay.realized_pnl_usd - (replay.max_drawdown_usd * drawdown_penalty) - (excess_trades * overtrading_penalty)
    return TournamentScore(
        score=score,
        realized_pnl_usd=replay.realized_pnl_usd,
        max_drawdown_usd=replay.max_drawdown_usd,
        win_rate=replay.win_rate,
        trade_count=replay.trade_count,
    )

