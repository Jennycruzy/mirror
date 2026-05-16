import json
from typing import Any

import httpx
from pydantic import ValidationError

from mirror.config import Settings
from mirror.errors import InferenceMalformedJSON


class FeatherlessClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def ensure_configured(self) -> None:
        if not self.settings.featherless_api_key:
            raise RuntimeError("FEATHERLESS_API_KEY is required for Featherless inference")

    async def chat_json(self, messages: list[dict[str, str]], response_model: type[Any], retries: int = 2) -> Any:
        self.ensure_configured()
        last_error: Exception | None = None
        for _ in range(retries + 1):
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.settings.featherless_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.featherless_api_key}"},
                    json={"model": self.settings.featherless_model, "messages": messages, "temperature": 0.2},
                )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            try:
                return response_model.model_validate(json.loads(content))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
        raise InferenceMalformedJSON(f"Featherless response failed JSON validation: {last_error}")

    async def verify(self) -> dict[str, Any]:
        self.ensure_configured()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.settings.featherless_base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {self.settings.featherless_api_key}"},
            )
        response.raise_for_status()
        return response.json()

