#!/usr/bin/env python3
"""Isolated stdin/stdout wrapper for Linux AT-SPI bridge requests."""

from __future__ import annotations

import json
import sys

from atspi_runner import run_atspi_bridge_request


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        response = run_atspi_bridge_request(int(payload["processId"]), payload["request"])
    except Exception as exc:
        response = {
            "ok": False,
            "requestId": None,
            "status": "uia-response",
            "error": f"{type(exc).__name__}: {exc}",
        }
    json.dump(response, sys.stdout, ensure_ascii=False)
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
