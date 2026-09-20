import os
from typing import Any


def proc_memory() -> dict[str, int]:
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
