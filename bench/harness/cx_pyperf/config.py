from bench.harness.cx_pyperf import state


def config() -> str:
    if state.config is None:
        raise RuntimeError("call boot() first")
    return state.config
