from pydantic import BaseModel, Field

from ..media.models import JellyfinConfig
from ..tailscale.models import TailscaleConfig
from ..wifi.models import WifiConfig


class ActionResponse(BaseModel):
    ok: bool = Field(..., description="Whether the action succeeded.")
    action: str = Field(..., description="Frontend action identifier.")
    message: str = Field(..., description="Short human-readable outcome message.")
    detail: str = Field("", description="Longer detail or command output.")
    link: str = Field("", description="Optional follow-up URL.")
    refresh: str | None = Field(None, description="Suggested screen to refresh after success.")


class CommandResult(BaseModel):
    ok: bool = Field(..., description="Whether the underlying command or system call succeeded.")
    stdout: str = Field("", description="Standard output or equivalent response text.")
    stderr: str = Field("", description="Standard error or equivalent failure text.")
    command: str = Field("", description="Command string or synthetic operation label.")
    auth_url: str = Field("", description="Optional URL extracted from the command output.")


class AppSettings(BaseModel):
    wifi: WifiConfig
    tailscale: TailscaleConfig
    jellyfin: JellyfinConfig
