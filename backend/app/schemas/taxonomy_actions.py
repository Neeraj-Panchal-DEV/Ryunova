import uuid

from pydantic import BaseModel, Field


class TaxonomyReorderBody(BaseModel):
    """Set sort_order to row index (0..n-1) for each id in order."""

    ordered_ids: list[uuid.UUID] = Field(min_length=1)
