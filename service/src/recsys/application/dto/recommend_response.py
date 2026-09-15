
from pydantic import BaseModel

from recsys.application.dto.ranked_item import RankedItem
from recsys.application.dto.recommend_meta import RecommendMeta
from recsys.domain.values.ids import UserId


class RecommendResponse(BaseModel):
    user_id: UserId
    items: list[RankedItem]
    meta: RecommendMeta
