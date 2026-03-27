from fastapi import APIRouter, Query

from ..api_models import (
    ActionResponse,
    ImportJobsResponse,
    ImportMountBody,
    ImportResponse,
    ImportUploadFilesBody,
    ImportUploadFolderBody,
)
from ..screen_data import action_payload, import_payload
from ..system_apis import import_job_manager, mount_import_device, unmount_import_device


router = APIRouter()


@router.get(
    "/import",
    response_model=ImportResponse,
    tags=["import"],
    summary="Get import screen data",
    description="Returns the SD card import screen payload including removable devices, current source browser state, transfer settings summary, and upload queue jobs.",
)
async def api_import(device: str = Query(default=""), source: str = Query(default="")):
    return import_payload(device_path=device.strip() or None, source_path=source.strip() or None)


@router.get(
    "/import/jobs",
    response_model=ImportJobsResponse,
    tags=["import"],
    summary="Get import jobs",
    description="Returns the current upload queue and recent job history for SD card imports.",
)
async def api_import_jobs():
    return {"jobs": import_job_manager.list_jobs()}


@router.post(
    "/import/mount",
    response_model=ActionResponse,
    tags=["import"],
    summary="Mount removable SD card",
    description="Mounts the selected removable SD card partition so the Import screen can browse it.",
)
async def api_import_mount(body: ImportMountBody):
    result = mount_import_device(body.device_path.strip())
    return action_payload("import_mount", result, "SD card mounted", "Could not mount SD card", refresh="import")


@router.post(
    "/import/unmount",
    response_model=ActionResponse,
    tags=["import"],
    summary="Unmount removable SD card",
    description="Unmounts the selected removable SD card partition.",
)
async def api_import_unmount(body: ImportMountBody):
    result = unmount_import_device(body.device_path.strip())
    return action_payload("import_unmount", result, "SD card unmounted", "Could not unmount SD card", refresh="import")


@router.post(
    "/import/upload-folder",
    response_model=ActionResponse,
    tags=["import"],
    summary="Queue folder upload",
    description="Queues a recursive folder upload from the mounted SD card to the chosen destination path on TrueNAS.",
)
async def api_import_upload_folder(body: ImportUploadFolderBody):
    result = import_job_manager.enqueue_folder(body.device_path.strip(), body.source_path.strip(), body.destination_path.strip())
    if not result["ok"]:
        return {
            "ok": False,
            "action": "import_upload_folder",
            "message": "Could not queue folder upload",
            "detail": result["error"],
            "link": "",
            "refresh": None,
        }
    return {
        "ok": True,
        "action": "import_upload_folder",
        "message": "Folder upload queued",
        "detail": "",
        "link": "",
        "refresh": "import",
    }


@router.post(
    "/import/upload-files",
    response_model=ActionResponse,
    tags=["import"],
    summary="Queue photo upload",
    description="Queues the selected photo files from the current SD card folder for upload to the chosen destination path on TrueNAS.",
)
async def api_import_upload_files(body: ImportUploadFilesBody):
    result = import_job_manager.enqueue_files(body.device_path.strip(), body.source_path.strip(), body.selected_files, body.destination_path.strip())
    if not result["ok"]:
        return {
            "ok": False,
            "action": "import_upload_files",
            "message": "Could not queue selected photos",
            "detail": result["error"],
            "link": "",
            "refresh": None,
        }
    return {
        "ok": True,
        "action": "import_upload_files",
        "message": "Photo upload queued",
        "detail": "",
        "link": "",
        "refresh": "import",
    }


@router.post(
    "/import/jobs/{job_id}/retry",
    response_model=ActionResponse,
    tags=["import"],
    summary="Retry import job",
    description="Retries a failed, cancelled, or waiting import job.",
)
async def api_import_retry(job_id: str):
    if not import_job_manager.retry_job(job_id):
        return {
            "ok": False,
            "action": "import_job_retry",
            "message": "Could not retry upload",
            "detail": "Job not found.",
            "link": "",
            "refresh": None,
        }
    return {
        "ok": True,
        "action": "import_job_retry",
        "message": "Upload queued again",
        "detail": "",
        "link": "",
        "refresh": "import",
    }


@router.post(
    "/import/jobs/{job_id}/cancel",
    response_model=ActionResponse,
    tags=["import"],
    summary="Cancel import job",
    description="Cancels a queued or running import job.",
)
async def api_import_cancel(job_id: str):
    if not import_job_manager.cancel_job(job_id):
        return {
            "ok": False,
            "action": "import_job_cancel",
            "message": "Could not cancel upload",
            "detail": "Job not found.",
            "link": "",
            "refresh": None,
        }
    return {
        "ok": True,
        "action": "import_job_cancel",
        "message": "Upload cancelled",
        "detail": "",
        "link": "",
        "refresh": "import",
    }
