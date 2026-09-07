from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_id, get_db_session
from app.core.config import get_settings
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    OAuthAccountSummary,
    OAuthExchangeRequest,
    OAuthProviderName,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    SetPasswordRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
    VerifyEmailRequestResponse,
)
from app.services import auth as auth_service
from app.services import email_verification as email_verification_service
from app.services import oauth as oauth_service
from app.services import oauth_accounts as oauth_accounts_service
from app.services import password_reset as password_reset_service
from app.services.rate_limit import check_rate_limit, client_ip

router = APIRouter(prefix="/auth", tags=["auth"])

_AUTH_429 = {
    "description": "Rate limit exceeded — see Retry-After header",
    "headers": {
        "Retry-After": {
            "description": "Seconds until the client may retry",
            "schema": {"type": "integer"},
        }
    },
}


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register",
    description=(
        "Create a new account. Rate limited by client IP (default 10/hour).\n\n"
        "Returns user profile without tokens — call **login** afterward."
    ),
    responses={
        409: {"description": "Email already registered"},
        429: _AUTH_429,
        422: {"description": "Validation error (password min 8 chars, etc.)"},
    },
)
async def register(
    data: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> RegisterResponse:
    settings = get_settings()
    ip = client_ip(request)
    await check_rate_limit(
        "register_ip",
        ip,
        limit=settings.auth_register_ip_limit,
        window_seconds=settings.auth_register_ip_window,
    )
    return await auth_service.register_user(session, data)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description=(
        "Authenticate with email and password. "
        "Returns JWT **access_token** and **refresh_token**.\n\n"
        "Rate limited by IP (20/15 min) and email (10/15 min). "
        "OAuth-only accounts (no password) receive 401."
    ),
    responses={
        401: {"description": "Invalid email or password"},
        403: {"description": "Account inactive"},
        429: _AUTH_429,
    },
)
async def login(
    data: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    settings = get_settings()
    ip = client_ip(request)
    await check_rate_limit(
        "login_ip",
        ip,
        limit=settings.auth_login_ip_limit,
        window_seconds=settings.auth_login_ip_window,
    )
    await check_rate_limit(
        "login_email",
        data.email.lower(),
        limit=settings.auth_login_email_limit,
        window_seconds=settings.auth_login_email_window,
    )
    return await auth_service.login_user(session, data.email, data.password)


@router.post(
    "/forgot-password",
    summary="Forgot password",
    description=(
        "Request a password reset for the given email.\n\n"
        "- **Production:** always `204` (no body) to prevent email enumeration. "
        "Token is stored in Redis; email delivery is not wired yet.\n"
        "- **Dev/stage** (`APP_ENV != production` or `DEBUG=true`): `200` with "
        "`reset_token` when the account exists.\n\n"
        "Rate limited: 3/hour per email, 10/hour per IP."
    ),
    responses={
        200: {
            "model": ForgotPasswordResponse,
            "description": "Dev/stage — reset token returned for testing",
        },
        204: {"description": "Request accepted (production or unknown email)"},
        429: _AUTH_429,
    },
)
async def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    settings = get_settings()
    ip = client_ip(request)
    await check_rate_limit(
        "forgot_ip",
        ip,
        limit=settings.auth_forgot_ip_limit,
        window_seconds=settings.auth_forgot_ip_window,
    )
    await check_rate_limit(
        "forgot_email",
        data.email.lower(),
        limit=settings.auth_forgot_email_limit,
        window_seconds=settings.auth_forgot_email_window,
    )

    result = await password_reset_service.request_password_reset(session, data.email)
    if result is not None:
        return JSONResponse(content=result.model_dump(), status_code=status.HTTP_200_OK)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset password",
    description=(
        "Set a new password using the token from **forgot-password**. "
        "Token is single-use and expires after 1 hour (configurable)."
    ),
    responses={
        204: {"description": "Password updated"},
        400: {"description": "Invalid or expired reset token"},
    },
)
async def reset_password(
    data: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await password_reset_service.reset_password(session, data)


@router.get(
    "/oauth/{provider}",
    summary="OAuth authorize",
    description=(
        "Start OAuth login — redirects browser to the provider (Google or GitHub).\n\n"
        "**Flow:**\n"
        "1. Browser hits this endpoint\n"
        "2. User approves at provider\n"
        "3. Provider redirects to `/auth/oauth/{provider}/callback`\n"
        "4. API redirects to frontend `OAUTH_FRONTEND_CALLBACK_URL?code=…`\n"
        "5. Frontend calls **POST /auth/oauth/exchange** with the code\n\n"
        "Returns `503` if provider credentials are not configured in env."
    ),
    responses={
        302: {"description": "Redirect to OAuth provider"},
        404: {"description": "Unknown provider"},
        503: {"description": "Provider not configured (missing client ID/secret)"},
    },
)
async def oauth_authorize(
    provider: Annotated[
        OAuthProviderName,
        Path(description="OAuth provider", examples=["google"]),
    ],
) -> RedirectResponse:
    url = await oauth_service.build_authorize_redirect(provider)
    return RedirectResponse(url=url, status_code=302)


@router.get(
    "/oauth/{provider}/callback",
    summary="OAuth callback",
    description=(
        "Provider redirect target — do not call manually. "
        "Exchanges authorization code, upserts user/oauth_account, "
        "then redirects to frontend with a one-time exchange code (60s TTL)."
    ),
    responses={
        302: {"description": "Redirect to OAUTH_FRONTEND_CALLBACK_URL?code=…"},
        400: {"description": "Invalid state or missing email from provider"},
        403: {"description": "Account inactive"},
        404: {"description": "Unknown provider"},
        503: {"description": "Provider not configured"},
    },
    include_in_schema=True,
)
async def oauth_callback(
    provider: Annotated[OAuthProviderName, Path(description="OAuth provider")],
    code: Annotated[str, Query(description="Authorization code from provider")],
    state: Annotated[str, Query(description="CSRF state token")],
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    exchange_code = await oauth_service.handle_oauth_callback(
        session, provider, code=code, state=state
    )
    return RedirectResponse(
        url=oauth_service.frontend_callback_url(exchange_code),
        status_code=302,
    )


@router.post(
    "/oauth/exchange",
    response_model=TokenResponse,
    summary="OAuth token exchange",
    description=(
        "Exchange the one-time `code` from the frontend OAuth callback for JWT tokens. "
        "Code is single-use and expires in 60 seconds."
    ),
    responses={
        401: {"description": "Invalid or expired OAuth code"},
    },
)
async def oauth_exchange(
    data: OAuthExchangeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    return await oauth_service.exchange_oauth_code(session, data.code)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh tokens",
    description=(
        "Rotate access + refresh tokens. Old refresh token is revoked (single-use rotation)."
    ),
    responses={
        401: {"description": "Invalid or revoked refresh token"},
    },
)
async def refresh(data: RefreshRequest) -> TokenResponse:
    return await auth_service.refresh_tokens(data.refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current user",
    description=(
        "Return the authenticated user's profile. "
        "Requires `Authorization: Bearer <access_token>`."
    ),
    responses={401: {"description": "Missing or invalid access token"}},
)
async def me(
    session: AsyncSession = Depends(get_db_session),
    user_id: Annotated[str, Depends(get_current_user_id)] = "",
) -> UserResponse:
    return await auth_service.get_current_user_response(session, user_id)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update profile",
    description="Update the authenticated user's display name.",
)
async def update_me(
    data: UpdateProfileRequest,
    session: AsyncSession = Depends(get_db_session),
    user_id: Annotated[str, Depends(get_current_user_id)] = "",
) -> UserResponse:
    return await auth_service.update_profile(session, user_id, data)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change password",
    description="Change password for accounts that already have one.",
)
async def change_password(
    data: ChangePasswordRequest,
    session: AsyncSession = Depends(get_db_session),
    user_id: Annotated[str, Depends(get_current_user_id)] = "",
) -> None:
    await auth_service.change_password(session, user_id, data)


@router.post(
    "/set-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Set password",
    description="Set initial password for OAuth-only accounts.",
)
async def set_password(
    data: SetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
    user_id: Annotated[str, Depends(get_current_user_id)] = "",
) -> None:
    await auth_service.set_password(session, user_id, data)


@router.get(
    "/me/oauth",
    response_model=list[OAuthAccountSummary],
    summary="List linked OAuth providers",
)
async def list_my_oauth(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> list[OAuthAccountSummary]:
    return await oauth_accounts_service.list_oauth_accounts(session, user)


@router.delete(
    "/me/oauth/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlink OAuth provider",
    description="Cannot unlink the only sign-in method — set a password first.",
    responses={
        404: {"description": "Provider not linked"},
        409: {"description": "Last sign-in method"},
    },
)
async def unlink_my_oauth(
    provider: Annotated[OAuthProviderName, Path(description="OAuth provider")],
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> None:
    await oauth_accounts_service.unlink_oauth_account(session, user, provider)


@router.post(
    "/verify-email/request",
    summary="Request email verification",
    responses={
        200: {"model": VerifyEmailRequestResponse, "description": "Dev/stage token when SMTP off"},
        204: {"description": "Verification email sent"},
    },
)
async def request_verify_email(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    result = await email_verification_service.send_verification_email(user)
    if result is not None:
        return JSONResponse(content=result.model_dump(), status_code=status.HTTP_200_OK)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/verify-email/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirm email verification",
)
async def confirm_verify_email(
    token: Annotated[str, Query(min_length=16)],
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await email_verification_service.confirm_verification_token(session, token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
    description="Revoke the given refresh token server-side (Redis delete).",
    responses={204: {"description": "Token revoked (or already invalid)"}},
)
async def logout(data: RefreshRequest) -> None:
    await auth_service.logout_user(data.refresh_token)
