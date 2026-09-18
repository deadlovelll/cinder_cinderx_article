from __future__ import annotations

import base64

from recsys.infrastructure.seed.config import EMBED_DIM


def build_embeddings(n_items: int, rnd) -> list[dict]:
    out = []
    for i in range(n_items):
        vec = bytearray(EMBED_DIM)
        norm_sq = 0
        for d in range(EMBED_DIM):
            v = (next(rnd) % 255) - 127
            vec[d] = v & 0xFF
            norm_sq += v * v
        norm = max(1, int(norm_sq ** 0.5))
        out.append({"item_id": i, "dim": EMBED_DIM,
                    "vec": base64.b64encode(bytes(vec)).decode(), "norm": norm})
    return out
