"""Composition root: the one place that knows every concrete type."""

from __future__ import annotations

from dataclasses import dataclass

from recsys.application.use_cases.recommend import RecommendUseCase
from recsys.application.use_cases.record_event import RecordEventUseCase
from recsys.application.use_cases.similar import SimilarUseCase
from recsys.domain.kernels.registry import load_kernel
from recsys.infrastructure.clock import SystemClock
from recsys.infrastructure.db.engine import create_engine, driver_implementation
from recsys.infrastructure.db.event_repository import SqlEventRepository
from recsys.infrastructure.db.user_repository import SqlUserRepository
from recsys.settings import Settings


@dataclass(slots=True)
class Container:
    settings: Settings
    engine: object
    recommend: RecommendUseCase
    similar: SimilarUseCase
    record_event: RecordEventUseCase
    driver: str

    async def aclose(self) -> None:
        await self.engine.dispose()


def build(settings: Settings, *, graph, embeddings, catalogue) -> Container:
    engine = create_engine(settings)

    users = SqlUserRepository(engine, catalogue)
    events = SqlEventRepository(engine)
    clock = SystemClock()

    return Container(
        settings=settings,
        engine=engine,
        driver=driver_implementation(),
        recommend=RecommendUseCase(
            users=users, catalogue=catalogue, events=events,
            graph=graph, kernel=load_kernel(), clock=clock,
            log_impressions=settings.log_impressions,
            selection=settings.selection,
        ),
        similar=SimilarUseCase(embeddings=embeddings, items=catalogue, clock=clock),
        record_event=RecordEventUseCase(events=events),
    )
