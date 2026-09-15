from __future__ import annotations

from typing import Sequence


def format_cpu_list(cpus: Sequence[int]) -> str:
    runs: list[list[int]] = []
    for cpu in sorted(set(cpus)):
        if runs and cpu == runs[-1][-1] + 1:
            runs[-1].append(cpu)
        else:
            runs.append([cpu])
    return ",".join(str(r[0]) if len(r) == 1 else f"{r[0]}-{r[-1]}" for r in runs)
