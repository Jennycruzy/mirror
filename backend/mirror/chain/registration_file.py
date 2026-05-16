from typing import Any


def build_registration_file(
    *,
    name: str,
    description: str,
    image: str,
    service_endpoint: str,
    identity_registry: str,
    token_id: str | None,
    lineage: str,
    version: int,
    strategy_hash: str,
    parent_token_id: str | None = None,
    crossover_parent_token_id: str | None = None,
    patch_hash: str | None = None,
    holdout_brier_pre: float | None = None,
    holdout_brier_post: float | None = None,
    holdout_trade_rate: float | None = None,
) -> dict[str, Any]:
    return {
        "type": "https://erc8004.org/schemas/registration/v1",
        "name": name,
        "description": description,
        "image": image,
        "services": [{"type": "mirror-agent", "endpoint": service_endpoint}],
        "registrations": [{"agentRegistry": f"eip155:84532:{identity_registry}", "agentId": token_id}],
        "supportedTrust": ["reputation"],
        "mirror_metadata": {
            "lineage": lineage,
            "version": version,
            "parent_token_id": parent_token_id,
            "crossover_parent_token_id": crossover_parent_token_id,
            "patch_hash": patch_hash,
            "holdout_brier_pre": holdout_brier_pre,
            "holdout_brier_post": holdout_brier_post,
            "holdout_trade_rate": holdout_trade_rate,
            "strategy_hash": strategy_hash,
        },
    }

