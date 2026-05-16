from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.clients.featherless import FeatherlessClient
from mirror.clients.gemini import GeminiClient
from mirror.config import Settings
from mirror.models import Agent, BlueFinding, Event, Forecast


class BlueFindingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    regime_context: dict[str, Any]
    sample_size: int = Field(ge=0)
    predicted_confidence_avg: float = Field(ge=0, le=1)
    realized_accuracy: float = Field(ge=0, le=1)
    brier_gap: float
    suggested_failure_mode: str
    suggested_fix_direction: str


BLUE_SYSTEM_PROMPT = """You are a MIRROR Blue adversarial calibration analyst.
You do not write strategy patches. Identify the single most exploitable miscalibration pattern.
Return strict JSON only with regime_context, sample_size, predicted_confidence_avg, realized_accuracy, brier_gap, suggested_failure_mode, suggested_fix_direction.
"""


async def run_blue_scan(session: AsyncSession, settings: Settings, lineage: str) -> list[BlueFinding]:
    agent = (
        await session.execute(
            select(Agent)
            .where(Agent.lineage == lineage, Agent.status == "active")
            .order_by(Agent.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if agent is None:
        return []

    since = datetime.now(UTC) - timedelta(hours=48)
    forecasts = (
        await session.execute(
            select(Forecast)
            .where(
                Forecast.agent_id == agent.id,
                Forecast.status == "resolved",
                Forecast.resolved_at >= since,
                Forecast.brier_score.is_not(None),
            )
            .order_by(Forecast.resolved_at.desc())
        )
    ).scalars().all()

    strata = stratify_forecasts(forecasts)
    eligible = [summary for summary in strata if summary["sample_size"] >= 15]
    if not eligible:
        session.add(
            Event(
                agent_id=agent.id,
                kind="blue_scan_no_eligible_strata",
                severity="info",
                payload_json={"resolved_samples": len(forecasts), "eligible_min_n": 15},
            )
        )
        await session.commit()
        return []

    prompt = [
        {"role": "system", "content": BLUE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Agent lineage: {agent.lineage}\n"
                f"Agent prior: {agent.prior}\n"
                "Eligible calibration strata JSON:\n"
                f"{eligible}\n"
                "Select the single most exploitable miscalibration pattern. Return strict JSON only."
            ),
        },
    ]
    if settings.featherless_api_key:
        payload = await FeatherlessClient(settings).chat_json(prompt, BlueFindingPayload)
    elif settings.gemini_api_key:
        payload = await GeminiClient(settings).generate_json(prompt[-1]["content"], BlueFindingPayload)
    else:
        session.add(
            Event(
                agent_id=agent.id,
                kind="blue_scan_failed",
                severity="error",
                payload_json={"reason": "Set FEATHERLESS_API_KEY or GEMINI_API_KEY for real Blue inference"},
            )
        )
        await session.commit()
        return []

    finding = BlueFinding(
        agent_id=agent.id,
        regime_context=payload.regime_context,
        sample_size=payload.sample_size,
        predicted_confidence_avg=payload.predicted_confidence_avg,
        realized_accuracy=payload.realized_accuracy,
        brier_gap=payload.brier_gap,
        suggested_failure_mode=payload.suggested_failure_mode,
        suggested_fix_direction=payload.suggested_fix_direction,
        raw_blue_response=payload.model_dump(),
        status="pending" if payload.brier_gap >= 0.08 and payload.sample_size >= 20 else "stored",
    )
    session.add(finding)
    await session.flush()
    session.add(
        Event(
            agent_id=agent.id,
            kind="blue_finding_created",
            severity="warning" if finding.status == "pending" else "info",
            payload_json={"finding_id": str(finding.id), "brier_gap": finding.brier_gap, "sample_size": finding.sample_size},
        )
    )
    if finding.status == "pending":
        session.add(
            Event(
                agent_id=agent.id,
                kind="patch_proposal_queued",
                severity="info",
                payload_json={"blue_finding_id": str(finding.id)},
            )
        )
    await session.commit()
    return [finding]


def stratify_forecasts(forecasts: list[Forecast]) -> list[dict[str, Any]]:
    groups: dict[str, list[Forecast]] = {}
    for forecast in forecasts:
        tags = forecast.regime_tags or ["untagged"]
        key = "|".join(sorted(tags))
        groups.setdefault(key, []).append(forecast)

    summaries: list[dict[str, Any]] = []
    for key, rows in groups.items():
        if not rows:
            continue
        predicted_avg = sum(f.confidence for f in rows) / len(rows)
        correct = sum(1 for f in rows if forecast_was_directionally_correct(f))
        realized_accuracy = correct / len(rows)
        summaries.append(
            {
                "regime_context": {"tags": key.split("|")},
                "sample_size": len(rows),
                "predicted_confidence_avg": predicted_avg,
                "realized_accuracy": realized_accuracy,
                "brier_gap": abs(predicted_avg - realized_accuracy),
                "mean_brier": sum(float(f.brier_score or 0) for f in rows) / len(rows),
            }
        )
    return sorted(summaries, key=lambda item: item["brier_gap"], reverse=True)


def forecast_was_directionally_correct(forecast: Forecast) -> bool:
    if forecast.predicted_direction == "flat":
        return False
    if forecast.predicted_direction == "long":
        return forecast.realized_direction == "up"
    if forecast.predicted_direction == "short":
        return forecast.realized_direction == "down"
    return False
