
from pydantic import BaseModel

from recsys.domain.values.ids import ItemId


class RankedItem(BaseModel):
    item_id: ItemId
    score: int
    rank: int
    reasons: list[str]
