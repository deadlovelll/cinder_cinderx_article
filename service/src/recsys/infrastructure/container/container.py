from __future__ import annotations

from dataclasses import dataclass

from recsys.application.use_cases.recommend import RecommendUseCase
from recsys.application.use_cases.record_event import RecordEventUseCase
from recsys.application.use_cases.show_bundle import ShowBundleUseCase
from recsys.application.use_cases.similar import SimilarUseCase
from recsys.settings import Settings


@dataclass(slots=True)
class Container:
    settings: Settings
    engine: object
    recommend: RecommendUseCase
    similar: SimilarUseCase
    record_event: RecordEventUseCase
    show_bundle: ShowBundleUseCase
    bundles: object
    driver: str

    async def aclose(self) -> None:
        await self.engine.dispose()
