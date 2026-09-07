from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

OAuthProviderName = Literal["google", "github"]


class RegisterRequest(BaseModel):
    """Create a new account with email and password."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "user@moziketo.ir",
                    "password": "securepass1",
                    "display_name": "کاربر موزیکتو",
                }
            ]
        }
    )

    email: EmailStr = Field(description="Account email (unique, lowercased on save)")
    password: str = Field(min_length=8, max_length=128, description="Minimum 8 characters")
    display_name: str = Field(min_length=1, max_length=200, description="Display name in UI")


class RegisterResponse(BaseModel):
    """Registration result — may include dev-only verification token."""

    user: "UserResponse"
    verify_token: str | None = Field(
        default=None,
        description="Dev/stage only when SMTP is disabled",
    )
    verify_expires_in: int | None = None


class LoginRequest(BaseModel):
    """Email/password login — returns JWT access + refresh tokens."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"email": "user@moziketo.ir", "password": "securepass1"}]
        }
    )

    email: EmailStr
    password: str = Field(description="Account password")


class RefreshRequest(BaseModel):
    """Rotate tokens using a valid refresh token (single-use)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                }
            ]
        }
    )

    refresh_token: str = Field(description="Refresh token from login or OAuth exchange")


class TokenResponse(BaseModel):
    """JWT pair for authenticated API calls."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                }
            ]
        }
    )

    access_token: str = Field(description="Short-lived JWT for Bearer auth (default 15 min)")
    refresh_token: str = Field(description="Long-lived token for /auth/refresh (default 30 days)")
    token_type: str = Field(default="bearer", examples=["bearer"])


class OAuthAccountSummary(BaseModel):
    provider: str
    linked_at: datetime


class UserResponse(BaseModel):
    """Public user profile."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "user@moziketo.ir",
                    "display_name": "کاربر موزیکتو",
                    "is_active": True,
                    "email_verified": False,
                    "has_password": True,
                    "oauth_providers": [],
                }
            ]
        }
    )

    id: str = Field(description="User UUID")
    email: str
    display_name: str
    is_active: bool = Field(description="Inactive users cannot log in")
    email_verified: bool = Field(description="Soft verification flag — login not blocked")
    has_password: bool = Field(description="False for OAuth-only accounts")
    oauth_providers: list[str] = Field(default_factory=list)
    avatar_url: str | None = None


class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    avatar_url: str | None = Field(default=None, max_length=500)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class SetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    """Request a password reset link/token for the given email."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"email": "user@moziketo.ir"}]}
    )

    email: EmailStr = Field(description="Registered account email")


class ForgotPasswordResponse(BaseModel):
    """Dev/stage only — production returns 204 with no body when email is sent."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "reset_token": "xK9mP2nQ7vR4sT1uW8yZ3aB6cD0eF5gH",
                    "expires_in": 3600,
                }
            ]
        }
    )

    reset_token: str = Field(
        description="One-time reset token (only returned when APP_ENV != production or DEBUG=true)"
    )
    expires_in: int = Field(description="Token TTL in seconds", examples=[3600])


class ResetPasswordRequest(BaseModel):
    """Set a new password using a reset token from forgot-password."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "token": "xK9mP2nQ7vR4sT1uW8yZ3aB6cD0eF5gH",
                    "new_password": "newsecure1",
                }
            ]
        }
    )

    token: str = Field(min_length=16, description="Reset token from forgot-password")
    new_password: str = Field(min_length=8, max_length=128, description="New account password")


class VerifyEmailRequestResponse(BaseModel):
    """Dev/stage only — production sends email with no token in response."""

    verify_token: str
    expires_in: int


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr


class ChangeEmailRequestResponse(BaseModel):
    change_email_token: str | None = None
    expires_in: int | None = None


class DeleteAccountRequest(BaseModel):
    password: str | None = None
    confirm: bool = False


class UserExportResponse(BaseModel):
    profile: dict
    favorites: list[str]
    playlists: list[dict]
    play_history: list[dict]


class OAuthExchangeRequest(BaseModel):
    """Exchange one-time OAuth code (from frontend callback) for JWT tokens."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"code": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"}]
        }
    )

    code: str = Field(
        min_length=16,
        description="Single-use code from redirect to OAUTH_FRONTEND_CALLBACK_URL?code=…",
    )
