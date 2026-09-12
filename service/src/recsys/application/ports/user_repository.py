"""Everything the rule pipeline needs about the user, in one round trip."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from recsys.domain.entities.user_context import UserContext
from recsys.domain.values.ids import UserId


@runtime_checkable
class UserRepository(Protocol):
    async def load_context(self, user_id: UserId) -> UserContext | None: ...
