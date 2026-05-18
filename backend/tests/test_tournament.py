from mirror.agents.strategy_schema import RedForecast, initial_strategy_yaml, parse_strategy_yaml
from mirror.backtest.replay import ReplayResult
from mirror.tournament.gate import evaluate_tournament_gate
from mirror.tournament.ranking import SymbolOpportunity, rank_opportunities
from mirror.tournament.risk import validate_tournament_trade


def test_tournament_gate_passes_pnl_improvement_with_guardrails():
    pre = ReplayResult(brier=0.20, trade_rate=0.5, sample_size=20, trade_count=10, realized_pnl_usd=100, max_drawdown_usd=20)
    post = ReplayResult(brier=0.21, trade_rate=0.5, sample_size=20, trade_count=10, realized_pnl_usd=120, max_drawdown_usd=22)
    result = evaluate_tournament_gate(pre, post)
    assert result.passed
    assert result.pnl_improvement_pct == 20


def test_tournament_gate_rejects_drawdown_blowout():
    pre = ReplayResult(brier=0.20, trade_rate=0.5, sample_size=20, trade_count=10, realized_pnl_usd=100, max_drawdown_usd=20)
    post = ReplayResult(brier=0.20, trade_rate=0.5, sample_size=20, trade_count=10, realized_pnl_usd=120, max_drawdown_usd=40)
    result = evaluate_tournament_gate(pre, post)
    assert not result.passed
    assert "drawdown" in result.rejection_reason


def test_tournament_risk_vetoes_low_confidence_trade():
    strategy = parse_strategy_yaml(initial_strategy_yaml("red-a"))
    forecast = RedForecast(
        predicted_direction="long",
        predicted_magnitude_bps=50,
        confidence=0.6,
        time_horizon_minutes=60,
        regime_tags=[],
        will_trade=True,
        position_size_usd=75,
        leverage=1,
        stop_loss_pct=1,
        take_profit_pct=2,
        reasoning="test",
    )
    result = validate_tournament_trade(strategy, forecast, min_confidence=0.68, max_position_risk_pct=3)
    assert not result.allowed
    assert "confidence" in result.reason


def test_tournament_risk_allows_low_confidence_scout_sized_trade():
    strategy = parse_strategy_yaml(initial_strategy_yaml("red-a"))
    forecast = RedForecast(
        predicted_direction="long",
        predicted_magnitude_bps=50,
        confidence=0.6,
        time_horizon_minutes=60,
        regime_tags=[],
        will_trade=True,
        position_size_usd=50,
        leverage=1,
        stop_loss_pct=1,
        take_profit_pct=2,
        reasoning="test",
    )
    result = validate_tournament_trade(strategy, forecast, min_confidence=0.68, max_position_risk_pct=3)
    assert result.allowed


def test_tournament_risk_uses_absolute_expected_move_for_shorts():
    strategy = parse_strategy_yaml(initial_strategy_yaml("red-a"))
    forecast = RedForecast(
        predicted_direction="short",
        predicted_magnitude_bps=-50,
        confidence=0.7,
        time_horizon_minutes=60,
        regime_tags=[],
        will_trade=True,
        position_size_usd=50,
        leverage=1,
        stop_loss_pct=1,
        take_profit_pct=2,
        reasoning="test",
    )
    result = validate_tournament_trade(strategy, forecast, min_confidence=0.68, max_position_risk_pct=3)
    assert result.allowed


def test_rank_opportunities_returns_highest_score_first():
    ranked = rank_opportunities(
        [
            SymbolOpportunity("PF_LOW", expected_move_bps=20, confidence=0.7, liquidity_score=1, risk_score=1),
            SymbolOpportunity("PF_HIGH", expected_move_bps=40, confidence=0.8, liquidity_score=1, risk_score=1),
        ],
        limit=1,
    )
    assert [item.symbol for item in ranked] == ["PF_HIGH"]
