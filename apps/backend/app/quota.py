"""Atomic, conservative Anthropic budget accounting."""
import math
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select

from app.auth import current_user_id
from app.config import settings
from app.database import db
from app.models import UsageLedger, User


MODEL_RATES_MICROS: dict[str, tuple[int, int]] = {
    "claude-haiku-4-5-20251001": (1, 5),
}
MAX_OUTPUT_TOKENS = 8192
TRANSPORT_ATTEMPTS = 4  # initial request plus Router.num_retries=3
MESSAGE_OVERHEAD_TOKENS = 4096


def reserve(prompt: str, max_output_tokens: int, operation: str) -> str:
    """Atomically reserve a byte-safe full-message bound for every transport attempt.

    One UTF-8 byte per token is deliberately more conservative than Anthropic's
    tokenizer. The fixed allowance covers message framing and provider-added
    metadata. Content-quality retries call this function independently.
    """
    owner = current_user_id.get()
    if owner == "legacy":
        if not settings.auth_required:
            return "auth-disabled"
        raise RuntimeError("AI accounting requires an authenticated owner context")
    if not 1 <= max_output_tokens <= MAX_OUTPUT_TOKENS:
        raise HTTPException(422, f"AI output limit must be between 1 and {MAX_OUTPUT_TOKENS} tokens")
    rates = MODEL_RATES_MICROS.get(settings.llm_model)
    if rates is None:
        raise HTTPException(503, "AI model pricing is not configured; no provider request was made")
    input_rate, output_rate = rates
    # Refuse a deployment-time rate that understates the reviewed model table.
    if (settings.anthropic_input_micros_per_token, settings.anthropic_output_micros_per_token) != rates:
        raise HTTPException(503, "AI pricing configuration does not match the selected model")
    bounded_input = len(prompt.encode("utf-8")) + MESSAGE_OVERHEAD_TOKENS
    micros = (bounded_input * input_rate + max_output_tokens * output_rate) * TRANSPORT_ATTEMPTS
    cents = max(1, math.ceil(micros / 10_000))
    usage_id = str(uuid4())
    with db._sync_write_session() as session:
        total = session.scalar(select(func.sum(func.coalesce(UsageLedger.actual_cents,
            UsageLedger.reserved_cents)))) or 0
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        member = session.scalar(select(func.sum(func.coalesce(UsageLedger.actual_cents,
            UsageLedger.reserved_cents))).where(UsageLedger.owner_id == owner,
                                                UsageLedger.created_at >= month_start)) or 0
        user = session.get(User, owner)
        member_limit = user.monthly_limit_cents if user else 0
        if total + cents > settings.ai_allowance_cents or member + cents > member_limit:
            raise HTTPException(429, "AI usage limit reached; no provider request was made")
        session.add(UsageLedger(usage_id=usage_id, owner_id=owner, operation=operation,
            reserved_cents=cents, status="reserved"))
        session.commit()
    return usage_id


def settle(usage_id: str, response: object | None, *, uncertain: bool = False) -> None:
    """Record provider usage; failures retain the full conservative reservation."""
    if usage_id == "auth-disabled":
        return
    with db._sync_write_session() as session:
        row = session.get(UsageLedger, usage_id)
        if not row:
            return
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", None)
        if not uncertain and input_tokens is not None and output_tokens is not None:
            micros = input_tokens * settings.anthropic_input_micros_per_token + output_tokens * settings.anthropic_output_micros_per_token
            # The response reports the successful attempt only. Earlier Router
            # attempts may also have been billed, so never refund the group reservation.
            row.actual_cents = max(row.reserved_cents, max(1, math.ceil(micros / 10_000)))
            row.input_tokens, row.output_tokens, row.status = input_tokens, output_tokens, "settled"
        else:
            row.actual_cents, row.status = row.reserved_cents, "uncertain"
        session.commit()
