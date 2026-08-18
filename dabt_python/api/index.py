"""Vercel entrypoint for the Dabt policy engine.

Vercel discovers a FastAPI application exposed as `app` from a supported
entrypoint path. The service itself lives in `dabt_api.main`; this module only
makes it discoverable and guarantees the package root is importable regardless
of the working directory the function is invoked with.

Nothing about the policy engine changes here. There is no subprocess: on Vercel
the FastAPI app *is* the function, which removes the spawn seam entirely rather
than hardening it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dabt_api.main import app  # noqa: E402

__all__ = ["app"]
