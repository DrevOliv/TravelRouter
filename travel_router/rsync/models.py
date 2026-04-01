from enum import Enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    starting = "starting"
    running = "running"
    done = "done"
    error = "error"
    cancelled = "cancelled"


class DriveTransport(str, Enum):
    usb = "usb"
    sata = "sata"
    nvme = "nvme"


class Partition(BaseModel):
    name: str = Field(..., description="Partition name, e.g. 'sda1'.")
    size: str = Field(..., description="Partition size, e.g. '512 GB'.")
    mountpoint: Optional[str] = Field(None, description="Current mountpoint if mounted, e.g. '/mnt/backup_source/sda'.")
    fstype: Optional[str] = Field(None, description="Filesystem type, e.g. 'ext4', 'ntfs', 'exfat'.")


class Drive(BaseModel):
    name: str = Field(..., description="Block device name, e.g. 'sda'.")
    size: str = Field(..., description="Total drive size, e.g. '1.0 TB'.")
    label: Optional[str] = Field(None, description="Drive label if set.")
    transport: Optional[DriveTransport] = Field(None, description="Connection type of the drive.")
    partitions: list[Partition] = Field(default_factory=list, description="List of partitions on the drive.")


class DriveListResponse(BaseModel):
    drives: list[Drive] = Field(default_factory=list, description="List of all connected drives.")


class StartBackupRequest(BaseModel):
    device: str = Field(..., description="Block device name to back up, e.g. 'sda'.")


class StopJobRequest(BaseModel):
    job_id: str = Field(..., description="UUID of the job to stop if running, or remove if already done.")


class JobProgress(BaseModel):
    job_id: str = Field(..., description="Unique UUID identifying this backup job.")
    device: str = Field(..., description="Block device being backed up, e.g. 'sda'.")
    status: JobStatus = Field(..., description="Current status of the job.")
    started_at: datetime = Field(..., description="ISO timestamp of when the job started.")
    finished_at:             Optional[datetime] = Field(None, description="ISO timestamp of when the job finished. Null if still running.")
    percent: int = Field(0, ge=0, le=100, description="Overall backup progress as a percentage.")
    speed: Optional[str] = Field(None, description="Current transfer speed, e.g. '45.6MB/s'.")
    eta: Optional[str] = Field(None, description="Estimated time remaining, e.g. '0:12:34'.")
    bytes_transferred: int = Field(0, description="Total bytes transferred so far.")
    bytes_transferred_human: str             = Field("0 B", description="Human-readable bytes transferred, e.g. '1.1 GB'.")
    files_transferred: int = Field(0, description="Number of files transferred so far.")
    files_remaining: Optional[int] = Field(None, description="Number of files still to transfer. Null until rsync has scanned all files.")
    total_files: Optional[int] = Field(None, description="Total number of files to transfer. Null until rsync has scanned all files.")
    current_file: Optional[str] = Field(None, description="Path of the file currently being transferred.")
    error: Optional[str] = Field(None, description="Error message if the job failed. Null otherwise.")


class StartBackupResponse(BaseModel):
    job_id: str = Field(..., description="UUID of the newly created backup job.")


class StopJobResponse(BaseModel):
    message: str = Field(..., description="Human-readable result of the stop/remove operation.")


class JobListResponse(BaseModel):
    jobs: list[JobProgress] = Field(..., description="List of all jobs and their current progress.")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Human-readable error message.")
