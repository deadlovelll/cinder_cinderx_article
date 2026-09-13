from __future__ import annotations

from bench.b_framework.constants import META, PAGE


def render_by_hand(user_id):
    return {"user_id": user_id,
            "items": [{"item_id": r["item_id"], "score": r["score"],
                       "rank": r["rank"], "reasons": list(r["reasons"])}
                      for r in PAGE],
            "meta": META}
