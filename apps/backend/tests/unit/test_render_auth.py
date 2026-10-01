import time

from app.render_auth import issue_render_token, verify_render_token


def test_render_token_is_scoped_and_expires(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1000)
    token = issue_render_token("member-a", "resume-a", ttl_seconds=2)
    assert verify_render_token(token, "resume-a") == "member-a"
    assert verify_render_token(token, "resume-b") is None
    monkeypatch.setattr(time, "time", lambda: 1003)
    assert verify_render_token(token, "resume-a") is None


def test_render_token_rejects_tampering():
    token = issue_render_token("member-a", "resume-a")
    assert verify_render_token(token + "x", "resume-a") is None
