from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .env import load_dotenv
from .routers import api, router


def create_app() -> FastAPI:
    load_dotenv()

    app = FastAPI(title="Pi Travel Router")
    app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")
    app.include_router(router)
    app.include_router(api)
    return app
