from __future__ import annotations

import argparse
import asyncio

from recsys.infrastructure.seed.seed import seed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", type=int, default=100_000)
    ap.add_argument("--users", type=int, default=20_000)
    ap.add_argument("--avg-degree", type=int, default=24)
    args = ap.parse_args()
    asyncio.run(seed(args.items, args.users, args.avg_degree))
