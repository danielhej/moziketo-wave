from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_db_session
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    return await auth_service.register_user(session, data)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    return await auth_service.login_user(session, data.email, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest) -> TokenResponse:
    return await auth_service.refresh_tokens(data.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(
    session: AsyncSession = Depends(get_db_session),
    user_id: Annotated[str, Depends(get_current_user_id)] = "",
) -> UserResponse:
    return await auth_service.get_current_user_response(session, user_id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest) -> None:
    await auth_service.logout_user(data.refresh_token)
