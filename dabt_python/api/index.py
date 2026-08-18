"""Vercel entrypoint for the Dabt policy engine.

Vercel discovers a FastAPI application exposed as `app`. The service itself
lives in `dabt_api.main`; this module only makes it discoverable, guarantees the
package root is importable regardless of the function's working directory, and
pins down the routing.

The policy app is mounted twice, deliberately. Vercel maps this file to `/api/*`
while the service declares its routes at `/v1/*`, and which prefix actually
reaches the app depends on how the platform rewrites the request. Mounting under
both means `/v1/action/evaluate` and `/api/v1/action/evaluate` resolve to the
same handler, so a routing detail cannot silently turn the gate into a 404. The
`/api` mount is registered first so it wins for those paths; the root mount
catches everything else.

There is no subprocess here. On Vercel the FastAPI app *is* the function, which
removes the spawn seam that `server/dabt.ts` has to work around when the engine
runs behind the Node bridge locally.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI  # noqa: E402

from dabt_api.main import app as policy_app  # noqa: E402

app = FastAPI(
    title="Dabt Policy Gate",
    description="Saudi regulatory policy enforcement for AI retrieval and agent actions. Not legal advice.",
)
app.mount("/api", policy_app)
app.mount("/", policy_app)

__all__ = ["app"]
