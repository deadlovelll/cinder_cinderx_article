from recsys.infrastructure.container.container import Container
from recsys.application.use_cases.recommend.recommend import RecommendUseCase
from recsys.application.use_cases.bundle.show_bundle import ShowBundleUseCase
from recsys.application.use_cases.similar.similar import SimilarUseCase
from recsys.domain.kernels.load_kernel import load_kernel
from recsys.infrastructure.clock.system_clock import SystemClock
from recsys.infrastructure.db.create_engine import create_engine
from recsys.infrastructure.db.driver_implementation import driver_implementation
from recsys.infrastructure.db.event_repository import SqlEventRepository
from recsys.infrastructure.db.user_repository import SqlUserRepository
from recsys.settings import Settings


def build(settings: Settings, *, graph, embeddings, catalogue,
          bundles) -> Container:
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
        show_bundle=ShowBundleUseCase(cache=bundles, items=catalogue,
                                      clock=clock),
        bundles=bundles,
    )
