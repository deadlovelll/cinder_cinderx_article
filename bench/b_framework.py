"""What the web framework costs, and which half of it CinderX can reach."""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.harness import cx_pyperf as h

h.boot()

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


class HandValidationError(Exception):
    pass


def parse_by_hand(body):
    """The service's previous validator, field for field."""
    if not isinstance(body, dict):
        raise HandValidationError("body")
    user_id = body.get("user_id")
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        raise HandValidationError("user_id")
    limit = body.get("limit", 20)
    if (not isinstance(limit, int) or isinstance(limit, bool)
            or not 1 <= limit <= MAX_LIMIT):
        raise HandValidationError("limit")
    candidates = body.get("candidate_limit", 400)
    if (not isinstance(candidates, int) or isinstance(candidates, bool)
            or not limit <= candidates <= MAX_CANDIDATES):
        raise HandValidationError("candidate_limit")
    return user_id, limit, candidates


def render_by_hand(user_id):
    return {"user_id": user_id,
            "items": [{"item_id": r["item_id"], "score": r["score"],
                       "rank": r["rank"], "reasons": list(r["reasons"])}
                      for r in PAGE],
            "meta": META}


# Module level, not inside build_apps: string annotations need module globals.
try:
    from pydantic import BaseModel, Field

    class In(BaseModel):
        user_id: int = Field(gt=0)
        limit: int = Field(default=20, ge=1, le=MAX_LIMIT)
        candidate_limit: int = Field(default=400, ge=1, le=MAX_CANDIDATES)

    class ItemOut(BaseModel):
        item_id: int
        score: int
        rank: int
        reasons: list[str]

    class MetaOut(BaseModel):
        candidates_considered: int
        dropped_by_rule: dict[str, int]
        backfilled: int
        kernel: str

    class Out(BaseModel):
        user_id: int
        items: list[ItemOut]
        meta: MetaOut

    HAVE_PYDANTIC = True
except ImportError:  # reported as unavailable by main(), not raised here
    HAVE_PYDANTIC = False


def build_apps():
    """Built lazily so an import failure is reported as unavailable, not a crash."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse as StarletteJSON
    from starlette.routing import Route

    async def hand(request):
        body = await request.json()
        try:
            user_id, _, _ = parse_by_hand(body)
        except HandValidationError as exc:
            return StarletteJSON({"title": str(exc)}, status_code=422)
        return StarletteJSON(render_by_hand(user_id))

    apps = {"hand": Starlette(routes=[Route("/r", hand, methods=["POST"])])}

    a = FastAPI()

    @a.post("/r", response_model=Out)
    async def _dict(payload: In):
        return {"user_id": payload.user_id, "items": PAGE, "meta": META}
    apps["model_dict"] = a

    b = FastAPI()

    @b.post("/r", response_model=Out)
    async def _instance(payload: In):
        return Out(user_id=payload.user_id,
                   items=[ItemOut(**r) for r in PAGE], meta=MetaOut(**META))
    apps["model_instance"] = b

    c = FastAPI()

    @c.post("/r")
    async def _none(payload: In):
        return {"user_id": payload.user_id, "items": PAGE, "meta": META}
    apps["no_model"] = c

    d = FastAPI()

    @d.post("/r")
    async def _response(payload: In):
        return JSONResponse(render_by_hand(payload.user_id))
    apps["response_obj"] = d

    return apps


async def _noop_send(message) -> None:
    pass


async def _receive():
    return {"type": "http.request", "body": BODY, "more_body": False}


BATCH = 200


def make_driver(app, loop):
    """BATCH requests through the ASGI callable inside one loop entry."""
    async def call():
        i = 0
        while i < BATCH:
            await app(dict(SCOPE), _receive, _noop_send)
            i += 1

    def work():
        loop.run_until_complete(call())
    return work


def response_of(app, loop) -> tuple[int, object]:
    sent = []

    async def send(message):
        sent.append(message)

    loop.run_until_complete(app(dict(SCOPE), _receive, send))
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent
                    if m["type"] == "http.response.body")
    return status, json.loads(body)


def start_lifespan(app, loop) -> None:
    """FastAPI's router needs its lifespan to have run before it will serve."""
    async def receive():
        return {"type": "lifespan.startup"}

    async def send(message):
        pass

    async def go():
        task = asyncio.ensure_future(
            app({"type": "lifespan", "asgi": {"version": "3.0"}}, receive, send))
        await asyncio.sleep(0.05)
        return task

    loop.run_until_complete(go())


def main() -> None:
    suite = h.Suite("b_framework", forward=("leg",))
    suite.runner.argparser.add_argument(
        "--leg", default="all",
        help="one of hand|model_dict|model_instance|no_model|response_obj, or all")
    args = suite.parse()

    if not HAVE_PYDANTIC:
        suite.unavailable(case="framework", impl=h.config(),
                          note="pydantic not installed")
        suite.write_sidecar()
        return
    try:
        apps = build_apps()
    except ImportError as exc:
        suite.unavailable(case="framework", impl=h.config(),
                          note=f"fastapi not installed: {exc}")
        suite.write_sidecar()
        return

    legs = list(apps) if args.leg == "all" else [args.leg]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    reference = None
    for name in legs:
        app = apps[name]
        start_lifespan(app, loop)
        status, body = response_of(app, loop)
        if status != 200:
            suite.gate(case="framework", impl=f"{h.config()}/{name}",
                       got=status, expected=200)
            continue
        if reference is None:
            reference = body
        # the gate: five ways of saying the same thing must say the same thing.
        if not suite.gate(case="framework", impl=f"{h.config()}/{name}",
                          got=body, expected=reference):
            continue

        work = make_driver(app, loop)
        if h.jit_on():
            # auto(), not force_compile: the hot path is dozens of third-party functions.
            h.jit().auto()
        suite.bench(case="framework", impl=f"{h.config()}/{name}", fn=work,
                    params={"leg": name, "page_items": N_ITEMS, "batch": BATCH,
                            "response_bytes": len(json.dumps(body))},
                    inner_loops=BATCH,
                    note="per request through the ASGI callable; no server, no "
                         "socket, and the event loop is entered once per batch")

    if h.jit_on():
        jit = h.jit()
        suite.facts["compiled_functions"] = len(jit.get_compiled_functions())
        stats = jit.get_and_clear_runtime_stats()
        suite.facts["deopts"] = len(stats.get("deopt", []))
        # SIGSEGV under auto() here, twice on macOS/arm64; chase it on Linux.
        suite.facts["note_intermittent_crash"] = (
            "SIGSEGV under auto() over the framework path, reproduced twice on "
            "macOS/arm64, never under force_compile over a list; needs a core dump")

    suite.machine_probe()
    suite.write_sidecar()
    loop.close()


if __name__ == "__main__":
    main()
