from pydantic import BaseModel, Field

from ...common.models import AppSettings
from ...media.models import JellyfinSummary


class SettingsResponse(BaseModel):
    settings: AppSettings
    jellyfin: JellyfinSummary
