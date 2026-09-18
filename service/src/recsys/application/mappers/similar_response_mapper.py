
from recsys.application.use_cases.similar.similar_result import SimilarResult


def to_similar_response(result: SimilarResult) -> dict:
    return {
        "item_id": result.item_id,
        "items": [
            {"item_id": r.item_id, "score": r.score, "rank": r.rank,
             "reasons": r.reasons}
            for r in result.items
        ],
        "meta": {
            "candidates_considered": result.candidates_considered,
            "dropped_by_rule": result.dropped_by_rule,
            "implementation": result.implementation,
        },
    }
