from __future__ import annotations

from pydantic import BaseModel


class ItemOut(BaseModel):

    item_id: int
    score: int
    rank: int
    reasons: list[str]
