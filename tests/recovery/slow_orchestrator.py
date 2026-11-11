"""Slow-orchestrator launcher for the Day 4 recovery container tests.

The image runs in real mode with `app.core.orchestrator.handle_chat` as its
entry, read at call time via getattr. That function does not exist yet (lead
follow-up, see app/api/main.py), so a real-mode request would fall back at once
and never be in-flight long enough to test a shutdown.

This launcher is mounted read-only into the container and run instead of the
image CMD. It installs a deliberately slow `handle_chat` *after* the app is
importable, then starts uvicorn with the same graceful-shutdown and keep-alive
values the image CMD uses. Nothing under the repo's app/core is modified.

Environment:
    PROBE_SLEEP  seconds each chat request sleeps (default 0)
    GRACEFUL     --timeout-graceful-shutdown value (default 30, matches CMD)
    KEEPALIVE    --timeout-keep-alive value (default 5, matches CMD)
"""
import os
import time

from app.schemas.guide import GuideResponse, Intent
import app.core.orchestrator as orch

SLEEP = float(os.environ.get("PROBE_SLEEP", "0"))


def handle_chat(req, **_kwargs):
    time.sleep(SLEEP)
    return GuideResponse(intent=req.intent or Intent.next_steps,
                         reply=f"slow reply after {SLEEP}s")


orch.handle_chat = handle_chat

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="warning",
        timeout_graceful_shutdown=int(os.environ.get("GRACEFUL", "30")),
        timeout_keep_alive=int(os.environ.get("KEEPALIVE", "5")),
    )
