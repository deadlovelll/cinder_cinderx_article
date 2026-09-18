from __future__ import annotations

from datetime import UTC, datetime

MASK = (1 << 64) - 1
BASE_DATE = datetime(2026, 1, 1, tzinfo=UTC)
SEGMENTS = ("new", "casual", "loyal", "bargain")
REGION_MASKS = (1, 2, 4, 3, 7)
N_CATEGORIES = 120
N_BRANDS = 300
EMBED_DIM = 64
BATCH = 5_000
