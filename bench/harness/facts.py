"""Observations that are not timings."""

from __future__ import annotations

import json
import os
from typing import Any

from . import system
from .cx_pyperf import RESULTS, bench_tag, config, interp_facts, machine_facts


class FactsRun:
    """Sidecar-only run: observations, no timings, no pyperf."""

    def __init__(self, name: str, *, label: str | None = None) -> None:
        self.name = name
        self.label = label or bench_tag()
        self.facts: dict[str, Any] = {}
        self.problems: list[dict[str, Any]] = []

    def record(self, key: str, value: Any) -> None:
        """Attach one observation. Repeated keys accumulate into a list."""
        if key in self.facts:
            existing = self.facts[key]
            if isinstance(existing, list):
                existing.append(value)
            else:
                self.facts[key] = [existing, value]
        else:
            self.facts[key] = value

    def unavailable(self, *, case: str, note: str) -> None:
        """A non-ok status is itself a result, not a reason to report nothing."""
        self.problems.append({"case": case, "status": "unavailable", "note": note[:300]})
        print(f"  UNAVAILABLE {case:<28} {note[:80]}", flush=True)

    def unsupported(self, *, case: str, note: str) -> None:
        self.problems.append({"case": case, "status": "unsupported", "note": note[:300]})
        print(f"  UNSUPPORTED {case:<28} {note[:80]}", flush=True)

    def log(self, msg: str) -> None:
        print(msg, flush=True)

    def write(self) -> str:
        os.makedirs(RESULTS, exist_ok=True)
        path = os.path.join(RESULTS, f"{self.name}-{self.label}.facts.json")
        payload = {
            "suite": self.name,
            "label": self.label,
            "cx_config": config(),
            "kind": "observations",
            "interp": interp_facts(),
            "machine": machine_facts(),
            "preflight": system.preflight(),
            "problems": self.problems,
            "facts": self.facts,
        }
        with open(path, "w") as fh:
            json.dump(payload, fh, indent=1, default=str)
        print(f"[{self.name}] sidecar -> {path}", flush=True)
        return path
