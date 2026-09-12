"""What the recommendation use case accepts."""

from pydantic import BaseModel, ConfigDict, Field

from recsys.domain.values.ids import UserId

MAX_LIMIT = 100
MAX_CANDIDATES = 2_000


class RecommendPayload(BaseModel):
    """`extra="forbid"`: a typo in a field name must fail, not serve a default."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId = Field(gt=0)
    limit: int = Field(default=20, ge=1, le=MAX_LIMIT)
    candidate_limit: int = Field(default=400, ge=1, le=MAX_CANDIDATES)
