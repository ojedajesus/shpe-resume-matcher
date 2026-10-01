"""Cloud contracts verified without provider calls or real credentials."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import respx
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from app.auth import current_user_id
from app.cloud_pdf import render_cloud_pdf
from app.config import settings, _read_config_json, save_config_file
from app.crypto import encrypt, decrypt
from app.database import Database
from app.db_engine import make_async_engine, make_sync_engine
from app.models import Resume, RenderDraft
from app.services.page_fit import RenderDraftStore


def test_cloud_config_shared_between_workers(isolated_backend_state, monkeypatch):
    db = isolated_backend_state
    monkeypatch.setattr(settings, 'database_url', 'postgresql://synthetic.test/db')
    save_config_file({'language': 'es', 'api_key': 'must-not-persist', 'api_keys': {'x': 'secret'}})
    other = Database(db_path=db.db_path)
    assert other.get_cloud_config() == {'language': 'es'}
    assert _read_config_json() == {'language': 'es'}
    from app.config_cache import load_config
    other.save_cloud_config({'language': 'en'})
    assert load_config() == {'language': 'en'}


def test_drafts_shared_with_ownership_and_expiry(isolated_backend_state, monkeypatch):
    db = isolated_backend_state
    monkeypatch.setattr(settings, 'database_url', 'postgresql://synthetic.test/db')
    owner = current_user_id.set('member-a')
    try:
        first, second = RenderDraftStore(), RenderDraftStore()
        token = first.put({'summary': 'Synthetic private draft'})
        assert second.get(token)['summary'] == 'Synthetic private draft'
        changed = current_user_id.set('member-b')
        try:
            assert second.get(token) is None
            second.discard(token)
        finally:
            current_user_id.reset(changed)
        assert first.get(token) is not None
        with db._sync_write_session() as session:
            row = session.get(RenderDraft, token)
            row.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
            session.commit()
        assert second.get(token) is None
        second.discard(token)
    finally:
        current_user_id.reset(owner)


def test_cloud_secret_stable_without_local_file(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'data_dir', tmp_path)
    monkeypatch.setattr(settings, 'database_url', 'postgresql://synthetic.test/db')
    monkeypatch.setattr(settings, 'encryption_key', Fernet.generate_key().decode())
    assert decrypt(encrypt('synthetic secret')) == 'synthetic secret'
    assert not (tmp_path / '.secret_key').exists()
    monkeypatch.setattr(settings, 'encryption_key', '')
    with pytest.raises(RuntimeError, match='ENCRYPTION_KEY'):
        encrypt('secret')


@pytest.mark.asyncio
async def test_postgres_engines_and_partial_default_index():
    url = 'postgresql://synthetic:fake@localhost:6543/postgres'
    sync = make_sync_engine(Path('/unused'), url)
    asynchronous = make_async_engine(Path('/unused'), url)
    try:
        assert sync.dialect.name == asynchronous.dialect.name == 'postgresql'
        index = next(i for i in Resume.__table__.indexes if i.name == 'ux_resumes_single_default_master')
        sql = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        assert 'WHERE is_default_master = true' in sql
    finally:
        sync.dispose()
        await asynchronous.dispose()


@pytest.mark.asyncio
@respx.mock
async def test_cloud_pdf_authenticates_exact_payload(monkeypatch):
    import hashlib, hmac, json
    monkeypatch.setattr(settings, 'frontend_base_url', 'https://frontend.example.test')
    monkeypatch.setattr(settings, 'pdf_renderer_url', 'https://frontend.example.test/internal/pdf')
    monkeypatch.setattr(settings, 'pdf_renderer_secret', 'synthetic-shared-secret')
    captured = []
    def renderer(request):
        captured.append(request)
        return httpx.Response(200, content=b'%PDF-1.7\nsynthetic', headers={'Content-Type': 'application/pdf'})
    route = respx.post(settings.pdf_renderer_url).mock(side_effect=renderer)
    result = await render_cloud_pdf('https://frontend.example.test/print/resumes/example?renderToken=fake', 'LETTER', '.resume-print', {'top': 10})
    assert result.startswith(b'%PDF-') and route.called
    sent = captured[0]
    assert sent.headers['x-render-signature'] == hmac.new(b'synthetic-shared-secret', sent.content, hashlib.sha256).hexdigest()
    assert json.loads(sent.content)['pageSize'] == 'LETTER'
    with pytest.raises(ValueError, match='origin'):
        await render_cloud_pdf('https://untrusted.example/print/resumes/example', 'A4', '.resume-print', {})
    route.mock(return_value=httpx.Response(200, text='not a PDF'))
    with pytest.raises(ValueError, match='invalid PDF'):
        await render_cloud_pdf('https://frontend.example.test/print/resumes/example', 'A4', '.resume-print', {})
