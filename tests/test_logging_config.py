import json
import logging

from recruiter_agent.logging_config import JsonFormatter, redact


def test_json_formatter_emits_structured_request_metadata() -> None:
    record = logging.LogRecord(
        name="recruiter_agent.api",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="http_request_completed",
        args=(),
        exc_info=None,
    )
    record.event = "http_request_completed"
    record.request_id = "request-123"
    record.method = "POST"
    record.path = "/v1/agent/input"
    record.status_code = 200
    record.duration_ms = 42.5

    entry = json.loads(JsonFormatter().format(record))

    assert entry["level"] == "INFO"
    assert entry["event"] == "http_request_completed"
    assert entry["request_id"] == "request-123"
    assert entry["status_code"] == 200
    assert entry["duration_ms"] == 42.5


def test_redact_hides_sensitive_fields_and_url_values() -> None:
    safe = redact(
        {
            "event": "request",
            "prompt": "private prompt",
            "api_key": "secret",
            "metadata": {"email": "person@example.com"},
            "detail": "request to https://example.com/job/123",
        }
    )

    assert safe == {
        "event": "request",
        "prompt": "[REDACTED]",
        "api_key": "[REDACTED]",
        "metadata": {"email": "[REDACTED]"},
        "detail": "request to [URL]",
    }
