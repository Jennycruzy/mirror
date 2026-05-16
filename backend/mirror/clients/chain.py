import json
from pathlib import Path
from typing import Any

from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3

from mirror.config import Settings
from mirror.errors import ChainTransactionFailed


ABI_DIR = Path(__file__).resolve().parents[2] / "abis"


class ChainClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.w3 = AsyncWeb3(AsyncHTTPProvider(settings.base_sepolia_rpc_url))

    async def verify(self) -> dict[str, int | bool]:
        chain_id = await self.w3.eth.chain_id
        return {"connected": await self.w3.is_connected(), "chain_id": chain_id}

    def _load_abi(self, name: str) -> list[dict[str, Any]]:
        path = ABI_DIR / f"{name}.json"
        if not path.exists():
            raise ChainTransactionFailed(f"Missing ABI file: {path}")
        return json.loads(path.read_text())

    def identity_contract(self):
        return self.w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(self.settings.erc8004_identity_registry),
            abi=self._load_abi("IdentityRegistry"),
        )

    def reputation_contract(self):
        return self.w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(self.settings.erc8004_reputation_registry),
            abi=self._load_abi("ReputationRegistry"),
        )

    async def _send_transaction(self, fn, private_key: str) -> dict[str, Any]:
        account = Account.from_key(private_key)
        tx = await fn.build_transaction(
            {
                "from": account.address,
                "chainId": self.settings.base_sepolia_chain_id,
                "nonce": await self.w3.eth.get_transaction_count(account.address),
            }
        )
        signed = account.sign_transaction(tx)
        raw_tx = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
        tx_hash = await self.w3.eth.send_raw_transaction(raw_tx)
        receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        if receipt.get("status") != 1:
            raise ChainTransactionFailed(f"Transaction reverted: {tx_hash.hex()}")
        return {"tx_hash": tx_hash.hex(), "receipt": receipt}

    async def register_agent(self, agent_uri: str) -> dict[str, Any]:
        if not self.settings.owner_private_key:
            raise ChainTransactionFailed("OWNER_PRIVATE_KEY is required for identity registration")
        contract = self.identity_contract()
        result = await self._send_transaction(contract.functions.register(agent_uri), self.settings.owner_private_key)
        token_id = self._extract_transfer_token_id(result["receipt"])
        if token_id is None:
            raise ChainTransactionFailed("Could not parse ERC-721 Transfer tokenId from registration receipt")
        return {"tx_hash": result["tx_hash"], "token_id": str(token_id)}

    async def set_agent_uri(self, token_id: int, agent_uri: str) -> dict[str, Any]:
        if not self.settings.owner_private_key:
            raise ChainTransactionFailed("OWNER_PRIVATE_KEY is required for setAgentURI")
        contract = self.identity_contract()
        result = await self._send_transaction(contract.functions.setAgentURI(token_id, agent_uri), self.settings.owner_private_key)
        return {"tx_hash": result["tx_hash"]}

    async def post_brier_feedback(self, token_id: int, value: int, value_decimals: int, feedback_hash: bytes) -> dict[str, Any]:
        if not self.settings.evaluator_private_key:
            raise ChainTransactionFailed("EVALUATOR_PRIVATE_KEY is required for reputation feedback")
        contract = self.reputation_contract()
        result = await self._send_transaction(
            contract.functions.giveFeedback(
                token_id,
                value,
                value_decimals,
                "mirror.brier",
                "",
                self.settings.backend_public_url,
                "",
                feedback_hash,
            ),
            self.settings.evaluator_private_key,
        )
        return {"tx_hash": result["tx_hash"]}

    def _extract_transfer_token_id(self, receipt: dict[str, Any]) -> int | None:
        contract = self.identity_contract()
        try:
            events = contract.events.Transfer().process_receipt(receipt)
        except Exception:
            return None
        for event in events:
            args = event.get("args", {})
            if str(args.get("from")).lower() == "0x0000000000000000000000000000000000000000":
                token_id = args.get("tokenId")
                return int(token_id) if token_id is not None else None
        return None
