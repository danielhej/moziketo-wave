from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.api.v1.admin import _verify_admin_key
from app.models import User
from app.schemas.upload import UploadResponse
from app.services.storage import upload_bytes

router = APIRouter(tags=["uploads"])
me_router = APIRouter(prefix="/me/uploads", tags=["uploads"])


@router.post(
    "/admin/uploads",
    response_model=UploadResponse,
    dependencies=[Depends(_verify_admin_key)],
    summary="Upload cover or audio for catalog ops",
)
async def admin_upload(
    kind: Annotated[Literal["cover", "audio"], Form()],
    file: UploadFile = File(...),
) -> UploadResponse:
    if not file.content_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing content type")
    content = await file.read()
    url = await upload_bytes(kind=kind, content=content, content_type=file.content_type)
    return UploadResponse(url=url, kind=kind)


@me_router.post(
    "/avatar",
    response_model=UploadResponse,
    summary="Upload profile avatar",
)
async def upload_avatar(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> UploadResponse:
    if not file.content_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing content type")
    content = await file.read()
    url = await upload_bytes(kind="avatar", content=content, content_type=file.content_type)
    user.avatar_url = url
    await session.commit()
    await session.refresh(user, ["oauth_accounts"])
    return UploadResponse(url=url, kind="avatar")
