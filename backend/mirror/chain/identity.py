from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror.chain.registration_file import build_registration_file
from mirror.clients.chain import ChainClient
from mirror.clients.ipfs import IPFSClient
from mirror.config import Settings
from mirror.errors import ChainTransactionFailed, IPFSPinningFailed
from mirror.models import Agent, Event, OnchainJob


ABI_PATH = Path(__file__).resolve().parents[2] / "abis" / "IdentityRegistry.json"

IDENTITY_REQUIRED_FUNCTIONS = {"register", "setAgentURI", "ownerOf", "tokenURI"}


def verify_identity_abi() -> dict:
    import json

    if not ABI_PATH.exists():
        return {"ok": False, "detail": f"missing {ABI_PATH}"}
    abi = json.loads(ABI_PATH.read_text())
    functions = {item["name"] for item in abi if item.get("type") == "function" and "name" in item}
    missing = sorted(IDENTITY_REQUIRED_FUNCTIONS - functions)
    return {"ok": not missing, "missing": missing, "functions": sorted(functions)}


async def queue_or_register_agent(session: AsyncSession, settings: Settings, agent: Agent) -> OnchainJob | None:
    if agent.on_chain_token_id:
        return None
    existing = (
        await session.execute(
            select(OnchainJob).where(
                OnchainJob.job_type == "register_agent",
                OnchainJob.agent_id == agent.id,
                OnchainJob.status.in_(["queued", "pending", "confirmed"]),
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    parent_token_id, crossover_parent_token_id = await load_parent_token_ids(session, agent)
    payload = build_agent_registration_payload(
        settings,
        agent,
        token_id=None,
        parent_token_id=parent_token_id,
        crossover_parent_token_id=crossover_parent_token_id,
    )
    job = OnchainJob(job_type="register_agent", agent_id=agent.id, patch_id=None, status="queued", payload_json=payload)
    session.add(job)
    session.add(Event(agent_id=agent.id, kind="onchain_registration_queued", severity="info", payload_json={"agent_id": str(agent.id)}))
    await session.flush()
    if settings.onchain_enabled:
        await execute_registration_job(session, settings, job)
    return job


async def execute_registration_job(session: AsyncSession, settings: Settings, job: OnchainJob) -> None:
    agent = await session.get(Agent, job.agent_id)
    if agent is None:
        job.status = "failed"
        job.last_error = "agent not found"
        return
    job.status = "pending"
    job.attempt_count += 1
    try:
        provisional_cid = await IPFSClient(settings).pin_json(f"mirror-{agent.lineage}-v{agent.version}-provisional", job.payload_json)
        provisional_uri = f"ipfs://{provisional_cid}"
        result = await ChainClient(settings).register_agent(provisional_uri)
        token_id = result["token_id"]
        parent_token_id, crossover_parent_token_id = await load_parent_token_ids(session, agent)
        final_payload = build_agent_registration_payload(
            settings,
            agent,
            token_id=token_id,
            parent_token_id=parent_token_id,
            crossover_parent_token_id=crossover_parent_token_id,
        )
        final_cid = await IPFSClient(settings).pin_json(f"mirror-{agent.lineage}-v{agent.version}", final_payload)
        final_uri = f"ipfs://{final_cid}"
        set_uri = await ChainClient(settings).set_agent_uri(int(token_id), final_uri)
        agent.on_chain_token_id = token_id
        agent.on_chain_tx_hash = result["tx_hash"]
        agent.agent_uri = final_uri
        agent.ipfs_cid = final_cid
        job.status = "confirmed"
        job.tx_hash = result["tx_hash"]
        job.last_error = None
        job.payload_json = final_payload
        session.add(
            Event(
                agent_id=agent.id,
                kind="onchain_registration_confirmed",
                severity="info",
                payload_json={"token_id": token_id, "mint_tx_hash": result["tx_hash"], "set_uri_tx_hash": set_uri["tx_hash"], "agent_uri": final_uri},
            )
        )
    except (IPFSPinningFailed, ChainTransactionFailed, Exception) as exc:
        job.status = "failed"
        job.last_error = str(exc)
        session.add(Event(agent_id=agent.id, kind="onchain_registration_failed", severity="error", payload_json={"error": str(exc)}))


async def load_parent_token_ids(session: AsyncSession, agent: Agent) -> tuple[str | None, str | None]:
    parent_token_id = None
    crossover_parent_token_id = None
    if agent.parent_agent_id:
        parent = await session.get(Agent, agent.parent_agent_id)
        parent_token_id = parent.on_chain_token_id if parent else None
    if agent.crossover_parent_agent_id:
        crossover_parent = await session.get(Agent, agent.crossover_parent_agent_id)
        crossover_parent_token_id = crossover_parent.on_chain_token_id if crossover_parent else None
    return parent_token_id, crossover_parent_token_id


def build_agent_registration_payload(
    settings: Settings,
    agent: Agent,
    token_id: str | None,
    parent_token_id: str | None = None,
    crossover_parent_token_id: str | None = None,
) -> dict[str, Any]:
    return build_registration_file(
        name=f"MIRROR {agent.lineage.upper()} v{agent.version}",
        description=f"Adversarially-calibrated trading agent. Lineage: {agent.prior}.",
        image="ipfs://pending-lineage-badge",
        service_endpoint=f"{settings.backend_public_url.rstrip('/')}/agents/{agent.id}",
        identity_registry=settings.erc8004_identity_registry,
        token_id=token_id,
        lineage=agent.lineage,
        version=agent.version,
        strategy_hash=agent.strategy_hash,
        parent_token_id=parent_token_id,
        crossover_parent_token_id=crossover_parent_token_id,
    )
