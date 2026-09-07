from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    url: str = Field(description="Public URL of uploaded object")
    kind: str
