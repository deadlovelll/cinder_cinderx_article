from __future__ import annotations

import os

KERNEL_MODE = os.environ.get("RECSYS_KERNEL", "plain").lower()
