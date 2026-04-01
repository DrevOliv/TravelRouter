from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .auth import ensure_auth_config, get_session_secret, require_api_auth
from .env import load_dotenv
from .meta import router as meta_router
from .pages import protected_api as pages_protected_api
from .pages import public_api as pages_public_api
from .pages import router as pages_router


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


def create_app() -> FastAPI:
    load_dotenv()
    ensure_auth_config()

    router = APIRouter()
    api = APIRouter(prefix="/api")
    protected_api = APIRouter(dependencies=[Depends(require_api_auth)])

    router.include_router(pages_router)
    api.include_router(pages_public_api)
    protected_api.include_router(meta_router)
    protected_api.include_router(pages_protected_api)
    api.include_router(protected_api)

    app = FastAPI(
        title="Pi Travel Router API",
        description="API for the Pi Travel Router web UI, including Wi-Fi, Tailscale, Jellyfin, playback control, and rsync backups.",
        version="1.0.0",
        openapi_tags=[
            {"name": "auth", "description": "Authentication endpoints for the admin session."},
            {"name": "meta", "description": "App-level metadata and environment information."},
            {"name": "home", "description": "Home dashboard data and upstream Wi-Fi actions."},
            {"name": "settings", "description": "Wi-Fi, Tailscale, and Jellyfin configuration endpoints."},
            {"name": "media", "description": "Jellyfin browsing and playback start endpoints."},
            {"name": "remote", "description": "Playback transport and track-selection controls."},
            {"name": "rsync", "description": "Drive discovery and rsync backup job management."},
        ],
    )
    app.add_middleware(SessionMiddleware, secret_key=get_session_secret(), same_site="lax", https_only=False)
    app.mount("/static", NoCacheStaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")
    app.include_router(router)
    app.include_router(api)
    return app
