from __future__ import annotations

from bench.b_framework.constants import META, PAGE
from bench.b_framework.in_ import In
from bench.b_framework.item_out import ItemOut
from bench.b_framework.meta_out import MetaOut
from bench.b_framework.out import Out
from bench.b_framework.hand_validation_error import HandValidationError
from bench.b_framework.parse_by_hand import parse_by_hand
from bench.b_framework.render_by_hand import render_by_hand


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
