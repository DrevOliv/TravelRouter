from fastapi import APIRouter

from ...settings_store import load_settings
from .models import HomeResponse, WifiLiveResponse
from .system_api import home_payload, wifi_live_payload


api_router = APIRouter()


@api_router.get(
    "/home",
    response_model=HomeResponse,
    tags=["home"],
    summary="Get home dashboard data",
    description="Returns the Home screen payload including current upstream Wi-Fi, scanned networks, connected devices, exit-node choices, and Wi-Fi interface settings.",
)
async def api_home():
    return home_payload()


@api_router.get(
    "/home/wifi-live",
    response_model=WifiLiveResponse,
    tags=["home"],
    summary="Get live Wi-Fi dashboard data",
    description="Returns only the current upstream Wi-Fi state and nearby scanned networks for lightweight Home screen polling.",
)
async def api_home_wifi_live():
    settings = load_settings()
    return wifi_live_payload(settings["wifi"]["upstream_interface"])
