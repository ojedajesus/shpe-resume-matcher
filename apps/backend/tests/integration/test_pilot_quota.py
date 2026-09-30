"""Persistent quota reservations across connections, failures, and retries."""
import multiprocessing
from pathlib import Path

import pytest
from fastapi import HTTPException


def _reserve_worker(db_path: str, start, queue) -> None:
    from app.auth import current_user_id
    from app.config import settings
    from app.database import Database
    import app.quota as quota

    quota.db = Database(Path(db_path))
    settings.ai_allowance_cents = 1
    settings.llm_model = "claude-haiku-4-5-20251001"
    current_user_id.set("member")
    start.wait()
    try:
        quota.reserve("x", 1, "concurrent")
        queue.put("reserved")
    except HTTPException as error:
        queue.put(str(error.status_code))


@pytest.mark.integration
def test_atomic_cap_across_process_connections(tmp_path):
    from app.database import Database
    from app.models import User

    path = tmp_path / "quota.db"
    database = Database(path)
    with database._sync_write_session() as session:
        session.add(User(user_id="member", email="member@example.test", password_hash="unused",
                         monthly_limit_cents=100))
        session.commit()
    context = multiprocessing.get_context("spawn")
    start, queue = context.Event(), context.Queue()
    processes = [context.Process(target=_reserve_worker, args=(str(path), start, queue)) for _ in range(2)]
    for process in processes: process.start()
    start.set()
    results = [queue.get(timeout=15) for _ in processes]
    for process in processes: process.join(timeout=15)
    assert sorted(results) == ["429", "reserved"]


@pytest.mark.integration
def test_full_payload_bound_retry_accounting_and_uncertain_failure(isolated_backend_state, monkeypatch):
    from app.auth import current_user_id
    from app.config import settings
    import app.quota as quota
    from app.models import UsageLedger, User

    monkeypatch.setattr(quota, "db", isolated_backend_state)
    monkeypatch.setattr(settings, "ai_allowance_cents", 4000)
    with isolated_backend_state._sync_write_session() as session:
        session.add(User(user_id="member", email="member@example.test", password_hash="unused",
                         monthly_limit_cents=4000))
        session.commit()
    token = current_user_id.set("member")
    first = quota.reserve("é" * 100, 100, "attempt-1")
    quota.settle(first, None, uncertain=True)
    second = quota.reserve("é" * 100, 100, "attempt-2")
    class Usage: input_tokens = 10; output_tokens = 5
    class Response: usage = Usage()
    quota.settle(second, Response())
    current_user_id.reset(token)
    with isolated_backend_state._sync() as session:
        rows = session.query(UsageLedger).order_by(UsageLedger.created_at).all()
        assert len(rows) == 2
        assert rows[0].status == "uncertain" and rows[0].actual_cents == rows[0].reserved_cents
        assert rows[1].status == "settled" and rows[1].actual_cents >= rows[1].reserved_cents
        # UTF-8 bytes + framing, four transport attempts; never len(text)//3.
        assert rows[0].reserved_cents == 2


@pytest.mark.integration
def test_cap_rejected_before_transport(monkeypatch):
    """LLM transport is not reached when reservation rejects the call."""
    import asyncio
    import app.llm as llm
    import app.quota as quota
    called = False
    def reject(*args, **kwargs):
        raise HTTPException(429, "cap")
    class Router:
        async def acompletion(self, **kwargs):
            nonlocal called; called = True
    monkeypatch.setattr(quota, "reserve", reject)
    monkeypatch.setattr(llm, "get_router", lambda config=None: (Router(), llm.LLMConfig(provider="anthropic", model="claude-haiku-4-5-20251001", api_key="mock")))
    with pytest.raises(HTTPException):
        asyncio.run(llm.complete("synthetic"))
    assert not called
