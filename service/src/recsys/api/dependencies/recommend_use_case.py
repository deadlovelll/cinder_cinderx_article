from fastapi import Request

from recsys.application.use_cases.recommend.recommend import RecommendUseCase


def recommend_use_case(request: Request) -> RecommendUseCase:
    return request.app.state.container.recommend
