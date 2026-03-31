from pydantic import BaseModel, Field


class MetaResponse(BaseModel):
    demo_mode: bool = Field(..., description="Whether the app is currently running in demo mode.")
