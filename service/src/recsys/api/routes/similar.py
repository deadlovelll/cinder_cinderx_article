
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from recsys.application.commands.similar_command import SimilarCommand
from recsys.application.dto.similar.similar_response import SimilarResponse
from recsys.application.mappers.similar_response_mapper import to_similar_response
from recsys.application.use_cases.similar.item_not_found import ItemNotFound
from recsys.domain.values.ids import ItemId
from recsys.api.dependencies.injected import SimilarUseCaseDep

router = APIRouter()


@router.get("/v1/items/{item_id}/similar", response_model=SimilarResponse)
async def similar(
    use_case: SimilarUseCaseDep,
    item_id: Annotated[int, Path(gt=0)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    command = SimilarCommand(item_id=ItemId(item_id), limit=limit)
    try:
        result = await use_case.execute(command)
    except ItemNotFound:
        raise HTTPException(404, f"item {item_id}") from None
    return to_similar_response(result)
