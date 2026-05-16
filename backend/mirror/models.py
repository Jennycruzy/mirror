import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mirror.db import Base


class TimestampMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Agent(TimestampMixin, Base):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("lineage", "version", name="uq_agents_lineage_version"),
        Index("ix_agents_parent_agent_id", "parent_agent_id"),
        Index("ix_agents_crossover_parent_agent_id", "crossover_parent_agent_id"),
    )

    lineage: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    prior: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"))
    crossover_parent_agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"))
    strategy_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    brier_at_promotion: Mapped[float | None] = mapped_column(Float)
    trade_rate_at_promotion: Mapped[float | None] = mapped_column(Float)
    on_chain_token_id: Mapped[str | None] = mapped_column(String(128))
    on_chain_tx_hash: Mapped[str | None] = mapped_column(String(128))
    agent_uri: Mapped[str | None] = mapped_column(Text)
    ipfs_cid: Mapped[str | None] = mapped_column(String(128))


class Forecast(TimestampMixin, Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_forecasts_confidence"),
        Index("ix_forecasts_agent_emitted", "agent_id", "emitted_at"),
        Index("ix_forecasts_ticker_emitted", "ticker", "emitted_at"),
        Index("ix_forecasts_status", "status"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    horizon_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_direction: Mapped[str] = mapped_column(String(16), nullable=False)
    predicted_magnitude_bps: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    probability_up: Mapped[float] = mapped_column(Float, nullable=False)
    regime_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    will_trade: Mapped[bool] = mapped_column(Boolean, nullable=False)
    position_size_usd: Mapped[float] = mapped_column(Float, nullable=False)
    leverage: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_loss_pct: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_pct: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    raw_model_response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    emitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolves_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    realized_direction: Mapped[str | None] = mapped_column(String(16))
    realized_magnitude_bps: Mapped[float | None] = mapped_column(Float)
    realized_probability_outcome: Mapped[float | None] = mapped_column(Float)
    brier_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    agent: Mapped[Agent] = relationship()


class Trade(TimestampMixin, Base):
    __tablename__ = "trades"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_trades_idempotency_key"),
        Index("ix_trades_agent_opened", "agent_id", "opened_at"),
        Index("ix_trades_status", "status"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    forecast_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("forecasts.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    size_usd: Mapped[float] = mapped_column(Float, nullable=False)
    leverage: Mapped[int] = mapped_column(Integer, nullable=False)
    order_type: Mapped[str] = mapped_column(String(32), nullable=False)
    kraken_order_id: Mapped[str | None] = mapped_column(String(128))
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entry_price: Mapped[float | None] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float)
    realized_pnl_usd: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_kraken_response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class Patch(TimestampMixin, Base):
    __tablename__ = "patches"
    __table_args__ = (
        UniqueConstraint("target_agent_id", "patch_hash", name="uq_patches_target_hash"),
        Index("ix_patches_gate_passed", "gate_passed"),
        Index("ix_patches_status", "status"),
    )

    source_agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"))
    target_agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    patch_type: Mapped[str] = mapped_column(String(32), nullable=False)
    blue_finding_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("blue_findings.id"))
    blue_finding_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    base_strategy_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_patch_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    patch_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    holdout_pre_brier: Mapped[float | None] = mapped_column(Float)
    holdout_post_brier: Mapped[float | None] = mapped_column(Float)
    holdout_pre_trade_rate: Mapped[float | None] = mapped_column(Float)
    holdout_post_trade_rate: Mapped[float | None] = mapped_column(Float)
    brier_improvement_pct: Mapped[float | None] = mapped_column(Float)
    trade_rate_preservation_pct: Mapped[float | None] = mapped_column(Float)
    gate_passed: Mapped[bool | None] = mapped_column(Boolean)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    applied_agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"))
    on_chain_tx_hash: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BlueFinding(TimestampMixin, Base):
    __tablename__ = "blue_findings"

    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    regime_context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_confidence_avg: Mapped[float] = mapped_column(Float, nullable=False)
    realized_accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    brier_gap: Mapped[float] = mapped_column(Float, nullable=False)
    suggested_failure_mode: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_fix_direction: Mapped[str] = mapped_column(Text, nullable=False)
    raw_blue_response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class MarketTick(TimestampMixin, Base):
    __tablename__ = "market_ticks"
    __table_args__ = (
        UniqueConstraint("ticker", "observed_at", name="uq_market_ticks_ticker_observed"),
        Index("ix_market_ticks_ticker", "ticker"),
        Index("ix_market_ticks_observed_at", "observed_at"),
    )

    ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    bid: Mapped[float | None] = mapped_column(Float)
    ask: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    funding_rate: Mapped[float | None] = mapped_column(Float)
    funding_rate_prediction: Mapped[float | None] = mapped_column(Float)
    raw_ticker: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_created_at", "created_at"),
        Index("ix_events_kind", "kind"),
        Index("ix_events_agent_id", "agent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"))
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OnchainJob(TimestampMixin, Base):
    __tablename__ = "onchain_jobs"

    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"))
    patch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patches.id"))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    tx_hash: Mapped[str | None] = mapped_column(String(128))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

