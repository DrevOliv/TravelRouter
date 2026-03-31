from pathlib import Path

from fastapi.responses import FileResponse


STATIC_INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"
LOGIN_INDEX = Path(__file__).resolve().parent.parent / "static" / "login.html"


def shell_response() -> FileResponse:
    return FileResponse(
        STATIC_INDEX,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def login_response() -> FileResponse:
    return FileResponse(
        LOGIN_INDEX,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
