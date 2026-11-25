"""Detect files that changed outside an explicit allowlist.

Mutating skills are expected to touch only the object they were asked to edit.
The guard snapshots cheap file metadata before the operation and reports every
path outside the allowlist that changed afterwards.  It is intentionally
read-only: the caller decides whether to abort.
"""

from __future__ import annotations

import os
from pathlib import Path


IGNORED_DIRECTORY_NAMES = {".git", "__pycache__"}


class TreeGuard:
    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        self._state = self._snapshot()

    def _snapshot(self) -> dict[str, tuple[int, int]]:
        state: dict[str, tuple[int, int]] = {}
        for current, directories, files in os.walk(self.root):
            directories[:] = [name for name in directories if name not in IGNORED_DIRECTORY_NAMES]
            for name in files:
                path = Path(current) / name
                try:
                    stat = path.stat()
                except OSError:
                    continue
                relative = str(path.relative_to(self.root)).replace("\\", "/")
                state[relative] = (stat.st_size, stat.st_mtime_ns)
        return state

    def changed_except(
        self,
        allowed: list[str | os.PathLike[str]],
        allowed_prefixes: list[str | os.PathLike[str]] | None = None,
    ) -> list[str]:
        allowed_resolved = {str(Path(item).resolve()) for item in allowed}
        prefixes = [str(Path(item).resolve()) for item in (allowed_prefixes or [])]

        def is_allowed(absolute: str) -> bool:
            return absolute in allowed_resolved or any(
                absolute == prefix or absolute.startswith(prefix + os.sep)
                for prefix in prefixes
            )

        current = self._snapshot()
        changed: list[str] = []
        for relative, signature in current.items():
            if signature == self._state.get(relative):
                continue
            if is_allowed(str((self.root / relative).resolve())):
                continue
            changed.append(relative)
        for relative in self._state:
            if relative not in current:
                if not is_allowed(str((self.root / relative).resolve())):
                    changed.append(relative)
        return sorted(changed)
