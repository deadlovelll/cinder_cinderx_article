from __future__ import annotations

from pydantic import BaseModel, Field

from bench.b_framework.constants import MAX_CANDIDATES, MAX_LIMIT


class In(BaseModel):
    """The request as the framework validates it."""

    user_id: int = Field(gt=0)
    limit: int = Field(default=20, ge=1, le=MAX_LIMIT)
    candidate_limit: int = Field(default=400, ge=1, le=MAX_CANDIDATES)
