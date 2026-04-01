from fastapi import APIRouter

from .backup import api_router as backup_api_router, page_router as backup_page_router
from .home import api_router as home_api_router, page_router as home_page_router
from .login import api_router as login_api_router, page_router as login_page_router
from .media import api_router as media_api_router, page_router as media_page_router
from .remote import api_router as remote_api_router, page_router as remote_page_router
from .settings import api_router as settings_api_router, page_router as settings_page_router


router = APIRouter()
public_api = APIRouter()
protected_api = APIRouter()

router.include_router(login_page_router)
router.include_router(home_page_router)
router.include_router(backup_page_router)
router.include_router(settings_page_router)
router.include_router(media_page_router)
router.include_router(remote_page_router)

public_api.include_router(login_api_router)
protected_api.include_router(home_api_router)
protected_api.include_router(settings_api_router)
protected_api.include_router(media_api_router)
protected_api.include_router(remote_api_router)
protected_api.include_router(backup_api_router)

__all__ = ["protected_api", "public_api", "router"]
