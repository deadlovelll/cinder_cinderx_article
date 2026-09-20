
from recsys.domain.entities.recommendation_set import RecommendationSet


def to_recommend_response(result: RecommendationSet) -> dict:
    return {
        "user_id": result.user_id,
        "items": [
            {"item_id": r.item_id, "score": r.score, "rank": r.rank,
             "reasons": r.reasons}
            for r in result.items
        ],
        "meta": {
            "candidates_considered": result.candidates_considered,
            "dropped_by_rule": result.dropped_by_rule,
            "backfilled": result.backfilled,
            "kernel": result.kernel,
        },
    }
