from datetime import datetime

from pydantic import BaseModel


class AdminCatalogSummary(BaseModel):
    tracks_total: int
    tracks_published: int
    artists_total: int
    albums_total: int
    albums_published: int
    users_total: int


class AdminUserSummary(BaseModel):
    id: str
    email: str
    display_name: str
    is_active: bool
    email_verified: bool
    deleted: bool
    created_at: datetime


class AdminUsersResponse(BaseModel):
    items: list[AdminUserSummary]
    total: int
    page: int
    page_size: int


class AdminUserPatch(BaseModel):
    is_active: bool


class ImportStatusResponse(BaseModel):
    last_job_id: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict | None = None
    error: str | None = None
