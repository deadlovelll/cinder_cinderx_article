"""Everything about the user the rules need, assembled in one round trip."""

from __future__ import annotations

from dataclasses import dataclass

from recsys.domain.entities.user import User
from recsys.domain.values.ids import ItemId


@dataclass(slots=True, frozen=True)
class UserContext:
    """One object rather than eleven loose arguments through a long pipeline."""

    user: User
    recent_items: tuple[ItemId, ...]
    purchased: frozenset[ItemId]
    disliked: frozenset[ItemId]
    impressions: dict[ItemId, int]  # item -> times shown inside the dedup window
    pinned: tuple[ItemId, ...]      # merchandiser pins, in slot order
