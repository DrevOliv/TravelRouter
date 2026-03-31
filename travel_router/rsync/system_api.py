import subprocess, threading, re, json, uuid
from datetime import datetime

progress_store = {}
process_store  = {}   # tracks live subprocess handles for cancellation


def humanize_bytes(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


def parse_progress2(line: str, state: dict) -> dict:
    overall = re.match(
        r"^\s*([\d,]+)\s+(\d+)%\s+([\d.]+\s*\S+/s)\s+([\d:]+|\-\-:--:--)"
        r"(?:\s+\(xfr#(\d+),\s*to-chk=(\d+)/(\d+)\))?",
        line
    )
    if overall:
        bytes_transferred = int(overall.group(1).replace(",", ""))
        percent           = int(overall.group(2))
        speed             = overall.group(3).strip()
        eta               = overall.group(4)
        xfr_index         = int(overall.group(5)) if overall.group(5) else state.get("files_transferred", 0)
        remaining         = int(overall.group(6)) if overall.group(6) else None
        total_files       = int(overall.group(7)) if overall.group(7) else state.get("total_files")
        files_done        = (total_files - remaining) if (total_files and remaining is not None) else xfr_index

        state.update({
            "bytes_transferred":       bytes_transferred,
            "bytes_transferred_human": humanize_bytes(bytes_transferred),
            "percent":                 percent,
            "speed":                   speed,
            "eta":                     eta,
            "files_transferred":       files_done,
            "files_remaining":         remaining,
            "total_files":             total_files,
            "current_line":            line.strip(),
            "status":                  "running",
        })
        return state

    if not line.startswith(" ") and line.strip():
        state["current_file"] = line.strip()

    return state


def get_all_jobs(status_filter: str = None) -> list:
    jobs = list(progress_store.values())
    if status_filter:
        jobs = [j for j in jobs if j.get("status") == status_filter]
    return jobs


def get_job(job_id: str) -> dict | None:
    return progress_store.get(job_id)


def start_backup(device: str) -> str:
    job_id = str(uuid.uuid4())

    progress_store[job_id] = {
        "job_id":                  job_id,
        "device":                  device,
        "status":                  "starting",
        "started_at":              datetime.now().isoformat(),
        "finished_at":             None,
        "percent":                 0,
        "speed":                   None,
        "eta":                     None,
        "bytes_transferred":       0,
        "bytes_transferred_human": "0 B",
        "files_transferred":       0,
        "files_remaining":         None,
        "total_files":             None,
        "current_file":            None,
        "error":                   None,
    }

    thread = threading.Thread(target=_run_backup, args=(device, job_id), daemon=True)
    thread.start()
    return job_id


def stop_job(job_id: str) -> tuple[bool, str]:
    """
    - If job is running  → kill the process, mark cancelled, remove from store
    - If job is done/error → just remove from store
    Returns (success, message)
    """
    job = progress_store.get(job_id)
    if not job:
        return False, "job not found"

    status = job.get("status")

    if status == "running" or status == "starting":
        proc = process_store.get(job_id)
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        process_store.pop(job_id, None)

    progress_store.pop(job_id, None)
    return True, f"job {job_id} {'cancelled and ' if status == 'running' else ''}removed"


TRUENAS_USER = "backupuser"
TRUENAS_HOST = "192.168.1.x"
TRUENAS_PATH = "/mnt/pool/backups"


def _run_backup(device: str, job_id: str):
    source = f"/mnt/backup_source/{device}/"
    dest   = f"{TRUENAS_USER}@{TRUENAS_HOST}:{TRUENAS_PATH}/{device}/"

    cmd = [
        "rsync", "-avz", "--delete",
        "--info=progress2",
        "--info=name1",
        "--no-inc-recursive",
        "-e", "ssh -i /home/pi/.ssh/truenas_key -o StrictHostKeyChecking=no",
        source, dest,
    ]

    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1
        )
        process_store[job_id] = process
        state = progress_store[job_id]
        state["status"] = "running"

        for line in process.stdout:
            if job_id not in progress_store:
                break   # job was stopped mid-run
            parse_progress2(line, state)

        stderr_output = process.stderr.read()
        process.wait()
        process_store.pop(job_id, None)

        if job_id not in progress_store:
            return  # was removed by stop_job, don't write back

        if process.returncode == 0:
            state["status"]  = "done"
            state["percent"] = 100
        else:
            state["status"] = "error"
            state["error"]  = stderr_output.strip()

        state["finished_at"] = datetime.now().isoformat()

    except Exception as e:
        if job_id in progress_store:
            progress_store[job_id]["status"] = "error"
            progress_store[job_id]["error"]  = str(e)
        process_store.pop(job_id, None)