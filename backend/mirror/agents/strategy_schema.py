import hashlib
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from mirror.errors import PatchValidationFailed


class StrategyMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lineage: str
    prior: str
    version: int = Field(ge=1)


class LockedStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_trades_per_day: int = Field(ge=0)
    scout_mode_enabled: bool
    scout_size_usd: float = Field(gt=0)
    max_position_hold_hours: int = Field(gt=0)
    forecast_cadence_minutes: int = Field(gt=0)
    default_horizon_minutes: int = Field(gt=0)
    locked_tickers: list[str]


class MutableStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry_confidence_threshold: float = Field(ge=0.50, le=0.90)
    stop_distance_atr: float = Field(ge=0.5, le=5.0)
    take_profit_atr: float = Field(ge=0.5, le=8.0)
    volume_filter_zscore: float = Field(ge=-2.0, le=5.0)
    regime_confidence_min: float = Field(ge=0.20, le=0.80)
    position_size_multiplier: float = Field(ge=0.1, le=2.0)
    max_leverage: int = Field(ge=1, le=5)
    momentum_lookback_minutes: int = Field(ge=15, le=1440)
    mean_reversion_zscore_entry: float = Field(ge=0.5, le=5.0)
    news_signal_required: bool
    tournament_min_expected_move_bps: float = Field(default=20.0, ge=0, le=500)
    tournament_max_spread_bps: float = Field(default=35.0, ge=0, le=500)
    tournament_profit_lock_bps: float = Field(default=60.0, ge=0, le=1000)
    tournament_trailing_stop_bps: float = Field(default=35.0, ge=0, le=1000)
    tournament_cooldown_minutes_after_loss: int = Field(default=20, ge=0, le=1440)


class Strategy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meta: StrategyMeta
    locked: LockedStrategy
    mutable: MutableStrategy

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.model_dump(), sort_keys=False)

    def strategy_hash(self) -> str:
        return strategy_hash(self.to_yaml())


class PatchProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mutable_changes: dict[str, Any]
    rationale: str
    expected_brier_improvement: float

    @model_validator(mode="after")
    def validate_mutable_changes(self) -> "PatchProposal":
        known = set(MutableStrategy.model_fields)
        unknown = set(self.mutable_changes) - known
        if unknown:
            raise ValueError(f"unknown mutable fields: {sorted(unknown)}")
        return self


class RedForecast(BaseModel):
    model_config = ConfigDict(extra="forbid")
    predicted_direction: Literal["long", "short", "flat"]
    predicted_magnitude_bps: float
    confidence: float = Field(ge=0, le=1)
    time_horizon_minutes: int = Field(gt=0)
    regime_tags: list[str]
    will_trade: bool
    position_size_usd: float = Field(ge=0)
    leverage: int = Field(ge=1)
    stop_loss_pct: float = Field(ge=0)
    take_profit_pct: float = Field(ge=0)
    reasoning: str


def parse_strategy_yaml(strategy_yaml: str) -> Strategy:
    data = yaml.safe_load(strategy_yaml)
    return Strategy.model_validate(data)


def strategy_hash(strategy_yaml: str) -> str:
    normalized = parse_strategy_yaml(strategy_yaml).to_yaml()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def apply_patch_to_strategy(strategy_yaml: str, patch_json: dict[str, Any]) -> Strategy:
    if "meta" in patch_json or "locked" in patch_json:
        raise PatchValidationFailed("patch attempted to modify locked fields")
    try:
        proposal = PatchProposal.model_validate(patch_json)
    except ValidationError as exc:
        raise PatchValidationFailed(str(exc)) from exc

    strategy = parse_strategy_yaml(strategy_yaml)
    current = strategy.mutable.model_dump()
    changed = False
    for key, value in proposal.mutable_changes.items():
        if current[key] != value:
            changed = True
        current[key] = value
    if not changed:
        raise PatchValidationFailed("patch creates no meaningful change")

    try:
        mutable = MutableStrategy.model_validate(current)
    except ValidationError as exc:
        raise PatchValidationFailed(str(exc)) from exc
    return Strategy(meta=strategy.meta, locked=strategy.locked, mutable=mutable)


def initial_strategy_yaml(lineage: str, tickers: list[str] | None = None) -> str:
    tickers = tickers or []
    presets: dict[str, dict[str, Any]] = {
        "red-a": {"prior": "aggressive_momentum", "horizon": 60, "mutable": {"entry_confidence_threshold": 0.58, "stop_distance_atr": 1.3, "take_profit_atr": 2.8, "volume_filter_zscore": 0.7, "regime_confidence_min": 0.35, "position_size_multiplier": 0.7, "max_leverage": 3, "momentum_lookback_minutes": 45, "mean_reversion_zscore_entry": 2.4, "news_signal_required": False}},
        "red-b": {"prior": "mean_reversion", "horizon": 60, "mutable": {"entry_confidence_threshold": 0.64, "stop_distance_atr": 1.8, "take_profit_atr": 2.2, "volume_filter_zscore": 1.2, "regime_confidence_min": 0.45, "position_size_multiplier": 0.45, "max_leverage": 2, "momentum_lookback_minutes": 90, "mean_reversion_zscore_entry": 1.8, "news_signal_required": False}},
        "red-c": {"prior": "trend_following", "horizon": 120, "mutable": {"entry_confidence_threshold": 0.62, "stop_distance_atr": 2.0, "take_profit_atr": 3.5, "volume_filter_zscore": 0.9, "regime_confidence_min": 0.42, "position_size_multiplier": 0.55, "max_leverage": 3, "momentum_lookback_minutes": 240, "mean_reversion_zscore_entry": 2.8, "news_signal_required": False}},
        "red-d": {"prior": "news_driven", "horizon": 60, "mutable": {"entry_confidence_threshold": 0.66, "stop_distance_atr": 1.6, "take_profit_atr": 3.0, "volume_filter_zscore": 1.4, "regime_confidence_min": 0.50, "position_size_multiplier": 0.40, "max_leverage": 2, "momentum_lookback_minutes": 120, "mean_reversion_zscore_entry": 2.2, "news_signal_required": True}},
    }
    preset = presets[lineage]
    strategy = Strategy(
        meta=StrategyMeta(lineage=lineage, prior=preset["prior"], version=1),
        locked=LockedStrategy(
            min_trades_per_day=8,
            scout_mode_enabled=True,
            scout_size_usd=50,
            max_position_hold_hours=12,
            forecast_cadence_minutes=30,
            default_horizon_minutes=preset["horizon"],
            locked_tickers=tickers,
        ),
        mutable=MutableStrategy.model_validate(preset["mutable"]),
    )
    return strategy.to_yaml()
