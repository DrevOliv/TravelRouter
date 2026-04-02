from pydantic import BaseModel, Field


class ExitNodeSelectionBody(BaseModel):
    exit_node: str = Field("", description="Preferred Tailscale exit node DNS name or IP to save in settings.")


class ExitNodeToggleBody(BaseModel):
    enabled: bool = Field(..., description="Turn the saved exit node on or off.")


class TailscaleConfig(BaseModel):
    advertise_exit_node: bool = Field(False, description="Legacy config flag; not used by the current UI.")
    current_exit_node: str = Field("", description="Currently selected Tailscale exit node.")
    exit_node_enabled: bool = Field(False, description="Whether the saved exit node should be actively used.")


class ExitNode(BaseModel):
    value: str = Field(..., description="Node identifier sent back when selecting this exit node.")
    label: str = Field(..., description="Human-readable exit node label.")
    online: bool = Field(..., description="Whether the exit node is currently online.")
