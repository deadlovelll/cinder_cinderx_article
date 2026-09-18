
from pydantic import BaseModel, ConfigDict, Field

from recsys.domain.values.ids import UserId

MAX_LIMIT = 100
MAX_CANDIDATES = 2_000


class RecommendPayload(BaseModel):

    model_config = ConfigDict(extra="forbid")

    user_id: UserId = Field(gt=0)
    limit: int = Field(default=20, ge=1, le=MAX_LIMIT)
    candidate_limit: int = Field(default=400, ge=1, le=MAX_CANDIDATES)
