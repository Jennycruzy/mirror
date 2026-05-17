import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.agents.strategy_schema import MutableStrategy, PatchProposal, Strategy, apply_patch_to_strategy, parse_strategy_yaml
from mirror.backtest.gate import evaluate_holdout_gate
from mirror.backtest.replay import replay_strategy
from mirror.calibration.brier import calibration_buckets
from mirror.chain.identity import queue_or_register_agent
from mirror.chain.reputation import queue_brier_feedback
from mirror.clients.gemini import GeminiClient
from mirror.config import Settings
from mirror.errors import PatchValidationFailed
from mirror.models import Agent, BlueFinding, Event, Forecast, Patch
from mirror.tournament.gate import evaluate_tournament_gate


PATCHER_PROMPT = """You are MIRROR Strategy Patcher.
Return strict JSON only. You may only modify keys under mutable_changes.
Do not include meta, locked, unknown fields, markdown, or commentary.
The patch must address the Blue finding while preserving trade rate.
"""


async def propose_patch_for_finding(session: AsyncSession, settings: Settings, finding_id: str) -> Patch:
    finding = await session.get(BlueFinding, finding_id)
    if finding is None:
        raise PatchValidationFailed(f"Blue finding not found: {finding_id}")
    agent = await session.get(Agent, finding.agent_id)
    if agent is None:
        raise PatchValidationFailed(f"Agent not found for finding: {finding_id}")

    existing = (
        await session.execute(
            select(Patch)
            .where(Patch.target_agent_id == agent.id, Patch.blue_finding_id == finding.id)
            .order_by(Patch.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    recent_forecasts = (
        await session.execute(
            select(Forecast)
            .where(Forecast.agent_id == agent.id, Forecast.status == "resolved", Forecast.brier_score.is_not(None))
            .order_by(Forecast.resolved_at.desc())
            .limit(100)
        )
    ).scalars().all()
    if len(recent_forecasts) < 1:
        return await store_rejected_patch(
            session=session,
            agent=agent,
            finding=finding,
            proposed_patch={"mutable_changes": {}, "rationale": "insufficient holdout data", "expected_brier_improvement": 0},
            rejection_reason="holdout replay requires resolved forecasts",
        )

    proposal = await request_patch(settings, agent.strategy_yaml, finding, recent_forecasts)
    try:
        patched_strategy = apply_patch_to_strategy(agent.strategy_yaml, proposal.model_dump())
    except PatchValidationFailed as exc:
        return await store_rejected_patch(
            session=session,
            agent=agent,
            finding=finding,
            proposed_patch=proposal.model_dump(),
            rejection_reason=str(exc),
        )

    pre = replay_strategy(agent.strategy_yaml, list(recent_forecasts))
    post = replay_strategy(patched_strategy.to_yaml(), list(recent_forecasts))
    gate = evaluate_holdout_gate(pre.brier, post.brier, pre.trade_rate, post.trade_rate)
    gate_passed = gate.passed
    rejection_reason = gate.rejection_reason
    tournament_gate_payload = None
    if settings.mirror_mode == "tournament":
        tournament_gate = evaluate_tournament_gate(
            pre,
            post,
            min_pnl_improvement_pct=settings.tournament_min_pnl_improvement_pct,
            max_drawdown_worsening_pct=settings.tournament_max_drawdown_worsening_pct,
            max_brier_degradation_pct=settings.tournament_max_brier_degradation_pct,
        )
        tournament_gate_payload = {
            "pnl_improvement_pct": tournament_gate.pnl_improvement_pct,
            "drawdown_change_pct": tournament_gate.drawdown_change_pct,
            "brier_change_pct": tournament_gate.brier_change_pct,
            "passed": tournament_gate.passed,
        }
        gate_passed = gate_passed and tournament_gate.passed
        if tournament_gate.rejection_reason:
            rejection_reason = "; ".join(reason for reason in [rejection_reason, tournament_gate.rejection_reason] if reason)
    patch_hash = compute_patch_hash(agent.id, proposal.model_dump(), agent.strategy_hash)
    patch = Patch(
        source_agent_id=agent.id,
        target_agent_id=agent.id,
        patch_type="blue_finding",
        blue_finding_id=finding.id,
        blue_finding_json=finding.raw_blue_response,
        base_strategy_yaml=agent.strategy_yaml,
        proposed_yaml=patched_strategy.to_yaml(),
        proposed_patch_json=proposal.model_dump(),
        patch_hash=patch_hash,
        holdout_pre_brier=pre.brier,
        holdout_post_brier=post.brier,
        holdout_pre_trade_rate=pre.trade_rate,
        holdout_post_trade_rate=post.trade_rate,
        brier_improvement_pct=gate.brier_improvement_pct,
        trade_rate_preservation_pct=gate.trade_rate_preservation_pct,
        gate_passed=gate_passed,
        rejection_reason=rejection_reason,
        status="accepted" if gate_passed else "rejected",
    )
    session.add(patch)
    await session.flush()

    if gate_passed:
        promoted = await promote_agent_from_patch(session, settings, agent, patch, patched_strategy, post.brier, post.trade_rate)
        patch.applied_agent_id = promoted.id
        patch.applied_at = datetime.now(UTC)
        finding.status = "patched"
        session.add(
            Event(
                agent_id=agent.id,
                kind="patch_accepted",
                severity="info",
                payload_json={
                    "patch_id": str(patch.id),
                    "applied_agent_id": str(promoted.id),
                    "brier_improvement_pct": gate.brier_improvement_pct,
                    "holdout_pre_pnl_usd": pre.realized_pnl_usd,
                    "holdout_post_pnl_usd": post.realized_pnl_usd,
                    "tournament_gate": tournament_gate_payload,
                },
            )
        )
        from mirror.agents.crossover import attempt_crossovers_for_accepted_patch

        await attempt_crossovers_for_accepted_patch(session, settings, patch)
    else:
        finding.status = "patch_rejected"
        session.add(
            Event(
                agent_id=agent.id,
                kind="patch_rejected",
                severity="warning",
                payload_json={
                    "patch_id": str(patch.id),
                    "reason": rejection_reason,
                    "holdout_pre_pnl_usd": pre.realized_pnl_usd,
                    "holdout_post_pnl_usd": post.realized_pnl_usd,
                    "tournament_gate": tournament_gate_payload,
                },
            )
        )
    await session.commit()
    return patch


async def request_patch(settings: Settings, strategy_yaml: str, finding: BlueFinding, recent_forecasts: list[Forecast]) -> PatchProposal:
    if not settings.gemini_api_key:
        raise PatchValidationFailed("GEMINI_API_KEY is required for Strategy Patcher")
    strategy = parse_strategy_yaml(strategy_yaml)
    samples = [(f.probability_up, f.realized_probability_outcome) for f in recent_forecasts if f.realized_probability_outcome is not None]
    calibration = [
        bucket.__dict__
        for bucket in calibration_buckets(samples)
        if bucket.count > 0
    ]
    prompt = (
        f"{PATCHER_PROMPT}\n\n"
        "Current strategy YAML:\n"
        f"{strategy_yaml}\n\n"
        f"Locked fields: {list(strategy.locked.model_fields)}\n"
        f"Mutable fields and valid ranges: {mutable_field_ranges()}\n\n"
        f"Blue finding JSON:\n{finding.raw_blue_response}\n\n"
        f"Calibration summary JSON:\n{calibration}\n\n"
        f"Recent forecast examples JSON:\n{forecast_examples(recent_forecasts)}\n\n"
        "Return JSON shape: {\"mutable_changes\": {...}, \"rationale\": \"...\", \"expected_brier_improvement\": 0.05}"
    )
    return await GeminiClient(settings).generate_json(prompt, PatchProposal)


async def store_rejected_patch(
    *,
    session: AsyncSession,
    agent: Agent,
    finding: BlueFinding,
    proposed_patch: dict[str, Any],
    rejection_reason: str,
) -> Patch:
    patch_hash = compute_patch_hash(agent.id, proposed_patch, agent.strategy_hash)
    patch = Patch(
        source_agent_id=agent.id,
        target_agent_id=agent.id,
        patch_type="blue_finding",
        blue_finding_id=finding.id,
        blue_finding_json=finding.raw_blue_response,
        base_strategy_yaml=agent.strategy_yaml,
        proposed_yaml=agent.strategy_yaml,
        proposed_patch_json=proposed_patch,
        patch_hash=patch_hash,
        gate_passed=False,
        rejection_reason=rejection_reason,
        status="rejected",
    )
    finding.status = "patch_rejected"
    session.add(patch)
    session.add(Event(agent_id=agent.id, kind="patch_rejected", severity="warning", payload_json={"reason": rejection_reason}))
    await session.commit()
    return patch


async def promote_agent_from_patch(
    session: AsyncSession,
    settings: Settings,
    parent: Agent,
    patch: Patch,
    patched_strategy: Strategy,
    brier: float,
    trade_rate: float,
) -> Agent:
    next_version = int(
        await session.scalar(select(func.coalesce(func.max(Agent.version), 0)).where(Agent.lineage == parent.lineage))
    ) + 1
    promoted_strategy = patched_strategy.model_copy(update={"meta": patched_strategy.meta.model_copy(update={"version": next_version})})
    promoted = Agent(
        lineage=parent.lineage,
        name=f"MIRROR {parent.lineage.upper()}",
        version=next_version,
        prior=parent.prior,
        parent_agent_id=parent.id,
        crossover_parent_agent_id=None,
        strategy_yaml=promoted_strategy.to_yaml(),
        strategy_hash=promoted_strategy.strategy_hash(),
        status="active",
        brier_at_promotion=brier,
        trade_rate_at_promotion=trade_rate,
    )
    parent.status = "superseded"
    session.add(promoted)
    await session.flush()
    registration_job = await queue_or_register_agent(session, settings, promoted)
    feedback_job = await queue_brier_feedback(session, settings, promoted, brier)
    session.add(
        Event(
            agent_id=promoted.id,
            kind="agent_promoted",
            severity="info",
            payload_json={
                "parent_agent_id": str(parent.id),
                "patch_id": str(patch.id),
                "version": promoted.version,
                "registration_job_id": str(registration_job.id) if registration_job else None,
                "feedback_job_id": str(feedback_job.id) if feedback_job else None,
            },
        )
    )
    return promoted


def compute_patch_hash(agent_id: Any, patch_json: dict[str, Any], strategy_hash: str) -> str:
    payload = {"agent_id": str(agent_id), "strategy_hash": strategy_hash, "patch": patch_json}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def mutable_field_ranges() -> dict[str, str]:
    return {
        "entry_confidence_threshold": "0.50 to 0.90",
        "stop_distance_atr": "0.5 to 5.0",
        "take_profit_atr": "0.5 to 8.0",
        "volume_filter_zscore": "-2.0 to 5.0",
        "regime_confidence_min": "0.20 to 0.80",
        "position_size_multiplier": "0.1 to 2.0",
        "max_leverage": "1 to 5",
        "momentum_lookback_minutes": "15 to 1440",
        "mean_reversion_zscore_entry": "0.5 to 5.0",
        "news_signal_required": "boolean",
        "tournament_min_expected_move_bps": "0 to 500",
        "tournament_max_spread_bps": "0 to 500",
        "tournament_profit_lock_bps": "0 to 1000",
        "tournament_trailing_stop_bps": "0 to 1000",
        "tournament_cooldown_minutes_after_loss": "0 to 1440",
    }


def forecast_examples(forecasts: list[Forecast]) -> list[dict[str, Any]]:
    return [
        {
            "ticker": f.ticker,
            "predicted_direction": f.predicted_direction,
            "confidence": f.confidence,
            "probability_up": f.probability_up,
            "regime_tags": f.regime_tags,
            "will_trade": f.will_trade,
            "realized_direction": f.realized_direction,
            "brier_score": f.brier_score,
        }
        for f in forecasts[:25]
    ]


__all__ = ["PatchProposal", "propose_patch_for_finding"]
