from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolOpportunity:
    symbol: str
    expected_move_bps: float
    confidence: float
    liquidity_score: float
    risk_score: float

    @property
    def score(self) -> float:
        denominator = self.risk_score if self.risk_score > 0 else 1.0
        return self.expected_move_bps * self.confidence * self.liquidity_score / denominator


def rank_opportunities(opportunities: list[SymbolOpportunity], limit: int = 3) -> list[SymbolOpportunity]:
    eligible = [item for item in opportunities if item.expected_move_bps > 0 and item.confidence > 0 and item.liquidity_score > 0]
    return sorted(eligible, key=lambda item: item.score, reverse=True)[:limit]

