from __future__ import annotations

import os
from pathlib import Path


ERRORS_DIR = os.path.join(
    str(Path(__file__).resolve().parents[2]), "dialect", "errors")
