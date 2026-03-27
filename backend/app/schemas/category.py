import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=16000)
    parent_id: uuid.UUID | None = None
    sort_order: int = 0
    active: bool = True


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=16000)
    parent_id: uuid.UUID | None = None
    sort_order: int | None = None  # None = append after current max sort_order
    active: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = None
    description: str | None = Field(None, max_length=16000)
    parent_id: uuid.UUID | None = None
    sort_order: int | None = None
    active: bool | None = None


class CategoryRead(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    created_by_user_id: uuid.UUID | None = None
    updated_by_user_id: uuid.UUID | None = None
    created_by_label: str | None = None
    updated_by_label: str | None = None
    parent_name: str | None = None
