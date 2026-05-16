import logging
from collections.abc import MutableMapping
from typing import Any

import structlog


SECRET_MARKERS = ("key", "secret", "token", "private", "password", "authorization")


def redact(value: Any) -> Any:
    if isinstance(value, MutableMapping):
        return {k: ("[REDACTED]" if any(m in k.lower() for m in SECRET_MARKERS) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def redaction_processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return redact(event_dict)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            redaction_processor,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )

