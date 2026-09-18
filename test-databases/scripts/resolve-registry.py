#!/usr/bin/env python3
"""Resolve and validate the private 1C test database registry."""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.test_database_registry import RegistryResolutionError, resolve_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resolve the 1C test database registry",
        allow_abbrev=False,
    )
    parser.add_argument("-RegistryPath", "--registry-path", default="")
    parser.add_argument("-LocalConfigPath", "--local-config-path", default="")
    args = parser.parse_args(argv)

    try:
        path = resolve_registry(args.registry_path, args.local_config_path)
    except RegistryResolutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
