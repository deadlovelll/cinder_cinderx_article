from __future__ import annotations

import json


N_ITEMS = 20
MAX_LIMIT = 100
MAX_CANDIDATES = 2_000
PAGE = [{"item_id": 1000 + i, "score": 500 + i, "rank": i,
         "reasons": ["covisit", "fresh", "in_stock"]} for i in range(N_ITEMS)]
META = {"candidates_considered": 353, "dropped_by_rule": {"region": 12, "stock": 4},
        "backfilled": 0, "kernel": "static/bounded"}
BODY = json.dumps({"user_id": 42, "limit": 20, "candidate_limit": 400}).encode()
SCOPE = {
    "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
    "method": "POST", "scheme": "http", "path": "/r", "raw_path": b"/r",
    "query_string": b"", "root_path": "",
    "headers": [(b"host", b"t"), (b"content-type", b"application/json"),
                (b"content-length", str(len(BODY)).encode())],
    "client": ("127.0.0.1", 1), "server": ("127.0.0.1", 80),
}
BATCH = 200
