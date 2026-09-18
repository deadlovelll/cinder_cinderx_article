
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from recsys.domain.kernels.kernel_name import kernel_name
from recsys.infrastructure.graph.loaded_csr import LoadedCSR
from recsys.infrastructure.db.tables.covisitation import covisitation




class CovisitationGraph:

    def __init__(self, engine: AsyncEngine, n_items: int, *,
                 batch_rows: int = 200_000) -> None:
        self._engine = engine
        self._n_items = n_items
        self._batch_rows = batch_rows
        self._csr: LoadedCSR | None = None
        self._edges = 0

    async def load(self) -> None:
        degrees = [0] * (self._n_items + 1)
        stmt = select(covisitation.c.src, covisitation.c.dst, covisitation.c.weight)

        async with self._engine.connect() as conn:
            result = await conn.stream(stmt.order_by(covisitation.c.src))
            async for src, _dst, _w in result:
                degrees[src + 1] += 1

        indptr = [0] * (self._n_items + 1)
        total = 0
        for i in range(self._n_items):
            total += degrees[i + 1]
            indptr[i + 1] = total

        indices = [0] * total
        weights = [0] * total
        cursor = list(indptr[:-1])

        async with self._engine.connect() as conn:
            result = await conn.stream(stmt.order_by(covisitation.c.src))
            async for src, dst, w in result:
                pos = cursor[src]
                indices[pos] = dst
                weights[pos] = w
                cursor[src] = pos + 1

        self._edges = total
        self._csr = self._materialise(indptr, indices, weights, total)

    def _materialise(self, indptr: list[int], indices: list[int],
                     weights: list[int], total: int) -> LoadedCSR:
        if kernel_name() == "static":
            from recsys.domain.kernels import walk_static

            return LoadedCSR(
                indptr=walk_static.from_list(indptr, len(indptr)),
                indices=walk_static.from_list(indices, total),
                weights=walk_static.from_list(weights, total),
                n_items=self._n_items,
            )
        return LoadedCSR(indptr=indptr, indices=indices, weights=weights,
                         n_items=self._n_items)

    def csr(self) -> LoadedCSR:
        if self._csr is None:
            raise RuntimeError("graph not loaded: load() must run before the fork")
        return self._csr

    def loaded_edges(self) -> int:
        return self._edges
