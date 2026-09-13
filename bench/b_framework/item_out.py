from __future__ import annotations

from pydantic import BaseModel


class ItemOut(BaseModel):
    """One recommended item in the response."""

    item_id: int
    score: int
    rank: int
    reasons: list[str]
