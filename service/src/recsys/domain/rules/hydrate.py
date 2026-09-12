"""Attach fetched item data to candidates. The only stage that is not a decision."""

from __future__ import annotations

from recsys.domain.entities.candidate import Candidate
from recsys.domain.entities.item import Item
from recsys.domain.values.ids import ItemId


def hydrate(candidates: list[Candidate], items: dict[ItemId, Item]) -> None:
    for cand in candidates:
        cand.item = items.get(cand.item_id)
