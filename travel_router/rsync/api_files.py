import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from .drives import list_drives
from .models import (
    DriveListResponse,
    ErrorResponse,
    JobListResponse,
    JobProgress,
    JobStatus,
    StartBackupRequest,
    StartBackupResponse,
    StopJobResponse,
)
from .system_api import get_all_jobs, get_job, start_backup, stop_job


router = APIRouter()


@router.get(
    "/drives",
    response_model=DriveListResponse,
    tags=["rsync"],
    summary="List connected drives",
    description="Returns block devices and partitions that can be used as backup sources.",
)
def api_get_drives():
    return {"drives": list_drives()}


@router.post(
    "/backup/start",
    response_model=StartBackupResponse,
    responses={400: {"model": ErrorResponse}},
    tags=["rsync"],
)
def api_start_backup(body: StartBackupRequest):
    job_id = start_backup(body.device)
    return StartBackupResponse(job_id=job_id)


@router.get(
    "/backup/jobs",
    response_model=JobListResponse,
    tags=["rsync"],
)
def api_get_all_jobs(status: Optional[JobStatus] = Query(None, description="Filter by job status")):
    jobs = get_all_jobs(status_filter=status)
    return JobListResponse(jobs=[JobProgress(**job) for job in jobs])


@router.get(
    "/backup/jobs/{job_id}",
    response_model=JobProgress,
    responses={404: {"model": ErrorResponse}},
    tags=["rsync"],
)
def api_get_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return JobProgress(**job)


@router.post(
    "/backup/jobs/{job_id}/stop",
    response_model=StopJobResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["rsync"],
)
def api_stop_job(job_id: str):
    success, message = stop_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return StopJobResponse(message=message)


@router.get("/backup/jobs/{job_id}/progress", tags=["rsync"])
async def backup_progress(job_id: str):
    async def stream():
        while True:
            job = get_job(job_id)
            if not job:
                data = ErrorResponse(error="job not found").model_dump_json()
                yield f"data: {data}\n\n"
                break

            progress = JobProgress(**job)
            yield f"data: {progress.model_dump_json()}\n\n"

            if progress.status in (JobStatus.done, JobStatus.error):
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream")
