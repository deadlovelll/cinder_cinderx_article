
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from recsys.api.dependencies import Injected
from recsys.application.dto.similar_payload import SimilarPayload
from recsys.application.dto.similar_response import SimilarResponse
from recsys.application.mappers.similar_response_mapper import to_similar_response
from recsys.application.use_cases.similar import ItemNotFound

router = APIRouter()


@router.get("/v1/items/{item_id}/similar", response_model=SimilarResponse)
async def similar(
    container: Injected,
    item_id: Annotated[int, Path(gt=0)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    payload = SimilarPayload(item_id=item_id, limit=limit)
    try:
        result = await container.similar.execute(payload)
    except ItemNotFound:
        raise HTTPException(404, f"item {item_id}") from None
    return to_similar_response(result)
