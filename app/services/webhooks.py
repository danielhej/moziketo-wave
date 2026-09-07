from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import DeliveryStatus, WebhookDelivery, WebhookEvent, WebhookSubscription
from app.schemas.webhooks import WebhookCreate, WebhookUpdate


def _sign_payload(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def list_subscriptions(session: AsyncSession) -> list[WebhookSubscription]:
    stmt = select(WebhookSubscription).order_by(WebhookSubscription.created_at.desc())
    return list(await session.scalars(stmt))


async def create_subscription(session: AsyncSession, data: WebhookCreate) -> WebhookSubscription:
    for event in data.events:
        if event not in WebhookEvent.ALL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown event: {event}"
            )
    sub = WebhookSubscription(
        url=str(data.url), secret=data.secret, events=data.events, is_active=True
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub


async def update_subscription(
    session: AsyncSession, sub_id: UUID, data: WebhookUpdate
) -> WebhookSubscription:
    sub = await session.get(WebhookSubscription, sub_id)
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    if data.url is not None:
        sub.url = str(data.url)
    if data.secret is not None:
        sub.secret = data.secret
    if data.events is not None:
        for event in data.events:
            if event not in WebhookEvent.ALL:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown event: {event}"
                )
        sub.events = data.events
    if data.is_active is not None:
        sub.is_active = data.is_active
    await session.commit()
    await session.refresh(sub)
    return sub


async def delete_subscription(session: AsyncSession, sub_id: UUID) -> None:
    sub = await session.get(WebhookSubscription, sub_id)
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    await session.delete(sub)
    await session.commit()


async def emit_event(session: AsyncSession, event: str, payload: dict[str, Any]) -> None:
    subs = await session.scalars(
        select(WebhookSubscription).where(WebhookSubscription.is_active.is_(True))
    )
    for sub in subs:
        if event not in sub.events:
            continue
        delivery = WebhookDelivery(
            subscription_id=sub.id,
            event=event,
            payload=payload,
            status=DeliveryStatus.PENDING,
        )
        session.add(delivery)
    await session.commit()
    await deliver_pending(session)


async def deliver_pending(session: AsyncSession, *, max_attempts: int = 5) -> int:
    now = datetime.now(UTC)
    deliveries = await session.scalars(
        select(WebhookDelivery)
        .where(
            WebhookDelivery.status.in_([DeliveryStatus.PENDING, DeliveryStatus.RETRYING]),
            (WebhookDelivery.next_retry_at.is_(None)) | (WebhookDelivery.next_retry_at <= now),
        )
        .limit(20)
    )
    count = 0
    async with httpx.AsyncClient(timeout=15) as client:
        for delivery in deliveries:
            sub = await session.get(WebhookSubscription, delivery.subscription_id)
            if sub is None or not sub.is_active:
                delivery.status = DeliveryStatus.FAILED
                delivery.last_error = "Subscription inactive"
                delivery.finished_at = now
                continue

            body = json.dumps(
                {"event": delivery.event, "payload": delivery.payload},
                ensure_ascii=False,
            ).encode()
            headers = {
                "Content-Type": "application/json",
                "X-Moziketo-Signature": _sign_payload(sub.secret, body),
                "X-Moziketo-Event": delivery.event,
            }
            delivery.attempts += 1
            try:
                resp = await client.post(sub.url, content=body, headers=headers)
                if 200 <= resp.status_code < 300:
                    delivery.status = DeliveryStatus.SUCCESS
                    delivery.finished_at = now
                    delivery.last_error = None
                    count += 1
                else:
                    raise RuntimeError(f"HTTP {resp.status_code}")
            except Exception as exc:
                delivery.last_error = str(exc)
                if delivery.attempts >= max_attempts:
                    delivery.status = DeliveryStatus.FAILED
                    delivery.finished_at = now
                else:
                    delivery.status = DeliveryStatus.RETRYING
                    delay = min(3600, 2 ** delivery.attempts * 30)
                    delivery.next_retry_at = now + timedelta(seconds=delay)
    await session.commit()
    return count


async def list_deliveries(
    session: AsyncSession, sub_id: UUID, *, limit: int = 50
) -> list[WebhookDelivery]:
    sub = await session.get(WebhookSubscription, sub_id)
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return list(
        await session.scalars(
            select(WebhookDelivery)
            .where(WebhookDelivery.subscription_id == sub_id)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
        )
    )


async def send_test_event(session: AsyncSession, sub_id: UUID) -> WebhookDelivery:
    sub = await session.get(WebhookSubscription, sub_id)
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    delivery = WebhookDelivery(
        subscription_id=sub.id,
        event="webhook.test",
        payload={"message": "Moziketo webhook test"},
        status=DeliveryStatus.PENDING,
    )
    session.add(delivery)
    await session.commit()
    await deliver_pending(session)
    await session.refresh(delivery)
    return delivery
