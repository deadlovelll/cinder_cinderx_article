
from __future__ import annotations

from datetime import datetime

from recsys.domain.entities.candidate import Candidate
from recsys.domain.entities.user_context import UserContext
from recsys.domain.rules.config import (
    FRESHNESS_BOOST_BPS,
    FRESHNESS_WINDOW,
    NEUTRAL_BPS,
    PRICE_BAND_MULTIPLIER,
    PRICE_BAND_PENALTY_BPS,
    SEGMENT_WEIGHTS,
)


def apply_scoring(candidates: list[Candidate], ctx: UserContext,
                  now: datetime) -> None:
    affinity_w, margin_w = SEGMENT_WEIGHTS[ctx.user.segment]
    price_ceiling = ctx.user.median_basket_cents * PRICE_BAND_MULTIPLIER
    fresh_after = now - FRESHNESS_WINDOW

    for cand in candidates:
        if not cand.alive:
            continue
        item = cand.item
        if item is None:
            continue

        score = cand.affinity * affinity_w // NEUTRAL_BPS
        score += cand.affinity * item.margin_bps // NEUTRAL_BPS * margin_w // NEUTRAL_BPS

        if item.created_at >= fresh_after:
            score = score * FRESHNESS_BOOST_BPS // NEUTRAL_BPS
            cand.reasons.append("fresh")

        if item.promo_multiplier_bps != NEUTRAL_BPS:
            score = score * item.promo_multiplier_bps // NEUTRAL_BPS
            cand.reasons.append("promoted")

        if price_ceiling and item.price_cents > price_ceiling:
            score = score * PRICE_BAND_PENALTY_BPS // NEUTRAL_BPS
            cand.reasons.append("above_price_band")

        cand.score = score
