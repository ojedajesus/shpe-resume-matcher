"""FastAPI application entry point."""

import asyncio
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send

# Fix for Windows: Use ProactorEventLoop for subprocess support (Playwright)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.ai_budget import operation_error_content
from app.config import settings
from app.database import DatabaseBusyError, db
from app.pdf import close_pdf_renderer, init_pdf_renderer
from app.routers import (
    applications_router,
    config_router,
    enrichment_router,
    health_router,
    jobs_router,
    resume_wizard_router,
    resumes_router,
)
from app.routers.resumes import drain_processing_cleanup_tasks
from app.auth import current_is_admin, current_user_id, resolve_session, router as auth_router
from app.render_auth import verify_render_token


class AuthenticationMiddleware:
    """Require server sessions and same-session CSRF on every state change."""
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Keep authentication in the request task so cancellation awaits route
        # cleanup and owner context remains valid through that cleanup.
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        public = request.url.path in {"/api/v1/health", "/api/v1/auth/login", "/api/v1/auth/accept-invitation"}
        if not settings.auth_required or public:
            if public and request.method == "POST":
                origin = request.headers.get("origin")
                allowed = {value.rstrip("/") for value in settings.effective_cors_origins}
                if origin and origin.rstrip("/") not in allowed:
                    return await JSONResponse({"detail": "Origin not allowed"}, status_code=403)(scope, receive, send)
            return await self.app(scope, receive, send)
        render_token = request.headers.get("x-internal-render-token")
        if render_token and request.method == "GET" and request.url.path == "/api/v1/resumes":
            resume_id = request.query_params.get("resume_id", "")
            render_owner = verify_render_token(render_token, resume_id)
            if render_owner:
                owner_token = current_user_id.set(render_owner)
                try:
                    return await self.app(scope, receive, send)
                finally:
                    current_user_id.reset(owner_token)
        resolved = resolve_session(request.cookies.get("shpe_session"))
        if resolved is None:
            return await JSONResponse({"detail": "Authentication required"}, status_code=401)(scope, receive, send)
        user, session = resolved
        admin_config_routes = {
            ("GET", "/api/v1/config/llm-api-key"), ("PUT", "/api/v1/config/llm-api-key"),
            ("POST", "/api/v1/config/llm-test"), ("GET", "/api/v1/config/api-keys"),
            ("POST", "/api/v1/config/api-keys"), ("DELETE", "/api/v1/config/api-keys"),
            ("POST", "/api/v1/config/reset"),
        }
        is_provider_key_delete = request.method == "DELETE" and request.url.path.startswith("/api/v1/config/api-keys/")
        shared_config_write = request.method in {"PUT", "POST", "DELETE"} and request.url.path.startswith("/api/v1/config/")
        if ((request.method, request.url.path) in admin_config_routes or is_provider_key_delete or shared_config_write) and not user.is_admin:
            return await JSONResponse({"detail": "Administrator access required"}, status_code=403)(scope, receive, send)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("x-csrf-token") != session.csrf_token:
            return await JSONResponse({"detail": "CSRF validation failed"}, status_code=403)(scope, receive, send)
        request.state.user, request.state.session = user, session
        owner_token = current_user_id.set(user.user_id)
        admin_token = current_is_admin.set(user.is_admin)
        try:
            return await self.app(scope, receive, send)
        finally:
            current_user_id.reset(owner_token)
            current_is_admin.reset(admin_token)


def _configure_application_logging() -> None:
    """Set application log level from configuration."""
    numeric_level = getattr(logging, settings.log_level, logging.INFO)
    logging.getLogger("app").setLevel(numeric_level)


_configure_application_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    # Startup
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    # Import a legacy TinyDB database into SQLite if present (idempotent).
    # Fail-fast on error: starting with an empty DB would look like data loss.
    from app.scripts.migrate_tinydb_to_sqlite import migrate as migrate_tinydb

    result = await migrate_tinydb()
    if result.get("status") == "migrated":
        logger.info("Startup data migration: %s", result)
    # Fold any legacy plaintext API keys into the encrypted store (idempotent,
    # non-clobbering), then strip them from config.json.
    from app.config import migrate_legacy_keys

    migrate_legacy_keys()
    # PDF renderer uses lazy initialization - will initialize on first use
    # await init_pdf_renderer()
    yield
    # Shutdown - wrap each cleanup in try-except to ensure all resources are released
    try:
        await drain_processing_cleanup_tasks()
    except Exception:
        logger.exception("Error draining processing cleanup")

    try:
        await close_pdf_renderer()
    except Exception as e:
        logger.error(f"Error closing PDF renderer: {e}")

    try:
        await db.close()
    except Exception as e:
        logger.error(f"Error closing database: {e}")


app = FastAPI(
    title="Resume Matcher API",
    description="AI-powered resume tailoring for job descriptions",
    version=__version__,
    lifespan=lifespan,
)
app.add_middleware(AuthenticationMiddleware)

@app.exception_handler(DatabaseBusyError)
async def database_busy_handler(request: Request, error: DatabaseBusyError) -> JSONResponse:
    logger.warning("Database write contention for %s", request.url.path, exc_info=error)
    return JSONResponse(
        status_code=503,
        content=operation_error_content(request, "Database is busy. Please retry shortly."),
        headers={"Retry-After": "1"},
    )


# CORS middleware - origins configurable via CORS_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.effective_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(config_router, prefix="/api/v1")
app.include_router(resumes_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(enrichment_router, prefix="/api/v1")
app.include_router(applications_router, prefix="/api/v1")
app.include_router(resume_wizard_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Resume Matcher API",
        "version": __version__,
        "docs": "/docs",
    }


def main():
    """Entry point for the project.scripts console script."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
