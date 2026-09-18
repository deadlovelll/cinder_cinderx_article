from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from recsys.api.dependencies.recommend_use_case import recommend_use_case
from recsys.api.dependencies.similar_use_case import similar_use_case
from recsys.api.dependencies.show_bundle_use_case import show_bundle_use_case
from recsys.application.use_cases.recommend.recommend import RecommendUseCase
from recsys.application.use_cases.similar.similar import SimilarUseCase
from recsys.application.use_cases.bundle.show_bundle import ShowBundleUseCase

RecommendUseCaseDep = Annotated[RecommendUseCase, Depends(recommend_use_case)]
SimilarUseCaseDep = Annotated[SimilarUseCase, Depends(similar_use_case)]
ShowBundleUseCaseDep = Annotated[ShowBundleUseCase, Depends(show_bundle_use_case)]
