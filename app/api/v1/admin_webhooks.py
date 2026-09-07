from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.api.v1.admin import _verify_admin_key
from app.schemas.webhooks import (
    WebhookCreate,
    WebhookDeliveryResponse,
    WebhookResponse,
    WebhookUpdate,
)
from app.services import webhooks as webhooks_service

router = APIRouter(prefix="/admin/webhooks", tags=["admin"])


@router.get("", response_model=list[WebhookResponse], dependencies=[Depends(_verify_admin_key)])
async def list_webhooks(session: AsyncSession = Depends(get_db_session)) -> list:
    return await webhooks_service.list_subscriptions(session)


@router.post(
    "",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_verify_admin_key)],
)
async def create_webhook(
    payload: WebhookCreate,
    session: AsyncSession = Depends(get_db_session),
):
    return await webhooks_service.create_subscription(session, payload)


@router.patch(
    "/{subscription_id}",
    response_model=WebhookResponse,
    dependencies=[Depends(_verify_admin_key)],
)
async def update_webhook(
    subscription_id: UUID,
    payload: WebhookUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    return await webhooks_service.update_subscription(session, subscription_id, payload)


@router.delete(
    "/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_verify_admin_key)],
)
async def delete_webhook(
    subscription_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await webhooks_service.delete_subscription(session, subscription_id)


@router.get(
    "/{subscription_id}/deliveries",
    response_model=list[WebhookDeliveryResponse],
    dependencies=[Depends(_verify_admin_key)],
)
async def list_deliveries(
    subscription_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list:
    return await webhooks_service.list_deliveries(session, subscription_id)


@router.post(
    "/{subscription_id}/test",
    response_model=WebhookDeliveryResponse,
    dependencies=[Depends(_verify_admin_key)],
)
async def test_webhook(
    subscription_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    return await webhooks_service.send_test_event(session, subscription_id)
