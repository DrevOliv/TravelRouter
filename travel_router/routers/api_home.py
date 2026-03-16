from fastapi import APIRouter

from ..api_models import WifiConnectBody
from ..screen_data import action_payload, home_payload
from ..system_api import connect_wifi, load_settings


router = APIRouter()


@router.get("/home")
async def api_home():
    return home_payload()


@router.post("/wifi/connect")
async def api_wifi_connect(body: WifiConnectBody):
    settings = load_settings()
    result = connect_wifi(settings["wifi"]["upstream_interface"], body.ssid.strip(), body.password.strip() or None)
    clean_ssid = body.ssid.strip() or "network"
    return action_payload("wifi_connect", result, f"Connected to {clean_ssid}", "Wi-Fi connection failed", refresh="home")
