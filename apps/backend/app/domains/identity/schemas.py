"""Identity domain API contracts (Pydantic)."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr = Field(description="User email (validated)")
    password: str = Field(min_length=8, max_length=128, description="Password (min 8 chars)")
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserProfile(BaseModel):
    """Application-side user profile returned to clients."""

    id: str
    email: str
    full_name: str | None = None
    avatar_url: str | None = None
    auth_provider: str
    created_at: datetime | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile


class MessageResponse(BaseModel):
    message: str
