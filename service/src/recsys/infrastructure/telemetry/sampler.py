import json
import os
import threading
import time
from typing import Any

from recsys.infrastructure.telemetry.jit_metrics import jit_metrics
from recsys.infrastructure.telemetry.loop_metrics import loop_metrics
from recsys.infrastructure.telemetry.proc_memory import proc_memory


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
        record.update(proc_memory())
        record.update(jit_metrics())
        record.update(loop_metrics())
        return record
