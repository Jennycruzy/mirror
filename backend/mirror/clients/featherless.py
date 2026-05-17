import json
import re
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
        current_messages = list(messages)
        for _ in range(retries + 1):
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.settings.featherless_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.featherless_api_key}"},
                    json={"model": self.settings.featherless_model, "messages": current_messages, "temperature": 0.2},
                )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            try:
                return response_model.model_validate(json.loads(extract_json_object(content)))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                current_messages = [
                    *messages,
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "Your previous response failed validation. Return one JSON object only, with no markdown. "
                            f"Validation error: {exc}. Required JSON schema: {response_model.model_json_schema()}"
                        ),
                    },
                ]
        raise InferenceMalformedJSON(f"Featherless response failed JSON validation: {last_error}")

    async def verify(self) -> dict[str, Any]:
        self.ensure_configured()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.settings.featherless_base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {self.settings.featherless_api_key}"},
            )
        response.raise_for_status()
        payload = response.json()
        models = payload.get("data", [])
        selected = next((model for model in models if model.get("id") == self.settings.featherless_model), None)
        return {
            "model_count": len(models),
            "selected_model": self.settings.featherless_model,
            "selected_model_available": bool(selected and selected.get("available_on_current_plan", True)),
            "selected_model_context_length": selected.get("context_length") if selected else None,
        }


def extract_json_object(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return stripped
