
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from recsys.application.commands.show_bundle_command import ShowBundleCommand
from recsys.application.dto.bundle.bundle_response import BundleResponse
from recsys.application.mappers.bundle_response_mapper import to_bundle_response
from recsys.application.use_cases.bundle.bundle_not_found import BundleNotFound
from recsys.domain.values.ids import ItemId
from recsys.api.dependencies.injected import ShowBundleUseCaseDep

router = APIRouter()


@router.get("/v1/items/{item_id}/bundle", response_model=BundleResponse)
async def bundle(
    use_case: ShowBundleUseCaseDep,
    item_id: Annotated[int, Path(ge=0)],
    limit: Annotated[int, Query(ge=1, le=128)] = 24,
) -> dict:
    command = ShowBundleCommand(item_id=ItemId(item_id), limit=limit)
    try:
        result = await use_case.execute(command)
    except BundleNotFound:
        raise HTTPException(404, f"item {item_id}") from None
    return to_bundle_response(result)
