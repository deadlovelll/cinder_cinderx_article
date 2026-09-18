
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from recsys.domain.values.ids import ItemId, UserId


class EventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UserId = Field(gt=0)
    item_id: ItemId = Field(gt=0)
    kind: Literal["view", "cart", "purchase", "dislike"]
