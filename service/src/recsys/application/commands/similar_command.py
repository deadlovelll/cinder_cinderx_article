from dataclasses import dataclass

from recsys.domain.values.ids import ItemId

DEFAULT_CANDIDATE_LIMIT = 200


@dataclass(frozen=True, slots=True)
class SimilarCommand:
    item_id: ItemId
    limit: int
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT
