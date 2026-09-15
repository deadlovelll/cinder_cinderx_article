from __future__ import annotations

import os
import platform
import subprocess
from typing import Any


def machine_facts() -> dict[str, Any]:

    def sysctl(name: str) -> str | None:
        try:
            out = subprocess.run(["sysctl", "-n", name], capture_output=True,
                                 text=True, timeout=5)
            return out.stdout.strip() or None
        except Exception:
            return None

    info: dict[str, Any] = {"platform": platform.platform(),
                            "machine": platform.machine(),
                            "system": platform.system(),
                            "cpu_count": os.cpu_count()}
    if platform.system() == "Darwin":
        info["cpu_brand"] = sysctl("machdep.cpu.brand_string")
        info["cores_physical"] = sysctl("hw.physicalcpu")
        info["cores_perf"] = sysctl("hw.perflevel0.physicalcpu")
        info["cores_eff"] = sysctl("hw.perflevel1.physicalcpu")
        mem = sysctl("hw.memsize")
        info["mem_gb"] = round(int(mem) / 2**30, 1) if mem else None
        info["os_version"] = sysctl("kern.osproductversion")
    else:
        try:
            with open("/proc/cpuinfo") as fh:
                for line in fh:
                    if line.lower().startswith(("model name", "cpu model")):
                        info["cpu_brand"] = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass
    return info
