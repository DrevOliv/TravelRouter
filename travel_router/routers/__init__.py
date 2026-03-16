from fastapi import APIRouter

from .api_home import router as api_home_router
from .api_media import router as api_media_router
from .api_meta import router as api_meta_router
from .api_remote import router as api_remote_router
from .api_settings import router as api_settings_router
from .pages import router as pages_router


router = APIRouter()
api = APIRouter(prefix="/api")

router.include_router(pages_router)
api.include_router(api_meta_router)
api.include_router(api_home_router)
api.include_router(api_settings_router)
api.include_router(api_media_router)
api.include_router(api_remote_router)
