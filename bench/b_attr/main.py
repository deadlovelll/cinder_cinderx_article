import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.b_attr.constants import N
from bench.harness import cx_pyperf as h

h.boot()


def main() -> None:
    suite = h.Suite("b_attr")
    suite.parse()

    import bench.kernels.attr_plain as ap

    expected_read = 7 * N
    legs = [
        ("plain/dict", ap.read_attr, ap.Point(7, 11)),
        ("plain/slots", ap.read_attr, ap.PointSlots(7, 11)),
    ]
    if h.is_static():
        import bench.kernels.attr_static as as_

        legs.append(("static/field", as_.read_attr, as_.Point(7, 11)))
    else:
        suite.unavailable(case="attr_read", impl=h.config(),
                          note="the typed leg needs a static config")

    jit_info: dict[str, object] = {}
    for impl, fn, obj in legs:
        work = (lambda fn=fn, o=obj: fn(o, N))
        # проверка результата идёт через свою точку вызова: если прогреть ту,
        # которую потом меряем, force_compile оставит её на интерпретаторе
        if not suite.gate(case="attr_read", impl=impl, got=fn(obj, N),
                          expected=expected_read):
            continue
        if h.jit_on():
            jit_info[impl] = h.compile_now(fn, warmup=1, run=work)
        suite.check_once(("attr_read", impl), work, expected_read)
        suite.bench(case="attr_read", impl=impl, fn=work,
                    params={"n": N}, inner_loops=N,
                    note="one attribute read per iteration, accumulated")

    for impl, mod, cls in (("plain/dict", ap, ap.Point), ("plain/slots", ap, ap.PointSlots),
                           *( [("static/field", None, None)] if h.is_static() else [] )):
        if impl == "static/field":
            import bench.kernels.attr_static as as_
            mod, cls = as_, as_.Point
        obj = cls(7, 11)
        work = (lambda m=mod, o=obj: m.read_two(o, N))
        if h.jit_on():
            h.compile_now(mod.read_two, warmup=1, run=work)
        suite.bench(case="attr_rw", impl=impl, fn=work,
                    params={"n": N}, inner_loops=N,
                    note="two reads and one write per iteration")

    suite.machine_probe()
    suite.facts["jit"] = jit_info
    suite.write_sidecar()


if __name__ == "__main__":
    main()
