
from pydantic import BaseModel

from recsys.application.dto.ranked_item import RankedItem
from recsys.application.dto.similar.similar_meta import SimilarMeta
from recsys.domain.values.ids import ItemId


class SimilarResponse(BaseModel):
    item_id: ItemId
    items: list[RankedItem]
    meta: SimilarMeta
