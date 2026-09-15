
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any


class MetricSampler:
    def __init__(self, path: str, interval_ms: int, *,
                 context: dict[str, Any] | None = None) -> None:
        self._path = path
        self._interval = interval_ms / 1000.0
        self._context = context or {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._overhead_ns = 0
        self._ticks = 0

    def start(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        self._thread = threading.Thread(target=self._run, name="sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        with open(self._path, "a", buffering=1) as fh:
            while not self._stop.is_set():
                t0 = time.perf_counter_ns()
                record = self._sample()
                record["sampler_overhead_us"] = (time.perf_counter_ns() - t0) / 1000.0
                fh.write(json.dumps(record, default=str) + "\n")
                self._ticks += 1
                self._stop.wait(self._interval)

    def _sample(self) -> dict[str, Any]:
        import gc
        import resource

        ru = resource.getrusage(resource.RUSAGE_SELF)
        record: dict[str, Any] = {
            "ts": time.time(),
            "pid": os.getpid(),
            "tick": self._ticks,
            **self._context,
            "gc_stats": gc.get_stats(),
            "gc_count": list(gc.get_count()),
            "allocated_blocks": __import__("sys").getallocatedblocks(),
            "maxrss_kb": ru.ru_maxrss // (1024 if __import__("sys").platform == "darwin" else 1),
            "minflt": ru.ru_minflt,
            "majflt": ru.ru_majflt,
            "nvcsw": ru.ru_nvcsw,
            "nivcsw": ru.ru_nivcsw,
        }
        record.update(_proc_memory())
        record.update(_jit_metrics())
        record.update(_loop_metrics())
        return record


def _proc_memory() -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        with open("/proc/self/statm") as fh:
            size, rss = fh.read().split()[:2]
        page = os.sysconf("SC_PAGE_SIZE")
        out["rss_kb"] = int(rss) * page // 1024
        out["vsize_kb"] = int(size) * page // 1024
    except OSError:
        return out
    try:
        with open("/proc/self/smaps_rollup") as fh:
            for line in fh:
                key, _, rest = line.partition(":")
                if key in ("Pss", "Shared_Clean", "Shared_Dirty",
                           "Private_Clean", "Private_Dirty"):
                    out[f"smaps_{key.lower()}_kb"] = int(rest.split()[0])
    except OSError:
        pass
    return out


def _jit_metrics() -> dict[str, Any]:
    try:
        import cinderx.jit as jit
    except ImportError:
        return {}
    if not jit.is_enabled():
        return {"jit_enabled": False}
    stats = jit.get_and_clear_runtime_stats()
    return {
        "jit_enabled": True,
        "jit_compiled_functions": len(jit.get_compiled_functions()),
        "jit_compilation_time_us": jit.get_compilation_time(),
        "jit_deopts": len(stats.get("deopt", [])),
        "jit_allocator": jit.get_allocator_stats(),
    }


def _loop_metrics() -> dict[str, Any]:
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return {}
    try:
        return {"asyncio_tasks": len(asyncio.all_tasks(loop))}
    except RuntimeError:
        return {}
