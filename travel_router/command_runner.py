import re
import shlex
import subprocess


URL_PATTERN = re.compile(r"https://\S+")


def extract_url(text: str) -> str:
    if not text:
        return ""
    match = URL_PATTERN.search(text)
    return match.group(0).rstrip(".,)") if match else ""


def command_result(command: str, stdout: str = "", stderr: str = "", ok: bool = True, auth_url: str = "") -> dict:
    return {
        "ok": ok,
        "stdout": stdout,
        "stderr": stderr,
        "command": command,
        "auth_url": auth_url,
    }


def demo_command_result(command: str, stdout: str = "", stderr: str = "", ok: bool = True, auth_url: str = "") -> dict:
    return command_result(command, stdout=stdout, stderr=stderr, ok=ok, auth_url=auth_url)


def run_command(command: list[str], timeout: int = 20) -> dict:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "stdout": "",
            "stderr": f"Missing command: {command[0]}",
            "command": " ".join(shlex.quote(part) for part in command),
            "auth_url": "",
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "stdout": "",
            "stderr": "Command timed out",
            "command": " ".join(shlex.quote(part) for part in command),
            "auth_url": "",
        }

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    auth_url = extract_url(stdout) or extract_url(stderr)

    return {
        "ok": completed.returncode == 0,
        "stdout": stdout,
        "stderr": stderr,
        "command": " ".join(shlex.quote(part) for part in command),
        "auth_url": auth_url,
    }
