from typing import Any


def describe(facts: dict[str, Any]) -> str:
    a, c = facts["aslr"], facts["cpu"]
    lines = [f"preflight: {facts['verdict']}"]
    lines.append(f"  aslr      {a['verdict']:<14} personality={a.get('personality')} "
                 f"randomize_va_space={a.get('randomize_va_space')} "
                 f"layout_stable={a.get('layout_stable')}")
    shield = (c.get("shield") or {}).get("shielded")
    lines.append(f"  cpu       {c['verdict']:<14} reserved={c.get('reserved')} "
                 f"shielded={shield} affinity={c.get('affinity')} "
                 f"governor={c.get('governors')} turbo_disabled={c.get('turbo_disabled')}")
    for p in c.get("problems", []):
        lines.append(f"            - {p}")
    for n in c.get("notes", []):
        lines.append(f"            ~ {n}")
    return "\n".join(lines)
