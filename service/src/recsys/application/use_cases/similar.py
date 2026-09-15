
from __future__ import annotations

from dataclasses import dataclass

from recsys.application.dto.similar_payload import SimilarPayload
from recsys.application.ports.clock import Clock
from recsys.application.ports.embedding_store import EmbeddingStore
from recsys.application.ports.item_repository import ItemRepository
from recsys.domain.entities.candidate import Candidate
from recsys.domain.entities.recommendation import Recommendation
from recsys.domain.rules.assemble import to_recommendations
from recsys.domain.rules.diversity import apply_diversity
from recsys.domain.rules.drop_stats import count_drops
from recsys.domain.rules.eligibility import apply_eligibility
from recsys.domain.rules.hydrate import hydrate
from recsys.domain.values.ids import ItemId
from recsys.domain.values.region import Region
from recsys.domain.values.segment import Segment


class ItemNotFound(Exception):
    pass


@dataclass(slots=True, frozen=True)
class SimilarResult:
    item_id: ItemId
    items: tuple[Recommendation, ...]
    candidates_considered: int
    dropped_by_rule: dict[str, int]
    implementation: str


class SimilarUseCase:

    def __init__(self, *, embeddings: EmbeddingStore, items: ItemRepository,
                 clock: Clock) -> None:
        self._embeddings = embeddings
        self._items = items
        self._clock = clock

    async def execute(self, request: SimilarPayload) -> SimilarResult:
        raw = self._embeddings.similar(request.item_id, request.candidate_limit)
        if not raw:
            raise ItemNotFound(request.item_id)

        candidates = [Candidate(item_id=iid, affinity=score, score=score)
                      for iid, score in raw]
        items = self._items.get_many([c.item_id for c in candidates])
        hydrate(candidates, items)

        ctx = _AnonymousContext(items.get(request.item_id))
        apply_eligibility(candidates, ctx)
        chosen = apply_diversity(candidates, request.limit)

        return SimilarResult(
            item_id=request.item_id,
            items=to_recommendations(chosen),
            candidates_considered=len(candidates),
            dropped_by_rule=count_drops(candidates),
            implementation=self._embeddings.implementation(),
        )


class _AnonymousContext:

    __slots__ = ("user", "recent_items", "purchased", "disliked", "impressions",
                 "pinned")

    def __init__(self, seed_item) -> None:
        from recsys.domain.entities.user import User

        region = next(iter(seed_item.regions)) if seed_item else Region.EU
        self.user = User(id=0, segment=Segment.CASUAL, region=region, age=18,
                         median_basket_cents=0)
        self.recent_items = ()
        self.purchased = frozenset()
        self.disliked = frozenset()
        self.impressions = {}
        self.pinned = ()
