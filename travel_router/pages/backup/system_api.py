from ...rsync import get_all_jobs, list_drives


def backup_payload() -> dict:
    jobs = sorted(get_all_jobs(), key=lambda job: str(job.get("started_at") or ""), reverse=True)
    return {
        "drives": list_drives(),
        "jobs": jobs,
    }
