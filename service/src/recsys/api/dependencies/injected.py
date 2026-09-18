from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from recsys.api.dependencies.recommend_use_case import recommend_use_case
from recsys.api.dependencies.similar_use_case import similar_use_case
from recsys.api.dependencies.show_bundle_use_case import show_bundle_use_case
from recsys.api.dependencies.record_event_use_case import record_event_use_case
from recsys.application.use_cases.recommend import RecommendUseCase
from recsys.application.use_cases.similar import SimilarUseCase
from recsys.application.use_cases.show_bundle import ShowBundleUseCase
from recsys.application.use_cases.record_event import RecordEventUseCase

RecommendUseCaseDep = Annotated[RecommendUseCase, Depends(recommend_use_case)]
SimilarUseCaseDep = Annotated[SimilarUseCase, Depends(similar_use_case)]
ShowBundleUseCaseDep = Annotated[ShowBundleUseCase, Depends(show_bundle_use_case)]
RecordEventUseCaseDep = Annotated[RecordEventUseCase, Depends(record_event_use_case)]
