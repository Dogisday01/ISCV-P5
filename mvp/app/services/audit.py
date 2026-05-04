from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "token",
    "secret",
    "authorization",
    "cookie",
    "client_secret",
)
MAX_AUDIT_VALUE_LENGTH = 500
CONTROL_CHARS_RE = re.compile(r"[\r\n\t]+")


@dataclass(frozen=True)
class RequestContext:
    ip_address: str | None
    user_agent: str | None


def normalize_text(value: str | None, *, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = CONTROL_CHARS_RE.sub(" ", value).strip()
    if len(normalized) > max_length:
        return normalized[:max_length]
    return normalized


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        # P4 hardening point: recurse into nested structures so secrets are not leaked by str(dict).
        return {
            key: "[REDACTED]" if _is_sensitive_key(key) else _sanitize_value(inner_value)
            for key, inner_value in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        return normalize_text(value, max_length=MAX_AUDIT_VALUE_LENGTH)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return normalize_text(str(value), max_length=MAX_AUDIT_VALUE_LENGTH)


def sanitize_details(details: dict[str, Any] | None) -> dict[str, Any]:
    # report table 5.5: critical code area audit logging
    # report table 7.4: log redaction
    # audit logging: redact tokens and secrets before writing details
    if not details:
        return {}
    return {
        key: "[REDACTED]" if _is_sensitive_key(key) else _sanitize_value(value)
        for key, value in details.items()
    }


def write_audit_log(
    session: Session,
    *,
    action: str,
    outcome: str,
    context: RequestContext,
    actor_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    # report table 7.4: audit trail for critical actions
    # audit logging: store critical actions in the audit log
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        outcome=outcome,
        ip_address=context.ip_address,
        details=sanitize_details(details),
    )
    session.add(entry)
    return entry
