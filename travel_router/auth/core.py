import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request

from ..config_store import load_config, save_config


DEFAULT_ADMIN_PASSWORD = "admin"
SESSION_KEY = "authenticated"


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()


def ensure_auth_config() -> dict:
    config = load_config()
    auth = config.setdefault("auth", {})
    changed = False

    if not auth.get("password_salt"):
        auth["password_salt"] = secrets.token_hex(16)
        changed = True
    if not auth.get("password_hash"):
        auth["password_hash"] = hash_password(DEFAULT_ADMIN_PASSWORD, auth["password_salt"])
        changed = True
    if not auth.get("session_secret"):
        auth["session_secret"] = secrets.token_hex(32)
        changed = True

    if changed:
        save_config(config)
    return auth


def get_session_secret() -> str:
    return ensure_auth_config()["session_secret"]


def verify_password(password: str) -> bool:
    auth = ensure_auth_config()
    expected = auth["password_hash"]
    computed = hash_password(password, auth["password_salt"])
    return hmac.compare_digest(computed, expected)


def change_password(new_password: str) -> tuple[bool, str]:
    if len(new_password) < 8:
        return False, "New password must be at least 8 characters."

    config = load_config()
    salt = secrets.token_hex(16)
    config["auth"]["password_salt"] = salt
    config["auth"]["password_hash"] = hash_password(new_password, salt)
    save_config(config)
    return True, "Password updated."


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get(SESSION_KEY))


def require_api_auth(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
