import logging
from collections.abc import Mapping
from typing import Any

import structlog

SENSITIVE_KEYS = frozenset(
    {"authorization", "cookie", "email", "password", "phone", "session", "session_token"}
)


def redact_sensitive_values(event_dict: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else value
        for key, value in event_dict.items()
    }


def _redact(_: Any, __: str, event_dict: Mapping[str, Any]) -> dict[str, Any]:
    return redact_sensitive_values(event_dict)


def configure_logging(debug: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _redact,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
    )
