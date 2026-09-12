"""What the similar-items use case accepts."""

from pydantic import BaseModel, ConfigDict, Field

from recsys.domain.values.ids import ItemId


class SimilarPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: ItemId = Field(gt=0)
    limit: int = Field(default=20, ge=1, le=100)
    candidate_limit: int = Field(default=200, ge=1, le=2_000)
