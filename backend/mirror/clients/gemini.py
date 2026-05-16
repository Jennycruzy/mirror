import json
from typing import Any

import httpx
from pydantic import ValidationError

from mirror.config import Settings
from mirror.errors import InferenceMalformedJSON


class GeminiClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def ensure_configured(self) -> None:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini calls")

    async def generate_json(self, prompt: str, response_model: type[Any], retries: int = 2) -> Any:
        self.ensure_configured()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model}:generateContent"
        last_error: Exception | None = None
        for _ in range(retries + 1):
            async with httpx.AsyncClient(timeout=90) as client:
                response = await client.post(
                    url,
                    params={"key": self.settings.gemini_api_key},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
                    },
                )
            response.raise_for_status()
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            try:
                return response_model.model_validate(json.loads(text))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
        raise InferenceMalformedJSON(f"Gemini response failed JSON validation: {last_error}")

    async def verify(self) -> dict[str, Any]:
        self.ensure_configured()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params={"key": self.settings.gemini_api_key})
        response.raise_for_status()
        return response.json()

