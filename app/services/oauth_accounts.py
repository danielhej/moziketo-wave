from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OAuthAccount, OAuthProvider, User
from app.schemas.auth import OAuthAccountSummary


async def list_oauth_accounts(session: AsyncSession, user: User) -> list[OAuthAccountSummary]:
    await session.refresh(user, ["oauth_accounts"])
    return [
        OAuthAccountSummary(provider=account.provider, linked_at=account.created_at)
        for account in user.oauth_accounts
    ]


def _can_unlink(user: User, provider: str) -> None:
    has_password = user.password_hash is not None
    other_oauth = [a for a in user.oauth_accounts if a.provider != provider]
    if not has_password and len(other_oauth) == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot unlink the only sign-in method. Set a password first.",
        )


async def unlink_oauth_account(session: AsyncSession, user: User, provider: str) -> None:
    if provider not in OAuthProvider.ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown OAuth provider")

    await session.refresh(user, ["oauth_accounts"])
    account = next((a for a in user.oauth_accounts if a.provider == provider), None)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth provider not linked",
        )

    _can_unlink(user, provider)
    await session.execute(
        delete(OAuthAccount).where(
            OAuthAccount.user_id == user.id,
            OAuthAccount.provider == provider,
        )
    )
    await session.commit()
