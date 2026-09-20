import sys

from bench.harness.system.aslr_disable_and_reexec import aslr_disable_and_reexec
from bench.harness.system.cpu_budget import cpu_budget
from bench.harness.system.describe import describe
from bench.harness.system.format_cpu_list import format_cpu_list
from bench.harness.system.host_cpus import host_cpus
from bench.harness.system.workshop_budget import workshop_budget
from bench.harness.system.irq_mask import irq_mask
from bench.harness.system.pin_to_reserved import pin_to_reserved
from bench.harness.system.preflight import preflight


def cli() -> None:
    if "--cpu-budget" in sys.argv:
        budget = cpu_budget()
        rest = sys.argv[sys.argv.index("--cpu-budget") + 1:]
        key = rest[0] if rest and not rest[0].startswith("-") else None
        if key is not None:
            print(format_cpu_list(budget[key]))
        else:
            for name in ("service", "db", "load", "os", "threads"):
                print(f"{name} {format_cpu_list(budget[name])} {len(budget[name])}")
        raise SystemExit(0)
    if "--workshop-budget" in sys.argv:
        budget = workshop_budget()
        rest = sys.argv[sys.argv.index("--workshop-budget") + 1:]
        key = rest[0] if rest and not rest[0].startswith("-") else None
        if key in ("workers", "gc_threads"):
            print(budget[key][0])
        elif key is not None:
            print(format_cpu_list(budget[key]))
        else:
            for name in ("service", "load", "db", "os"):
                print(f"{name} {format_cpu_list(budget[name])} {len(budget[name])}")
            print(f"workers {budget['workers'][0]}")
            print(f"gc_threads {budget['gc_threads'][0]}")
        raise SystemExit(0)
    if "--host-cpus" in sys.argv:
        print(host_cpus())
        raise SystemExit(0)
    if "--irq-mask" in sys.argv:
        print(irq_mask())
        raise SystemExit(0)
    if "--irq-mask-all" in sys.argv:
        print(irq_mask([]))
        raise SystemExit(0)
    aslr_disable_and_reexec()
    pin_to_reserved()
    print(describe(preflight()))


if __name__ == "__main__":
    cli()
