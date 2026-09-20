import base64

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from recsys.domain.values.ids import ItemId
from recsys.infrastructure.db.tables.item_embeddings import item_embeddings


class NumpyEmbeddingStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._ids: list[ItemId] = []
        self._row_of: dict[ItemId, int] = {}
        self._matrix = None
        self._norms = None
        self._dim = 0

    async def load(self) -> None:
        import numpy as np

        stmt = select(item_embeddings.c.item_id, item_embeddings.c.dim,
                      item_embeddings.c.vec, item_embeddings.c.norm)
        ids: list[int] = []
        vectors: list[bytes] = []
        norms: list[int] = []
        async with self._engine.connect() as conn:
            result = await conn.stream(stmt.order_by(item_embeddings.c.item_id))
            async for iid, dim, vec, norm in result:
                self._dim = dim
                ids.append(iid)
                vectors.append(base64.b64decode(vec))
                norms.append(norm)

        self._ids = ids
        self._row_of = {iid: i for i, iid in enumerate(ids)}
        self._matrix = np.frombuffer(b"".join(vectors), dtype=np.int8).reshape(
            len(ids), self._dim).astype(np.int32)
        self._norms = np.asarray(norms, dtype=np.int64)

    def dim(self) -> int:
        return self._dim

    def similar(self, item_id: ItemId, limit: int) -> list[tuple[ItemId, int]]:
        import numpy as np

        row = self._row_of.get(item_id)
        if row is None or self._matrix is None:
            return []
        query = self._matrix[row]
        dots = self._matrix @ query
        denom = np.maximum(self._norms * self._norms[row], 1)
        scores = (dots.astype(np.int64) << 12) // denom
        scores[row] = -(1 << 62)
        top = np.argpartition(-scores, min(limit, len(scores) - 1))[:limit]
        top = top[np.argsort(-scores[top])]
        return [(self._ids[i], int(scores[i])) for i in top]

    def implementation(self) -> str:
        return "numpy"
