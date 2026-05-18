from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.agents.patcher import (
    compute_patch_hash,
    forecast_examples,
    mutable_field_ranges,
)
from mirror.agents.strategy_schema import PatchProposal, Strategy, apply_patch_to_strategy, parse_strategy_yaml
from mirror.backtest.gate import evaluate_holdout_gate
from mirror.backtest.replay import replay_strategy
from mirror.calibration.brier import calibration_buckets
from mirror.chain.identity import queue_or_register_agent
from mirror.chain.reputation import queue_brier_feedback
from mirror.clients.patcher_model import generate_patcher_json
from mirror.config import Settings
from mirror.errors import PatchValidationFailed
from mirror.models import Agent, Event, Forecast, Patch


CROSSOVER_PROMPT = """You are MIRROR Crossover Engine.
Adapt a successful donor patch to a different recipient Red lineage.
Return strict JSON only with mutable_changes, rationale, expected_brier_improvement.
Do not blindly copy donor values. Do not modify locked or meta fields.
"""


async def attempt_crossovers_for_patch(session: AsyncSession, settings: Settings, source_patch_id: str) -> list[Patch]:
    source_patch = await session.get(Patch, source_patch_id)
    if source_patch is None:
        raise PatchValidationFailed(f"Patch not found: {source_patch_id}")
    if not source_patch.gate_passed or not source_patch.applied_agent_id:
        raise PatchValidationFailed("Crossovers require an accepted patch with an applied agent")

    donor_parent = await session.get(Agent, source_patch.target_agent_id)
    donor_applied = await session.get(Agent, source_patch.applied_agent_id)
    if donor_parent is None or donor_applied is None:
        raise PatchValidationFailed("Donor patch agents are unavailable")

    recipients = (
        await session.execute(
            select(Agent)
            .where(Agent.status == "active", Agent.lineage != donor_parent.lineage)
            .order_by(Agent.lineage, Agent.version.desc())
        )
    ).scalars().all()
    latest_by_lineage: dict[str, Agent] = {}
    for recipient in recipients:
        latest_by_lineage.setdefault(recipient.lineage, recipient)

    results: list[Patch] = []
    for recipient in latest_by_lineage.values():
        existing = (
            await session.execute(
                select(Patch)
                .where(
                    Patch.target_agent_id == recipient.id,
                    Patch.patch_type == "crossover",
                    Patch.source_agent_id == donor_applied.id,
                )
                .order_by(Patch.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing:
            results.append(existing)
            continue
        results.append(await attempt_crossover_for_recipient(session, settings, source_patch, donor_parent, donor_applied, recipient))

    await session.commit()
    return results


async def attempt_crossovers_for_accepted_patch(session: AsyncSession, settings: Settings, source_patch: Patch) -> list[Patch]:
    if not source_patch.gate_passed or not source_patch.applied_agent_id:
        raise PatchValidationFailed("Crossovers require an accepted patch with an applied agent")

    donor_parent = await session.get(Agent, source_patch.target_agent_id)
    donor_applied = await session.get(Agent, source_patch.applied_agent_id)
    if donor_parent is None or donor_applied is None:
        raise PatchValidationFailed("Donor patch agents are unavailable")

    recipients = (
        await session.execute(
            select(Agent)
            .where(Agent.status == "active", Agent.lineage != donor_parent.lineage)
            .order_by(Agent.lineage, Agent.version.desc())
        )
    ).scalars().all()
    latest_by_lineage: dict[str, Agent] = {}
    for recipient in recipients:
        latest_by_lineage.setdefault(recipient.lineage, recipient)

    results: list[Patch] = []
    for recipient in latest_by_lineage.values():
        existing = (
            await session.execute(
                select(Patch)
                .where(
                    Patch.target_agent_id == recipient.id,
                    Patch.patch_type == "crossover",
                    Patch.source_agent_id == donor_applied.id,
                )
                .order_by(Patch.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing:
            results.append(existing)
            continue
        results.append(await attempt_crossover_for_recipient(session, settings, source_patch, donor_parent, donor_applied, recipient))
    return results


async def attempt_crossover_for_recipient(
    session: AsyncSession,
    settings: Settings,
    source_patch: Patch,
    donor_parent: Agent,
    donor_applied: Agent,
    recipient: Agent,
) -> Patch:
    recent_forecasts = (
        await session.execute(
            select(Forecast)
            .where(Forecast.agent_id == recipient.id, Forecast.status == "resolved", Forecast.brier_score.is_not(None))
            .order_by(Forecast.resolved_at.desc())
            .limit(100)
        )
    ).scalars().all()
    if len(recent_forecasts) < 1:
        return store_crossover_rejection(
            session,
            source_patch,
            donor_applied,
            recipient,
            {"mutable_changes": {}, "rationale": "insufficient holdout data", "expected_brier_improvement": 0},
            "recipient holdout replay requires resolved forecasts",
        )

    try:
        proposal = await request_crossover_patch(settings, source_patch, donor_parent, donor_applied, recipient, list(recent_forecasts))
        patched_strategy = apply_patch_to_strategy(recipient.strategy_yaml, proposal.model_dump())
    except PatchValidationFailed as exc:
        return store_crossover_rejection(session, source_patch, donor_applied, recipient, proposal.model_dump() if "proposal" in locals() else {}, str(exc))

    pre = replay_strategy(recipient.strategy_yaml, list(recent_forecasts))
    post = replay_strategy(patched_strategy.to_yaml(), list(recent_forecasts))
    gate = evaluate_holdout_gate(pre.brier, post.brier, pre.trade_rate, post.trade_rate)
    patch_hash = compute_patch_hash(recipient.id, proposal.model_dump(), recipient.strategy_hash)
    patch = Patch(
        source_agent_id=donor_applied.id,
        target_agent_id=recipient.id,
        patch_type="crossover",
        blue_finding_id=source_patch.blue_finding_id,
        blue_finding_json=source_patch.blue_finding_json,
        base_strategy_yaml=recipient.strategy_yaml,
        proposed_yaml=patched_strategy.to_yaml(),
        proposed_patch_json=proposal.model_dump(),
        patch_hash=patch_hash,
        holdout_pre_brier=pre.brier,
        holdout_post_brier=post.brier,
        holdout_pre_trade_rate=pre.trade_rate,
        holdout_post_trade_rate=post.trade_rate,
        brier_improvement_pct=gate.brier_improvement_pct,
        trade_rate_preservation_pct=gate.trade_rate_preservation_pct,
        gate_passed=gate.passed,
        rejection_reason=gate.rejection_reason,
        status="accepted" if gate.passed else "rejected",
    )
    session.add(patch)
    await session.flush()

    if gate.passed:
        promoted = await promote_crossover_agent(session, settings, recipient, donor_applied, patch, patched_strategy, post.brier, post.trade_rate)
        patch.applied_agent_id = promoted.id
        patch.applied_at = datetime.now(UTC)
        session.add(
            Event(
                agent_id=recipient.id,
                kind="crossover_accepted",
                severity="info",
                payload_json={"patch_id": str(patch.id), "donor_agent_id": str(donor_applied.id), "applied_agent_id": str(promoted.id)},
            )
        )
    else:
        session.add(
            Event(
                agent_id=recipient.id,
                kind="crossover_rejected",
                severity="warning",
                payload_json={"patch_id": str(patch.id), "donor_agent_id": str(donor_applied.id), "reason": gate.rejection_reason},
            )
        )
    return patch


async def request_crossover_patch(
    settings: Settings,
    source_patch: Patch,
    donor_parent: Agent,
    donor_applied: Agent,
    recipient: Agent,
    recent_forecasts: list[Forecast],
) -> PatchProposal:
    samples = [(f.probability_up, f.realized_probability_outcome) for f in recent_forecasts if f.realized_probability_outcome is not None]
    calibration = [bucket.__dict__ for bucket in calibration_buckets(samples) if bucket.count > 0]
    recipient_strategy = parse_strategy_yaml(recipient.strategy_yaml)
    prompt = (
        f"{CROSSOVER_PROMPT}\n\n"
        f"Donor Red prior: {donor_parent.prior}\n"
        f"Recipient Red prior: {recipient.prior}\n\n"
        "Donor strategy before patch:\n"
        f"{source_patch.base_strategy_yaml}\n\n"
        "Donor strategy after patch:\n"
        f"{donor_applied.strategy_yaml}\n\n"
        f"Donor Blue finding JSON:\n{source_patch.blue_finding_json}\n\n"
        "Donor holdout result JSON:\n"
        f"{donor_holdout_summary(source_patch)}\n\n"
        "Recipient current strategy:\n"
        f"{recipient.strategy_yaml}\n\n"
        f"Recipient mutable fields and valid ranges: {mutable_field_ranges()}\n"
        f"Recipient locked fields: {list(recipient_strategy.locked.model_fields)}\n\n"
        f"Recipient calibration summary JSON:\n{calibration}\n\n"
        f"Recipient recent forecast examples JSON:\n{forecast_examples(recent_forecasts)}\n\n"
        "Return JSON shape: {\"mutable_changes\": {...}, \"rationale\": \"...\", \"expected_brier_improvement\": 0.05}"
    )
    return await generate_patcher_json(settings, prompt, PatchProposal)


def store_crossover_rejection(
    session: AsyncSession,
    source_patch: Patch,
    donor_applied: Agent,
    recipient: Agent,
    proposed_patch: dict[str, Any],
    rejection_reason: str,
) -> Patch:
    patch_hash = compute_patch_hash(recipient.id, proposed_patch, recipient.strategy_hash)
    patch = Patch(
        source_agent_id=donor_applied.id,
        target_agent_id=recipient.id,
        patch_type="crossover",
        blue_finding_id=source_patch.blue_finding_id,
        blue_finding_json=source_patch.blue_finding_json,
        base_strategy_yaml=recipient.strategy_yaml,
        proposed_yaml=recipient.strategy_yaml,
        proposed_patch_json=proposed_patch,
        patch_hash=patch_hash,
        gate_passed=False,
        rejection_reason=rejection_reason,
        status="rejected",
    )
    session.add(patch)
    session.add(
        Event(
            agent_id=recipient.id,
            kind="crossover_rejected",
            severity="warning",
            payload_json={"donor_agent_id": str(donor_applied.id), "reason": rejection_reason},
        )
    )
    return patch


async def promote_crossover_agent(
    session: AsyncSession,
    settings: Settings,
    recipient: Agent,
    donor_applied: Agent,
    patch: Patch,
    patched_strategy: Strategy,
    brier: float,
    trade_rate: float,
) -> Agent:
    next_version = int(
        await session.scalar(select(func.coalesce(func.max(Agent.version), 0)).where(Agent.lineage == recipient.lineage))
    ) + 1
    promoted_strategy = patched_strategy.model_copy(update={"meta": patched_strategy.meta.model_copy(update={"version": next_version})})
    promoted = Agent(
        lineage=recipient.lineage,
        name=f"MIRROR {recipient.lineage.upper()}",
        version=next_version,
        prior=recipient.prior,
        parent_agent_id=recipient.id,
        crossover_parent_agent_id=donor_applied.id,
        strategy_yaml=promoted_strategy.to_yaml(),
        strategy_hash=promoted_strategy.strategy_hash(),
        status="active",
        brier_at_promotion=brier,
        trade_rate_at_promotion=trade_rate,
    )
    recipient.status = "superseded"
    session.add(promoted)
    await session.flush()
    registration_job = await queue_or_register_agent(session, settings, promoted)
    feedback_job = await queue_brier_feedback(session, settings, promoted, brier)
    session.add(
        Event(
            agent_id=promoted.id,
            kind="crossover_agent_promoted",
            severity="info",
            payload_json={
                "patch_id": str(patch.id),
                "parent_agent_id": str(recipient.id),
                "crossover_parent_agent_id": str(donor_applied.id),
                "registration_job_id": str(registration_job.id) if registration_job else None,
                "feedback_job_id": str(feedback_job.id) if feedback_job else None,
            },
        )
    )
    return promoted


def donor_holdout_summary(patch: Patch) -> dict[str, Any]:
    return {
        "holdout_pre_brier": patch.holdout_pre_brier,
        "holdout_post_brier": patch.holdout_post_brier,
        "holdout_pre_trade_rate": patch.holdout_pre_trade_rate,
        "holdout_post_trade_rate": patch.holdout_post_trade_rate,
        "brier_improvement_pct": patch.brier_improvement_pct,
        "trade_rate_preservation_pct": patch.trade_rate_preservation_pct,
    }


__all__ = ["PatchProposal", "attempt_crossovers_for_patch", "attempt_crossovers_for_accepted_patch"]
