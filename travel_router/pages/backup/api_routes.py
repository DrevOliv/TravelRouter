from fastapi import APIRouter

from .models import BackupResponse
from .system_api import backup_payload


api_router = APIRouter()


@api_router.get(
    "/backup",
    response_model=BackupResponse,
    tags=["rsync"],
    summary="Get backup page data",
    description="Returns connected drives and recent rsync backup jobs for the backup page.",
)
def api_backup():
    return backup_payload()
