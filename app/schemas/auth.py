from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

OAuthProviderName = Literal["google", "apple", "github"]


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
                }
            ]
        }
    )

    id: str = Field(description="User UUID")
    email: str
    display_name: str
    is_active: bool = Field(description="Inactive users cannot log in")


class ForgotPasswordRequest(BaseModel):
    """Request a password reset link/token for the given email."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"email": "user@moziketo.ir"}]}
    )

    email: EmailStr = Field(description="Registered account email")


class ForgotPasswordResponse(BaseModel):
    """Dev/stage only — production returns 204 with no body (email delivery TBD)."""

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
