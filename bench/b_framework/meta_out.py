from __future__ import annotations

from pydantic import BaseModel


class MetaOut(BaseModel):

    candidates_considered: int
    dropped_by_rule: dict[str, int]
    backfilled: int
    kernel: str
