"""Release-blocking invite/session/CSRF and owner-isolation HTTP regressions."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import _digest
from app.config import settings
from app.main import app
from app.models import Invitation, User
from app.passwords import hash_password


@pytest.fixture
async def secured_client(isolated_backend_state, monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "cookie_secure", False)
    with isolated_backend_state._sync_write_session() as session:
        session.add(User(user_id="owner", email="owner@example.test",
                         password_hash=hash_password("owner-password-123"), is_admin=True))
        session.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, isolated_backend_state


async def login(client, email="owner@example.test", password="owner-password-123"):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password},
                             headers={"Origin": "http://localhost:3000"})


@pytest.mark.integration
async def test_login_csrf_logout_and_session_expiry(secured_client):
    client, database = secured_client
    assert (await client.get("/api/v1/resumes/list")).status_code == 401
    signed_in = await login(client)
    assert signed_in.status_code == 200
    csrf = signed_in.json()["csrf_token"]
    assert (await client.post("/api/v1/jobs/upload", json={"job_descriptions": ["synthetic"]})).status_code == 403
    assert (await client.post("/api/v1/jobs/upload", json={"job_descriptions": ["synthetic"]},
                              headers={"X-CSRF-Token": csrf})).status_code != 403
    assert (await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})).status_code == 204
    assert (await client.get("/api/v1/resumes/list")).status_code == 401
    await login(client)
    raw = client.cookies.get("shpe_session")
    with database._sync_write_session() as session:
        record = session.get(__import__("app.models", fromlist=["Session"]).Session, _digest(raw))
        record.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        session.commit()
    assert (await client.get("/api/v1/resumes/list")).status_code == 401


@pytest.mark.integration
async def test_invitation_expiry_reuse_origin_admin_and_rate_limit(secured_client):
    client, database = secured_client
    assert (await client.post("/api/v1/auth/login", json={"email": "x@y.test", "password": "wrong-password"},
                              headers={"Origin": "https://evil.test"})).status_code == 403
    signed_in = await login(client)
    csrf = signed_in.json()["csrf_token"]
    invitation = await client.post("/api/v1/auth/invitations", json={"email": "member@example.test"},
                                   headers={"X-CSRF-Token": csrf})
    token = invitation.json()["invitation_token"]
    await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    accepted = await client.post("/api/v1/auth/accept-invitation", json={"email": "member@example.test",
        "password": "member-password-123", "invitation_token": token}, headers={"Origin": "http://localhost:3000"})
    assert accepted.status_code == 201
    assert (await client.post("/api/v1/auth/accept-invitation", json={"email": "member@example.test",
        "password": "member-password-123", "invitation_token": token}, headers={"Origin": "http://localhost:3000"})).status_code == 400
    member_csrf = accepted.json()["csrf_token"]
    assert (await client.post("/api/v1/auth/invitations", json={"email": "no@example.test"},
                              headers={"X-CSRF-Token": member_csrf})).status_code == 403
    assert (await client.put("/api/v1/config/llm-api-key", json={},
                             headers={"X-CSRF-Token": member_csrf})).status_code == 403
    expired = "expired-token-which-is-long-enough-1234567890"
    with database._sync_write_session() as session:
        session.add(Invitation(token_hash=_digest(expired), email="old@example.test",
            expires_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(), created_by="owner"))
        session.commit()
    assert (await client.post("/api/v1/auth/accept-invitation", json={"email": "old@example.test",
        "password": "member-password-123", "invitation_token": expired}, headers={"Origin": "http://localhost:3000"})).status_code == 400
    await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": member_csrf})
    results = [await login(client, "abuse@example.test", "wrong-password") for _ in range(9)]
    assert results[-1].status_code == 429


@pytest.mark.integration
async def test_cross_member_http_crud_isolation(secured_client):
    client, database = secured_client
    owner_login = await login(client); owner_csrf = owner_login.json()["csrf_token"]
    from app.auth import current_user_id
    token = current_user_id.set("owner")
    resume = await database.create_resume("synthetic owner content", processing_status="ready")
    current_user_id.reset(token)
    invitation = await client.post("/api/v1/auth/invitations", json={"email": "member2@example.test"}, headers={"X-CSRF-Token": owner_csrf})
    await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": owner_csrf})
    member = await client.post("/api/v1/auth/accept-invitation", json={"email": "member2@example.test", "password": "member-password-123",
        "invitation_token": invitation.json()["invitation_token"]}, headers={"Origin": "http://localhost:3000"})
    csrf = member.json()["csrf_token"]
    assert (await client.get(f"/api/v1/resumes?resume_id={resume['resume_id']}")).status_code == 404
    assert all(item.get("resume_id") != resume["resume_id"] for item in (await client.get("/api/v1/resumes/list")).json().get("resumes", []))
    assert (await client.patch(f"/api/v1/resumes/{resume['resume_id']}", json={"title": "stolen"}, headers={"X-CSRF-Token": csrf})).status_code == 404
    assert (await client.delete(f"/api/v1/resumes/{resume['resume_id']}", headers={"X-CSRF-Token": csrf})).status_code == 404
    assert (await client.get(f"/api/v1/resumes/{resume['resume_id']}/pdf")).status_code == 404
