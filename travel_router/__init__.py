from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .env import load_dotenv
from .routers import api, router


def create_app() -> FastAPI:
    load_dotenv()

    app = FastAPI(
        title="Pi Travel Router API",
        description="API for the Pi Travel Router web UI, including Wi-Fi, Tailscale, Jellyfin, and playback control.",
        version="1.0.0",
        openapi_tags=[
            {"name": "meta", "description": "App-level metadata and environment information."},
            {"name": "home", "description": "Home dashboard data and upstream Wi-Fi actions."},
            {"name": "settings", "description": "Wi-Fi, Tailscale, and Jellyfin configuration endpoints."},
            {"name": "media", "description": "Jellyfin browsing and playback start endpoints."},
            {"name": "remote", "description": "Playback transport and track-selection controls."},
        ],
    )
    app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")
    app.include_router(router)
    app.include_router(api)
    return app
