import httpx

from mirror.config import Settings
from mirror.errors import IPFSPinningFailed


class IPFSClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def pin_json(self, name: str, payload: dict) -> str:
        if self.settings.pinata_jwt:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    "https://api.pinata.cloud/pinning/pinJSONToIPFS",
                    headers={"Authorization": f"Bearer {self.settings.pinata_jwt}"},
                    json={"pinataMetadata": {"name": name}, "pinataContent": payload},
                )
            response.raise_for_status()
            return response.json()["IpfsHash"]
        raise IPFSPinningFailed("No IPFS pinning provider configured. Set PINATA_JWT or WEB3_STORAGE_TOKEN.")

