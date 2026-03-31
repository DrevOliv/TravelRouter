def action_payload(
    action: str,
    result: dict,
    success_message: str,
    error_message: str,
    detail: str = "",
    link: str = "",
    refresh: str | None = None,
) -> dict:
    return {
        "ok": result["ok"],
        "action": action,
        "message": success_message if result["ok"] else error_message,
        "detail": detail or result.get("stderr") or result.get("stdout") or "",
        "link": link or result.get("auth_url", ""),
        "refresh": refresh,
    }
