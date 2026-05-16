"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("lineage", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("prior", sa.String(128), nullable=False),
        sa.Column("parent_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("crossover_parent_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("strategy_yaml", sa.Text(), nullable=False),
        sa.Column("strategy_hash", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("brier_at_promotion", sa.Float()),
        sa.Column("trade_rate_at_promotion", sa.Float()),
        sa.Column("on_chain_token_id", sa.String(128)),
        sa.Column("on_chain_tx_hash", sa.String(128)),
        sa.Column("agent_uri", sa.Text()),
        sa.Column("ipfs_cid", sa.String(128)),
        sa.UniqueConstraint("lineage", "version", name="uq_agents_lineage_version"),
    )
    op.create_index("ix_agents_parent_agent_id", "agents", ["parent_agent_id"])
    op.create_index("ix_agents_crossover_parent_agent_id", "agents", ["crossover_parent_agent_id"])

    op.create_table(
        "forecasts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("ticker", sa.String(64), nullable=False),
        sa.Column("horizon_minutes", sa.Integer(), nullable=False),
        sa.Column("predicted_direction", sa.String(16), nullable=False),
        sa.Column("predicted_magnitude_bps", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("probability_up", sa.Float(), nullable=False),
        sa.Column("regime_tags", postgresql.JSONB(), nullable=False),
        sa.Column("will_trade", sa.Boolean(), nullable=False),
        sa.Column("position_size_usd", sa.Float(), nullable=False),
        sa.Column("leverage", sa.Integer(), nullable=False),
        sa.Column("stop_loss_pct", sa.Float(), nullable=False),
        sa.Column("take_profit_pct", sa.Float(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("raw_model_response", postgresql.JSONB(), nullable=False),
        sa.Column("emitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolves_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("realized_direction", sa.String(16)),
        sa.Column("realized_magnitude_bps", sa.Float()),
        sa.Column("realized_probability_outcome", sa.Float()),
        sa.Column("brier_score", sa.Float()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_forecasts_confidence"),
    )
    op.create_index("ix_forecasts_agent_emitted", "forecasts", ["agent_id", "emitted_at"])
    op.create_index("ix_forecasts_ticker_emitted", "forecasts", ["ticker", "emitted_at"])
    op.create_index("ix_forecasts_status", "forecasts", ["status"])

    op.create_table(
        "trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("forecast_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("forecasts.id"), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("ticker", sa.String(64), nullable=False),
        sa.Column("side", sa.String(16), nullable=False),
        sa.Column("size_usd", sa.Float(), nullable=False),
        sa.Column("leverage", sa.Integer(), nullable=False),
        sa.Column("order_type", sa.String(32), nullable=False),
        sa.Column("kraken_order_id", sa.String(128)),
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("entry_price", sa.Float()),
        sa.Column("exit_price", sa.Float()),
        sa.Column("realized_pnl_usd", sa.Float()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("raw_kraken_response", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_trades_idempotency_key"),
    )
    op.create_index("ix_trades_agent_opened", "trades", ["agent_id", "opened_at"])
    op.create_index("ix_trades_status", "trades", ["status"])

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_events_created_at", "events", ["created_at"])
    op.create_index("ix_events_kind", "events", ["kind"])
    op.create_index("ix_events_agent_id", "events", ["agent_id"])

    op.create_table(
        "blue_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("regime_context", postgresql.JSONB(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("predicted_confidence_avg", sa.Float(), nullable=False),
        sa.Column("realized_accuracy", sa.Float(), nullable=False),
        sa.Column("brier_gap", sa.Float(), nullable=False),
        sa.Column("suggested_failure_mode", sa.Text(), nullable=False),
        sa.Column("suggested_fix_direction", sa.Text(), nullable=False),
        sa.Column("raw_blue_response", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
    )

    op.create_table(
        "market_ticks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ticker", sa.String(64), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("bid", sa.Float()),
        sa.Column("ask", sa.Float()),
        sa.Column("volume", sa.Float()),
        sa.Column("funding_rate", sa.Float()),
        sa.Column("funding_rate_prediction", sa.Float()),
        sa.Column("raw_ticker", postgresql.JSONB(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ticker", "observed_at", name="uq_market_ticks_ticker_observed"),
    )
    op.create_index("ix_market_ticks_ticker", "market_ticks", ["ticker"])
    op.create_index("ix_market_ticks_observed_at", "market_ticks", ["observed_at"])

    op.create_table(
        "patches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("target_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("patch_type", sa.String(32), nullable=False),
        sa.Column("blue_finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("blue_findings.id")),
        sa.Column("blue_finding_json", postgresql.JSONB()),
        sa.Column("base_strategy_yaml", sa.Text(), nullable=False),
        sa.Column("proposed_yaml", sa.Text(), nullable=False),
        sa.Column("proposed_patch_json", postgresql.JSONB(), nullable=False),
        sa.Column("patch_hash", sa.String(128), nullable=False),
        sa.Column("holdout_pre_brier", sa.Float()),
        sa.Column("holdout_post_brier", sa.Float()),
        sa.Column("holdout_pre_trade_rate", sa.Float()),
        sa.Column("holdout_post_trade_rate", sa.Float()),
        sa.Column("brier_improvement_pct", sa.Float()),
        sa.Column("trade_rate_preservation_pct", sa.Float()),
        sa.Column("gate_passed", sa.Boolean()),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("applied_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("on_chain_tx_hash", sa.String(128)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("target_agent_id", "patch_hash", name="uq_patches_target_hash"),
    )
    op.create_index("ix_patches_gate_passed", "patches", ["gate_passed"])
    op.create_index("ix_patches_status", "patches", ["status"])

    op.create_table(
        "onchain_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("patch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patches.id")),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("tx_hash", sa.String(128)),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("onchain_jobs")
    op.drop_table("patches")
    op.drop_table("market_ticks")
    op.drop_table("blue_findings")
    op.drop_table("events")
    op.drop_table("trades")
    op.drop_table("forecasts")
    op.drop_table("agents")
