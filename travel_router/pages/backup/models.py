from pydantic import BaseModel, Field

from ...rsync.models import Drive, DriveListResponse, JobProgress


class BackupResponse(BaseModel):
    drives: list[Drive] = Field(default_factory=list, description="Connected drives available for backup.")
    jobs: list[JobProgress] = Field(default_factory=list, description="Current and recent backup jobs.")


__all__ = ["BackupResponse", "DriveListResponse"]
