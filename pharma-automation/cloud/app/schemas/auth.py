from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    pharmacy_id: int
    invite_code: str = Field(..., min_length=1, max_length=20)
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=8)
    role: str = Field(default="STAFF", pattern=r"^(PHARMACIST|STAFF|ADMIN)$")


class RegisterResponse(BaseModel):
    id: int
    pharmacy_id: int
    username: str
    role: str


class LoginRequest(BaseModel):
    pharmacy_id: int
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    refresh_token: str


class LogoutResponse(BaseModel):
    detail: str = "Logged out successfully"
