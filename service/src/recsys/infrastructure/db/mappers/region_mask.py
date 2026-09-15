
from __future__ import annotations

from recsys.domain.values.region import Region
from recsys.infrastructure.db.metadata import REGION_BITS

_REGION_BY_BIT = {bit: Region(name) for name, bit in REGION_BITS.items()}


def regions_from_mask(mask: int) -> frozenset[Region]:
    return frozenset(region for bit, region in _REGION_BY_BIT.items() if mask & bit)
