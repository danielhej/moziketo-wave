from datetime import datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field


class WebhookCreate(BaseModel):
    url: AnyHttpUrl
    secret: str = Field(min_length=8, max_length=255)
    events: list[str] = Field(min_length=1)


class WebhookUpdate(BaseModel):
    url: AnyHttpUrl | None = None
    secret: str | None = Field(default=None, min_length=8, max_length=255)
    events: list[str] | None = None
    is_active: bool | None = None


class WebhookResponse(BaseModel):
    id: UUID
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    event: str
    status: str
    attempts: int
    last_error: str | None
    created_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}
