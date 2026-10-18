"""Structured logging configuration for the API and agent service."""

import json
import logging
import logging.config
import re
from datetime import UTC, datetime
from typing import Any

REDACTED = "[REDACTED]"
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(api[_-]?key|authorization|cookie|password|secret|token|resume|email|phone|"
    r"prompt|input|output|content|text|answer|profile)",
    re.IGNORECASE,
)
_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")


def redact(value: Any, *, key: str | None = None) -> Any:
    """Redact sensitive structured fields and credentials from log data."""
    if key and _SENSITIVE_KEY_PATTERN.search(key):
        return REDACTED
    if isinstance(value, dict):
        return {
            str(item_key): redact(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        sanitized = _BEARER_PATTERN.sub(f"Bearer {REDACTED}", value)
        return _URL_PATTERN.sub("[URL]", sanitized)
    return value


class JsonFormatter(logging.Formatter):
    """One JSON object per line, useful in terminals and log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        event = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for attribute in (
            "request_id",
            "event",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "host",
            "text_length",
            "truncated",
            "message_count",
        ):
            if hasattr(record, attribute):
                event[attribute] = getattr(record, attribute)
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(redact(event), ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger with compact structured JSON output."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": "recruiter_agent.logging_config.JsonFormatter"}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"level": level.upper(), "handlers": ["console"]},
        }
    )
