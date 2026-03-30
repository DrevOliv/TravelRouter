from fastapi import APIRouter, Depends

from ..auth import require_api_auth
from .api_auth import router as api_auth_router

from .api_home import router as api_home_router
from .api_import import router as api_import_router
from .api_media import router as api_media_router
from .api_meta import router as api_meta_router
from .api_remote import router as api_remote_router
from .api_settings import router as api_settings_router
from .pages import router as pages_router


router = APIRouter()
api = APIRouter(prefix="/api")
protected_api = APIRouter(dependencies=[Depends(require_api_auth)])

router.include_router(pages_router)
api.include_router(api_auth_router)
protected_api.include_router(api_meta_router)
protected_api.include_router(api_home_router)
protected_api.include_router(api_import_router)
protected_api.include_router(api_settings_router)
protected_api.include_router(api_media_router)
protected_api.include_router(api_remote_router)
api.include_router(protected_api)
