from dataclasses import dataclass


@dataclass(frozen=True)
class ReplayResult:
    brier: float
    trade_rate: float

