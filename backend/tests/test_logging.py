from app.logging import redact_sensitive_values


def test_sensitive_values_are_redacted_case_insensitively() -> None:
    event = {"Authorization": "Bearer secret", "email": "person@example.test", "event": "ok"}

    redacted = redact_sensitive_values(event)

    assert redacted == {"Authorization": "[REDACTED]", "email": "[REDACTED]", "event": "ok"}
