import json
from typing import Any

import httpx
from pydantic import ValidationError

from mirror.clients.featherless import FeatherlessClient, extract_json_object
from mirror.clients.gemini import GeminiClient
from mirror.config import Settings
from mirror.errors import InferenceMalformedJSON, PatchValidationFailed


async def generate_patcher_json(settings: Settings, prompt: str, response_model: type[Any]) -> Any:
    provider = settings.patcher_provider.lower().strip()
    if provider == "featherless":
        return await FeatherlessClient(settings).chat_json(
            [
                {"role": "system", "content": "Return strict JSON only. No markdown."},
                {"role": "user", "content": prompt},
            ],
            response_model,
            retries=2,
        )
    if provider == "gemini":
        return await GeminiClient(settings).generate_json(prompt, response_model)
    if provider in {"openai_compatible", "vultr", "openrouter", "together"}:
        return await generate_openai_compatible_json(settings, prompt, response_model)
    raise PatchValidationFailed(f"Unsupported PATCHER_PROVIDER={settings.patcher_provider}")


async def generate_openai_compatible_json(settings: Settings, prompt: str, response_model: type[Any], retries: int = 2) -> Any:
    if not settings.patcher_base_url or not settings.patcher_api_key or not settings.patcher_model:
        raise PatchValidationFailed("PATCHER_BASE_URL, PATCHER_API_KEY, and PATCHER_MODEL are required for OpenAI-compatible patcher providers")
    last_error: Exception | None = None
    messages = [
        {"role": "system", "content": "Return one strict JSON object only. No markdown, no commentary."},
        {"role": "user", "content": prompt},
    ]
    for _ in range(retries + 1):
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{settings.patcher_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.patcher_api_key}"},
                json={"model": settings.patcher_model, "messages": messages, "temperature": 0.1},
            )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        try:
            return response_model.model_validate(json.loads(extract_json_object(content)))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            messages = [
                messages[0],
                messages[1],
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": (
                        "Your previous response failed validation. Return one JSON object only. "
                        f"Validation error: {exc}. Required JSON schema: {response_model.model_json_schema()}"
                    ),
                },
            ]
    raise InferenceMalformedJSON(f"OpenAI-compatible patcher response failed JSON validation: {last_error}")
