"""Rule tunables. In a real service these come from a config service; here they"""

from datetime import timedelta

from recsys.domain.values.segment import Segment

NEUTRAL_BPS = 10_000
FRESHNESS_WINDOW = timedelta(days=30)
FRESHNESS_BOOST_BPS = 12_000
IMPRESSION_CAP = 3
PRICE_BAND_MULTIPLIER = 3
PRICE_BAND_PENALTY_BPS = 4_000
MAX_PER_CATEGORY = 3
MAX_PER_BRAND = 2

#: Affinity weighted against commercial signal, per segment.
SEGMENT_WEIGHTS: dict[Segment, tuple[int, int]] = {
    #                affinity_bps, margin_bps
    Segment.NEW: (12_000, 6_000),
    Segment.CASUAL: (10_000, 10_000),
    Segment.LOYAL: (9_000, 13_000),
    Segment.BARGAIN: (13_000, 4_000),
}
