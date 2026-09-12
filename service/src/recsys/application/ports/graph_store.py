"""Co-visitation graph, loaded once in the parent before the fork."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from recsys.application.ports.csr import CSR


@runtime_checkable
class GraphStore(Protocol):
    async def load(self) -> None: ...
    def csr(self) -> CSR: ...
    def loaded_edges(self) -> int: ...
