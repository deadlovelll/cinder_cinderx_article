"""The recommendation use case: orchestration only, no business logic, no SQL."""

from __future__ import annotations

from recsys.application.dto.recommend_payload import RecommendPayload
from recsys.application.ports.catalogue import Catalogue
from recsys.application.ports.clock import Clock
from recsys.application.ports.event_repository import EventRepository
from recsys.application.ports.graph_store import GraphStore
from recsys.application.ports.user_repository import UserRepository
from recsys.domain.entities.candidate import Candidate
from recsys.domain.entities.recommendation_set import RecommendationSet
from recsys.domain.rules.assemble import to_recommendations
from recsys.domain.rules.backfill import apply_backfill
from recsys.domain.rules.diversity import apply_diversity
from recsys.domain.rules.drop_stats import count_drops
from recsys.domain.rules.eligibility import apply_eligibility
from recsys.domain.rules.exclusions import apply_exclusions
from recsys.domain.rules.hydrate import hydrate
from recsys.domain.rules.pins import apply_pins
from recsys.domain.rules.scoring import apply_scoring


class UserNotFound(Exception):
    """Raised rather than returned: an unknown user is a 404, not an empty page."""


class RecommendUseCase:
    def __init__(self, *, users: UserRepository, catalogue: Catalogue,
                 events: EventRepository, graph: GraphStore, kernel, clock: Clock,
                 log_impressions: bool = True, selection: str = "sorted") -> None:
        self._users = users
        self._catalogue = catalogue
        self._events = events
        self._graph = graph
        self._kernel = kernel
        self._clock = clock
        self._log_impressions = log_impressions
        # Which top-k selection the plain kernel uses. `sorted` is what production
        self._selection = selection
        self._select = getattr(kernel, "SELECTIONS", {}).get(
            selection, getattr(kernel, "take_top", None))
        # Scratch is per worker, not per request, and that is a correctness claim
        self._scratch: dict[str, object] = {}

    async def execute(self, request: RecommendPayload) -> RecommendationSet:
        ctx = await self._users.load_context(request.user_id)
        if ctx is None:
            raise UserNotFound(request.user_id)

        raw = self._generate_candidates(ctx, request.candidate_limit)
        candidates = [Candidate(item_id=iid, affinity=affinity)
                      for iid, affinity in raw]

        # a dict lookup, not a round trip: the catalogue is resident
        items = self._catalogue.get_many([c.item_id for c in candidates])
        hydrate(candidates, items)

        apply_eligibility(candidates, ctx)
        apply_exclusions(candidates, ctx)
        apply_scoring(candidates, ctx, self._clock.now())

        chosen = apply_diversity(candidates, request.limit)
        by_id = {c.item_id: c for c in candidates}
        chosen = apply_pins(chosen, ctx, by_id, request.limit)

        backfilled = 0
        if len(chosen) < request.limit:
            chosen, backfilled = self._backfill(chosen, request.limit)

        recommendations = to_recommendations(chosen)

        if self._log_impressions and recommendations:
            # Off the critical path: nobody waits for a write they will never read.
            self._events.schedule_impressions(
                ctx.user.id, [r.item_id for r in recommendations])

        return RecommendationSet(
            user_id=ctx.user.id,
            items=recommendations,
            candidates_considered=len(candidates),
            dropped_by_rule=count_drops(candidates),
            backfilled=backfilled,
            kernel=(f"{self._kernel.IMPLEMENTATION}/{self._selection}"
                    if hasattr(self._kernel, "IMPLEMENTATION") else "static/bounded"),
        )

    def _generate_candidates(self, ctx, candidate_limit: int) -> list[tuple[int, int]]:
        """Two-hop walk from the user's recent items. Delegates to the kernel."""
        csr = self._graph.csr()
        seeds = ctx.recent_items
        if not seeds:
            return []
        return self._kernel_walk(csr, seeds, candidate_limit, ctx)

    def _static_scratch(self, n: int, candidate_limit: int) -> dict:
        """Per-worker buffers for the static kernel, built once."""
        scratch = self._scratch.get("static")
        if scratch is None:
            from recsys.domain.kernels import walk_static as ws

            zeros = [0] * n
            scratch = {
                "scores": ws.from_list(zeros, n),
                "touched": ws.from_list(zeros, n),
                "out_ids": ws.from_list([0] * candidate_limit, candidate_limit),
                "out_scores": ws.from_list([0] * candidate_limit, candidate_limit),
            }
            self._scratch["static"] = scratch
        return scratch

    def _plain_scratch(self, n: int) -> tuple[list, list]:
        scratch = self._scratch.get("plain")
        if scratch is None:
            scratch = ([0] * n, [0] * n)
            self._scratch["plain"] = scratch
        return scratch

    def _kernel_walk(self, csr, seeds, candidate_limit: int, ctx):
        kernel = self._kernel
        n = csr.n_items

        if kernel.__name__.endswith("walk_static"):
            from recsys.domain.kernels import walk_static as ws

            buf = self._static_scratch(n, candidate_limit)
            scores, touched = buf["scores"], buf["touched"]
            seed_arr = ws.from_list(list(seeds), len(seeds))

            n_touched = ws.walk(csr.indptr, csr.indices, csr.weights,
                                seed_arr, len(seeds), scores, touched)
            n_out = ws.take_top_ids(scores, touched, n_touched, candidate_limit,
                                    buf["out_ids"], buf["out_scores"])
            result = ws.boxed_pairs(buf["out_ids"], buf["out_scores"], n_out)
            # clearing only what was written is O(touched), not O(catalogue)
            ws.reset(scores, touched, n_touched)
            return result

        scores, touched = self._plain_scratch(n)
        n_touched = kernel.walk(csr.indptr, csr.indices, csr.weights,
                                seeds, scores, touched)
        result = self._select(scores, touched, n_touched, candidate_limit,
                              ctx.purchased)
        kernel.reset(scores, touched, n_touched)
        return result

    def _backfill(self, chosen: list[Candidate],
                  limit: int) -> tuple[list[Candidate], int]:
        popular_rows = self._catalogue.popular(limit * 3)
        popular_ids = [iid for iid, _ in popular_rows]
        popular_items = self._catalogue.get_many(popular_ids)
        popular = [Candidate(item_id=iid, affinity=score, score=score,
                             item=popular_items.get(iid))
                   for iid, score in popular_rows]
        # backfill is still subject to eligibility: a promoted out-of-stock item
        for cand in popular:
            if cand.item is None or not cand.item.active or cand.item.stock <= 0:
                cand.drop("backfill_ineligible")
        return apply_backfill(chosen, popular, limit)
