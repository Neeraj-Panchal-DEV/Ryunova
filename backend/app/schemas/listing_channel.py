import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    integration_requirements: dict[str, Any] = Field(default_factory=dict)
    active: bool = True
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime


class MarketplaceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    integration_requirements: dict[str, Any] | None = None
    active: bool | None = None
    sort_order: int | None = None


class ProductMarketplaceListingRead(BaseModel):
    marketplace_id: uuid.UUID
    code: str
    name: str
    enabled: bool
    last_refreshed_at: datetime | None = None
    posted_at: datetime | None = None


class ProductMarketplaceListingItemUpdate(BaseModel):
    marketplace_id: uuid.UUID
    enabled: bool = False
    mark_refreshed: bool = False  # sets last_refreshed_at to now() when true and enabled


class ProductMarketplaceListingsPatch(BaseModel):
    items: list[ProductMarketplaceListingItemUpdate]


class BulkSetListingReadinessBody(BaseModel):
    product_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    listing_readiness: Literal["draft", "ready_to_post"]


class BulkSetMarketplaceFlagsBody(BaseModel):
    product_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    marketplace_id: uuid.UUID
    enabled: bool = True
