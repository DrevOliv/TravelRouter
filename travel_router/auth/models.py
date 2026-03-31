from pydantic import BaseModel, Field


class AuthLoginBody(BaseModel):
    password: str = Field(..., description="Admin password used to log in to the control panel.")


class PasswordChangeBody(BaseModel):
    new_password: str = Field(..., description="New admin password.")
    confirm_password: str = Field(..., description="Repeat of the new admin password.")
