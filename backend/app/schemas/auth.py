from pydantic import BaseModel, Field, model_validator


class LoginRequest(BaseModel):
    # Accept both field names for backwards compatibility with frontend
    auth_id: str | None = None
    username: str | None = None  # frontend sends "username"
    password: str

    @model_validator(mode="after")
    def coerce_auth_id(self) -> "LoginRequest":
        # Use whichever identifier was provided
        if not self.auth_id and self.username:
            self.auth_id = self.username
        if not self.auth_id:
            raise ValueError("auth_id or username is required")
        return self


class RegisterRequest(BaseModel):
    auth_id: str
    username: str
    department: str
    scene: str = "frontend"
    description: str = ""
    password: str


class RecoverRequest(BaseModel):
    auth_id: str
    username: str
    department: str
    scene: str = "frontend"
    new_password: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserInfo(BaseModel):
    id: int
    auth_id: str | None = None
    username: str
    department: str = ""
    scene: str = ""
    description: str = ""
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
