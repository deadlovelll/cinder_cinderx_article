from __future__ import annotations

import importlib.util


def have_pydantic() -> bool:
    return importlib.util.find_spec("pydantic") is not None
