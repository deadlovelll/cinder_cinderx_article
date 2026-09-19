
from __future__ import annotations

import os
from dataclasses import dataclass

from recsys.env.flag_env import flag_env
from recsys.env.int_env import int_env


@dataclass(slots=True, frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_pool_size: int

    cinderx_mode: str
    precompile: bool
    immortalize: bool
    parallel_gc: bool
    parallel_gc_threads: int
    perf_trampoline: bool

    kernel: str
    selection: str
    embeddings: str
    workers: int
    bundle_items: int
    gc_interval_ms: int
    bundle_width: int
    sampler_interval_ms: int
    sampler_dir: str
    log_impressions: bool

    @property
    def dsn(self) -> str:
        return (f"postgresql+psycopg://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            db_host=os.environ.get("RECSYS_DB_HOST", "localhost"),
            db_port=int_env("RECSYS_DB_PORT", 5432),
            db_name=os.environ.get("RECSYS_DB_NAME", "recsys"),
            db_user=os.environ.get("RECSYS_DB_USER", "recsys"),
            db_password=os.environ.get("RECSYS_DB_PASSWORD", "recsys"),
            db_pool_size=int_env("RECSYS_DB_POOL_SIZE", 10),
            cinderx_mode=os.environ.get("RECSYS_CINDERX_MODE", "off").lower(),
            precompile=flag_env("RECSYS_PRECOMPILE"),
            immortalize=flag_env("RECSYS_IMMORTALIZE"),
            parallel_gc=flag_env("RECSYS_PARALLEL_GC"),
            parallel_gc_threads=int_env("RECSYS_PARALLEL_GC_THREADS", 8),
            perf_trampoline=flag_env("RECSYS_PERF_TRAMPOLINE"),
            kernel=os.environ.get("RECSYS_KERNEL", "plain").lower(),
            selection=os.environ.get("RECSYS_SELECTION", "sorted").lower(),
            embeddings=os.environ.get("RECSYS_EMBEDDINGS", "numpy").lower(),
            workers=int_env("RECSYS_WORKERS", 4),
            bundle_items=int_env("RECSYS_BUNDLE_ITEMS", 40_000),
            gc_interval_ms=int_env("RECSYS_GC_INTERVAL_MS", 0),
            bundle_width=int_env("RECSYS_BUNDLE_WIDTH", 128),
            sampler_interval_ms=int_env("RECSYS_SAMPLER_INTERVAL_MS", 250),
            sampler_dir=os.environ.get("RECSYS_SAMPLER_DIR", "/tmp"),
            log_impressions=flag_env("RECSYS_LOG_IMPRESSIONS", True),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "cinderx_mode": self.cinderx_mode, "kernel": self.kernel,
            "selection": self.selection,
            "embeddings": self.embeddings, "precompile": self.precompile,
            "immortalize": self.immortalize, "parallel_gc": self.parallel_gc,
            "parallel_gc_threads": self.parallel_gc_threads,
            "bundle_items": self.bundle_items,
            "gc_interval_ms": self.gc_interval_ms,
            "bundle_width": self.bundle_width,
            "perf_trampoline": self.perf_trampoline,
            "workers": self.workers,
            "db_pool_size": self.db_pool_size,
            "dep_extra": os.environ.get("RECSYS_DEP_EXTRA", "?"),
            "with_cinderx": os.environ.get("RECSYS_WITH_CINDERX", "?"),
        }
