
from fastapi import APIRouter, HTTPException

from recsys.api.dependencies import Injected
from recsys.application.dto.recommend_payload import RecommendPayload
from recsys.application.dto.recommend_response import RecommendResponse
from recsys.application.mappers.recommend_response_mapper import to_recommend_response
from recsys.application.use_cases.recommend import UserNotFound

router = APIRouter()


@router.post("/v1/recommendations", response_model=RecommendResponse)
async def recommend(payload: RecommendPayload, container: Injected) -> dict:
    try:
        result = await container.recommend.execute(payload)
    except UserNotFound:
        raise HTTPException(404, f"user {payload.user_id}") from None
    return to_recommend_response(result)
