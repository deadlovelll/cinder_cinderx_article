from bench.harness.cx_pyperf.config import config


def is_static() -> bool:
    return config().startswith("static")
