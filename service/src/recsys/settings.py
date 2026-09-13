"""Configuration from the environment. One object, read once, never re-read."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("", "0", "false", "no")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


@dataclass(slots=True, frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_pool_size: int

    # rung of the ladder: off | runtime | jit | jit_static
    cinderx_mode: str
    # each step of the pre-fork chain, independently switchable
    precompile: bool
    immortalize: bool
    parallel_gc: bool
    perf_trampoline: bool

    kernel: str            # plain | static
    selection: str         # sorted | bounded -- top-k selection of the plain kernel
    embeddings: str        # numpy | python
    workers: int
    sampler_interval_ms: int
    sampler_dir: str
    log_impressions: bool

    @property
    def dsn(self) -> str:
        # psycopg3 async, whether the C speedups are installed or not: the driver
        return (f"postgresql+psycopg://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            db_host=os.environ.get("RECSYS_DB_HOST", "localhost"),
            db_port=_int("RECSYS_DB_PORT", 5432),
            db_name=os.environ.get("RECSYS_DB_NAME", "recsys"),
            db_user=os.environ.get("RECSYS_DB_USER", "recsys"),
            db_password=os.environ.get("RECSYS_DB_PASSWORD", "recsys"),
            db_pool_size=_int("RECSYS_DB_POOL_SIZE", 10),
            cinderx_mode=os.environ.get("RECSYS_CINDERX_MODE", "off").lower(),
            precompile=_flag("RECSYS_PRECOMPILE"),
            immortalize=_flag("RECSYS_IMMORTALIZE"),
            parallel_gc=_flag("RECSYS_PARALLEL_GC"),
            perf_trampoline=_flag("RECSYS_PERF_TRAMPOLINE"),
            kernel=os.environ.get("RECSYS_KERNEL", "plain").lower(),
            selection=os.environ.get("RECSYS_SELECTION", "sorted").lower(),
            embeddings=os.environ.get("RECSYS_EMBEDDINGS", "numpy").lower(),
            workers=_int("RECSYS_WORKERS", 4),
            sampler_interval_ms=_int("RECSYS_SAMPLER_INTERVAL_MS", 250),
            sampler_dir=os.environ.get("RECSYS_SAMPLER_DIR", "/tmp"),
            log_impressions=_flag("RECSYS_LOG_IMPRESSIONS", True),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "cinderx_mode": self.cinderx_mode, "kernel": self.kernel,
            "selection": self.selection,
            "embeddings": self.embeddings, "precompile": self.precompile,
            "immortalize": self.immortalize, "parallel_gc": self.parallel_gc,
            "perf_trampoline": self.perf_trampoline,
            "workers": self.workers,
            "db_pool_size": self.db_pool_size,
            "dep_extra": os.environ.get("RECSYS_DEP_EXTRA", "?"),
            "with_cinderx": os.environ.get("RECSYS_WITH_CINDERX", "?"),
        }
