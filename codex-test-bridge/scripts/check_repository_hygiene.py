#!/usr/bin/env python3
"""Fail when distributable bridge files contain environment-specific access data."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
SKIP_PARTS = {".git", "__pycache__", "artifacts"}
SKIP_SUFFIXES = {".pyc", ".bmp", ".png"}

# Pieces are joined so the checker does not flag its own source.
BANNED = {
    "private .local domain": re.compile(r"\b[A-Za-z0-9.-]+\.local(?=[:/\\])", re.IGNORECASE),
    "hard-coded privileged login": re.compile("Админи" + "стратор", re.IGNORECASE),
    "workspace path": re.compile(r"[A-Za-z]:\\(?:Users|workspace-owner|bases|bsl|tests|temp|1c-bases)\\", re.IGNORECASE),
    "credential in URL": re.compile(r"https?://[^/\s:@]+:[^@\s/]+@", re.IGNORECASE),
}
SENSITIVE_FLAGS = {"/p", "/n", "/s", "/f", "--password", "--user", "--server", "--database-path"}


def text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path == SELF:
            continue
        if any(part in SKIP_PARTS for part in path.parts) or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if path.suffix.lower() == ".cfe":
            continue
        try:
            yield path, path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue


def check_worker_config(path: Path) -> list[str]:
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    errors = []
    for key in ("bridgeBaseUrl", "bridgeUsername", "bridgePassword"):
        value = config.get(key)
        if value is not None and not re.fullmatch(r"\{[A-Za-z][A-Za-z0-9]*}", value):
            errors.append(f"{path.name}: {key} must be an environment placeholder")
    for command_name in ("clientCommand", "managerCommand"):
        command = config.get(command_name, [])
        for index, item in enumerate(command[:-1]):
            if item.lower() in SENSITIVE_FLAGS and not re.fullmatch(r"\{[A-Za-z][A-Za-z0-9]*}", command[index + 1]):
                errors.append(f"{path.name}: literal value after {item} in {command_name}")
    return errors


def main() -> int:
    errors = []
    for path, text in text_files(ROOT):
        relative = path.relative_to(ROOT)
        for label, pattern in BANNED.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                errors.append(f"{relative}:{line}: {label}")
    for path in ROOT.glob("ui-worker*.example.json"):
        errors.extend(check_worker_config(path))
    if errors:
        print("Repository hygiene check failed:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print("Repository hygiene check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
