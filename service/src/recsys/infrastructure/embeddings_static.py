
from __future__ import annotations

import base64

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from recsys.domain.kernels import similar_static as ss
from recsys.domain.values.ids import ItemId
from recsys.infrastructure.db.tables.item_embeddings import item_embeddings


class StaticEmbeddingStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._ids: list[ItemId] = []
        self._row_of: dict[ItemId, int] = {}
        self._ids_arr = None
        self._flat = None
        self._norms = None
        self._dim = 0

    async def load(self) -> None:
        stmt = select(item_embeddings.c.item_id, item_embeddings.c.dim,
                      item_embeddings.c.vec, item_embeddings.c.norm)
        flat: list[int] = []
        norms: list[int] = []
        async with self._engine.connect() as conn:
            result = await conn.stream(stmt.order_by(item_embeddings.c.item_id))
            async for iid, dim, vec, norm in result:
                self._dim = dim
                self._ids.append(iid)
                norms.append(norm)
                flat.extend(b - 256 if b > 127 else b
                            for b in base64.b64decode(vec))
        self._row_of = {iid: i for i, iid in enumerate(self._ids)}
        self._ids_arr = ss.from_list(self._ids, len(self._ids))
        self._flat = ss.from_list(flat, len(flat))
        self._norms = ss.from_list(norms, len(norms))

    def dim(self) -> int:
        return self._dim

    def similar(self, item_id: ItemId, limit: int) -> list[tuple[ItemId, int]]:
        row = self._row_of.get(item_id)
        if row is None:
            return []
        n_items = len(self._ids)
        scores = ss.zeros(n_items)
        out_ids = ss.zeros(limit)
        out_scores = ss.zeros(limit)

        ss.score_all(self._flat, self._norms, scores, n_items, self._dim, row)
        n_out = ss.take_top(scores, self._ids_arr, n_items, limit,
                            out_ids, out_scores)
        return ss.boxed_pairs(out_ids, out_scores, n_out)

    def implementation(self) -> str:
        return "static"
