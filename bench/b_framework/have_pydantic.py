from __future__ import annotations

import importlib.util


def have_pydantic() -> bool:
    """Whether the models can be built: pydantic is an optional dependency."""
    return importlib.util.find_spec("pydantic") is not None
