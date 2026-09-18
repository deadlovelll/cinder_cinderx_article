
from fastapi import APIRouter, HTTPException

from recsys.application.commands.recommend_command import RecommendCommand
from recsys.application.dto.recommend_payload import RecommendPayload
from recsys.application.dto.recommend_response import RecommendResponse
from recsys.application.mappers.recommend_response_mapper import to_recommend_response
from recsys.application.use_cases.user_not_found import UserNotFound
from recsys.api.dependencies.injected import RecommendUseCaseDep

router = APIRouter()


@router.post("/v1/recommendations", response_model=RecommendResponse)
async def recommend(payload: RecommendPayload, use_case: RecommendUseCaseDep) -> dict:
    command = RecommendCommand(user_id=payload.user_id, limit=payload.limit,
                               candidate_limit=payload.candidate_limit)
    try:
        result = await use_case.execute(command)
    except UserNotFound:
        raise HTTPException(404, f"user {payload.user_id}") from None
    return to_recommend_response(result)
