from __future__ import annotations

from pydantic import BaseModel


class MetaOut(BaseModel):
    """What the ranking did, alongside the items it returned."""

    candidates_considered: int
    dropped_by_rule: dict[str, int]
    backfilled: int
    kernel: str
