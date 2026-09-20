import base64

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from recsys.domain.values.ids import ItemId
from recsys.infrastructure.db.tables.item_embeddings import item_embeddings

SHIFT = 12
NEG_INF = -(1 << 62)


class PythonEmbeddingStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._ids: list[ItemId] = []
        self._row_of: dict[ItemId, int] = {}
        self._flat: list[int] = []
        self._norms: list[int] = []
        self._dim = 0

    async def load(self) -> None:
        stmt = select(item_embeddings.c.item_id, item_embeddings.c.dim,
                      item_embeddings.c.vec, item_embeddings.c.norm)
        async with self._engine.connect() as conn:
            result = await conn.stream(stmt.order_by(item_embeddings.c.item_id))
            async for iid, dim, vec, norm in result:
                self._dim = dim
                self._ids.append(iid)
                self._norms.append(norm)
                self._flat.extend(b - 256 if b > 127 else b
                                  for b in base64.b64decode(vec))
        self._row_of = {iid: i for i, iid in enumerate(self._ids)}

    def dim(self) -> int:
        return self._dim

    def similar(self, item_id: ItemId, limit: int) -> list[tuple[ItemId, int]]:
        row = self._row_of.get(item_id)
        if row is None:
            return []
        dim, flat, norms = self._dim, self._flat, self._norms
        qbase = row * dim
        qnorm = norms[row]
        n_items = len(self._ids)

        scores = [0] * n_items
        i = 0
        while i < n_items:
            if i == row:
                scores[i] = NEG_INF
                i += 1
                continue
            base = i * dim
            acc = 0
            d = 0
            while d < dim:
                acc += flat[base + d] * flat[qbase + d]
                d += 1
            denom = norms[i] * qnorm
            scores[i] = (acc << SHIFT) // denom if denom else 0
            i += 1

        out: list[tuple[ItemId, int]] = []
        for _ in range(limit):
            best = -1
            best_score = NEG_INF
            j = 0
            while j < n_items:
                s = scores[j]
                if s > best_score:
                    best_score = s
                    best = j
                j += 1
            if best < 0:
                break
            out.append((self._ids[best], best_score))
            scores[best] = NEG_INF
        return out

    def implementation(self) -> str:
        return "python"
