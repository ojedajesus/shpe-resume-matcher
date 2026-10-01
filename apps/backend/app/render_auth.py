"""Short-lived, resource-scoped authorization for Chromium print requests."""
import json
import time

from app.crypto import decrypt, encrypt


def issue_render_token(owner_id: str, resume_id: str, *, ttl_seconds: int = 120) -> str:
    payload = {"owner_id": owner_id, "resume_id": resume_id, "exp": int(time.time()) + ttl_seconds}
    return encrypt(json.dumps(payload, separators=(",", ":")))


def verify_render_token(token: str, resume_id: str) -> str | None:
    try:
        payload = json.loads(decrypt(token))
        if payload.get("resume_id") != resume_id or int(payload.get("exp", 0)) < int(time.time()):
            return None
        owner_id = payload.get("owner_id")
        return owner_id if isinstance(owner_id, str) and owner_id else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
