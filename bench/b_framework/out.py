from __future__ import annotations

from pydantic import BaseModel

from bench.b_framework.item_out import ItemOut
from bench.b_framework.meta_out import MetaOut


class Out(BaseModel):

    user_id: int
    items: list[ItemOut]
    meta: MetaOut
