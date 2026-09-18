
from pydantic import BaseModel

from recsys.application.dto.bundle_meta import BundleMeta
from recsys.application.dto.bundle_slot import BundleSlot
from recsys.domain.values.ids import ItemId


class BundleResponse(BaseModel):
    item_id: ItemId
    slots: list[BundleSlot]
    meta: BundleMeta
