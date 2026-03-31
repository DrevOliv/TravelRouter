from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------

class JobStatus(str, Enum):
    starting  = "starting"
    running   = "running"
    done      = "done"
    error     = "error"
    cancelled = "cancelled"


# ------------------------------------------------------------------
# Backup — Requests
# ------------------------------------------------------------------

class StartBackupRequest(BaseModel):
    device: str = Field(..., description="Block device name to back up, e.g. 'sda'.")


class StopJobRequest(BaseModel):
    job_id: str = Field(..., description="UUID of the job to stop if running, or remove if already done.")


# ------------------------------------------------------------------
# Backup — Job progress / response
# ------------------------------------------------------------------

class JobProgress(BaseModel):
    job_id:                  str              = Field(...,   description="Unique UUID identifying this backup job.")
    device:                  str              = Field(...,   description="Block device being backed up, e.g. 'sda'.")
    status:                  JobStatus        = Field(...,   description="Current status of the job.")
    started_at:              datetime         = Field(...,   description="ISO timestamp of when the job started.")
    finished_at:             Optional[datetime] = Field(None, description="ISO timestamp of when the job finished. Null if still running.")
    percent:                 int              = Field(0,     ge=0, le=100, description="Overall backup progress as a percentage.")
    speed:                   Optional[str]   = Field(None,  description="Current transfer speed, e.g. '45.6MB/s'.")
    eta:                     Optional[str]   = Field(None,  description="Estimated time remaining, e.g. '0:12:34'.")
    bytes_transferred:       int             = Field(0,     description="Total bytes transferred so far.")
    bytes_transferred_human: str             = Field("0 B", description="Human-readable bytes transferred, e.g. '1.1 GB'.")
    files_transferred:       int             = Field(0,     description="Number of files transferred so far.")
    files_remaining:         Optional[int]   = Field(None,  description="Number of files still to transfer. Null until rsync has scanned all files.")
    total_files:             Optional[int]   = Field(None,  description="Total number of files to transfer. Null until rsync has scanned all files.")
    current_file:            Optional[str]   = Field(None,  description="Path of the file currently being transferred.")
    error:                   Optional[str]   = Field(None,  description="Error message if the job failed. Null otherwise.")


class StartBackupResponse(BaseModel):
    job_id: str = Field(..., description="UUID of the newly created backup job.")


class StopJobResponse(BaseModel):
    message: str = Field(..., description="Human-readable result of the stop/remove operation.")


class JobListResponse(BaseModel):
    jobs: list[JobProgress] = Field(..., description="List of all jobs and their current progress.")


# ------------------------------------------------------------------
# Generic
# ------------------------------------------------------------------

class ErrorResponse(BaseModel):
    error: str = Field(..., description="Human-readable error message.")