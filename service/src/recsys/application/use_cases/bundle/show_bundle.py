from __future__ import annotations

from recsys.application.commands.show_bundle_command import ShowBundleCommand
from recsys.application.ports.clock import Clock
from recsys.application.ports.item_repository import ItemRepository
from recsys.application.use_cases.bundle.bundle_not_found import BundleNotFound
from recsys.application.use_cases.bundle.bundle_result import BundleResult
from recsys.application.use_cases.bundle.bundle_slot_result import BundleSlotResult
from recsys.domain.rules.shelf.score_slots import score_slots
from recsys.domain.rules.shelf.take_top_slots import take_top_slots


class ShowBundleUseCase:

    def __init__(self, *, cache, items: ItemRepository, clock: Clock) -> None:
        self._cache = cache
        self._items = items
        self._clock = clock
        self._scratch: list = []

    async def execute(self, request: ShowBundleCommand) -> BundleResult:
        bundle = self._cache.get(request.item_id)
        if bundle is None:
            raise BundleNotFound(request.item_id)

        freshness = self._clock.now().second + 1
        written = score_slots(bundle, freshness, self._scratch)
        top = take_top_slots(self._scratch, written, request.limit)

        neighbours = bundle.neighbours
        shares = bundle.shares
        labels = bundle.labels
        slots = tuple(
            BundleSlotResult(item_id=neighbours[slot], score=score,
                             rank=position, share=shares[slot],
                             label=labels[slot])
            for position, (score, slot) in enumerate(top)
        )
        return BundleResult(item_id=request.item_id, slots=slots,
                            width=self._cache.width(), considered=written)
