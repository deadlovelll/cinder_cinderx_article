
from recsys.application.use_cases.bundle.bundle_result import BundleResult


def to_bundle_response(result: BundleResult) -> dict:
    return {
        "item_id": result.item_id,
        "slots": [
            {"item_id": s.item_id, "score": s.score, "rank": s.rank,
             "share": s.share, "label": s.label}
            for s in result.slots
        ],
        "meta": {"width": result.width, "considered": result.considered},
    }
