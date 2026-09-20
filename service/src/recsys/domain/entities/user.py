from dataclasses import dataclass

from recsys.domain.values.ids import UserId
from recsys.domain.values.region import Region
from recsys.domain.values.segment import Segment


@dataclass(slots=True, frozen=True)
class User:
    id: UserId
    segment: Segment
    region: Region
    age: int
    median_basket_cents: int
