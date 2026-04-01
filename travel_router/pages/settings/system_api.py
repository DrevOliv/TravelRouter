from ...settings_store import load_settings


def settings_payload() -> dict:
    settings = load_settings()
    jellyfin_configured = bool(
        settings["jellyfin"]["server_url"] and settings["jellyfin"]["api_key"] and settings["jellyfin"]["user_id"]
    )
    return {
        "settings": settings,
        "jellyfin": {
            "configured": jellyfin_configured,
            "ok": False,
            "error": "Checking Jellyfin server..." if jellyfin_configured else "Configure Jellyfin below.",
        },
    }
