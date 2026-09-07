from typing import Any

from pydantic import BaseModel, Field


class JobResponse(BaseModel):
    id: str
    kind: str
    status: str
    payload: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str
    finished_at: str | None = None


class ImportQueuedResponse(BaseModel):
    job_id: str
    status: str = Field(default="queued")
