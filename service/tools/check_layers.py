from __future__ import annotations

import ast
import configparser
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src"


def imported_modules(path: pathlib.Path) -> list[str]:
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.append(node.module)
    return out


def module_name(path: pathlib.Path) -> str:
    parts = list(path.relative_to(SRC).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def under(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def main() -> int:
    config = configparser.ConfigParser()
    config.read(ROOT / ".importlinter")

    layers: list[str] = []
    forbidden: list[tuple[str, list[str], list[str]]] = []
    for section in config.sections():
        if not section.startswith("importlinter:contract:"):
            continue
        body = config[section]
        if body.get("type") == "layers":
            layers = [l.strip() for l in body["layers"].split("\n") if l.strip()]
        elif body.get("type") == "forbidden":
            forbidden.append((
                body["name"],
                [s.strip() for s in body["source_modules"].split("\n") if s.strip()],
                [t.strip() for t in body["forbidden_modules"].split("\n") if t.strip()],
            ))

    rank = {name: index for index, name in enumerate(layers)}
    broken = []
    for path in sorted(SRC.rglob("*.py")):
        name = module_name(path)
        source_layer = next((l for l in layers if under(name, l)), None)
        for target in imported_modules(path):
            if source_layer is not None:
                target_layer = next((l for l in layers if under(target, l)), None)
                if target_layer is not None and rank[target_layer] < rank[source_layer]:
                    broken.append(f"слои: {name} -> {target}")
            for contract, sources, targets in forbidden:
                if any(under(name, s) for s in sources) and any(
                        under(target, t) for t in targets):
                    broken.append(f"{contract}: {name} -> {target}")

    if broken:
        print(f"нарушений: {len(broken)}")
        for line in sorted(set(broken)):
            print("   ", line)
        return 1
    print(f"контракты слоёв соблюдены, модулей: {sum(1 for _ in SRC.rglob('*.py'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
