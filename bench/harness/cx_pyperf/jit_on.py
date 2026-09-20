from bench.harness.cx_pyperf.config import config


def jit_on() -> bool:
    return config().endswith("_jit")
