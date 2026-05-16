from eth_utils import keccak
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.clients.chain import ChainClient
from mirror.config import Settings
from mirror.models import Agent, Event, OnchainJob


ABI_PATH = Path(__file__).resolve().parents[2] / "abis" / "ReputationRegistry.json"
REPUTATION_REQUIRED_FUNCTIONS = {"giveFeedback", "getIdentityRegistry", "readFeedback"}


def brier_feedback_value(brier_score: float) -> tuple[int, int, bytes]:
    return int(brier_score * 10000), 4, keccak(text="mirror.brier")


def verify_reputation_abi() -> dict:
    import json

    if not ABI_PATH.exists():
        return {"ok": False, "detail": f"missing {ABI_PATH}"}
    abi = json.loads(ABI_PATH.read_text())
    functions = {item["name"] for item in abi if item.get("type") == "function" and "name" in item}
    missing = sorted(REPUTATION_REQUIRED_FUNCTIONS - functions)
    return {"ok": not missing, "missing": missing, "functions": sorted(functions)}


async def queue_brier_feedback(session: AsyncSession, settings: Settings, agent: Agent, brier_score: float) -> OnchainJob | None:
    if not agent.on_chain_token_id:
        return None
    existing = (
        await session.execute(
            select(OnchainJob).where(
                OnchainJob.job_type == "post_brier_feedback",
                OnchainJob.agent_id == agent.id,
                OnchainJob.status.in_(["queued", "pending", "confirmed"]),
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    value, value_decimals, tag_hash = brier_feedback_value(brier_score)
    job = OnchainJob(
        job_type="post_brier_feedback",
        agent_id=agent.id,
        patch_id=None,
        status="queued",
        payload_json={"token_id": agent.on_chain_token_id, "brier_score": brier_score, "value": value, "value_decimals": value_decimals},
    )
    session.add(job)
    if settings.onchain_enabled:
        await execute_brier_feedback_job(session, settings, job, tag_hash)
    return job


async def execute_brier_feedback_job(session: AsyncSession, settings: Settings, job: OnchainJob, feedback_hash: bytes | None = None) -> None:
    agent = await session.get(Agent, job.agent_id)
    if agent is None or not agent.on_chain_token_id:
        job.status = "failed"
        job.last_error = "agent token id unavailable"
        return
    value = int(job.payload_json["value"])
    value_decimals = int(job.payload_json["value_decimals"])
    feedback_hash = feedback_hash or brier_feedback_value(float(job.payload_json["brier_score"]))[2]
    job.status = "pending"
    job.attempt_count += 1
    try:
        result = await ChainClient(settings).post_brier_feedback(int(agent.on_chain_token_id), value, value_decimals, feedback_hash)
        job.status = "confirmed"
        job.tx_hash = result["tx_hash"]
        session.add(Event(agent_id=agent.id, kind="brier_feedback_posted", severity="info", payload_json={"tx_hash": result["tx_hash"]}))
    except Exception as exc:
        job.status = "failed"
        job.last_error = str(exc)
        session.add(Event(agent_id=agent.id, kind="brier_feedback_failed", severity="error", payload_json={"error": str(exc)}))
