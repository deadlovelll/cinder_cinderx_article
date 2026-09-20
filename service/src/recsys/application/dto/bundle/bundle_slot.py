
from pydantic import BaseModel

from recsys.domain.values.ids import ItemId


class BundleSlot(BaseModel):
    item_id: ItemId
    score: int
    rank: int
    share: float
    label: str
