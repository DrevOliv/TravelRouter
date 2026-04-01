from fastapi import Request

from .core import SESSION_KEY, change_password, verify_password


def login(request: Request, password: str) -> dict:
    if not verify_password(password):
        return {
            "ok": False,
            "action": "auth_login",
            "message": "Login failed",
            "detail": "Incorrect password.",
            "link": "",
            "refresh": None,
        }

    request.session[SESSION_KEY] = True
    return {"ok": True, "action": "auth_login", "message": "Logged in", "detail": "", "link": "", "refresh": None}


def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True, "action": "auth_logout", "message": "Logged out", "detail": "", "link": "", "refresh": None}


def update_password(new_password: str, confirm_password: str) -> dict:
    if new_password != confirm_password:
        return {
            "ok": False,
            "action": "auth_password",
            "message": "Password change failed",
            "detail": "New passwords do not match.",
            "link": "",
            "refresh": None,
        }

    ok, detail = change_password(new_password)
    return {
        "ok": ok,
        "action": "auth_password",
        "message": "Password updated" if ok else "Password change failed",
        "detail": detail if not ok else "",
        "link": "",
        "refresh": "settings" if ok else None,
    }
