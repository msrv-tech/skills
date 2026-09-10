#!/usr/bin/env python3
"""One-shot isolated process for a blocking UI Automation bridge request."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from uia_runner import run_uia_bridge_request


def main() -> int:
    payload: dict = {}
    try:
        payload = json.loads(sys.stdin.read())
        response = run_uia_bridge_request(
            str(payload["desktopName"]), int(payload["processId"]), payload["request"],
        )
    except Exception as exc:
        request = payload.get("request") if isinstance(payload, dict) else {}
        response = {
            "ok": False,
            "requestId": request.get("requestId") if isinstance(request, dict) else None,
            "status": "uia-response",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(limit=6),
        }
    sys.stdout.write(json.dumps(response, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
