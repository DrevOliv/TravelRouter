from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .auth import ensure_auth_config, get_session_secret
from .env import load_dotenv
from .routers import api, router
from .system_apis import ensure_import_dirs, import_job_manager


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

    app = FastAPI(
        title="Pi Travel Router API",
        description="API for the Pi Travel Router web UI, including Wi-Fi, Tailscale, Jellyfin, and playback control.",
        version="1.0.0",
        openapi_tags=[
            {"name": "meta", "description": "App-level metadata and environment information."},
            {"name": "home", "description": "Home dashboard data and upstream Wi-Fi actions."},
            {"name": "import", "description": "SD card import, browsing, and resumable upload queue endpoints."},
            {"name": "settings", "description": "Wi-Fi, Tailscale, and Jellyfin configuration endpoints."},
            {"name": "media", "description": "Jellyfin browsing and playback start endpoints."},
            {"name": "remote", "description": "Playback transport and track-selection controls."},
        ],
    )
    app.add_middleware(SessionMiddleware, secret_key=get_session_secret(), same_site="lax", https_only=False)
    ensure_import_dirs()
    app.mount("/static", NoCacheStaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")
    app.include_router(router)
    app.include_router(api)
    app.add_event_handler("startup", import_job_manager.start)
    app.add_event_handler("shutdown", import_job_manager.stop)
    return app
