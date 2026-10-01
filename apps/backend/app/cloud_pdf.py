"""Authenticated PDF rendering on the paired Vercel frontend."""
import hashlib
import hmac
import json
import time
from urllib.parse import urlparse

import httpx

from app.config import settings


async def render_cloud_pdf(url: str, page_size: str, selector: str, margins: dict | None) -> bytes:
    if not settings.pdf_renderer_secret:
        raise ValueError("PDF_RENDERER_SECRET is required")
    target = urlparse(url)
    frontend = urlparse(settings.frontend_base_url)
    if (target.scheme, target.netloc) != (frontend.scheme, frontend.netloc):
        raise ValueError("Invalid print origin")
    renderer = urlparse(settings.pdf_renderer_url)
    if (renderer.scheme, renderer.netloc) != (frontend.scheme, frontend.netloc) or renderer.path != "/internal/pdf":
        raise ValueError("Invalid renderer origin")
    payload = json.dumps({"url": url, "pageSize": page_size, "selector": selector,
        "margins": margins or {}, "timestamp": int(time.time())}, separators=(",", ":"))
    signature = hmac.new(settings.pdf_renderer_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    headers = {"Content-Type": "application/json", "X-Render-Signature": signature}
    # Protection bypass is kept server-only. No redirects are followed.
    import os
    bypass = os.environ.get("FRONTEND_PROTECTION_BYPASS_SECRET")
    if bypass:
        headers["X-Vercel-Protection-Bypass"] = bypass
    async with httpx.AsyncClient(timeout=110, follow_redirects=False, trust_env=False) as client:
        response = await client.post(settings.pdf_renderer_url, content=payload, headers=headers)
        response.raise_for_status()
        if response.headers.get("content-type", "").split(";")[0] != "application/pdf" or not response.content.startswith(b"%PDF-"):
            raise ValueError("Renderer returned invalid PDF data")
        return response.content
